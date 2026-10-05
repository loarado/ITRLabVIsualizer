import unittest
from inventory import bin_display_name

class EmptyBins(unittest.TestCase):
    def test_visual_style_is_not_content(self):
        bin=dict(id='b',name='New bin',w=9,h=2,background='#ffaa00',offsetX=.5,bold=True)
        self.assertEqual(bin_display_name(bin,'s',{'stocks':{}}),'empty')
        for name in ['A new bin of tools','New bin 2','Hardware']:
            self.assertEqual(bin_display_name(dict(bin,name=name),'s',{'stocks':{}}),name)
        for metadata in [dict(contents='pending'),dict(notes='description'),dict(hasLegacyDescription=True)]:
            self.assertEqual(bin_display_name(dict(bin,**metadata),'s',{'stocks':{}}),'New bin')
        stock=dict(shelfId='s',binId='b',archived=False)
        self.assertEqual(bin_display_name(bin,'s',{'stocks':{'one':stock}}),'New bin')
        self.assertEqual(bin_display_name(bin,'s',{'stocks':{'one':dict(stock,archived=True)}}),'empty')
