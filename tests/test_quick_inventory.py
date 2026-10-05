import unittest
import test_inventory

class QuickInventory(unittest.TestCase):
    setUp = test_inventory.InventoryTests.setUp
    tearDown = test_inventory.InventoryTests.tearDown
    request = test_inventory.InventoryTests.request
    login = test_inventory.InventoryTests.login
    mutation = test_inventory.InventoryTests.mutation

    def test_quick_identity_retry_details_and_authorization(self):
        payload=dict(action='quick',item={'name':'  Comma, stays one item  '},stock={'shelfId':'R01','binId':None})
        self.assertEqual(self.mutation(**payload)[0],403)
        self.login()
        payload.update(revision=0,operationId='quick-retry')
        first=self.request('POST','/api/inventory',payload)
        self.assertEqual(first[0],200)
        self.assertEqual(self.request('POST','/api/inventory',payload),first)
        doc=self.server.stock_document();self.assertEqual(len(doc['stocks']),1)
        item=doc['items'][first[1]['itemId']];self.assertEqual(item['name'],'Comma, stays one item');self.assertIsNone(item['unitPrice'])
        stock=doc['stocks'][first[1]['stockId']];self.assertIsNone(stock['quantity'])
        self.assertEqual(self.mutation(action='save',itemId=first[1]['itemId'],stockId=first[1]['stockId'],stock=dict(stock,tracking='exact',quantity='12.5',unit='pack'),item=dict(item,vendor='Keep me'))[0],200)
        duplicate=self.mutation(action='quick',item={'name':item['name']},stock={'shelfId':'R01','binId':None})
        self.assertTrue(duplicate[1]['existing']);self.assertEqual(self.server.stock_document()['stocks'][first[1]['stockId']]['quantity'],'12.5')
        self.assertEqual(self.server.stock_document()['items'][first[1]['itemId']]['vendor'],'Keep me')
        self.assertEqual(self.mutation(action='quick',item={'name':' '},stock={'shelfId':'R01'})[0],400)
        self.assertEqual(self.mutation(action='quick',item={'name':'Other'},stock={'shelfId':'R01'},revision=0)[0],409)

    def test_physical_locations_survive_rename_remove_and_restore(self):
        self.login()
        lab=self.request('GET','/api/lab')[1]
        physical=[i for i in lab['items'] if i['kind'] in ('table','machine','cart')]
        for obj in physical[:3]:
            self.assertEqual(self.mutation(action='quick',item={'name':obj['name']},stock={'shelfId':obj['id']})[0],200)
        loc=self.request('GET','/api/inventory')[1]['locations']
        for obj in lab['items']:
            if obj['kind'] in ('wall','text','misc','section'):
                self.assertNotIn(obj['id'],loc)
                self.assertEqual(self.mutation(action='quick',item={'name':'Forbidden'},stock={'shelfId':obj['id']})[0],400)
        before=self.server.stock_document()
        lab['items']=[i for i in lab['items'] if i['id']!=physical[0]['id']]
        physical[1]['name']='Renamed physical location'
        lab.update(versionName='Physical objects')
        self.assertEqual(self.request('PUT','/api/lab',lab)[0],200)
        self.assertEqual(self.server.stock_document(),before)
        doc=self.request('GET','/api/inventory')[1]
        self.assertNotIn(physical[0]['id'],doc['locations'])
        self.assertIn('Renamed physical location',doc['locations'][physical[1]['id']]['label'])
