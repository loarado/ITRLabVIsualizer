import unittest
from browser_features import Features

class DoorLabels(Features):
    def test_whole_word_labels(self):
        p=self.page
        p.evaluate("()=>{lab.data.items=[{...defaults(),id:'a',kind:'table',name:'Table',x:10,y:10,w:2,h:2,locked:false},{...defaults(),id:'b',kind:'table',name:'Metal work table',x:20,y:10,w:4,h:3,locked:false},{...defaults(),id:'c',kind:'shelf',name:'Hardware shelf',x:30,y:10,w:1,h:6,locked:false},{...defaults(),id:'d',kind:'misc',shape:'circle',showLabel:true,name:'Extinguisher',x:40,y:10,w:3,h:3,locked:false}];render();}")
        p.wait_for_timeout(100)
        for width in (1440,390):
            p.set_viewport_size({'width':width,'height':900})
            for zoom in (.75,1,2):
                p.evaluate('(z)=>setZoom(z)',zoom);p.wait_for_timeout(100)
                result=p.locator('#plan .fit-label').evaluate_all("labels=>labels.map(label=>({fits:label.querySelector('.label-text').scrollHeight<=label.clientHeight&&label.querySelector('.label-text').scrollWidth<=label.clientWidth,words:[...label.querySelectorAll('.label-word')].map(word=>{const range=document.createRange();range.selectNodeContents(word);return range.getClientRects().length;})}))")
                for label in result:self.assertTrue(label['fits'],label);self.assertTrue(all(lines==1 for lines in label['words']),label)
        p.set_viewport_size({'width':1440,'height':1000});p.evaluate('setZoom(1)');p.wait_for_timeout(100)
        self.assertLess(p.locator('[data-id="a"] .fit-label').evaluate('(e)=>parseFloat(getComputedStyle(e).fontSize)'),14)
        # Both shelf views use the same fitter, including fractional bins.
        p.evaluate("()=>{const host=document.createElement('div');host.id='label-test';document.body.append(host);const data={rows:2,cols:3,matrix:[[{...defaults(),name:'Table',contents:'',keywords:'',w:1.5,h:1.5},null,null],[null,null,null]]};readOnlyShelfGrid(host,data);}")
        p.wait_for_timeout(100);self.assertTrue(p.locator('#label-test .fit-label').evaluate('(e)=>e.querySelector(".label-text").scrollWidth<=e.clientWidth'))

    def test_door_contact(self):
        self.login();p=self.page
        for direction in ('NW','NE','SW','SE'):
            for rect,blocked in [([-2,0,2,2],False),([0,-2,2,2],False),([4,0,2,2],False),([3,4,1,1],False),([1,1,2,2],True),([-1,1,2,2],True),([0,0,1,1],True)]:
                radius=5 if rect==[3,4,1,1] else 4
                result=p.evaluate("([orientation,r,rect])=>{const d={x:20,y:20,radius:r,orientation},[sx,sy]=doorSigns(d),[x,y,w,h]=rect;return doorIntersectsRectangle(d,{x:20+(sx>0?x:-x-w),y:20+(sy>0?y:-y-h),w,h});}",[direction,radius,rect]);self.assertEqual(result,blocked,(direction,rect))
        p.evaluate("()=>{lab.data.items=[{...defaults(),id:'table',kind:'table',name:'Table',x:10,y:20,w:2,h:2,locked:false}];lab.data.outline=[[0,0],[100,0],[100,48],[0,48]];lab.data.walls=[];lab.data.doors=[{id:'door',x:20,y:20,radius:4,orientation:'SE'}];render();}")
        for x,y,expected in [(19,21,[19,21]),(20,21,[19,21]),(25,21,[25,21])]:
            item=p.evaluate('clone(lab.data.items[0])');el=p.locator('[data-id="table"]');el.scroll_into_view_if_needed();box=el.bounding_box();rect=p.locator('#plan').bounding_box();sx=box['x']+box['width']/2;sy=box['y']+box['height']/2;p.mouse.move(sx,sy);p.mouse.down();p.mouse.move(sx+(x-item['x'])*rect['width']/100,sy+(y-item['y'])*rect['height']/48);p.mouse.up();self.assertEqual(p.evaluate('[selected().x,selected().y]'),expected)
        self.save('Touching door');p.reload();p.wait_for_function('typeof lab!=="undefined" && lab.data!==null');self.assertEqual(p.evaluate('lab.data.items[0].x'),25)

if __name__=='__main__':unittest.main()
