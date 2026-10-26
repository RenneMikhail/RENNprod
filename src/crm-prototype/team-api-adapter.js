/* Live read-only, same-origin local registry. Session is never stored or logged. */
window.RPRegistry={status:'idle',rows:[],error:'',async refresh(){
 const meta=document.querySelector('meta[name="rp-local-session"]');
 const session=meta?.content;
 if(location.hostname!=='127.0.0.1'||!location.pathname.startsWith('/crm')||!session||session.startsWith('__')){this.status='offline';this.error='Откройте CRM через локальный backend /crm. На автономном просмотре реестр не подключён.';window.dispatchEvent(new Event('rp-registry'));return;}
 this.status='loading';this.error='';window.dispatchEvent(new Event('rp-registry'));
 try{const response=await fetch('/api/specialists',{headers:{'X-Local-Session':session,Accept:'application/json'},credentials:'omit',cache:'no-store',redirect:'error',signal:AbortSignal.timeout(10000)});
 if(!response.ok)throw new Error(response.status===403?'Локальная сессия обновилась. Перезагрузите страницу.':'Реестр недоступен: HTTP '+response.status);
 const data=await response.json();if(!Array.isArray(data))throw new Error('Неверный формат реестра');
 this.rows=data.map(s=>{if(typeof s.id!=='string'||typeof s.name!=='string'||!s.profile||!Array.isArray(s.profile.roles))throw new Error('Неверный формат анкеты');const demo=s.name.startsWith('Демо ·')&&/@example\.invalid$/.test(s.profile.email||'');return {id:s.id,name:s.name,test:/^(TEST|ТЕСТ)(?:\s|[·:])/i.test(s.name),roles:s.profile.roles.filter(r=>typeof r==='string'),city:String(s.profile.city||''),verified:s.verified===1,source:demo?'seed':s.telegram_id?'telegram':'local'};});this.status='ready';
 }catch(e){this.status='error';this.rows=[];this.error=e.name==='TimeoutError'?'Локальный API не ответил вовремя':String(e.message||'Ошибка соединения');}window.dispatchEvent(new Event('rp-registry'));
}};
