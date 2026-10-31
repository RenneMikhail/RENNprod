const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
test('live registry loads server projects and clears them on API failure',async()=>{
 let fail=false;const window={dispatchEvent(){}};
 const responses={'/api/questions':[{id:'q1',city:'TEST',body:'Question'}], '/api/specialists':[], '/api/intakes':[], '/api/state':{orders:[{id:'real',title:'Server project',city:'TEST',status:'staffing',end:'2030-01-01'}],manager_acceptance:[],specialist:[]}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/team-api-adapter.js','utf8'),{window,Event,AbortSignal,location:{hostname:'127.0.0.1',pathname:'/crm'},document:{querySelector:()=>({content:'test-session'})},fetch:async url=>({ok:!fail,status:fail?503:200,json:async()=>responses[url]})});
 await window.RPRegistry.refresh();assert.equal(window.RPRegistry.status,'ready');assert.equal(window.RPRegistry.projects[0].id,'real');assert.equal(window.RPRegistry.projects[0].source,'live');assert.equal(window.RPRegistry.questions[0].id,'q1');
 fail=true;await window.RPRegistry.refresh();assert.deepEqual(Array.from(window.RPRegistry.projects),[]);assert.equal(window.RPRegistry.status,'error');assert.equal(window.RPRegistry.questions.length,0);
});
test('production dashboard does not fall back to demo orders',()=>{
 const code=fs.readFileSync(__dirname+'/app.js','utf8');
 const fn=code.slice(code.indexOf('function projects()'),code.indexOf('function tasks()'));
 const projects=vm.runInNewContext('('+fn.trim()+')',{demo:false,window:{RPRegistry:{projects:[{id:'server-only'}]}}});
 assert.equal(projects()[0].id,'server-only');
});

test('create project sends explicit schedule and preserves errors',async()=>{
 const calls=[];let fail=false;const window={dispatchEvent(){}};
 const responses={'/api/questions':[], '/api/specialists':[], '/api/intakes':[], '/api/state':{orders:[],manager_acceptance:[],specialist:[]}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/team-api-adapter.js','utf8'),{window,Event,AbortSignal,location:{hostname:'127.0.0.1',pathname:'/crm'},document:{querySelector:()=>({content:'test-session'})},fetch:async(url,options)=>{calls.push({url,options});return {ok:!fail,status:fail?403:200,json:async()=>url==='/api/intake/project'?{order_id:'project-test'}:responses[url]};}});
 const fields={id:'intake-test',title:'TEST project',start:'2030-01-01T10:00',end:'2030-01-01T12:00',timezone:'Europe/Moscow'};
 const result=await window.RPRegistry.createProject(fields);
 assert.equal(result.order_id,'project-test');assert.equal(calls[0].url,'/api/intake/project');assert.equal(calls[0].options.method,'POST');assert.equal(calls[0].options.credentials,'same-origin');assert.equal(calls[0].options.headers['X-Local-Session'],'test-session');assert.deepEqual(JSON.parse(calls[0].options.body),fields);
 const count=calls.length;fail=true;await assert.rejects(()=>window.RPRegistry.createProject(fields),/403/);assert.equal(calls.length,count+1);
});
