import copy
import hashlib
import json
import threading
import unittest
import test_server
from server import LabServer, write_json
from inventory import identify_bins, validate_item, validate_stock, estimated_value


def bin_data():
    return dict(name='Hardware', contents='Legacy descriptive notes', keywords='bolts', w=2, h=2,
                background='#ffffff', color='#000000', fontSize=12, fontFamily='Arial', bold=False)


class InventoryTests(unittest.TestCase):
    setUp = test_server.ServerTests.setUp
    tearDown = test_server.ServerTests.tearDown
    request = test_server.ServerTests.request
    login = test_server.ServerTests.login

    def restart(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()
        self.server = LabServer(('127.0.0.1',0), self.data, 'itr')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.cookie = ''

    def test_migration_checkpoint_idempotence_and_copied_locations(self):
        shelf = self.request('GET', '/api/shelves/R01')[1]
        shelf['matrix'][0][0] = bin_data()
        shelf['matrix'][0][3] = dict(bin_data(), id='existing')
        shelf['decor'] = []
        shelf.update(mode='complex',contents='Keep notes')
        write_json(self.data/'shelves/R01.json',shelf)
        other = copy.deepcopy(shelf); other['id'] = 'unplaced'; write_json(self.data/'shelves/unplaced.json',other)
        history = self.data/'history/lab/0.json'; write_json(history,dict(layout=self.request('GET','/api/lab')[1], shelves={'R01':shelf}))
        before = history.read_bytes()
        self.restart()
        saved = json.loads((self.data/'shelves/R01.json').read_text())
        self.assertEqual(saved['matrix'][0][3]['id'],'existing')
        self.assertEqual(saved['revision'],shelf['revision']+1)
        self.assertEqual(saved['contents'],'Keep notes')
        self.assertEqual(identify_bins(shelf)['matrix'],saved['matrix'])
        self.assertEqual(history.read_bytes(),before)
        self.assertEqual(self.server.stock_document()['stocks'],{})
        keys = self.server.stock_locations()
        self.assertIn('R01/existing',keys);self.assertIn('unplaced/existing',keys)
        self.assertFalse(keys['unplaced/existing']['mapped'])
        checkpoint = list((self.data.parent/'.itr-backups').glob('*.tar.gz'))
        self.assertTrue(checkpoint)
        digest = hashlib.sha256((self.data/'shelves/R01.json').read_bytes()).hexdigest()
        self.restart()
        self.assertEqual(hashlib.sha256((self.data/'shelves/R01.json').read_bytes()).hexdigest(),digest)
        self.assertEqual(history.read_bytes(),before)
        # Reads resolve IDs without modifying even a subsequently introduced legacy file.
        legacy = copy.deepcopy(shelf); legacy['id']='old-import';write_json(self.data/'shelves/old-import.json',legacy)
        raw=(self.data/'shelves/old-import.json').read_bytes()
        self.assertEqual(self.request('GET','/api/shelves/old-import')[1]['matrix'],identify_bins(legacy)['matrix'])
        self.assertEqual((self.data/'shelves/old-import.json').read_bytes(),raw)

    def test_unknown_values_decimal_units_and_currencies(self):
        item=validate_item({'name':'M4 bolts'})
        self.assertIsNone(item['unitPrice'])
        items={'a':item};stock=validate_stock(dict(itemId='a',tracking='exact',quantity=None),items,{})
        self.assertIsNone(stock['quantity']);self.assertIsNone(estimated_value(item,stock))
        item.update(unitPrice='0.105',priceUnit='each',currency='USD');stock['quantity']='3'
        self.assertEqual(estimated_value(item,stock),dict(amount='0.32',currency='USD'))
        item['currency']='JPY';self.assertEqual(estimated_value(item,stock)['amount'],'0')
        stock['unit']='pack';self.assertIsNone(estimated_value(item,stock))
        for qty in ('-1','NaN','1e6',True):
            with self.assertRaises(ValueError):validate_stock(dict(itemId='a',tracking='exact',quantity=qty),items,{})

if __name__ == '__main__':
    unittest.main()
