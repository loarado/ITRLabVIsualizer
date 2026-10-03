import json
import unittest
import browser_features
from playwright.sync_api import expect

class InventoryEditor(unittest.TestCase):
    setUp = browser_features.Features.setUp
    tearDown = browser_features.Features.tearDown
    login = browser_features.Features.login
    save = browser_features.Features.save

    def create(self, name, quantity=None):
        p=self.page
        p.locator('#inv-item-name').fill(name)
        if quantity is not None:
            p.locator('#inv-stock-tracking').select_option('exact')
            p.locator('#inv-stock-quantity').fill(quantity)
        p.locator('#inv-save').click()
        expect(p.locator('#inventoryEditor')).not_to_be_visible()
        expect(p.locator('#status')).to_contain_text('Inventory saved')

    def test_shared_editor_multi_location_unknown_values_and_read_only(self):
        p=self.page;self.login()
        p.locator('[data-id="R01"]').click()
        p.locator('#mapStockPanel').get_by_role('button',name='Add inventory to this shelf',exact=True).click()
        self.create('M4 bolts','20')
        doc=json.loads((self.data/'inventory.json').read_text());item_id=next(iter(doc['items']))
        p.locator('#mapStockPanel').get_by_role('button',name='M4 bolts',exact=True).click()
        p.get_by_role('button',name='Add this item to another location').click()
        p.locator('#inv-location').select_option('R02')
        p.locator('#inv-stock-tracking').select_option('availability');p.locator('#inv-stock-availability').select_option('low')
        p.locator('#inv-save').click();expect(p.locator('#inventoryEditor')).not_to_be_visible()
        expect(p.locator('#inventoryDetailContent')).to_contain_text('low')
        p.locator('#inventoryDetailClose').click()
        p.goto(self.url+'/shelf_editor.html?id=R01');p.wait_for_function('isAdmin && inventoryState')
        expect(p.locator('#shelfStockPanel')).to_contain_text('M4 bolts')
        p.locator('#shelfStockPanel').get_by_role('button',name='M4 bolts',exact=True).click()
        p.get_by_role('button',name='Edit item details',exact=True).click()
        p.locator('#inv-item-name').fill('M4 steel bolts');p.locator('#inv-item-unitPrice').fill('0.105')
        p.locator('#inv-save').click();expect(p.locator('#inventoryEditor')).not_to_be_visible()
        expect(p.locator('#inventoryDetailContent')).to_contain_text('USD 2.10')
        doc=json.loads((self.data/'inventory.json').read_text());self.assertEqual(len(doc['items']),1);self.assertEqual(len(doc['stocks']),2)
        self.assertEqual(doc['items'][item_id]['name'],'M4 steel bolts')
        p.locator('#inventoryDetailClose').click()
        p.locator('#shelfStockPanel').get_by_role('button',name='Add inventory to this shelf',exact=True).click()
        p.locator('#inv-stock-tracking').select_option('exact');self.create('Unknown count')
        doc=json.loads((self.data/'inventory.json').read_text());unknown=next(s for s in doc['stocks'].values() if doc['items'][s['itemId']]['name']=='Unknown count')
        self.assertIsNone(unknown['quantity']);self.assertIsNone(doc['items'][unknown['itemId']]['unitPrice'])
        p.locator('#auth').click();p.wait_for_function('!isAdmin')
        expect(p.locator('#shelfReadOnly')).to_contain_text('M4 steel bolts')
        expect(p.locator('#shelfReadOnly').get_by_role('button',name='Add inventory to this shelf',exact=True)).to_have_count(0)
        p.locator('#shelfReadOnly').get_by_role('button',name='M4 steel bolts',exact=True).click()
        expect(p.locator('#inventoryDetailContent').get_by_role('button',name='Edit item details')).to_have_count(0)

    def test_multiple_items_in_one_bin_and_transfer(self):
        p=self.page;self.login()
        p.goto(self.url+'/shelf_editor.html?id=R01');p.wait_for_function('isAdmin && inventoryState')
        p.locator('#shelfMode').select_option('complex');p.locator('#applyShelfMode').click()
        p.get_by_role('button',name='Empty cell, row 1, column 1',exact=True).click();p.locator('#addBin').click()
        self.save('Bin location')
        p.locator('#shelfStockPanel').get_by_role('button',name='Add inventory to this bin',exact=True).click();self.create('Bolts','10')
        p.locator('#shelfStockPanel').get_by_role('button',name='Add inventory to this bin',exact=True).click();self.create('Washers')
        expect(p.locator('#shelfStockPanel')).to_contain_text('Bolts');expect(p.locator('#shelfStockPanel')).to_contain_text('Washers')
        p.locator('#shelfStockPanel').get_by_role('button',name='Bolts',exact=True).click()
        p.get_by_role('button',name='Transfer quantity',exact=True).click()
        p.locator('#transfer-location').select_option('R02');p.locator('#transfer-amount').fill('3')
        # Commit on the disposable server but simulate a lost acknowledgement.
        def lose_ack(route):
            if route.request.method=='POST':
                route.fetch()
                route.fulfill(status=503,content_type='application/json',body='{"error":"Lost transfer acknowledgement"}')
            else:route.continue_()
        p.route('**/api/inventory',lose_ack)
        p.get_by_role('button',name='Transfer stock',exact=True).click()
        expect(p.locator('#transfer-feedback')).to_contain_text('Lost transfer acknowledgement')
        p.unroute('**/api/inventory')
        p.get_by_role('button',name='Transfer stock',exact=True).click();expect(p.locator('#inventoryTransfer')).not_to_be_visible()
        self.errors[:] = [e for e in self.errors if 'status of 503' not in e]
        expect(p.locator('#inventoryDetailContent')).to_contain_text('7 each');expect(p.locator('#inventoryDetailContent')).to_contain_text('3 each')
        doc=json.loads((self.data/'inventory.json').read_text());self.assertEqual(len(doc['items']),2);self.assertEqual(len(doc['stocks']),3)

    def test_unsaved_transfer_recovers_on_refresh(self):
        p=self.page;self.login();p.locator('[data-id="R01"]').click()
        p.locator('#mapStockPanel').get_by_role('button',name='Add inventory to this shelf',exact=True).click()
        self.create('Recoverable transfer','10')
        p.locator('#mapStockPanel').get_by_role('button',name='Recoverable transfer',exact=True).click()
        p.get_by_role('button',name='Transfer quantity',exact=True).click()
        p.locator('#transfer-location').select_option('R02');p.locator('#transfer-amount').fill('4')
        operation=p.evaluate('inventoryTransferEntry.operationId')
        p.on('dialog',lambda dialog:dialog.accept())
        p.reload();p.wait_for_function('typeof inventoryTransferEntry!=="undefined" && inventoryTransferEntry')
        expect(p.locator('#transfer-amount')).to_have_value('4')
        expect(p.locator('#transfer-location')).to_have_value('R02')
        self.assertEqual(p.evaluate('inventoryTransferEntry.operationId'),operation)
        p.get_by_role('button',name='Transfer stock',exact=True).click();expect(p.locator('#inventoryTransfer')).not_to_be_visible()
        doc=json.loads((self.data/'inventory.json').read_text());self.assertEqual(sorted(s['quantity'] for s in doc['stocks'].values()),['4','6'])
        self.assertIsNone(p.evaluate("localStorage.getItem(recoveryKey('inventory-transfer'))"))

    def test_entry_refresh_recovery_failed_save_and_concurrent_review(self):
        p=self.page;self.login();p.locator('[data-id="R01"]').click()
        p.locator('#mapStockPanel').get_by_role('button',name='Add inventory to this shelf',exact=True).click()
        p.locator('#inv-item-name').fill('Recovered entry')
        p.on('dialog',lambda dialog:dialog.accept())
        p.reload();p.wait_for_function('isAdmin && inventoryEntry')
        expect(p.locator('#inv-item-name')).to_have_value('Recovered entry')
        p.evaluate("api('/api/inventory','POST',{action:'save',item:{name:'Other editor item'},revision:0,operationId:'other-editor'})")
        p.locator('#inv-save').click()
        expect(p.locator('#inv-feedback')).to_contain_text('another editor')
        expect(p.locator('#inv-item-name')).to_have_value('Recovered entry')
        p.locator('#inv-reconcile').click()
        # A rejected save retains all values; the API does not commit anything.
        p.route('**/api/inventory',lambda route:route.fulfill(status=503,content_type='application/json',body='{"error":"Disposable failed save"}') if route.request.method=='POST' else route.continue_())
        p.locator('#inv-save').click();expect(p.locator('#inv-feedback')).to_contain_text('Disposable failed save')
        expect(p.locator('#inv-item-name')).to_have_value('Recovered entry')
        p.unroute('**/api/inventory')
        p.locator('#inv-save').click();expect(p.locator('#inventoryEditor')).not_to_be_visible()
        doc=json.loads((self.data/'inventory.json').read_text());self.assertEqual(len(doc['items']),2)
        self.assertEqual(len(doc['stocks']),1)
        self.assertEqual(p.evaluate("localStorage.getItem(recoveryKey('inventory-entry'))"),None)
        p.reload();p.wait_for_function('inventoryState?.revision===2')
        expect(p.locator('#inventoryEditor')).not_to_be_visible()
        self.assertEqual(json.loads((self.data/'lab.json').read_text())['revision'],0)
        self.errors[:] = [e for e in self.errors if 'status of 409' not in e and 'status of 503' not in e]

if __name__=='__main__':unittest.main()
