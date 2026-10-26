/* global chrome, performance, document, setTimeout, window, HTMLInputElement, Event */
// Own-page input events and private IPC only. No capture or global input.
(async()=>{
 let id=1000000000;const pending=new Map();
 chrome.webview.addEventListener('message',e=>{const p=pending.get(e.data.reply);if(p){pending.delete(e.data.reply);if(e.data.error){p.reject(Error(e.data.error));}else{p.resolve(e.data.result);}}});
 const request=command=>new Promise((resolve,reject)=>{const n=++id;pending.set(n,{resolve,reject});chrome.webview.postMessage(JSON.stringify({version:1,id:n,command}));});
 try{
  const calibration=[];
  for(let i=0;i<20;i++){const before=performance.now();const r=await request({type:'testClock'});const after=performance.now();calibration.push({rtt_ms:after-before,offset:r.qpc_ms-(before+after)/2});}
  const best=calibration.reduce((a,b)=>a.rtt_ms<b.rtt_ms?a:b);const rows=[];
  const slider=document.querySelector('[aria-label="Before / After divider"]');
  for(let i=0;i<20;i++){
   await new Promise(r=>setTimeout(r,100));
   const fraction=i%2?.25:.75;const input=performance.now();
   // A page-local input event follows the actual slider handler and IPC path.
   const completion=new Promise((resolve,reject)=>{window.__dividerProbe={input_ms:input,resolve,reject};});
   Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(slider,String(fraction));
   slider.dispatchEvent(new Event('input',{bubbles:true}));slider.dispatchEvent(new Event('change',{bubbles:true}));
   const row=await completion;row.input_qpc_ms=input+best.offset;row.processed_ms=row.frame_qpc_ms-row.input_qpc_ms;row.total_ms=row.next_estimated_qpc_ms-row.input_qpc_ms;rows.push(row);
  }
  chrome.webview.postMessage(JSON.stringify({version:1,id:++id,command:{type:'testReport',result:{calibration,rows}}}));
 }catch(error){chrome.webview.postMessage(JSON.stringify({version:1,id:++id,command:{type:'testReport',result:{error:String(error)}}}));}
})();
