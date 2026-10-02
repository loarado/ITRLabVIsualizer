import json
import unittest
import browser_features
from playwright.sync_api import expect


class Recovery(unittest.TestCase):
    def setUp(self):
        browser_features.Features.setUp(self)
        self.page.on('dialog', lambda dialog: dialog.accept())
    tearDown = browser_features.Features.tearDown
    login = browser_features.Features.login
    save = browser_features.Features.save

    def reload(self):
        self.page.reload()
        self.page.wait_for_function('isAdmin&&recoveryReady')

    def test_unsent_map_shelf_and_save(self):
        p=self.page
        self.login()
        original=(self.data/'lab.json').read_bytes()
        p.evaluate('''()=>{
            checkpoint();lab.data.items[0].name='Recovered section';
            lab.data.items.find(i=>i.kind==='table').x+=1;
            lab.data.items.push({...defaults(),id:'new-recovery',kind:'misc',name:'Recovered item',x:10,y:10,w:2,h:2,locked:false,shape:'circle'});
            lab.data.outline[1][0]-=1;
            lab.data.walls=[{id:'recovery-wall',a:[10,10],b:[10,15],thickness:.5}];
            lab.data.doors=[{id:'recovery-door',x:20,y:20,radius:3,orientation:'SE'}];
            lab.data.routes.push([[30,20],[30,25]]);
            render();changed();setMapEditing(true);clearTimeout(saveTimer);
        }''')
        expected=p.evaluate('lab.data')
        self.reload()
        self.assertEqual(p.evaluate('lab.data'), expected)
        self.assertTrue(p.evaluate('mapEditing'))
        self.assertTrue(p.evaluate('dirty'))
        self.assertEqual((self.data/'lab.json').read_bytes(),original)
        p.locator('#mapMode').click()
        p.goto(self.url+'/shelf_editor.html?id=R01')
        p.wait_for_function('isAdmin&&recoveryReady')
        p.locator('#shelfContents').fill('Recovered contents')
        p.locator('#shelfContents').press('Tab')
        p.locator('#shelfKeywords').fill('Recovered keywords')
        p.locator('#shelfKeywords').press('Tab')
        p.locator('#shelfMode').select_option('complex')
        p.locator('#applyShelfMode').click()
        p.get_by_role('button',name='Empty cell, row 1, column 1',exact=True).click()
        p.locator('#addBin').click()
        p.locator('#w').fill('1.5')
        p.locator('#w').press('Tab')
        for shape in ('rectangle','ellipse','triangle'):
            p.locator('#decorShape').select_option(shape)
            p.locator('#addDecor').click()
        p.evaluate("checkpoint();currentDecor().text='Pending recovery text';currentDecor().w=4.25;render();changed();clearTimeout(saveTimer)")
        expected_shelf=p.evaluate('shelf.data')
        self.reload()
        self.assertEqual(p.evaluate('shelf.data'),expected_shelf)
        p.locator('#back').click()
        p.wait_for_function('typeof lab!=="undefined"&&isAdmin&&recoveryReady')
        self.assertEqual(p.evaluate('lab.data'),expected)
        self.save('Recovered full workflow')
        self.reload()
        self.assertFalse(p.evaluate('dirty'))
        self.assertEqual(p.evaluate('lab.data.items'),expected['items'])
        saved=json.loads((self.data/'shelves/R01.json').read_text())
        self.assertEqual(saved['decor'],expected_shelf['decor'])
        self.assertEqual(saved['matrix'][0][0]['w'],1.5)
        p.locator('#auth').click()
        p.wait_for_function('!isAdmin')
        self.assertEqual(p.evaluate("Object.keys(localStorage).filter(k=>k.startsWith('itr-recovery:')).length"),0)
        self.assertEqual(p.evaluate('lab.data.revision'),1)

    def test_failed_save_keeps_work_and_corrupt_stale_recovery(self):
        p=self.page
        self.login()
        p.evaluate("checkpoint();lab.data.items[0].name='Keep after failure';changed();clearTimeout(saveTimer)")
        p.route('**/api/lab',lambda route: route.fulfill(status=503,json={'error':'Simulated save failure'}) if route.request.method=='PUT' else route.continue_())
        self.assertFalse(p.evaluate("save('Failure')"))
        self.errors[:]=[error for error in self.errors if '503' not in error]
        p.unroute('**/api/lab')
        self.reload()
        self.assertEqual(p.evaluate('lab.data.items[0].name'),'Keep after failure')
        self.assertTrue(p.evaluate('dirty'))
        # Advance the committed map independently; neither cached nor local old
        # working copies may overwrite its newer revision during hydration.
        p.evaluate("async()=>{const data=await api('/api/lab');data.versionName='Newer committed';data.items[0].name='Newer';await api('/api/lab','PUT',data,'other-editor');}")
        self.reload()
        self.assertEqual(p.evaluate('lab.data.items[0].name'),'Newer')
        self.assertFalse(p.evaluate('dirty'))
        p.evaluate("localStorage.setItem(recoveryKey(),'{broken');recoveryReady=false")
        self.reload()
        self.assertEqual(p.evaluate('lab.data.items[0].name'),'Newer')
        expect(p.locator('#fatal')).to_be_hidden()

    def test_new_shelf_pending_map_and_deleted_snapshot(self):
        p=self.page
        self.login()
        p.locator('#newKind').select_option('shelf')
        p.locator('#add').click()
        sid=p.evaluate('selected().id')
        p.evaluate("clearTimeout(saveTimer);allowNavigation=true")
        p.goto(self.url+'/shelf_editor.html?id='+sid)
        p.wait_for_function('isAdmin&&recoveryReady')
        self.assertEqual(p.evaluate('shelf.data.id'),sid)
        p.locator('#addDecor').click()
        p.evaluate('cacheDraft()')
        snapshot=p.evaluate('localStorage.getItem(recoveryKey())')
        p.locator('#manageDrafts').click()
        p.locator('.draft-row').filter(has_text='Active editor').get_by_role('button').click()
        p.locator('#confirmDeleteDraft').click()
        p.wait_for_function('!dirty')
        p.locator('#closeDrafts').click()
        p.evaluate('(record)=>{localStorage.setItem(recoveryKey(),record);recoveryReady=false}',snapshot)
        self.reload()
        self.assertEqual(p.evaluate('shelf.data.decor.length'),0)
        self.assertFalse(p.evaluate('dirty'))

    def test_typing_refresh_storage_failure_and_private_logout(self):
        p=self.page
        self.login()
        p.goto(self.url+'/shelf_editor.html?id=R01')
        p.wait_for_function('isAdmin&&recoveryReady')
        p.locator('#shelfContents').fill('Still typing when refreshed')
        self.reload()
        expect(p.locator('#shelfContents')).to_have_value('Still typing when refreshed')
        # Browser storage may be denied; server draft caching still functions.
        p.evaluate("()=>{Storage.prototype.setItem=function(){throw new DOMException('Full','QuotaExceededError')}}")
        p.locator('#shelfContents').fill('Server fallback')
        p.locator('#shelfContents').press('Tab')
        p.evaluate('cacheDraft()')
        self.reload()
        expect(p.locator('#shelfContents')).to_have_value('Server fallback')
        p.locator('#auth').click()
        p.wait_for_function('!isAdmin')
        self.assertNotIn('Server fallback',p.locator('#shelfReadOnly').inner_text())
        self.assertEqual(p.evaluate("Object.keys(localStorage).filter(k=>k.startsWith('itr-recovery:')).length"),0)
        self.login()
        self.assertNotEqual(p.locator('#shelfContents').input_value(),'Server fallback')

    def test_sibling_tab_deletion_clears_active_recovery(self):
        p=self.page
        self.login()
        baseline=p.evaluate('lab.data')
        p.evaluate("checkpoint();lab.data.items[0].name='Sibling deletion';changed()")
        p.evaluate('cacheDraft()')
        instance=p.evaluate('editorInstance')
        other=self.context.new_page()
        other.goto(self.url)
        other.wait_for_function('isAdmin&&recoveryReady')
        other.locator('#manageDrafts').click()
        other.locator(f'.draft-row[data-instance="{instance}"]').get_by_role('button').click()
        other.locator('#confirmDeleteDraft').click()
        p.wait_for_function('!dirty')
        self.assertEqual(p.evaluate('lab.data'),baseline)
        self.reload()
        self.assertEqual(p.evaluate('lab.data'),baseline)
        self.assertFalse(p.evaluate("async()=>!!await api('/api/drafts/lab')"))
        other.close()


if __name__ == '__main__':
    unittest.main()
