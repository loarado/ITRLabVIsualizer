"""Centering acceptance test against a disposable expanded lab."""
import unittest
from browser_features import Features
from playwright.sync_api import expect

class Centering(Features):
    def test_center_expanded_lab(self):
        p=self.page;self.login()
        p.evaluate("()=>{lab.data.cols=115;lab.data.rows=60;lab.data.walls=[{id:'wall',a:[40,24],b:[50,24],thickness:.3}];lab.data.doors=[{id:'door',x:50,y:24,radius:3,orientation:'NE'}];render();}")
        before=p.evaluate('clone(lab.data)');p.locator('#mapMode').click();p.locator('#centerLab').click();after=p.evaluate('clone(lab.data)')
        dx=after['outline'][0][0]-before['outline'][0][0];dy=after['outline'][0][1]-before['outline'][0][1]
        self.assertGreater(dx,0);self.assertGreater(dy,0)
        for axis,size in [(0,115),(1,60)]:
            coords=[point[axis] for point in after['outline']];self.assertLessEqual(abs(min(coords)-(size-max(coords))),1)
        for old,new in zip(before['items'],after['items']):
            self.assertEqual(new,{**old,'x':old['x']+dx,'y':old['y']+dy})
        for old,new in zip(before['routes'],after['routes']):self.assertEqual(new,[[x+dx,y+dy] for x,y in old])
        self.assertEqual(after['walls'][0]['a'],[40+dx,24+dy]);self.assertEqual(after['doors'][0]['x'],50+dx)
        p.locator('#centerLab').click();self.assertEqual(p.evaluate('clone(lab.data)'),after)
        p.locator('#undo').click();self.assertEqual(p.evaluate('clone(lab.data)'),before);p.locator('#redo').click();self.assertEqual(p.evaluate('clone(lab.data)'),after)
        self.save('Centered expanded lab');p.reload();p.wait_for_function('typeof lab!=="undefined" && lab.data!==null');self.assertEqual(p.evaluate('lab.data.outline'),after['outline'])
        unchanged=p.evaluate('JSON.stringify(lab.data)');p.evaluate('centerLab()');self.assertEqual(p.evaluate('JSON.stringify(lab.data)'),unchanged)
        p.locator('#auth').click();p.wait_for_function('!isAdmin');expect(p.locator('#centerLab')).to_be_hidden();p.evaluate('centerLab()');self.assertEqual(p.evaluate('JSON.stringify(lab.data)'),unchanged)
        # Outlying elements constrain the shift rather than getting clipped.
        self.assertEqual(p.evaluate("()=>{const d=clone(lab.data);d.items[0].x=115-d.items[0].w+1;return centeredLab(d).dx;}"),0)

if __name__=='__main__':unittest.main()
