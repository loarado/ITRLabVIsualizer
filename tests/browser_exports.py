"""Download regression checks against isolated lab data."""
import json
import struct
import unittest
import browser_features


class Exports(unittest.TestCase):
    setUp = browser_features.Features.setUp
    tearDown = browser_features.Features.tearDown
    login = browser_features.Features.login

    def test_image_and_inventory_downloads(self):
        page = self.page
        saved = (self.data/'lab.json').read_bytes()
        with page.expect_download() as result:
            page.locator('#export').click()
        download = result.value
        self.assertEqual(download.suggested_filename, 'lab-details.json')
        with open(download.path()) as file:
            exported = json.load(file)
        self.assertEqual(exported['items'], json.loads(saved)['items'])
        self.assertEqual(set(exported['shelves']), {i['id'] for i in exported['items'] if i['kind']=='shelf'})

        self.login()
        page.locator('#newKind').select_option('shelf')
        page.locator('#add').click()
        sid = page.evaluate('selected().id')
        page.locator('#name').fill('Unsaved export shelf')
        page.locator('#name').press('Tab')
        page.evaluate('''async sid=>{
            await cacheDraft();
            const data=await api('/api/shelves/'+sid);
            data.contents='Unsaved inventory contents';
            await api('/api/drafts/shelves/'+sid,'PUT',{data,history:[],future:[],dirty:true});
        }''', sid)
        with page.expect_download() as result:
            page.locator('#export').click()
        with open(result.value.path()) as file:
            exported = json.load(file)
        self.assertEqual(exported['items'][-1]['name'], 'Unsaved export shelf')
        self.assertEqual(exported['shelves'][sid]['contents'], 'Unsaved inventory contents')

        page.locator('#zoomIn').click()
        before = page.evaluate('JSON.stringify(lab.data)')
        with page.expect_download() as result:
            page.locator('#exportImage').click()
        download = result.value
        self.assertEqual(download.suggested_filename, 'lab-grid.png')
        with open(download.path(), 'rb') as file:
            png = file.read()
        self.assertEqual(png[:8], b'\x89PNG\r\n\x1a\n')
        width, height = struct.unpack('>II', png[16:24])
        self.assertGreater(width, page.locator('#viewport').evaluate('(el)=>el.clientWidth'))
        self.assertGreater(height, 100)
        self.assertGreater(len(png), 10000)
        self.assertEqual(page.evaluate('JSON.stringify(lab.data)'), before)
        self.assertEqual((self.data/'lab.json').read_bytes(), saved)


if __name__ == '__main__':
    unittest.main()
