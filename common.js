'use strict';
const $ = selector => document.querySelector(selector);
const clone = value => JSON.parse(JSON.stringify(value));
let isAdmin = false;
let dirty = false;
let saving = false;
let generation = 0;
let saveTimer;
let savePromise;
let history = [];
let future = [];
let app;
async function api(path, method='GET', body) {
  const response = await fetch(path, {method, headers: {'X-Editor-Instance':editorInstance,...(body?{'Content-Type':'application/json'}:{})}, body: body ? JSON.stringify(body) : undefined});
  let result;
  try { result = await response.json(); } catch { throw new Error('Run this app with python3 server.py. The editor needs its save API.'); }
  if (!response.ok) { const error=new Error(result.error || `Request failed (${response.status}).`); error.status=response.status; throw error; }
  return result;
}
function message(text, error=false) { $('#status').textContent = text; $('#status').classList.toggle('error', error); }
function checkpoint() { history.push(clone(app.data)); if(history.length>40) history.shift(); future=[]; }
// Each tab keeps one editor-instance ID across navigation and refresh.
if(!/^itr-[a-f0-9]{32}$/.test(window.name))window.name='itr-'+Array.from(crypto.getRandomValues(new Uint8Array(16)),n=>n.toString(16).padStart(2,'0')).join('');
const editorInstance=window.name;
let cacheQueue=Promise.resolve(true), allowNavigation=false;
function changed() { dirty=true; generation++; message('Draft changed · not saved'); clearTimeout(saveTimer); saveTimer=setTimeout(()=>cacheDraft(),250); updateUndo(); }
function updateUndo() { $('#undo').disabled=!isAdmin||!history.length; $('#redo').disabled=!isAdmin||!future.length; }
async function cacheDraft() {
  clearTimeout(saveTimer);
  if(!isAdmin||!app?.data)return true;
  const state={data:clone(app.data),history:clone(history),future:clone(future),dirty};
  cacheQueue=cacheQueue.then(async()=>{
    try {const result=await api(app.endpoint.replace('/api/','/api/drafts/'),'PUT',state);if(result.inventoryChanged)await app.onInventoryChanged?.();return true;}
    catch(error){message('Draft is still in this page, but caching failed: '+error.message,true);return false;}
  });
  return cacheQueue;
}
async function leaveEditor(target) {
  if(!await cacheDraft())return;
  allowNavigation=true;location.href=target;
}
function requestVersionName(){
  $('#versionName').value='';$('#saveVersionDialog').showModal();$('#versionName').focus();
  return new Promise(resolve=>{
    const dialog=$('#saveVersionDialog');
    const close=()=>{dialog.removeEventListener('close',close);resolve(dialog.returnValue==='save'?$('#versionName').value.trim():null);};
    dialog.returnValue='';dialog.addEventListener('close',close);
  });
}
async function save(name) {
  if(!isAdmin||!app?.data){message('Sign in as admin to save this draft.',true);return false;}
  if(saving||$('#saveVersionDialog').open)return false;
  if(typeof name!=='string')name=await requestVersionName();
  if(!name)return false;
  const snapshot=clone(app.data), version=generation;snapshot.versionName=name;
  saving=true;message('Saving named version…');
  savePromise=(async()=>{try {
    if(!await cacheDraft())throw new Error('Save postponed because draft caching failed.');
    const result=await api(app.endpoint,'PUT',snapshot);
    app.data.revision=result.revision;app.data.versionName=name;
    if(version===generation)dirty=false;
    await cacheDraft();await app.onSaved?.();
    message(dirty?`Saved “${name}”; newer edits remain in your draft`:`Saved “${name}” · revision ${result.revision}`);
    return true;
  } catch(error) {if(error.status===403)setAuth(false);message(error.message,true);return false;} finally {saving=false;}})();
  return savePromise;
}
function undoEdit(redo=false){
  const source=redo?future:history,target=redo?history:future;
  if(!isAdmin||!source.length)return;
  target.push(clone(app.data));if(target.length>40)target.shift();
  const revision=app.data.revision;app.data=source.pop();app.data.revision=revision;app.render();changed();
}
async function recoverDraft(){
  const cached=await api(app.endpoint.replace('/api/','/api/drafts/'));
  if(cached){app.data=cached.data;history=cached.history;future=cached.future;dirty=cached.dirty;app.render();updateUndo();message(dirty?'Recovered unsaved instance draft':'Recovered editor instance');return true;}
  return false;
}
function setAuth(value) {
  isAdmin=value;if(!value)app?.clearClipboard?.();document.body.classList.toggle('is-admin',value);document.body.classList.toggle('is-explorer',!value);
  $('#auth').textContent=value?'Log out':'Admin Login';
  $('#access').textContent=value?'Admin · editing enabled':'View Only';
  document.querySelectorAll('[data-admin]').forEach(el=>el.disabled=!value);
  app?.render(); updateUndo();app?.onAuthChanged?.(value);
}
function download(data,name) {
  data=clone(data);delete data._inventoryState;delete data._previousInventoryState;
  const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));
  const link=document.createElement('a');link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
