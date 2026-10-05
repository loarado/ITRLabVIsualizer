import unittest
import browser_features
from playwright.sync_api import expect

class QuickEntry(unittest.TestCase):
    setUp = browser_features.Features.setUp
    tearDown = browser_features.Features.tearDown
    login = browser_features.Features.login

    def test_name_only_failure_composition_double_submit_and_details(self):
        p=self.page;self.login();p.locator('[data-id="R01"]').click()
        field=p.locator('#mapStockPanel input[placeholder="Add inventory…"]')
        field.fill('  Bolts, washers  ')
        field.press('Enter')
        expect(p.locator('#mapStockPanel')).to_contain_text('Bolts, washers')
        expect(field).to_be_focused();expect(field).to_have_value('')
        self.assertEqual(len(self.server.stock_document()['stocks']),1)
        field.fill('Bolts, washers');field.press('Enter');expect(p.locator('#mapStockPanel')).to_contain_text('Already recorded')
        self.assertEqual(len(self.server.stock_document()['stocks']),1)
        field.fill('Composing');field.dispatch_event('compositionstart');field.press('Enter')
        self.assertEqual(len(self.server.stock_document()['stocks']),1)
        field.dispatch_event('compositionend')
        p.route('**/api/inventory',lambda route: route.fulfill(status=500,content_type='application/json',body='{"error":"Simulated save failure"}') if route.request.method=='POST' else route.continue_())
        field.press('Enter');expect(p.locator('#mapStockPanel')).to_contain_text('Simulated save failure');expect(field).to_have_value('Composing')
        p.unroute('**/api/inventory');self.errors[:]=[e for e in self.errors if 'status of 500' not in e]
        p.evaluate("document.querySelector('#mapStockPanel form').requestSubmit(); document.querySelector('#mapStockPanel form').requestSubmit()")
        expect(field).to_have_value('');self.assertEqual(len(self.server.stock_document()['stocks']),2)
        expect(p.locator('#mapStockPanel .stock-details')).to_have_count(0)
        p.locator('#mapStockPanel').get_by_role('button',name='Edit Bolts, washers',exact=True).click()
        p.locator('.inventory-optional summary').click();p.locator('#inv-stock-tracking').select_option('exact');p.locator('#inv-stock-quantity').fill('4');p.locator('#inv-item-vendor').fill('Keep vendor')
        p.locator('#inv-save').click();expect(p.locator('#inventoryEditor')).not_to_be_visible()
        p.locator('#mapStockPanel .stock-details summary').click()
        expect(p.locator('#mapStockPanel')).to_contain_text('4 each')
        self.assertEqual(len(self.server.stock_document()['stocks']),2)
        field.fill('Concurrent quick entry')
        p.evaluate("api('/api/inventory','POST',{action:'quick',item:{name:'Another editor'},stock:{shelfId:'R01'},revision:inventoryState.revision,operationId:'concurrent-quick'})")
        field.press('Enter');expect(p.locator('#mapStockPanel')).to_contain_text('Inventory refreshed')
        expect(field).to_have_value('Concurrent quick entry');field.press('Enter');expect(field).to_have_value('')
        def lose_ack(route):
            if route.request.method=='POST':
                route.fetch();route.fulfill(status=503,content_type='application/json',body='{"error":"Lost quick acknowledgement"}')
            else:route.continue_()
        p.route('**/api/inventory',lose_ack)
        field.fill('Retry confirmed entry');field.press('Enter');expect(field).to_have_value('Retry confirmed entry')
        expect(p.locator('#mapStockPanel')).to_contain_text('Lost quick acknowledgement')
        count=len(self.server.stock_document()['stocks']);p.unroute('**/api/inventory');field.press('Enter');expect(field).to_have_value('')
        self.assertEqual(len(self.server.stock_document()['stocks']),count)
        self.errors[:]=[e for e in self.errors if 'status of 409' not in e and 'status of 503' not in e]
        # Confirmation contains the saved record, so a failed refresh cannot hide it.
        p.route('**/api/inventory',lambda route: route.fulfill(status=503,content_type='application/json',body='{"error":"Refresh unavailable"}') if route.request.method=='GET' else route.continue_())
        field.fill('Confirmed despite refresh failure');field.press('Enter')
        expect(p.locator('#mapStockPanel')).to_contain_text('Confirmed despite refresh failure');expect(field).to_have_value('')
        p.unroute('**/api/inventory');self.errors[:]=[e for e in self.errors if 'status of 503' not in e]

if __name__=='__main__': unittest.main()
