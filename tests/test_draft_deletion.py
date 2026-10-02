import copy
import unittest
import test_server


class DraftDeletion(unittest.TestCase):
    setUp = test_server.ServerTests.setUp
    tearDown = test_server.ServerTests.tearDown
    request = test_server.ServerTests.request
    login = test_server.ServerTests.login

    def test_recovery_context_is_scoped_and_tracks_commits(self):
        self.assertEqual(self.request('GET', '/api/recovery-context')[0], 403)
        self.login()
        context = self.request('GET', '/api/recovery-context')[1]
        self.assertEqual(self.request('GET', '/api/recovery-context')[1], context)
        self.assertNotIn(self.cookie.split('=',1)[1], context['scope'])
        lab = self.request('GET', '/api/lab')[1]
        self.request('PUT', '/api/lab', lab)
        newer = self.request('GET', '/api/recovery-context')[1]
        self.assertEqual(newer['scope'], context['scope'])
        self.assertEqual(newer['labRevision'], context['labRevision']+1)
        self.request('POST', '/api/logout', {})
        self.login()
        self.assertNotEqual(self.request('GET', '/api/recovery-context')[1]['scope'], context['scope'])

    def test_scoped_deletion_and_versions(self):
        self.assertEqual(self.request('GET', '/api/drafts')[0], 403)
        self.assertEqual(self.request('DELETE', '/api/drafts/lab')[0], 403)
        self.login()
        lab = self.request('GET', '/api/lab')[1]
        self.assertEqual(self.request('PUT', '/api/lab', lab)[0], 200)
        lab = self.request('GET', '/api/lab')[1]
        before = {str(p): p.read_bytes() for p in self.data.rglob('*.json')}
        for instance in ('first', 'second'):
            draft = copy.deepcopy(lab)
            draft['items'][0]['name'] = instance
            state = dict(data=draft, history=[lab], future=[], dirty=True)
            self.assertEqual(self.request('PUT', '/api/drafts/lab', state, {'X-Editor-Instance':instance})[0], 200)
        self.assertEqual(len(self.request('GET', '/api/drafts')[1]['drafts']), 2)
        self.assertEqual(self.request('DELETE', '/api/drafts/lab', headers={'X-Editor-Instance':'first', 'Origin':'https://untrusted.invalid'})[0], 403)
        self.assertEqual(self.request('DELETE', '/api/drafts/lab', headers={'X-Editor-Instance':'first'})[0], 200)
        self.assertIsNone(self.request('GET', '/api/drafts/lab', headers={'X-Editor-Instance':'first'})[1])
        self.assertEqual(self.request('GET', '/api/drafts/lab', headers={'X-Editor-Instance':'second'})[1]['data']['items'][0]['name'], 'second')
        self.assertEqual(self.request('PUT', '/api/drafts/lab', state, {'X-Editor-Instance':'first', 'X-Draft-Epoch':'0'})[0], 409)
        self.assertEqual(self.request('DELETE', '/api/drafts/lab', headers={'X-Editor-Instance':'second'})[0], 200)
        self.assertEqual(self.request('GET', '/api/drafts')[1]['drafts'], [])
        self.request('POST', '/api/logout', {})
        self.login()
        self.assertEqual(self.request('GET', '/api/drafts')[1]['drafts'], [])
        self.assertEqual({str(p):p.read_bytes() for p in self.data.rglob('*.json')}, before)


if __name__ == '__main__':
    unittest.main()