// Font size is a maximum; shrink wrapped text to fit its actual grid rectangle.
function fitLabels(root=document) {
  root.querySelectorAll('.fit-label').forEach(label=>{
    const parent=label.parentElement;
    const vertical=parent.closest('#plan')&&parent.classList.contains('grid-item')&&!parent.classList.contains('misc-item')&&parent.clientHeight>parent.clientWidth*2.2;
    // Rotate narrow floor-plan labels to use the item's long axis.
    Object.assign(label.style,vertical?{position:'absolute',width:Math.max(1,parent.clientHeight-4)+'px',height:Math.max(1,parent.clientWidth-4)+'px',left:'50%',top:'50%',transform:'translate(-50%, -50%) rotate(90deg)'}:{position:'',width:'',height:'',left:'',top:'',transform:''});
    let size=Number(label.dataset.fontSize)||12;
    label.style.fontSize=size+'px';
    while(size>4&&(label.scrollHeight>label.clientHeight+1||label.scrollWidth>label.clientWidth+1)) {size-=.5;label.style.fontSize=size+'px';}
    // An exceptionally long label must never paint over adjacent items.
    label.title=label.textContent;
  });
}
function labelFor(item) {
  const span=document.createElement('span');span.className='fit-label';span.textContent=item.name;
  span.dataset.fontSize=item.fontSize;span.style.fontFamily=item.fontFamily;span.style.fontWeight=item.bold?'700':'400';span.style.color=item.color;return span;
}
function gridPosition(el,item) {el.style.gridArea=`${item.y} / ${item.x} / span ${item.h} / span ${item.w}`;}
function overlaps(a,b) {return a.x<b.x+b.w&&a.x+a.w>b.x&&a.y<b.y+b.h&&a.y+a.h>b.y;}
function defaults() {return {name:'New item',background:'#dc4545',color:'#ffffff',fontSize:14,fontFamily:'system-ui',bold:true};}
async function startApp(controller) {
  app=controller;
  const dialog=document.createElement('dialog');dialog.id='saveVersionDialog';dialog.innerHTML='<form method="dialog"><h2>Save a named version</h2><label class="field">Version name<input id="versionName" maxlength="120" required autocomplete="off" placeholder="e.g. Fall lab arrangement"></label><p class="hint">This saves your current draft to disk.</p><div class="actions"><button class="primary" value="save">Save version</button><button value="cancel" formnovalidate>Cancel</button></div></form>';document.body.append(dialog);
  $('#auth').addEventListener('click',async()=>{
    if(isAdmin) {if(!await cacheDraft())return;if((dirty||app.hasUnsavedChildren?.())&&!confirm('Log out and discard this session’s unsaved drafts? Export first to keep a copy.'))return;try{await api('/api/logout','POST',{});setAuth(false);history=[];future=[];dirty=false;app.data=await api(app.endpoint);app.render();updateUndo();}catch(e){message(e.message,true);}}
    else {$('#loginError').textContent='';$('#login').showModal();$('#password').focus();}
  });
  $('#cancelLogin').addEventListener('click',()=>$('#login').close());
  $('#loginForm').addEventListener('submit',async event=>{
    event.preventDefault();
    try {await api('/api/login','POST',{password:$('#password').value});$('#password').value='';$('#login').close();setAuth(true);if(!await recoverDraft())message(dirty?'Draft ready to save':'Admin editing enabled');}
    catch(error){$('#loginError').textContent=error.message;}
  });
  $('#save').addEventListener('click',()=>save());
  $('#undo').addEventListener('click',()=>undoEdit());
  $('#redo').addEventListener('click',()=>undoEdit(true));
  $('#export').addEventListener('click',()=>download(app.data,app.filename));
  $('#reload').addEventListener('click',async()=>{
    if(dirty&&!confirm('Discard your unsaved draft and reload the server version? Export first if you need a copy.'))return;
    clearTimeout(saveTimer);
    if(saving) await savePromise;
    try {const latest=await api(app.endpoint);checkpoint();app.data=latest;dirty=false;app.render();updateUndo();await cacheDraft();message('Latest saved version loaded');}catch(error){message(error.message,true);}
  });
  window.addEventListener('beforeunload',event=>{if(dirty&&!allowNavigation){event.preventDefault();event.returnValue='';}});
  document.addEventListener('keydown',event=>{
    if(document.querySelector('dialog[open]'))return;
    const key=event.key.toLowerCase();
    if((event.ctrlKey||event.metaKey)&&key==='s'){event.preventDefault();save();}
    const typing=['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)||document.activeElement.isContentEditable;
    if((event.ctrlKey||event.metaKey)&&!typing&&(key==='z'||key==='y')){event.preventDefault();undoEdit(key==='y'||event.shiftKey);} 
  });
  try {const [data,session]=await Promise.all([api(app.endpoint),api('/api/session')]);app.data=data;setAuth(session.admin);if(!session.admin||!await recoverDraft())message('Loaded from server');}
  catch(error){message(error.message,true);$('#fatal').hidden=false;$('#fatal').textContent=error.message+' Stop the old static server and run: python3 server.py';}
}

function typingShortcut(){const el=document.activeElement;return !!el&&(el.matches('input,textarea,select')||el.isContentEditable);}
function nearbyPositions(x,y,w,h,cols,rows,step=1,min=0){
  const candidates=[],seen=new Set();
  const add=(xx,yy)=>{const key=xx+','+yy;if(!seen.has(key)){seen.add(key);candidates.push({x:xx,y:yy});}};
  [[x+w,y],[x,y+h],[x-w,y],[x,y-h]].forEach(([xx,yy])=>add(xx,yy));
  const rest=[];for(let yy=min;yy<=rows-h+min;yy+=step)for(let xx=min;xx<=cols-w+min;xx+=step)rest.push({x:xx,y:yy});
  rest.sort((a,b)=>((a.x-x)**2+(a.y-y)**2)-((b.x-x)**2+(b.y-y)**2)||a.y-b.y||a.x-b.x);rest.forEach(p=>add(p.x,p.y));return candidates;
}
let clipboardJob=Promise.resolve();
document.addEventListener('keydown',event=>{
  if(event.defaultPrevented||!isAdmin||!(event.ctrlKey||event.metaKey)||typingShortcut()||document.querySelector('dialog[open]')||!app?.clipboardContext?.())return;
  const key=event.key.toLowerCase();if(key!=='c'&&key!=='v')return;event.preventDefault();
  clipboardJob=clipboardJob.then(()=>key==='c'?app.copySelection():app.pasteSelection()).catch(error=>message(error.message,true));
});

function uniqueId(){return Array.from(crypto.getRandomValues(new Uint8Array(16)),n=>n.toString(16).padStart(2,'0')).join('');}
