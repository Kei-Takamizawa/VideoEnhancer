const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {webcrypto} = require('node:crypto');

function app(fetch) {
  const elements = new Map();
  const element = selector => {
    if (!elements.has(selector)) elements.set(selector, {textContent:'',addEventListener(){}});
    return elements.get(selector);
  };
  const context = vm.createContext({
    document:{querySelector:element,querySelectorAll:() => [],addEventListener(){}},
    window:{addEventListener(){}},navigator:{webdriver:true},location:{pathname:'/'},
    localStorage:{getItem:()=>null,setItem(){}},sessionStorage:{getItem:()=>null,setItem(){}},
    fetch:(path,options) => path === '/api/config' ? new Promise(()=>{}) : fetch(path,options),
    crypto:webcrypto,performance,console,setTimeout,clearTimeout,AbortController,Blob,File,URL,
  });
  vm.runInContext(fs.readFileSync(__dirname + '/static/app.js','utf8'), context);
  return {context,run:code=>vm.runInContext(code,context)};
}

test('concurrent results are each delivered once without dropping a result', async () => {
  const sent = [], releases = [];
  const a = app(async (path,options) => {
    sent.push(JSON.parse(options.body).index);
    await new Promise(resolve => releases.push(resolve));
    return {ok:true,json:async()=>({})};
  });
  const first = a.run("record('T1',{index:1})");
  const second = a.run("record('T2',{index:2})");
  while (releases.length) { releases.shift()(); await new Promise(setImmediate); }
  await Promise.all([first,second]);
  assert.deepEqual(sent,[1,2]);
  assert.equal(a.run('pending.length'),0);
});

test('an already uploaded file is not evidence of resumed transfer', async () => {
  let result;
  const a = app(async (path,options) => {
    if (path === '/api/results') { result=JSON.parse(options.body);return {ok:true,json:async()=>({})}; }
    if (path.endsWith('/finish')) return {ok:true,json:async()=>({sha256:await a.context.hash})};
    return {ok:true,json:async()=>({offset:5})};
  });
  const file = new Blob(['hello']);
  a.context.file = file;
  a.context.hash = webcrypto.subtle.digest('SHA-256',await file.arrayBuffer()).then(b=>Buffer.from(b).toString('hex'));
  a.run('config={chunk_bytes:4}');
  await a.run("upload(file,'files')");
  assert.equal(result.hash_matches,true);
  assert.equal(result.resume_ok,false);
  assert.equal(result.transferred_bytes,0);
});

test('requests include mode and 401 shows only pairing controls', async () => {
  const calls = [];
  const a = app(async (path, options) => {
    calls.push(options);
    return {ok:false,status:401,text:async()=> 'Pair first'};
  });
  await assert.rejects(a.run("api('/api/other')"), /401/);
  assert.equal(calls[0].headers['X-Display-Mode'], 'browser');
  assert.equal(a.run("$('#pairing').hidden"), false);
  assert.match(a.run('status.textContent'), /Pair this app/);
});

test('records carry standalone mode and notification diagnostics', async () => {
  let result;
  const a = app(async (path, options) => {
    result = JSON.parse(options.body);
    return {ok:true,json:async()=>({})};
  });
  a.context.navigator.standalone = true;
  a.context.window.Notification = {permission:'denied'};
  a.context.window.PushManager = function(){};
  await a.run("record('T3',{phase:'subscribe'})");
  assert.equal(result.display_mode, 'standalone');
  assert.equal(result.notification_permission, 'denied');
  assert.equal(result.push_manager, true);
});

test('service worker tags native requests and reports unauthorized sessions', async () => {
  const handlers = {}, messages = [], outgoing = [];
  const context = vm.createContext({
    self:{location:{origin:'https://spike.local'}, addEventListener:(name, fn)=>{handlers[name]=fn;},
      clients:{get:async()=>({postMessage:(message, ports)=>{
        if (message.type === 'display-mode') ports[0].postMessage('standalone');
        else messages.push(message);
      }})}},
    URL, Request, Headers, MessageChannel, setTimeout, clearTimeout,
    fetch:async request=>{outgoing.push(request);return {status:401};},
  });
  vm.runInContext(fs.readFileSync(__dirname + '/static/sw.js','utf8'), context);
  let response;
  handlers.fetch({clientId:'app', request:new Request('https://spike.local/media/h264.mp4'), respondWith:p=>{response=p;}});
  await response;
  assert.equal(outgoing[0].headers.get('X-Display-Mode'), 'standalone');
  assert.equal(messages[0].type, 'unpaired');
});

test('T6 variants record size, completion, return and usable choice', async () => {
  const rows = [];
  const a = app(async (path, options) => {
    if (path === '/api/results') {rows.push(JSON.parse(options.body)); return {ok:true,json:async()=>({})};}
    return {ok:true,blob:async()=>new Blob(['synthetic'])};
  });
  a.context.File = File;
  a.context.navigator.canShare = () => true;
  a.context.navigator.share = async () => {};
  await a.run("startDownload('B','500MB')");
  await a.run('loadDownloadBlob()');
  await a.run('shareDownload()');
  await a.run('downloadReturned(true)');
  assert.deepEqual(rows.map(r=>r.phase), ['started','loaded','finished','owner_return']);
  assert.ok(rows.every(r=>r.variant === 'B' && r.size === '500MB'));
  assert.equal(rows.at(-1).usable, true);
  assert.equal(rows.at(-1).returned_without_relaunch, true);
  assert.ok(rows.at(-1).observation_elapsed_s >= 0);
});

test('T6 1GB Blob failure records memory error and return failure', async () => {
  const rows = [];
  const a = app(async (path, options) => {
    if (path === '/api/results') {rows.push(JSON.parse(options.body));return {ok:true,json:async()=>({})};}
    return {ok:true,blob:async()=>{const e = new Error('Out of memory');e.name='RangeError';throw e;}};
  });
  await a.run("startDownload('B','1GB')");
  await a.run('loadDownloadBlob()');
  await a.run('downloadReturned(false)');
  assert.equal(rows[1].phase,'load_error');
  assert.equal(rows[1].memory_failure,true);
  assert.equal(rows[2].returned_without_relaunch,false);
  assert.equal(rows[2].usable,false);
  assert.ok(rows.every(r=>r.size === '1GB'));
});

test('T6 native choices preserve separate variant run IDs', async () => {
  const rows = [];
  const a = app(async (path, options) => {rows.push(JSON.parse(options.body));return {ok:true,json:async()=>({})};});
  for (const variant of ['A','C']) {
    await a.run(`startDownload('${variant}','500MB')`);
    await a.run('downloadReturned(true)');
  }
  assert.deepEqual(rows.map(r=>r.variant),['A','A','C','C']);
  assert.notEqual(rows[0].run,rows[2].run);
  const html = fs.readFileSync(__dirname + '/static/index.html','utf8');
  assert.match(html,/data-download="A"[^>]*target="_blank"/);
  assert.match(html,/Warning: C may trap the app/);
});
