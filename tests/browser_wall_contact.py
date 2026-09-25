"""Items can abut walls without crossing them or disappearing into thick walls."""
import json, unittest
from browser_features import Features

class WallContact(Features):
    def test_flush_wall_placement(self):
        self.login();p=self.page
        p.evaluate("()=>{lab.data.items=[{...defaults(),id:'table',kind:'table',name:'Table',x:10,y:15,w:2,h:2,locked:false}];lab.data.outline=[[0,0],[100,0],[100,48],[0,48]];lab.data.walls=[{id:'wall',a:[20,5],b:[20,40],thickness:.3}];lab.data.doors=[];render();}")
        for x,expected in [(19,True),(21,True),(20,False)]:self.assertEqual(p.evaluate('(x)=>validPosition({...lab.data.items[0],x})',x),expected)
        for rect,expected in [({'x':10,'y':18,'w':2,'h':2},False),({'x':10,'y':20,'w':2,'h':2},False),({'x':10,'y':19,'w':2,'h':2},True)]:
            self.assertEqual(p.evaluate('(r)=>wallIntersectsRectangle({a:[5,20],b:[40,20],thickness:.3},r)',rect),expected)
        self.assertFalse(p.evaluate('wallIntersectsRectangle({a:[1,1],b:[5,5],thickness:.3},{x:1,y:2,w:1,h:1})'))
        self.assertTrue(p.evaluate('wallIntersectsRectangle({a:[1,1],b:[5,5],thickness:.3},{x:2,y:2,w:1,h:1})'))
        self.assertTrue(p.evaluate('wallIntersectsRectangle({a:[20,5],b:[20,40],thickness:2},{x:20,y:15,w:1,h:2})'))
        self.assertFalse(p.evaluate('wallIntersectsRectangle({a:[20,5],b:[20,40],thickness:2},{x:21,y:15,w:1,h:2})'))
        self.assertTrue(p.evaluate('wallIntersectsRectangle({a:[20,15],b:[20,16],thickness:.3},{x:19,y:14,w:2,h:3})'))
        for x,expected in [(19,19),(20,19),(21,21)]:
            before=p.evaluate('lab.data.items[0].x');rect=p.locator('#plan').bounding_box();el=p.locator('[data-id="table"]');el.scroll_into_view_if_needed();box=el.bounding_box();sx=box['x']+box['width']/2;sy=box['y']+box['height']/2;p.mouse.move(sx,sy);p.mouse.down();p.mouse.move(sx+(x-before)*rect['width']/100,sy);p.mouse.up();self.assertEqual(p.evaluate('lab.data.items[0].x'),expected)
        p.locator('#x').fill('19');p.locator('#x').press('Tab');p.locator('[data-id="table"]').focus();p.keyboard.press('Control+c');p.keyboard.press('Control+v');p.wait_for_function('lab.data.items.length===2');self.assertEqual(p.evaluate('selected().x'),21)
        self.save('Flush wall placement');p.reload();p.wait_for_function('typeof lab!=="undefined" && lab.data!==null');self.assertEqual(p.evaluate('lab.data.items.map(i=>i.x)'),[19,21]);self.assertEqual(json.loads((self.data/'lab.json').read_text())['walls'][0]['a'],[20,5])

if __name__=='__main__':unittest.main()
