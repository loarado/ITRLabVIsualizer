import json, unittest
from browser_features import Features
from playwright.sync_api import expect

class Misc(Features):
    def test_misc_markers(self):
        self.login();p=self.page;p.locator('#newKind').select_option('misc');p.locator('#add').click();sid=p.evaluate('selectedId');el=p.locator(f'[data-id="{sid}"]')
        expect(p.locator('#miscFields')).to_be_visible();expect(p.locator('#labelVisibility')).to_be_visible()
        p.locator('#name').fill('Fire extinguisher');p.locator('#name').press('Tab')
        for shape,tag in [('square','rect'),('triangle','polygon'),('circle','circle'),('line','line')]:
            p.locator('#shape').select_option(shape);expect(el.locator('.misc-art '+tag)).to_have_count(1)
        p.locator('#lineDirection').select_option('diagonal-up');p.locator('#lineWidth').fill('8');p.locator('#lineWidth').press('Tab');expect(el.locator('line')).to_have_attribute('stroke-width','8')
        p.locator('#background').fill('#ff0000');p.locator('#background').dispatch_event('change');expect(el.locator('line')).to_have_attribute('stroke','#ff0000')
        p.locator('#showLabel').uncheck();expect(el.locator('.fit-label')).to_have_count(0);p.locator('#showLabel').check();expect(el.locator('.fit-label')).to_have_text('Fire extinguisher')
        # Outside the footprint, and then directly on top of an existing item.
        for key,val in [('x','1'),('y','1'),('w','3'),('h','3')]:p.locator('#'+key).fill(val);p.locator('#'+key).press('Tab')
        self.assertEqual(p.evaluate('[selected().x,selected().y]'),[1,1]);self.assertTrue(p.evaluate('validPosition(selected())'))
        el.scroll_into_view_if_needed();box=el.bounding_box();plan=p.locator('#plan').bounding_box();sx=box['x']+box['width']/2;sy=box['y']+box['height']/2;p.mouse.move(sx,sy);p.mouse.down();p.mouse.move(sx+plan['width']/100*2,sy);p.mouse.up();self.assertEqual(p.evaluate('selected().x'),3)
        p.evaluate("()=>{const m=selected(),t=lab.data.items.find(i=>i.kind==='table');Object.assign(m,{x:t.x,y:t.y,w:t.w,h:t.h});lab.data.walls=[{id:'wall',a:[t.x,t.y],b:[t.x+1,t.y+1],thickness:.3}];lab.data.doors=[{id:'door',x:t.x,y:t.y,radius:1,orientation:'SE'}];render();}")
        self.assertTrue(p.evaluate('validPosition(selected())'))
        self.assertTrue(p.evaluate("()=>{const original=lab.data,m=selected();lab.data={...original,outline:[[0,0],[100,0],[100,48],[0,48]],walls:[],doors:[],items:[{...m,id:'equipment',kind:'table'},m]};const valid=validPosition(lab.data.items[0]);lab.data=original;return valid;}"))
        p.locator('#shape').select_option('circle');p.locator('#showLabel').uncheck();el.focus();p.keyboard.press('Control+c');p.keyboard.press('Control+v');p.wait_for_function('(id)=>selectedId!==id',arg=sid);copyid=p.evaluate('selectedId');self.assertEqual(p.evaluate('selected().shape'),'circle');self.assertFalse(p.evaluate('selected().showLabel'))
        p.locator('#undo').click();expect(p.locator(f'[data-id="{copyid}"]')).to_have_count(0);p.locator('#redo').click();expect(p.locator(f'[data-id="{copyid}"]')).to_have_count(1)
        p.locator('#miscVisible').uncheck();expect(p.locator('.misc-item')).to_have_count(0);p.locator('#miscVisible').check();expect(p.locator('.misc-item')).to_have_count(2)
        self.save('Safety markers');p.reload();p.wait_for_function('typeof lab!=="undefined" && lab.data!==null');p.locator('#auth').click();p.wait_for_function('!isAdmin');el=p.locator(f'[data-id="{sid}"]');expect(el.locator('circle')).to_have_count(1);expect(el.locator('.fit-label')).to_have_count(0);el.click();expect(p.locator('#explorerContent')).to_contain_text('Fire extinguisher');expect(p.locator('#miscFields')).to_be_hidden()
        saved=json.loads((self.data/'lab.json').read_text());self.assertEqual(len([i for i in saved['items'] if i['kind']=='misc']),2)

if __name__=='__main__':unittest.main()
