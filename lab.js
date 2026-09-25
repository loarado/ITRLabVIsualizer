'use strict';
let selectedId=null, zoom=1, shelfIndex={}, indexRequest=0;
const lab={data:null,endpoint:'/api/lab',filename:'lab.json',render,onAuthChanged:refreshShelfIndex,onInventoryChanged:refreshShelfIndex};
const plan=$('#plan');
const colors={section:'#e3f1fa',shelf:'#fff4d8',table:'#f0f8fd',cart:'#eff8e9',machine:'#fceeee',wall:'#334155',text:'#ffffff',misc:'#dc4545'};
function itemVisible(item){return item.kind==='section'?$('#sectionsVisible').checked:$('#'+item.kind+'Visible')?.checked!==false;}
function selected(){return lab.data?.items.find(item=>item.id===selectedId);}
function inside(x,y){
  const points=lab.data.outline;let result=false;
  for(let i=0,j=points.length-1;i<points.length;j=i++){
    const [xi,yi]=points[i],[xj,yj]=points[j];
    if((yi>y)!==(yj>y)&&x<(xj-xi)*(y-yi)/(yj-yi)+xi)result=!result;
  }return result;
}
function validPosition(item){
  const d=lab.data;
  if(!['x','y','w','h'].every(k=>Number.isInteger(item[k])&&item[k]>=1)||item.x+item.w-1>d.cols||item.y+item.h-1>d.rows)return false;
  if(item.kind==='section'||item.kind==='misc')return true;
  for(let y=item.y-1;y<item.y+item.h-1;y++)for(let x=item.x-1;x<item.x+item.w-1;x++)if(!inside(x+.5,y+.5))return false;
  return clearOfMapGeometry(item,d)&&!d.items.some(other=>other.id!==item.id&&!['section','misc'].includes(other.kind)&&overlaps(item,other));
}
function choose(id){const target=lab.data.items.find(i=>i.id===id);if(!isAdmin&&target?.kind==='shelf'){inspectShelf(target);return;}if(!isAdmin&&target?.kind==='section'){inspectSection(target);return;}if(!isAdmin&&target){inspectItem(target);return;}if(isAdmin&&!canEditItem(target)||target?.kind==='section'&&!canEditMap())return;selectedGeometry=null;selectedVertex=null;selectedRoute=null;selectedId=id;render();}
function svgElement(tag,attributes){const el=document.createElementNS('http://www.w3.org/2000/svg',tag);Object.entries(attributes).forEach(([k,v])=>el.setAttribute(k,v));return el;}
function drawStructure(){
  const d=lab.data,svg=svgElement('svg',{viewBox:`0 0 ${d.cols} ${d.rows}`,preserveAspectRatio:'none',class:'outline','aria-hidden':'true'});
  svg.append(svgElement('polygon',{points:d.outline.map(p=>p.join(',')).join(' '),fill:'none',stroke:'#293b46','stroke-width':'.25','stroke-linejoin':'round'}));plan.append(svg);
  drawRoutes();renderVertices();renderMapElements();
}
// Find an unoccupied rectangle for each section's label; never layer it under furniture.
function labelSpace(section,blockers){
  const heights=Array(section.w).fill(0);let best=null,score=0;
  for(let y=section.y;y<section.y+section.h;y++){
    for(let c=0;c<section.w;c++){
      const cell={x:section.x+c,y,w:1,h:1};
      heights[c]=blockers.some(b=>overlaps(cell,b))?0:heights[c]+1;
    }
    for(let left=0;left<section.w;left++){
      let height=Infinity;
      for(let right=left;right<section.w;right++){
        height=Math.min(height,heights[right]);if(!height)break;
        const width=right-left+1;
        // Favor readable horizontal labels over tall narrow slivers.
        const value=width*Math.min(height,4)*(width>=4?1:.2);
        if(value>score){score=value;best={x:section.x+left,y:y-height+1,w:width,h:height};}
      }
    }
  }return best;
}
function renderPlan(){
  if(!lab.data)return;
  plan.replaceChildren();plan.style.setProperty('--cols',lab.data.cols);plan.style.setProperty('--rows',lab.data.rows);plan.style.aspectRatio=`${lab.data.cols}/${lab.data.rows}`;
  const blockers=lab.data.items.filter(i=>i.kind!=='section').map(i=>({...i}));
  lab.data.items.filter(i=>i.kind==='section'&&$('#sectionsVisible').checked).forEach(item=>{
    const el=document.createElement('div');el.className='grid-item section'+(item.restricted?' restricted':'')+(item.id===selectedId?' selected':'');el.style.backgroundColor=item.background;el.dataset.sectionId=item.id;gridPosition(el,item);if(!isAdmin||canEditMap()){el.style.pointerEvents='auto';el.tabIndex=0;el.setAttribute('role','button');el.setAttribute('aria-label',item.name);el.addEventListener('click',()=>choose(item.id));el.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();choose(item.id);}});}plan.append(el);
    if(item.showLabel&&item.name){
      const space=labelSpace(item,blockers);
      if(space){const label=document.createElement('div');label.className='section-label';gridPosition(label,space);label.append(labelFor(item));
        if(!isAdmin){label.style.pointerEvents='auto';label.style.cursor='pointer';label.addEventListener('click',()=>inspectSection(item));}
        if(canEditItem(item)&&!item.locked){label.style.pointerEvents='auto';label.style.cursor='grab';label.style.touchAction='none';label.tabIndex=0;label.setAttribute('role','button');label.setAttribute('aria-label',item.name);label.addEventListener('click',()=>choose(item.id));bindDrag(label,item);}
        plan.append(label);blockers.push(space);
      }
    }
  });
  drawStructure();
  lab.data.items.filter(i=>i.kind!=='section'&&itemVisible(i)).forEach(item=>{
    const el=document.createElement('button');el.className='grid-item '+(item.kind==='shelf'?'shelf':'')+(item.id===selectedId?' selected':'')+(canEditItem(item)&&!item.locked?' editable':'');el.dataset.id=item.id;el.style.backgroundColor=item.background;el.style.setProperty('--bg',item.background);el.title=`${item.name} · ${item.id}`;el.setAttribute('aria-label',el.title);el.setAttribute('aria-pressed',item.id===selectedId);gridPosition(el,item);if(item.kind==='misc')renderMisc(el,item);else el.append(labelFor(item));el.addEventListener('click',()=>choose(item.id));bindDrag(el,item);plan.append(el);
  });
  requestAnimationFrame(()=>fitLabels(plan));
}
function bindDrag(element,item){
  element.addEventListener('pointerdown',event=>{
    if(!canEditItem(item)||item.locked||event.button!==0)return;
    const rect=plan.getBoundingClientRect(),startX=event.clientX,startY=event.clientY;
    let candidate={...item},moved=false;
    element.setPointerCapture(event.pointerId);
    const move=e=>{
      const dx=Math.round((e.clientX-startX)/rect.width*lab.data.cols),dy=Math.round((e.clientY-startY)/rect.height*lab.data.rows);
      if(dx||dy)moved=true;
      candidate={...item,x:item.x+dx,y:item.y+dy};
      element.classList.add('dragging');element.style.transform=`translate(${dx*rect.width/lab.data.cols}px,${dy*rect.height/lab.data.rows}px)`;element.classList.toggle('invalid-drop',!validPosition(candidate));
    };
    const end=e=>{
      element.removeEventListener('pointermove',move);element.removeEventListener('pointerup',end);element.removeEventListener('pointercancel',cancel);
      if(moved&&validPosition(candidate)){checkpoint();Object.assign(item,candidate);changed();}
      else if(moved)message('Position blocked: keep items inside the lab and clear of equipment, walls, and door swings.',true);
      selectedGeometry=null;selectedVertex=null;selectedRoute=null;selectedId=item.id;render();
    };
    const cancel=()=>{element.removeEventListener('pointermove',move);element.removeEventListener('pointerup',end);element.removeEventListener('pointercancel',cancel);render();};
    element.addEventListener('pointermove',move);element.addEventListener('pointerup',end);element.addEventListener('pointercancel',cancel);
  });
}
const fields=['name','x','y','w','h','background','color','fontSize','fontFamily','bold','locked','showLabel','restricted','shape','lineDirection','lineWidth'];
function renderDetails(){
  const item=selected();$('#empty').hidden=!!item;$('#details').hidden=!item;
  $('#empty').textContent=mapEditing?'Select an outline point, section, or arrow to edit the map.':'Choose an item on the plan or in the directory.';
  if(mapEditing&&selectedVertex!==null)$('#empty').hidden=true;
  if(!item)return;
  $('#area').value=itemArea(item,lab.data);
  $('#selectionId').textContent=`${item.id} / ${item.kind}`;$('#selectionTitle').textContent=item.name;
  fields.forEach(key=>{const input=$('#'+key);if(input.type==='checkbox')input.checked=!!item[key];else input.value=item[key]??'';input.disabled=!isAdmin||(['x','y','w','h'].includes(key)&&item.locked);});
  $('#miscFields').hidden=item.kind!=='misc';$('#miscLineFields').hidden=item.shape!=='line';$('#labelVisibility').hidden=!['section','misc'].includes(item.kind);
  if(item.kind==='misc'){$('#shape').value=item.shape||'square';$('#showLabel').checked=item.showLabel!==false;$('#lineDirection').value=item.lineDirection||'horizontal';$('#lineWidth').value=item.lineWidth??4;}
  $('#sectionFields').hidden=item.kind!=='section';$('#openShelf').hidden=item.kind!=='shelf';$('#shelfFile').hidden=item.kind!=='shelf';
  $('#openShelf').href=`shelf_editor.html?id=${encodeURIComponent(item.id)}`;$('#shelfFile').textContent=`File: data/shelves/${item.id}.json`;
  $('#delete').disabled=!isAdmin||item.locked;
}
function renderDirectory(){
  const query=$('#search').value.toLowerCase().trim(),kind=$('#filter').value;
  const items=lab.data.items.filter(i=>i.kind!=='section'&&(!kind||i.kind===kind)&&`${i.id} ${i.name} ${itemArea(i,lab.data)} ${shelfIndex[i.id]?.searchText??''}`.toLowerCase().includes(query));
  $('#directory').replaceChildren();
  const categories={shelf:'Shelves & storage',table:'Tables',cart:'Carts & seating',machine:'Machines & tools',wall:'Walls',text:'Labels',section:'Sections',misc:'Misc items'};
  Object.entries(categories).forEach(([type,title])=>{
    const members=items.filter(i=>i.kind===type);if(!members.length)return;
    const list=document.createElement('div');list.className='category-items';
    members.forEach(item=>{const b=document.createElement('button');b.className='directory-item'+(item.id===selectedId?' active':'');b.dataset.itemId=item.id;b.textContent=item.name;const sub=document.createElement('small');sub.textContent=`${item.id}${item.locked?' · locked':''}`;b.append(sub);b.addEventListener('click',()=>{choose(item.id);plan.querySelector(`[data-id="${item.id}"]`)?.scrollIntoView({block:'nearest',inline:'nearest'});});list.append(b);});
    $('#directory').append(editorGroup('items-'+type,`${title} (${members.length})`,list,!!query));
  });
  $('#mapSectionsDirectory').replaceChildren();
  lab.data.items.filter(i=>i.kind==='section').forEach(item=>{const button=document.createElement('button');button.textContent=item.name;button.dataset.sectionId=item.id;button.addEventListener('click',()=>choose(item.id));$('#mapSectionsDirectory').append(button);});
  renderExplorerResults(items,query);
  if(!items.length)$('#directory').textContent='No matching items.';
  plan.querySelectorAll('[data-id]').forEach(el=>el.style.opacity=items.some(i=>i.id===el.dataset.id)?'1':'.2');
  $('#count').textContent=`${items.length} items · ${lab.data.cols} × ${lab.data.rows} grid`;
}
function render(){
  if(!lab.data)return;renderWorkspace();renderPlan();renderDetails();renderDirectory();renderRouteTools();
  $('#cols').value=lab.data.cols;$('#rows').value=lab.data.rows;$('#outline').value=lab.data.outline.map(p=>p.join(', ')).join('\n');
  ['cols','rows','outline','applyOutline'].forEach(id=>$('#'+id).disabled=!canEditMap());
}
fields.forEach(key=>$('#'+key).addEventListener('change',()=>{
  const item=selected();if(!canEditItem(item))return;
  const input=$('#'+key),value=input.type==='checkbox'?input.checked:input.type==='number'?Number(input.value):input.value;
  const candidate={...item,[key]:value};
  if(['x','y','w','h'].includes(key)&&(item.locked||!validPosition(candidate))){message('That position or size is blocked. Unlock the item and keep it within the lab, clear of other equipment.',true);renderDetails();return;}
  if(key==='lineWidth'&&(!Number.isInteger(value)||value<1||value>20)){message('Line thickness must be 1–20 pixels.',true);renderDetails();return;}
  if(key==='fontSize'&&(!Number.isInteger(value)||value<6||value>96)){message('Font size must be 6–96 pixels.',true);renderDetails();return;}
  checkpoint();Object.assign(item,candidate);render();changed();
}));
$('#openShelf').addEventListener('click',async event=>{event.preventDefault();const target=event.currentTarget.href;await leaveEditor(target);});
$('#delete').addEventListener('click',()=>{const item=selected();if(!canEditItem(item)||item.locked)return;checkpoint();lab.data.items=lab.data.items.filter(i=>i.id!==item.id);selectedId=null;render();changed();});
function addLabItem(kind){
  if(kind==='section'?!canEditMap():!isAdmin||mapEditing)return;
  if(lab.data.items.length>=1000){message('The lab supports up to 1,000 items.',true);return;}
  const item={...defaults(),id:`${kind[0].toUpperCase()}-${Array.from(crypto.getRandomValues(new Uint8Array(4)),n=>n.toString(16).padStart(2,'0')).join('')}`,name:kind==='section'?'New section':`New ${kind}`,kind,x:1,y:1,w:kind==='section'?10:4,h:kind==='section'?6:3,background:colors[kind],color:'#233748',locked:false};
  if(kind==='misc'){Object.assign(item,{shape:'square',showLabel:true,lineDirection:'horizontal',lineWidth:4,w:2,h:2,x:Math.max(1,Math.floor(lab.data.cols/2)),y:Math.max(1,Math.floor(lab.data.rows/2)),color:'#ffffff'});}
  else if(kind==='section'){item.showLabel=true;item.restricted=false;item.fontSize=18;item.x=35;item.y=20;}
  else {let found=false;for(let y=1;y<=lab.data.rows-item.h+1&&!found;y++)for(let x=1;x<=lab.data.cols-item.w+1;x++){item.x=x;item.y=y;if(validPosition(item)){found=true;break;}}if(!found){message('No clear space for this item. Move or remove an item first.',true);return;}}
  checkpoint();lab.data.items.push(item);selectedGeometry=null;selectedVertex=null;selectedRoute=null;selectedId=item.id;render();changed();
}
$('#add').addEventListener('click',()=>addLabItem($('#newKind').value));
$('#addSection').addEventListener('click',()=>addLabItem('section'));
$('#applyOutline').addEventListener('click',()=>{
  if(!canEditMap())return;
  const cols=Number($('#cols').value),rows=Number($('#rows').value),outline=$('#outline').value.trim().split('\n').map(line=>line.split(',').map(v=>Number(v.trim())));
  if(!Number.isInteger(cols)||!Number.isInteger(rows)||cols<10||cols>200||rows<10||rows>200||!validOutline(outline,cols,rows)||lab.data.items.some(i=>i.x+i.w-1>cols||i.y+i.h-1>rows)||lab.data.routes.some(route=>route.some(p=>p[0]>cols||p[1]>rows))||(lab.data.walls||[]).some(w=>!validWall(w,cols,rows))||(lab.data.doors||[]).some(d=>!validDoor(d,cols,rows))){message('Invalid map outline. Use at least 3 x,y points and a grid large enough for all items and paths.',true);return;}
  checkpoint();Object.assign(lab.data,{cols,rows,outline});render();changed();
});
$('#search').addEventListener('input',()=>lab.data&&renderDirectory());$('#filter').addEventListener('change',()=>lab.data&&renderDirectory());$('#routes').addEventListener('change',renderPlan);
function setZoom(value){zoom=Math.min(3,Math.max(.75,value));plan.style.minWidth=`${1000*Math.min(1,zoom)}px`;plan.style.width=`${zoom*100}%`;$('#zoomOut').disabled=zoom===.75;$('#zoomIn').disabled=zoom===3;requestAnimationFrame(()=>fitLabels(plan));}
$('#zoomIn').addEventListener('click',()=>setZoom(zoom+.25));$('#zoomOut').addEventListener('click',()=>setZoom(zoom-.25));$('#fit').addEventListener('click',()=>{setZoom(1);$('#viewport').scrollTo(0,0);});
document.addEventListener('keydown',event=>{
  if(document.activeElement.isContentEditable||event.defaultPrevented||document.querySelector('dialog[open]')||!isAdmin||event.ctrlKey||event.metaKey||['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName))return;
  const item=selected(),delta={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]}[event.key];
  if(delta&&selectedRoute!==null){event.preventDefault();moveRoute(delta[0],delta[1]);return;}
  if(!canEditItem(item)||item.locked||!delta)return;event.preventDefault();const candidate={...item,x:item.x+delta[0],y:item.y+delta[1]};
  if(validPosition(candidate)){checkpoint();Object.assign(item,candidate);render();changed();}else message('That grid position is blocked.',true);
});
[['addPanel','Add to Lab'],['details','Properties'],['routeDetails','Arrow properties'],['pathsPanel','Traffic arrows'],['directoryPanel','Item Directory'],['sectionsPanel','Sections'],['outlinePanel','Outline & grid'],['mapPanel','Lab Map Editor']].forEach(([id,title])=>mountEditorGroup(id,title));
new ResizeObserver(()=>fitLabels(plan)).observe(plan);setZoom(1);startApp(lab);

$('#sectionsVisible').addEventListener('change',renderPlan);

async function refreshShelfIndex(){closeExplorer(true);const ticket=++indexRequest,admin=isAdmin;try{const result=await api('/api/shelf-index');if(ticket!==indexRequest||admin!==isAdmin)return;shelfIndex=result;if(lab.data)renderDirectory();}catch(error){if(ticket===indexRequest)message(error.message,true);}}

let itemClipboard=null;
lab.clipboardContext=()=>!mapEditing&&!!selected()&&!['section','wall'].includes(selected().kind);
lab.copySelection=async()=>{
  const item=clone(selected());let inventory=null;
  if(item.kind==='shelf'){
    const draft=await api('/api/drafts/shelves/'+encodeURIComponent(item.id));
    inventory=clone(draft?.data??await api('/api/shelves/'+encodeURIComponent(item.id)));
  }
  if(!isAdmin||mapEditing)return;
  itemClipboard={item,inventory};message('Item copied · Ctrl/Cmd+V to paste');
};
lab.pasteSelection=async()=>{
  if(!isAdmin||mapEditing||!itemClipboard)return;
  if(lab.data.items.length>=1000){message('The lab supports up to 1,000 items.',true);return;}
  const {item:source,inventory}=itemClipboard,item={...clone(source),id:source.kind[0].toUpperCase()+'-'+uniqueId()};
  const position=nearbyPositions(source.x,source.y,source.w,source.h,lab.data.cols,lab.data.rows,1,1).find(p=>validPosition({...item,...p}));
  if(!position){message('No valid space for the copied item.',true);return;}
  Object.assign(item,position);delete item.area;
  if(inventory){
    const data={...clone(inventory),id:item.id,revision:0};delete data.versionName;
    await api('/api/drafts/shelves/'+item.id,'PUT',{data,history:[],future:[],dirty:true});
    if(!isAdmin||mapEditing||!validPosition(item))return;
  }
  checkpoint();lab.data.items.push(item);selectedId=item.id;selectedRoute=null;selectedVertex=null;render();changed();await cacheDraft();await refreshShelfIndex();
};

document.querySelectorAll('[data-category],#sectionsVisible').forEach(input=>input.addEventListener('change',()=>{if(selected()&&!itemVisible(selected()))selectedId=null;render();}));

lab.hasUnsavedChildren=()=>Object.values(shelfIndex).some(s=>s.draftDirty);

lab.onSaved=refreshShelfIndex;
lab.clearClipboard=()=>{itemClipboard=null;selectedId=null;};

// The marker's artwork is independent of its grid hit target and text label.
function renderMisc(el,item){
  el.classList.add('misc-item');el.dataset.shape=item.shape||'square';el.style.backgroundColor='transparent';el.style.setProperty('--bg','transparent');
  const svg=svgElement('svg',{viewBox:'0 0 100 100',preserveAspectRatio:item.shape==='line'?'none':'xMidYMid meet',class:'misc-art','aria-hidden':'true'});
  let art;
  if(item.shape==='circle')art=svgElement('circle',{cx:50,cy:50,r:48});
  else if(item.shape==='triangle')art=svgElement('polygon',{points:'50,2 98,98 2,98'});
  else if(item.shape==='line'){
    const coords={horizontal:[3,50,97,50],vertical:[50,3,50,97],'diagonal-down':[3,3,97,97],'diagonal-up':[3,97,97,3]}[item.lineDirection||'horizontal'];
    art=svgElement('line',{x1:coords[0],y1:coords[1],x2:coords[2],y2:coords[3],stroke:item.background,'stroke-width':item.lineWidth??4,'stroke-linecap':'round','vector-effect':'non-scaling-stroke'});
  }else art=svgElement('rect',{x:2,y:2,width:96,height:96});
  art.setAttribute('fill',item.background);svg.append(art);el.append(svg);
  if(item.showLabel!==false)el.append(labelFor(item));
}
