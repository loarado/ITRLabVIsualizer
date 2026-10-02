import unittest
import browser_features
from playwright.sync_api import expect


class Drafts(unittest.TestCase):
    setUp = browser_features.Features.setUp
    tearDown = browser_features.Features.tearDown
    login = browser_features.Features.login

    def test_confirm_active_and_last_draft(self):
        p=self.page
        self.login()
        baseline=p.evaluate('JSON.stringify(lab.data)')
        p.evaluate("checkpoint();lab.data.items[0].name='Active draft';changed()")
        p.evaluate("async()=>{const data=clone(lab.data);data.items[0].name='Other tab';await api('/api/drafts/lab','PUT',{data,history:[],future:[],dirty:true},'other-tab');}")
        p.locator('#manageDrafts').click()
        expect(p.locator('.draft-row')).to_have_count(2)
        active=p.locator('.draft-row').filter(has_text='Active editor')
        active.get_by_role('button').click()
        expect(p.locator('#deleteDraftDialog')).to_be_visible()
        self.assertTrue(p.evaluate("async()=>!!await api('/api/drafts/lab')"))
        p.locator('#cancelDeleteDraft').click()
        expect(p.locator('.draft-row')).to_have_count(2)
        active.get_by_role('button').click()
        p.locator('#confirmDeleteDraft').click()
        expect(p.locator('.draft-row')).to_have_count(1)
        self.assertEqual(p.evaluate('JSON.stringify(lab.data)'),baseline)
        p.locator('#closeDrafts').click()
        p.reload()
        p.wait_for_function('isAdmin&&lab.data')
        self.assertEqual(p.evaluate('JSON.stringify(lab.data)'),baseline)
        p.locator('#manageDrafts').click()
        expect(p.locator('.draft-row')).to_have_count(1)
        p.locator('.draft-row button').click()
        p.locator('#confirmDeleteDraft').click()
        expect(p.locator('#draftList')).to_have_text('No temporary drafts.')
        p.locator('#closeDrafts').click()
        p.reload()
        p.wait_for_function('isAdmin&&lab.data')
        p.locator('#manageDrafts').click()
        expect(p.locator('#draftList')).to_have_text('No temporary drafts.')
        p.locator('#closeDrafts').click()
        p.locator('#auth').click()
        p.wait_for_function('!isAdmin')
        self.login()
        p.locator('#manageDrafts').click()
        expect(p.locator('#draftList')).to_have_text('No temporary drafts.')
        self.assertEqual(self.page.evaluate('lab.data.revision'),0)


if __name__ == '__main__':
    unittest.main()
