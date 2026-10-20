"""The Vercel entrypoint keeps sessions, drafts and saves consistent across serverless instances."""
import base64
import gzip
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cloud_store import MemoryRedis, unpack  # noqa: E402


def load_entrypoint():
    os.environ['ITR_ADMIN_PASSWORD'] = 'cloud-secret'
    spec = importlib.util.spec_from_file_location('vercel_index', ROOT / 'api' / 'index.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class VercelEntrypoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = load_entrypoint()
        cls.redis = MemoryRedis()  # Shared like a real Redis between instances.

    def instance(self):
        """A fresh cold start: nothing in process memory, everything from Redis."""
        lab = self.api.CloudLab(self.redis)
        lab.persistent = True
        self.api.LAB = lab
        return lab

    def request(self, method, path, body=None, cookie='', headers=None):
        raw = json.dumps(body).encode() if body is not None else b''
        environ = {'REQUEST_METHOD': method, 'PATH_INFO': path, 'QUERY_STRING': '', 'wsgi.input': io.BytesIO(raw),
                   'CONTENT_LENGTH': str(len(raw)), 'CONTENT_TYPE': 'application/json', 'HTTP_HOST': 'lab.example.app',
                   'HTTP_ORIGIN': 'https://lab.example.app', 'HTTP_X_FORWARDED_FOR': '203.0.113.9, 10.0.0.1',
                   'HTTP_X_FORWARDED_PROTO': 'https', 'HTTP_ACCEPT_ENCODING': 'gzip', 'HTTP_X_EDITOR_INSTANCE': 'tab1'}
        if cookie:
            environ['HTTP_COOKIE'] = cookie
        for key, value in (headers or {}).items():
            environ['HTTP_' + key.upper().replace('-', '_')] = value
        result = {}
        chunks = self.api.app(environ, lambda status, hdrs: result.update(status=int(status[:3]), headers=dict(hdrs)))
        payload = b''.join(chunks)
        if result['headers'].get('Content-Encoding') == 'gzip':
            payload = gzip.decompress(payload)
        return result['status'], result['headers'], payload

    def test_cross_instance_sessions_drafts_saves_and_backups(self):
        self.instance()
        status, headers, page = self.request('GET', '/')
        self.assertEqual(status, 200)
        self.assertIn(b'<html', page.lower())
        self.assertEqual(self.request('GET', '/server.py')[0], 404)
        self.assertEqual(self.request('GET', '/data/reports.json')[0], 404)
        self.assertEqual(self.request('POST', '/api/login', {'password': 'itr'})[0], 401)
        status, headers, _ = self.request('POST', '/api/login', {'password': 'cloud-secret'})
        self.assertEqual(status, 200)
        self.assertIn('Secure', headers['Set-Cookie'])
        cookie = headers['Set-Cookie'].split(';')[0]
        self.assertEqual(self.request('POST', '/api/inventory', {}, cookie, {'Origin': 'https://evil.example'})[0], 403)

        self.instance()  # Next request lands on another instance.
        self.assertTrue(json.loads(self.request('GET', '/api/session', cookie=cookie)[2])['admin'])
        lab = json.loads(self.request('GET', '/api/lab')[2])
        draft = dict(data=lab, history=[], future=[], dirty=True)
        self.assertEqual(self.request('PUT', '/api/drafts/lab', draft, cookie)[0], 200)

        self.instance()
        self.assertEqual(json.loads(self.request('GET', '/api/drafts/lab', cookie=cookie)[2])['data']['revision'], lab['revision'])
        inventory = json.loads(self.request('GET', '/api/inventory')[2])
        shelf = next(sid for sid, place in inventory['locations'].items() if place['saved'] and place['binId'] is None)
        status, _, saved = self.request('POST', '/api/inventory', dict(action='quick', item={'name': 'Cloud widget'}, stock={'shelfId': shelf, 'binId': None},
                                                                       revision=inventory['revision'], operationId='cloud-quick'), cookie)
        self.assertEqual(status, 200, saved)
        saved = json.loads(saved)

        self.instance()
        status, _, body = self.request('POST', '/api/inventory', dict(action='delete-item', itemId=saved['itemId'], revision=saved['revision'], operationId='cloud-delete'), cookie)
        self.assertEqual(status, 200, body)
        backups = self.redis.data['itr:backups']
        self.assertEqual(len(backups), 1)
        names = tarfile.open(fileobj=io.BytesIO(base64.b64decode(next(iter(backups.values()))))).getnames()
        self.assertIn('data/inventory.json', names)
        stored = json.loads(unpack(self.redis.data['itr:files']['inventory.json']))
        self.assertEqual(stored['revision'], saved['revision'] + 1)
        self.assertNotIn(saved['itemId'], stored['items'])

        status, headers, body = self.request('GET', '/api/backup', cookie=cookie)
        self.assertEqual(status, 200)
        self.assertLess(int(headers['Content-Length']), 4_500_000)
        backup = json.loads(body)
        self.assertIn('history/inventory/' + str(saved['revision']) + '.json', backup['data'])
        self.assertNotIn('itr:lock', self.redis.data)

    def test_without_redis_the_site_is_view_only(self):
        self.api.LAB = self.api.CloudLab(MemoryRedis())
        self.assertEqual(self.request('GET', '/api/lab')[0], 200)
        status, _, body = self.request('POST', '/api/login', {'password': 'cloud-secret'})
        self.assertEqual(status, 503)
        self.assertIn('Redis', json.loads(body)['error'])


if __name__ == '__main__':
    unittest.main()
