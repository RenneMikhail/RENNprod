/* Tab-scoped draft: never auto-submits or persists beyond this browser session. */
(function(root){
  'use strict';
  function createDraftStore(storage,clock=Date.now){
    const key='renn-shooting-draft-v1';
    const limits={service:80,idea:1200,city:120,contact:240,request_id:100};
    function valid(data){return data&&Object.entries(limits).every(([k,n])=>typeof data[k]==='string'&&data[k].length<=n)&&/^[a-zA-Z0-9-]{16,100}$/.test(data.request_id);}
    return {
      save(data){try{if(!valid(data))return false;storage.setItem(key,JSON.stringify({at:clock(),data}));return true;}catch{return false;}},
      load(){try{const raw=storage.getItem(key);if(!raw||raw.length>12000)return null;const item=JSON.parse(raw),age=clock()-item.at;if(!Number.isFinite(item.at)||age<0||age>86400000||!valid(item.data))return null;return item.data;}catch{return null;}},
      clear(){try{storage.removeItem(key);}catch{}}
    };
  }
  if(typeof module!=='undefined'&&module.exports)module.exports={createDraftStore};
  else root.RPDrafts={createDraftStore};
})(globalThis);
