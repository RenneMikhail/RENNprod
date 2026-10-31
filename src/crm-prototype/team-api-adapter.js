/* Live, same-origin local registry. Session is never stored or logged. */
window.RPRegistry={status:'idle',rows:[],intakes:[],questions:[],projects:[],error:'',async setStatus(id,status){
 const session=document.querySelector('meta[name="rp-local-session"]')?.content;
 const response=await fetch('/api/intake/status',{method:'POST',headers:{'Content-Type':'application/json','X-Local-Session':session||''},credentials:'same-origin',signal:AbortSignal.timeout(10000),body:JSON.stringify({id,status})});
 if(!response.ok)throw new Error('Статус не сохранён: HTTP '+response.status);
 await this.refresh();
},async createProject(fields){
 const session=document.querySelector('meta[name="rp-local-session"]')?.content;
 const response=await fetch('/api/intake/project',{method:'POST',headers:{'Content-Type':'application/json','X-Local-Session':session||''},credentials:'same-origin',signal:AbortSignal.timeout(10000),body:JSON.stringify(fields)});
 if(!response.ok)throw new Error('Проект не создан. Проверьте даты и права: HTTP '+response.status);
 const result=await response.json();await this.refresh();return result;
},async refresh(){
 if(this.status==='loading')return;
 const meta=document.querySelector('meta[name="rp-local-session"]');
 const session=meta?.content;
 if(location.hostname!=='127.0.0.1'||!location.pathname.startsWith('/crm')||!session||session.startsWith('__')){this.status='offline';this.error='Откройте CRM через локальный backend /crm. На автономном просмотре реестр не подключён.';window.dispatchEvent(new Event('rp-registry'));return;}
 this.status='loading';this.error='';window.dispatchEvent(new Event('rp-registry'));
 try{const response=await fetch('/api/specialists',{headers:{'X-Local-Session':session,Accept:'application/json'},credentials:'same-origin',cache:'no-store',redirect:'error',signal:AbortSignal.timeout(10000)});
 if(!response.ok)throw new Error(response.status===403?'Локальная сессия обновилась. Перезагрузите страницу.':'Реестр недоступен: HTTP '+response.status);
 const data=await response.json();if(!Array.isArray(data))throw new Error('Неверный формат реестра');
 this.rows=data.map(s=>{if(typeof s.id!=='string'||typeof s.name!=='string'||!s.profile||!Array.isArray(s.profile.roles))throw new Error('Неверный формат анкеты');const demo=s.name.startsWith('Демо ·')&&/@example\.invalid$/.test(s.profile.email||'');return {id:s.id,name:s.name,test:/^(TEST|ТЕСТ)(?:\s|[·:])/i.test(s.name),roles:s.profile.roles.filter(r=>typeof r==='string'),city:String(s.profile.city||''),verified:s.verified===1,source:demo?'seed':s.telegram_id?'telegram':'local'};});const intakeResponse=await fetch('/api/intakes',{headers:{'X-Local-Session':session},credentials:'same-origin',cache:'no-store',signal:AbortSignal.timeout(10000)});
 if(!intakeResponse.ok)throw new Error('Заявки недоступны: '+intakeResponse.status);
 this.intakes=await intakeResponse.json();if(!Array.isArray(this.intakes))throw new Error('Неверный формат заявок');const projectResponse=await fetch('/api/state',{headers:{'X-Local-Session':session},credentials:'same-origin',cache:'no-store',signal:AbortSignal.timeout(10000)});
 if(!projectResponse.ok)throw new Error('Проекты недоступны: '+projectResponse.status);
 const state=await projectResponse.json();
 if(!Array.isArray(state.orders)||!Array.isArray(state.manager_acceptance)||!Array.isArray(state.specialist))throw new Error('Неверный формат проектов');
 const labels={open:'Открыт',staffing:'Подбор команды',working:'В работе',completed:'Завершён',archive:'Архив'};
 const questionResponse=await fetch('/api/questions',{credentials:'same-origin',cache:'no-store',signal:AbortSignal.timeout(10000)});
 if(!questionResponse.ok)throw new Error('Вопросы недоступны: '+questionResponse.status);
 this.questions=await questionResponse.json();if(!Array.isArray(this.questions))throw new Error('Неверный формат вопросов');
 this.projects=state.orders.map(o=>{if(typeof o.id!=='string'||typeof o.title!=='string')throw new Error('Неверный формат проекта');const accepted=state.manager_acceptance.find(m=>m.order_id===o.id&&m.status==='accepted');const manager=accepted&&state.specialist.find(p=>p.id===accepted.specialist_id);return {id:o.id,name:o.title,client:'Не указан',city:o.city||'',manager:manager?.name||'Не назначен',stage:labels[o.status]||o.status||'Не указан',deadline:o.end||'',complete:['completed','archive'].includes(o.status),attention:o.status==='open',format:o.kind||'',source:'live'};});this.status='ready';
 }catch(e){this.status='error';this.rows=[];this.intakes=[];this.questions=[];this.projects=[];this.error=e.name==='TimeoutError'?'Локальный API не ответил вовремя':String(e.message||'Ошибка соединения');}window.dispatchEvent(new Event('rp-registry'));
}};
