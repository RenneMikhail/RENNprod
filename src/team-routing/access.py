"""HTTP authentication boundary for the loopback prototype."""
import io,json,html,sqlite3,os
from http.cookies import SimpleCookie
from urllib.parse import urlparse,parse_qs,urlencode
import auth,core,intake_delivery,telegram_link,question_delivery,documents
LOGIN='''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>RENN Prod · Вход</title><style>body{background:#111315;color:#eee;font:18px/1.5 system-ui;max-width:420px;margin:10vh auto;padding:20px}input,button{box-sizing:border-box;display:block;width:100%;padding:14px;margin:12px 0;font:inherit}button{background:#ffad29;border:0}a{color:#ffad29}</style><h1>Вход в RENN Prod</h1><form><label>Имя пользователя<input name="username" autocomplete="username" required></label><label>Пароль<input name="password" type="password" autocomplete="current-password" required></label><button>Войти</button></form><p role="status" id="status"></p><script>document.querySelector('form').onsubmit=async e=>{e.preventDefault();try{const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(e.target)))});const j=await r.json();if(!r.ok)throw Error(j.error);location.assign(j.role==='employee'?'/employee':'/crm/')}catch(e){document.querySelector('#status').textContent=e.message}}</script></html>'''
SECURE=os.environ.get('RENN_SECURE')=='1'  # set behind an HTTPS reverse proxy
SCHEME='https' if SECURE else 'http'
def allowed_hosts(port):
 """Loopback by default; RENN_ALLOWED_HOSTS='host[:port],...' adds public names."""
 extra=[h.strip() for h in os.environ.get('RENN_ALLOWED_HOSTS','').split(',') if h.strip()]
 return {'127.0.0.1:'+str(port),*extra}
