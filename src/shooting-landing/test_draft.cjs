const {test}=require('node:test');
const assert=require('node:assert/strict');
const {createDraftStore}=require('./draft.js');
const draft={service:'reels',idea:'TEST brief',city:'TEST city',contact:'test@example.invalid',request_id:'12345678-1234-1234-1234-123456789012'};
const storage=()=>{let value;return {getItem:()=>value,setItem:(_,v)=>value=v,removeItem:()=>value=null};};
test('reload preserves draft and id until confirmed clear',()=>{const s=storage(),a=createDraftStore(s);a.save(draft);assert.deepEqual(createDraftStore(s).load(),draft);a.clear();assert.equal(a.load(),null);});
test('expired, oversized and malformed drafts are ignored',()=>{const s=storage();createDraftStore(s,()=>0).save(draft);assert.equal(createDraftStore(s,()=>86400001).load(),null);s.setItem('',JSON.stringify({at:Date.now(),data:{...draft,idea:'x'.repeat(1201)}}));assert.equal(createDraftStore(s).load(),null);s.setItem('','{');assert.equal(createDraftStore(s).load(),null);});
test('blocked storage never breaks form',()=>{const s={getItem(){throw Error();},setItem(){throw Error();},removeItem(){throw Error();}};const a=createDraftStore(s);assert.equal(a.load(),null);assert.equal(a.save(draft),false);assert.doesNotThrow(()=>a.clear());});
