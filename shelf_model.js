'use strict';
function normalizeShelf(data,fallbackName=''){
  const hasBins=data.matrix?.some(row=>row.some(cell=>cell!==null));
  return {...data,schemaVersion:data.schemaVersion??2,mode:data.mode??(hasBins?'complex':'simple'),name:data.name??fallbackName,contents:data.contents??'',keywords:data.keywords??''};
}

function shelfBins(data){const result=[];data.matrix.forEach((row,r)=>row.forEach((bin,c)=>{if(bin)result.push({bin,r:r+(bin.offsetY||0),c:c+(bin.offsetX||0)});}));return result;}
function configureShelfGrid(grid,data,size=22){grid.style.setProperty('--cols',data.cols*2);grid.style.setProperty('--rows',data.rows*2);grid.style.setProperty('--cell',size+'px');}
function positionShelfBin(el,bin,r,c){gridPosition(el,{x:c*2+1,y:r*2+1,w:bin.w*2,h:bin.h*2});}
function readOnlyShelfGrid(host,data){
  const viewport=document.createElement('div');viewport.className='viewport readonly-shelf-viewport';
  const grid=document.createElement('div');grid.className='shelf-grid readonly-grid';grid.setAttribute('aria-label','Read-only shelf inventory matrix');configureShelfGrid(grid,data);
  const tooltip=document.createElement('div');tooltip.className='bin-tooltip';tooltip.id='bin-tip-'+uniqueId();tooltip.setAttribute('role','tooltip');tooltip.hidden=true;
  const hide=()=>{tooltip.hidden=true;};
  shelfBins(data).forEach(({bin,r,c})=>{
    const el=document.createElement('button');el.className='grid-item shelf-bin readonly-bin';positionShelfBin(el,bin,r,c);el.style.backgroundColor=bin.background;el.style.setProperty('--bg',bin.background);el.append(labelFor(bin));el.setAttribute('aria-label',`${bin.name||'Unnamed bin'}, row ${r+1}, column ${c+1}`);el.setAttribute('aria-describedby',tooltip.id);
    const show=()=>{tooltip.replaceChildren(infoField(bin.name||'Unnamed bin',bin.contents),infoField('Keywords',bin.keywords));tooltip.hidden=false;const rect=el.getBoundingClientRect();tooltip.style.left=Math.max(8,Math.min(rect.left,window.innerWidth-tooltip.offsetWidth-8))+'px';tooltip.style.top=Math.max(8,Math.min(rect.bottom+6,window.innerHeight-tooltip.offsetHeight-8))+'px';};
    el.addEventListener('mouseenter',show);el.addEventListener('focus',show);el.addEventListener('mouseleave',hide);el.addEventListener('blur',hide);el.addEventListener('keydown',e=>{if(e.key==='Escape')hide();});grid.append(el);
  });
  viewport.addEventListener('scroll',()=>{const hovered=grid.querySelector('.readonly-bin:hover');if(hovered)hovered.dispatchEvent(new Event('mouseenter'));else hide();});const stage=document.createElement('div');stage.className='readonly-shelf-stage';stage.append(grid);viewport.append(stage);
  const controls=document.createElement('div');controls.className='toolbar shelf-view-controls';controls.setAttribute('aria-label','Shelf zoom');
  const out=document.createElement('button'),inside=document.createElement('button'),fit=document.createElement('button'),level=document.createElement('output');
  out.textContent='−';out.setAttribute('aria-label','Zoom shelf out');inside.textContent='+';inside.setAttribute('aria-label','Zoom shelf in');fit.textContent='Fit shelf';level.setAttribute('aria-label','Shelf zoom level');
  controls.append(out,inside,fit,level);host.append(controls,viewport,tooltip);
  let scale=1,minimum=1,fitted=true;
  const apply=()=>{
    if(!grid.isConnected||!viewport.clientWidth)return;
    const style=getComputedStyle(viewport),width=viewport.clientWidth-parseFloat(style.paddingLeft)-parseFloat(style.paddingRight),height=viewport.clientHeight-parseFloat(style.paddingTop)-parseFloat(style.paddingBottom);
    minimum=Math.min(1,width/grid.offsetWidth,height/grid.offsetHeight);
    scale=fitted?minimum:Math.max(minimum,Math.min(3,scale));
    grid.style.transform=`scale(${scale})`;stage.style.width=grid.offsetWidth*scale+'px';stage.style.height=grid.offsetHeight*scale+'px';
    out.disabled=scale<=minimum+.0001;inside.disabled=scale>=3;level.textContent=Math.round(scale*100)+'%';hide();
  };
  const zoom=multiplier=>{fitted=false;scale*=multiplier;apply();};
  out.addEventListener('click',()=>zoom(1/1.25));inside.addEventListener('click',()=>zoom(1.25));fit.addEventListener('click',()=>{fitted=true;apply();viewport.scrollTo(0,0);});
  const observer=new ResizeObserver(()=>apply());observer.observe(viewport);
  host._disposeShelfGrid=()=>{observer.disconnect();hide();};
  requestAnimationFrame(()=>{fitLabels(grid);apply();});
}

// Matrix indices remain integers; optional offsets locate a bin on the half grid.
const halfStep=value=>Number.isFinite(value)&&Number.isInteger(value*2);
const snapHalf=value=>Math.round(value*2)/2;
function setShelfBin(data,r,c,bin){
  if(bin){bin={...bin};delete bin.offsetX;delete bin.offsetY;if(c%1)bin.offsetX=c%1;if(r%1)bin.offsetY=r%1;data.schemaVersion=3;}
  data.matrix[Math.floor(r)][Math.floor(c)]=bin;
}
function shelfBinFits(data,bin,r,c,ignore=null){
  if(![r,c,bin.w,bin.h].every(halfStep)||r<0||c<0||bin.w<1||bin.h<1||r+bin.h>data.rows||c+bin.w>data.cols)return false;
  return !shelfBins(data).some(p=>!(ignore&&p.r===ignore.r&&p.c===ignore.c)&&overlaps({x:c,y:r,w:bin.w,h:bin.h},{x:p.c,y:p.r,w:p.bin.w,h:p.bin.h}));
}