def secure_cookie(cookie):return cookie+('; Secure' if SECURE else '')
class AccessMixin:
 def account_link(self):
  principal=self.get_user()
  if not principal:return ''
  name=auth.profile(principal).get('display_name') or principal['username']
  initial=html.escape(name[:1].upper());name=html.escape(name)
  return '<a href="/account" aria-label="Мой аккаунт" style="display:flex;justify-content:flex-end;align-items:center;gap:10px;padding:12px;color:#ffae29;overflow-wrap:anywhere"><span aria-hidden="true" style="display:grid;place-items:center;flex:0 0 36px;height:36px;border-radius:50%;background:#ffae29;color:#101314">'+initial+'</span><span>'+name+'</span></a>'
 def cookie(self):
  try:
   c=SimpleCookie(self.headers.get('Cookie',''));return c['rp_session'].value if 'rp_session' in c else ''
  except Exception:return ''
 def host_ok(self):return self.headers.get('Host') in allowed_hosts(self.server.server_port)
 def origin_ok(self):return not self.headers.get('Origin') or self.headers['Origin']==SCHEME+'://'+self.headers.get('Host','')
 def get_user(self):return auth.principal(self.cookie())
 def body(self):
  n=int(self.headers.get('Content-Length',0))
  if n<1 or n>65536:raise ValueError('Invalid request size')
  p=json.loads(self.rfile.read(n))
  if not isinstance(p,dict):raise ValueError('JSON object required')
  return p
 def response_cookie(self,payload,cookie,status=200):
  raw=json.dumps(payload,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.send_header('Set-Cookie',secure_cookie(cookie));self.send_header('X-Frame-Options','DENY');self.send_header('Referrer-Policy','no-referrer');self.end_headers();self.wfile.write(raw)
 def do_GET(self):
  if not self.host_ok():return self.send({'error':'Loopback host required'},403)
  route=urlparse(self.path).path;p=self.get_user()
  if p and p.get('must_change') and route not in ('/account','/api/me','/login','/api/account/profile','/api/account/telegram'):
   # Temporary passwords work only for the password change screen.
   if route.startswith('/api/'):return self.send({'error':'Сначала смените временный пароль','must_change':True},403)
   self.send_response(303);self.send_header('Location','/account');self.end_headers();return
  if route=='/login':return self.send(LOGIN,200,'text/html')
  if route=='/employee.js':return self.send((core.ROOT/'employee.js').read_text(),200,'text/javascript')
  if route=='/api/me':return self.send(p or {'error':'Войдите в систему'},200 if p else 401)
  if route=='/api/delivery/status':
   if not p:return self.send({'error':'Войдите в систему'},401)
   if p['role']!='owner':return self.send({'error':'Только владелец'},403)
   with core.connect() as c:state=intake_delivery.delivery_status(c)
   return self.send(state)
  if route=='/api/questions':
   if not p:return self.send({'error':'Войдите в систему'},401)
   if p['role'] not in ('owner','manager') or not auth.allowed(p,'tasks:read'):return self.send({'error':'Нет доступа'},403)
   with core.connect() as c:rows=question_delivery.list_questions(c,p)
   return self.send(rows)
  if route=='/api/account/telegram':return self.send(telegram_link.status(p) if p else {'error':'Войдите в систему'},200 if p else 401)
  if route=='/api/account/profile':return self.send(auth.profile(p) if p else {'error':'Войдите в систему'},200 if p else 401)
  if route=='/manager':
   if not p or p['role'] not in ('owner','manager'):
    self.send_response(303);self.send_header('Location','/login');self.end_headers();return
   body=(core.ROOT/'manager.html').read_text().replace('__SESSION__',self.session_value()).encode('utf-8')
   self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store, private');self.end_headers();self.wfile.write(body);return
  if route=='/documents':
   if not p or p['role'] not in ('owner','manager'):
    self.send_response(303);self.send_header('Location','/login');self.end_headers();return
   body=(core.ROOT/'documents.html').read_text().replace('__SESSION__',self.session_value()).encode('utf-8')
   self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store, private');self.end_headers();self.wfile.write(body);return
  if route=='/owner':
   if not p or p['role']!='owner':
    self.send_response(303);self.send_header('Location','/login');self.end_headers();return
   body=(core.ROOT/'owner.html').read_text().replace('__SESSION__',self.session_value()).encode('utf-8')
   self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store, private');self.end_headers();self.wfile.write(body);return
  if route=='/account':
   if not p:
    self.send_response(303);self.send_header('Location','/login');self.end_headers();return
   return self.send((core.ROOT/'account.html').read_text().replace('__SESSION__',self.session_value()),200,'text/html')
  if route=='/api/employee/state':
   if not auth.allowed(p,'self:read'):return self.send({'error':'Нет доступа'},403)
   sid=p['specialist_id']
   with core.connect() as c:
    person=c.execute('SELECT id,name,profile,verified FROM specialist WHERE id=?',(sid,)).fetchone()
    if not person:return self.send({'error':'Профиль ещё не привязан'},404)
    person=dict(person);person['profile']=json.loads(person['profile'])
    offers=[dict(r) for r in c.execute('SELECT f.*,o.title,o.city,o.start,o.end,o.brief,o.kind AS type,o.id AS order_id FROM offer f JOIN role_slot s ON s.id=f.slot_id JOIN orders o ON o.id=s.order_id WHERE f.specialist_id=?',(sid,))]
    for x in offers:
     x['terms']=json.loads(x['terms']);x['brief']=json.loads(x['brief'])
     x['location']=x['brief'].get('address') or x['city'] or 'Адрес уточняется'
     x['description']=x['terms'].get('task') or x['brief'].get('task') or x['title']
     manager=c.execute("SELECT s.name FROM manager_acceptance m JOIN specialist s ON s.id=m.specialist_id WHERE m.order_id=? AND m.status='accepted'",(x['order_id'],)).fetchone()
     x['manager']=manager['name'] if manager else None
    availability=[dict(r) for r in c.execute('SELECT * FROM availability WHERE specialist_id=?',(sid,))]
    assignments=[dict(r) for r in c.execute('SELECT a.id,o.title,o.city,o.start,o.end FROM assignment a JOIN role_slot s ON s.id=a.slot_id JOIN orders o ON o.id=s.order_id WHERE a.specialist_id=?',(sid,))]
   with core.connect() as c:
    c.execute('CREATE TABLE IF NOT EXISTS employee_question(id TEXT PRIMARY KEY,specialist_id TEXT,offer_id TEXT,body TEXT,created_at TEXT,command_key TEXT,UNIQUE(specialist_id,command_key))')
    questions=[{'id':r['id'],'offer':r['offer_id'],'body':r['body'],'created_at':r['created_at']} for r in c.execute('SELECT * FROM employee_question WHERE specialist_id=? ORDER BY created_at',(sid,))]
   return self.send({'profile':person,'offers':offers,'availability':availability,'assignments':assignments,'questions':questions})
  if route=='/api/accounts':
   if not p or p['role']!='owner':return self.send({'error':'Только владелец'},403)
   with auth.connect() as c:rows=[auth.user(r) for r in c.execute('SELECT * FROM account')]
   return self.send(rows)
  private_page=route in ['/panel','/employee'] or route=='/crm' or route.startswith('/crm/')
  public_api=route=='/api/catalog'
  if private_page or route.startswith('/api/') and not public_api:
   if not p:
    if private_page:
     self.send_response(303);self.send_header('Location','/login');self.end_headers();return
    return self.send({'error':'Войдите в систему'},401)
   if route!='/employee' and route!='/api/workspace' and not auth.allowed(p,'dashboard:read'):return self.send({'error':'Нет доступа к панели менеджера'},403)
   if route=='/employee':return self.send((core.ROOT/'index.html').read_text().replace('__SESSION__',self.session_value()).replace('<nav>','<nav>'+self.account_link()),200,'text/html')
   if route=='/api/workspace':
    q=parse_qs(urlparse(self.path).query);actor='owner' if p['role']=='owner' else p.get('specialist_id')
    if not actor or p['role']!='owner' and q.get('actor',[actor])[0]!=actor:return self.send({'error':'Чужой профиль'},403)
    self.path='/api/workspace?'+urlencode({'order':q.get('order',[''])[0],'actor':actor})
  return self._local_get()
 def do_POST(self):
  if not self.host_ok() or not self.origin_ok():return self.send({'error':'Origin rejected'},403)
  route=urlparse(self.path).path
  try:
   if route=='/api/login':
    p=self.body()
    if not isinstance(p.get('username'),str) or not isinstance(p.get('password'),str) or len(p['password'])>1024:raise ValueError('Неверные данные')
    token,user=auth.login(p['username'],p['password']);return self.response_cookie(user,'rp_session='+token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800')
   if not self.authorized():return self.send({'error':'Local session required'},403)
   user=self.get_user()
   if route in ['/api/register','/api/intake']:return self._local_post()
   if not user:return self.send({'error':'Войдите в систему'},401)
   if user.get('must_change') and route not in ('/api/account/password','/api/logout'):return self.send({'error':'Сначала смените временный пароль','must_change':True},403)
   if route=='/api/delivery/retry':
    if user['role']!='owner':return self.send({'error':'Только владелец'},403)
    p=self.body()
    with core.connect() as c:intake_delivery.retry_delivery(c,p.get('id'))
    return self.send({'status':'queued'})
   if route=='/api/logout':self.body();auth.logout(self.cookie());return self.response_cookie({'status':'signed_out'},'rp_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
   if route=='/api/account/telegram':
    self.body();return self.send(telegram_link.issue(user))
   if route=='/api/account/telegram/unlink':
    self.body();return self.send(telegram_link.unlink(user))
   if route=='/api/account/profile':return self.send(auth.update_profile(user,self.body()))
   if route=='/api/account/password':
    p=self.body()
    if set(p)!={'current_password','new_password'}:raise ValueError('Invalid password fields')
    auth.change_password(user,p['current_password'],p['new_password'])
    return self.response_cookie({'status':'signed_out','message':'Пароль изменён. Войдите заново.'},'rp_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
   if route.startswith('/api/documents/') or route in ('/api/orders/transfer','/api/managers/list','/api/manager/digest','/api/reminders/time'):
    try:
     p=self.body()
     with core.connect() as c:
      if route=='/api/documents/upload':result=documents.upload(c,user,p.get('owner_kind'),p.get('owner_id'),p.get('kind'),p.get('title'),p.get('filename'),p.get('content_base64'))
      elif route=='/api/documents/list':result={'documents':documents.listing(c,user,p.get('owner_id'))}
      elif route=='/api/documents/download':result=documents.download(c,user,p.get('id'))
      elif route=='/api/orders/transfer':result=documents.transfer_order(c,user,p.get('order'),p.get('to'))
      elif route=='/api/manager/digest':
       import reminders
       result={'digest':reminders.digest(c,user),'time':reminders.get_time(c,user['id'])}
      elif route=='/api/reminders/time':
       import reminders
       result=reminders.set_time(c,user,p.get('time'))
      elif route=='/api/managers/list':
       if user['role'] not in ('owner','manager'):return self.send({'error':'Нет доступа'},403)
       with auth.connect() as acc:result={'managers':[{'id':r['id'],'username':r['username']} for r in acc.execute("SELECT id,username FROM account WHERE role='manager' AND active=1").fetchall()]}
      else:return self.send({'error':'Not found'},404)
     return self.send(result)
    except PermissionError as e:return self.send({'error':str(e)},403)
    except (ValueError,KeyError,TypeError) as e:return self.send({'error':str(e) or 'Запрос отклонён'},400)
   if route.startswith('/api/owner/'):
    if route!='/api/owner/role' and (not user or user['role']!='owner'):return self.send({'error':'Только владелец'},403)
    if route=='/api/owner/role' and (not user or user['role'] not in ('owner','manager')):return self.send({'error':'Нет доступа'},403)
    import owner_admin
    try:
     p=self.body()
     with core.connect() as c:
      if route=='/api/owner/staff':result={'staff':owner_admin.staff_list(c)}
      elif route=='/api/owner/staff/archive':result=owner_admin.archive_staff(c,user,p['id'])
      elif route=='/api/owner/staff/restore':result=owner_admin.restore_staff(c,user,p['id'])
      elif route=='/api/owner/economics':result=owner_admin.order_economics(c,p['order'])
      elif route=='/api/owner/price':result=owner_admin.set_client_price(c,user,p['order'],p['price'])
      elif route=='/api/owner/order/delete':result=owner_admin.delete_order(c,user,p['order'])
      elif route=='/api/owner/account/deactivate':result=owner_admin.deactivate_account(user,p['id'])
      elif route=='/api/owner/role':result=owner_admin.add_role_slot(c,user,p['order'],p.get('role'),p.get('skills',[]),p.get('budget'))
      elif route=='/api/owner/economics/summary':result=owner_admin.economics_summary(c)
      elif route=='/api/owner/invite':result=auth.create_invite(user,p.get('role'),p.get('permissions',[]))
      elif route=='/api/owner/account/reset-password':result=auth.reset_temp_password(user,p['id'])
      else:return self.send({'error':'Not found'},404)
     return self.send(result)
    except PermissionError as e:return self.send({'error':str(e)},403)
    except (ValueError,KeyError,TypeError) as e:return self.send({'error':str(e) or 'Запрос отклонён'},400)
   permissions={'/api/intake/project':'tasks:approve','/api/intake/status':'tasks:approve','/api/verify':'employees:approve','/api/staff/add':'employees:add','/api/route':'tasks:approve','/api/select':'tasks:approve','/api/auto':'tasks:approve','/api/tick':'tasks:approve','/api/ack':'dashboard:read','/api/channel':'dashboard:read'}
   if route in permissions and not auth.allowed(user,permissions[route]):return self.send({'error':'Недостаточно прав'},403)
   if route=='/api/intake/project':
    if user['role'] not in ('owner','manager'):return self.send({'error':'Нет доступа'},403)
    p=self.body()
    with core.connect() as c:ident=intake_delivery.create_project(c,p);documents.assign_order_manager(c,ident,user['id'])
    return self.send({'order_id':ident,'status':'saved'})
   if route in ['/api/accounts/permissions','/api/accounts/create']:
    if user['role']!='owner':return self.send({'error':'Только владелец'},403)
    p=self.body()
    if route.endswith('permissions'):auth.delegate(user,p['id'],p['permissions'])
    else:auth.create_user(p['username'],p['password'],p['role'],p.get('permissions',[]),p.get('specialist_id'))
    return self.send({'status':'saved'})
   if route=='/api/staff/add':return self.send({'id':core.register(self.body())})
   if route=='/api/employee/question':
    if not auth.allowed(user,'self:read'):return self.send({'error':'Нет доступа'},403)
    p=self.body();sid=user['specialist_id'];body=p.get('body','');key=p.get('key','')
    if not isinstance(body,str) or not 1<=len(body.strip())<=2000 or not isinstance(key,str) or not 1<=len(key)<=150:raise ValueError('Invalid question')
    with core.connect() as c:
     if not c.execute('SELECT 1 FROM offer WHERE id=? AND specialist_id=?',(p.get('offer'),sid)).fetchone():return self.send({'error':'Предложение недоступно'},403)
     c.execute('CREATE TABLE IF NOT EXISTS employee_question(id TEXT PRIMARY KEY,specialist_id TEXT,offer_id TEXT,body TEXT,created_at TEXT,command_key TEXT,UNIQUE(specialist_id,command_key))')
     previous=c.execute('SELECT id FROM employee_question WHERE specialist_id=? AND command_key=?',(sid,key)).fetchone()
     ident=previous['id'] if previous else core.uid()
     if not previous:c.execute('INSERT INTO employee_question VALUES(?,?,?,?,?,?)',(ident,sid,p['offer'],body.strip(),core.now(),key))
    return self.send({'id':ident,'status':'saved','message':'Вопрос сохранён. Уведомление назначенному менеджеру ожидает отправки в Telegram.'})
   if route=='/api/profile':
    if not auth.allowed(user,'self:update'):return self.send({'error':'Нет доступа'},403)
    patch=self.body();sid=user['specialist_id']
    allowed={'city','roles','skills','portfolio','portfolio_role','equipment','mobility'}
    if not set(patch)<=allowed|{'key'}:raise ValueError('Unknown profile field')
    with core.connect() as c:
     r=c.execute('SELECT profile FROM specialist WHERE id=?',(sid,)).fetchone()
     if not r:return self.send({'error':'Профиль не найден'},404)
     old=json.loads(r['profile']);merged={**old,**{k:v for k,v in patch.items() if k in allowed}}
     from urllib.parse import urlsplit
     if any(not isinstance(merged.get(k),list) or not merged[k] or any(not isinstance(x,str) for x in merged[k]) for k in ['roles','skills']):raise ValueError('Выберите роли и навыки из списка')
     if not isinstance(merged.get('portfolio'),str) or len(merged['portfolio'])>2048:raise ValueError('Проверьте ссылку на портфолио')
     link=urlsplit(merged['portfolio'])
     if link.scheme not in ['http','https'] or not link.hostname or any(x.isspace() for x in merged['portfolio']):raise ValueError('Нужна ссылка http или https на портфолио')
     if 'portfolio_role' in patch and merged['portfolio_role'] not in merged['roles']:raise ValueError('Выберите роль портфолио из ваших ролей')
     if merged['portfolio_role'] not in merged['roles']:merged['portfolio_role']=merged['roles'][0]
     p=core.validate(merged)
     changed=any(old.get(k)!=p.get(k) for k in ['roles','skills','portfolio','portfolio_role'])
     c.execute('UPDATE specialist SET profile=?,verified=CASE WHEN ? THEN 0 ELSE verified END WHERE id=?',(json.dumps(p,ensure_ascii=False),int(changed),sid))
    return self.send({'status':'saved','message':'Профиль сохранён'})
   if user['role']=='employee' and route not in ['/api/block','/api/block-update','/api/respond','/api/workspace','/api/discuss','/api/manager']:return self.send({'error':'Нет доступа'},403)
   if route in ['/api/block','/api/block-update','/api/respond','/api/discuss','/api/manager','/api/select']:
    p=self.body()
    if user['role']=='owner' and route in ['/api/select','/api/discuss']:
     p['actor']='owner'
    elif user['role']=='owner' and route in ['/api/block','/api/block-update']:
     if not p.get('actor'):return self.send({'error':'Выберите специалиста'},400)
    else:
     actor=user.get('specialist_id')
     if not actor or p.get('actor',actor)!=actor:return self.send({'error':'Чужой профиль или профиль не привязан'},403)
     p['actor']=actor
    raw=json.dumps(p).encode();self.rfile=io.BytesIO(raw);self.headers.replace_header('Content-Length',str(len(raw)))
   return self._local_post()
  except (ValueError,KeyError,TypeError,sqlite3.IntegrityError):return self.send({'error':'Запрос отклонён. Проверьте данные и права.'},400)
