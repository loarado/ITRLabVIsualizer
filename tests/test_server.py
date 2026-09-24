import copy
import http.client
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import blank_shelf, write_json, LabServer, ROOT, validate_lab, validate_shelf


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.data = Path(self.temp.name) / 'data'
        (self.data / 'shelves').mkdir(parents=True)
        shutil.copy(ROOT / 'defaults/lab.json', self.data / 'lab.json')
        for item in json.loads((self.data/'lab.json').read_text())['items']:
            if item['kind']=='shelf': write_json(self.data/'shelves'/f"{item['id']}.json", blank_shelf(item['id']))
        self.server = LabServer(('127.0.0.1', 0), self.data, 'itr')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.cookie = ''

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def request(self, method, path, data=None, headers=None):
        if method == 'PUT' and '/api/drafts/' not in path and isinstance(data, dict):
            data = {**data, 'versionName': data.get('versionName', 'Test version')}
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
        h = {'Content-Type': 'application/json', 'Cookie': self.cookie}
        h.update(headers or {})
        connection.request(method, path, json.dumps(data) if data is not None else None, h)
        response = connection.getresponse()
        if response.getheader('Set-Cookie'):
            self.cookie = response.getheader('Set-Cookie').split(';')[0]
        body = response.read()
        result = json.loads(body) if response.getheader('Content-Type') == 'application/json' else body
        connection.close()
        return response.status, result

    def login(self):
        self.assertEqual(self.request('POST', '/api/login', {'password': 'itr'})[0], 200)

    def test_authentication_enforced_and_logout_revokes(self):
        _, lab = self.request('GET', '/api/lab')
        self.assertEqual(self.request('PUT', '/api/lab', lab)[0], 403)
        self.assertEqual(self.request('POST', '/api/login', {'password': 'bad'})[0], 401)
        self.login()
        self.assertEqual(self.request('GET', '/api/session')[1], {'admin': True})
        self.assertEqual(self.request('PUT', '/api/lab', lab, {'Origin': 'http://evil.example'})[0], 403)
        self.assertEqual(self.request('PUT', '/api/lab', lab)[0], 200)
        self.request('POST', '/api/logout', {})
        self.assertEqual(self.request('PUT', '/api/lab', lab)[0], 403)

    def test_isolation_persistence_and_stale_revision(self):
        self.login()
        _, a = self.request('GET', '/api/shelves/R01')
        _, b = self.request('GET', '/api/shelves/R02')
        a['matrix'][0][0] = dict(name='Bolts', contents='M4', keywords='hardware', w=2, h=2,
            background='#dc4545', color='#ffffff', fontSize=14, fontFamily='system-ui', bold=True)
        self.assertEqual(self.request('PUT', '/api/shelves/R01', a), (200, {'revision': 1}))
        self.assertEqual(json.loads((self.data / 'shelves/R01.json').read_text())['matrix'][0][0]['name'], 'Bolts')
        self.assertEqual(self.request('GET', '/api/shelves/R02')[1], b)
        self.assertEqual(self.request('PUT', '/api/shelves/R01', a)[0], 409)
        self.assertEqual(self.request('GET', '/api/shelves/R01')[1]['matrix'][0][0]['name'], 'Bolts')

    def test_validation_and_private_files(self):
        self.login()
        _, shelf = self.request('GET', '/api/shelves/R01')
        shelf['matrix'] = []
        self.assertEqual(self.request('PUT', '/api/shelves/R01', shelf)[0], 400)
        _, lab = self.request('GET', '/api/lab')
        lab['items'][0]['x'] = -1
        self.assertEqual(self.request('PUT', '/api/lab', lab)[0], 400)
        for path in ['/server.py', '/data/lab.json', '/.git/config', '/api/shelves/../../server']:
            self.assertEqual(self.request('GET', path)[0], 404)
        self.assertEqual(self.request('GET', '/')[0], 200)

    def test_new_shelf_creates_file_and_removal_preserves_inventory(self):
        self.login()
        _, lab = self.request('GET', '/api/lab')
        item = copy.deepcopy(next(i for i in lab['items'] if i['kind'] == 'shelf'))
        item['id'] = 'new-shelf'
        lab['items'].append(item)
        self.assertEqual(self.request('PUT', '/api/lab', lab)[0], 200)
        self.assertEqual(self.request('GET', '/api/shelves/new-shelf')[0], 200)
        lab['revision'] += 1
        lab['items'].pop()
        self.assertEqual(self.request('PUT', '/api/lab', lab)[0], 200)
        self.assertTrue((self.data / 'shelves/new-shelf.json').exists())

    def test_initial_data_valid_and_bins_cannot_overlap(self):
        validate_lab(json.loads((self.data/'lab.json').read_text()))
        for path in (self.data/'shelves').glob('*.json'):
            validate_shelf(json.loads(path.read_text()), path.stem)
        shelf = json.loads((self.data/'shelves/R01.json').read_text())
        cell = dict(name='Bin', contents='', keywords='', w=2, h=2, background='#ffffff', color='#000000', fontSize=12, fontFamily='Arial', bold=False)
        shelf['matrix'][0][0] = cell
        shelf['matrix'][1][1] = copy.deepcopy(cell)
        with self.assertRaises(ValueError): validate_shelf(shelf, 'R01')

    def test_history_restore_original_restart_and_conflicts(self):
        self.assertEqual(self.request('POST', '/api/lab/restore', {'version': 'original', 'revision': 0})[0], 403)
        self.login()
        _, original = self.request('GET', '/api/lab')
        edited = copy.deepcopy(original)
        edited['routes'][0] = [[10, 10], [20, 20], [30, 10]]
        self.assertEqual(self.request('PUT', '/api/lab', edited)[0], 200)
        versions = self.request('GET', '/api/lab/history')[1]['versions']
        self.assertEqual([v['revision'] for v in versions], [1, 0])
        shelf_bytes = (self.data/'shelves/R01.json').read_bytes()
        self.assertEqual(self.request('POST', '/api/lab/restore', {'version': 'original', 'revision': 0})[0], 409)
        status, restored = self.request('POST', '/api/lab/restore', {'version': 'original', 'revision': 1})
        self.assertEqual(status, 200)
        self.assertEqual(restored['routes'], original['routes'])
        self.assertEqual(restored['revision'], 1)
        self.assertEqual(self.request('GET', '/api/lab')[1]['routes'], edited['routes'])
        self.assertEqual((self.data/'shelves/R01.json').read_bytes(), shelf_bytes)
        # A new server object reads history entirely from disk.
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        self.server = LabServer(('127.0.0.1', 0), self.data, 'itr')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start(); self.cookie = ''; self.login()
        self.assertEqual(len(self.request('GET', '/api/lab/history')[1]['versions']), 2)
        status, restored = self.request('POST', '/api/lab/restore', {'version': '1', 'revision': 1})
        self.assertEqual(status, 200)
        self.assertEqual(restored['routes'], edited['routes'])
        self.assertEqual(restored['revision'], 1)
        self.assertEqual(self.request('POST', '/api/lab/restore', {'version': '../lab', 'revision': 1})[0], 400)
        restored['routes'] = [[[0, 0], [999, 999]]]
        self.assertEqual(self.request('PUT', '/api/lab', restored)[0], 400)

    def test_drafts_are_private_volatile_and_only_named_saves_persist(self):
        self.login()
        original = self.request('GET', '/api/lab')[1]
        draft = copy.deepcopy(original)
        draft['items'][0]['name'] = 'Temporary arrangement'
        state = {'data': draft, 'history': [original], 'future': [], 'dirty': True}
        header = {'X-Editor-Instance': 'tab-one'}
        before = (self.data/'lab.json').read_bytes()
        self.assertEqual(self.request('PUT', '/api/drafts/lab', state, header)[0], 200)
        self.assertEqual(self.request('GET', '/api/drafts/lab', headers=header)[1], state)
        self.assertIsNone(self.request('GET', '/api/drafts/lab', headers={'X-Editor-Instance': 'tab-two'})[1])
        self.assertEqual((self.data/'lab.json').read_bytes(), before)
        for _ in range(3):
            self.assertEqual(self.request('POST', '/api/lab/restore', {'version': 'original', 'revision': 0})[0], 200)
        self.assertEqual((self.data/'lab.json').read_bytes(), before)
        self.assertFalse((self.data/'history').exists())
        draft['versionName'] = ' '
        self.assertEqual(self.request('PUT', '/api/lab', draft)[0], 400)
        draft['versionName'] = 'Fall semester'
        self.assertEqual(self.request('PUT', '/api/lab', draft), (200, {'revision': 1}))
        versions = self.request('GET', '/api/lab/history')[1]['versions']
        self.assertEqual(versions[0]['name'], 'Fall semester')
        self.assertEqual(len(versions), 2)
        self.request('POST', '/api/logout', {})
        self.assertEqual(self.request('GET', '/api/drafts/lab', headers=header)[0], 403)
        self.login()
        self.assertIsNone(self.request('GET', '/api/drafts/lab', headers=header)[1])

    def test_legacy_shelf_migration_and_modes_preserve_bins(self):
        path = self.data/'shelves/R01.json'
        legacy = json.loads(path.read_text())
        for key in ('mode', 'schemaVersion', 'name', 'contents', 'keywords'):
            legacy.pop(key, None)
        legacy['matrix'][0][0] = dict(name='M3 bolts', contents='Steel', keywords='metric', w=2, h=2,
            background='#dc4545', color='#ffffff', fontSize=14, fontFamily='system-ui', bold=True)
        write_json(path, legacy)
        before = path.read_bytes()
        status, migrated = self.request('GET', '/api/shelves/R01')
        self.assertEqual(status, 200)
        self.assertEqual(migrated['mode'], 'complex')
        self.assertEqual(migrated['name'], 'Computer shelf 1')
        self.assertEqual(path.read_bytes(), before)
        self.login()
        migrated.update(mode='simple', name='Hardware', contents='Screws', keywords='parts')
        self.assertEqual(self.request('PUT', '/api/shelves/R01', migrated)[0], 200)
        saved = self.request('GET', '/api/shelves/R01')[1]
        self.assertEqual(saved['mode'], 'simple')
        self.assertEqual(saved['matrix'], legacy['matrix'])
        saved['mode'] = 'complex'
        self.assertEqual(self.request('PUT', '/api/shelves/R01', saved)[0], 200)
        self.assertEqual(self.request('GET', '/api/shelves/R01')[1]['contents'], 'Screws')

    def test_search_index_and_private_draft_metadata(self):
        path = self.data/'shelves/R01.json'
        shelf = json.loads(path.read_text())
        shelf.update(mode='complex', name='Precision stock', contents='Assembly', keywords='robotics')
        shelf['matrix'][0][0] = dict(name='M3 bolts', contents='Stainless', keywords='metric', w=2, h=2,
            background='#dc4545', color='#ffffff', fontSize=14, fontFamily='system-ui', bold=True)
        write_json(path, shelf)
        index = self.request('GET', '/api/shelf-index')[1]['R01']
        for term in ['precision', 'assembly', 'robotics', 'm3 bolts', 'stainless', 'metric']:
            self.assertIn(term, index['searchText'])
        self.login()
        shelf['contents'] = 'Private draft contents'
        state = {'data': shelf, 'history': [], 'future': [], 'dirty': True}
        header = {'X-Editor-Instance': 'tab-one'}
        self.assertEqual(self.request('PUT', '/api/drafts/shelves/R01', state, header)[0], 200)
        self.assertIn('private draft', self.request('GET', '/api/shelf-index', headers=header)[1]['R01']['searchText'])
        self.assertNotIn('private draft', self.request('GET', '/api/shelf-index', headers={'X-Editor-Instance': 'tab-two'})[1]['R01']['searchText'])
        self.request('POST', '/api/logout', {})
        self.assertNotIn('private draft', self.request('GET', '/api/shelf-index', headers=header)[1]['R01']['searchText'])


if __name__ == '__main__':
    unittest.main()
