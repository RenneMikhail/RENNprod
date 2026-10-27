"""HTTP authentication boundary for the loopback prototype."""
import io,json
from http.cookies import SimpleCookie
from urllib.parse import urlparse,parse_qs,urlencode
import auth,core
LOGIN='''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>RENN Prod · Вход</title><style>body{background:#111315;color:#eee;font:18px/1.5 system-ui;max-width:420px;margin:10vh auto;padding:20px}input,button{box-sizing:border-box;display:block;width:100%;padding:14px;margin:12px 0;font:inherit}button{background:#ffad29;border:0}a{color:#ffad29}</style><h1>Вход в RENN Prod</h1><form><label>Имя пользователя<input name="username" autocomplete="username" required></label><label>Пароль<input name="password" type="password" autocomplete="current-password" required></label><button>Войти</button></form><p role="status" id="status"></p><script>document.querySelector('form').onsubmit=async e=>{e.preventDefault();try{const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(e.target)))});const j=await r.json();if(!r.ok)throw Error(j.error);location.assign(j.role==='employee'?'/employee':'/crm/')}catch(e){document.querySelector('#status').textContent=e.message}}</script></html>'''
class AccessMixin:
 def cookie(self):
  try:
   c=SimpleCookie(self.headers.get('Cookie',''));return c['rp_session'].value if 'rp_session' in c else ''
  except Exception:return ''
 def host_ok(self):return self.headers.get('Host')=='127.0.0.1:'+str(self.server.server_port)
 def origin_ok(self):return not self.headers.get('Origin') or self.headers['Origin']=='http://'+self.headers.get('Host','')
 def get_user(self):return auth.principal(self.cookie())
 def body(self):
  n=int(self.headers.get('Content-Length',0))
  if n<1 or n>65536:raise ValueError('Invalid request size')
  p=json.loads(self.rfile.read(n))
  if not isinstance(p,dict):raise ValueError('JSON object required')
  return p
 def response_cookie(self,payload,cookie,status=200):
  raw=json.dumps(payload,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Set-Cookie',cookie);self.end_headers();self.wfile.write(raw)
 def do_GET(self):
  if not self.host_ok():return self.send({'error':'Loopback host required'},403)
  route=urlparse(self.path).path;p=self.get_user()
  if route=='/login':return self.send(LOGIN,200,'text/html')
  if route=='/employee.js':return self.send((core.ROOT/'employee.js').read_text(),200,'text/javascript')
  if route=='/api/me':return self.send(p or {'error':'Войдите в систему'},200 if p else 401)
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
   if route=='/employee':return self.send((core.ROOT/'index.html').read_text().replace('__SESSION__',self.session_value()),200,'text/html')
   if route=='/api/workspace':
    q=parse_qs(urlparse(self.path).query);actor=p.get('specialist_id') if p['role']=='employee' else 'owner'
    if p['role']=='employee' and q.get('actor',[actor])[0]!=actor:return self.send({'error':'Чужой профиль'},403)
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
   if route=='/api/logout':auth.logout(self.cookie());return self.response_cookie({'status':'signed_out'},'rp_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
   permissions={'/api/verify':'employees:approve','/api/staff/add':'employees:add','/api/route':'tasks:approve','/api/select':'tasks:approve','/api/auto':'tasks:approve','/api/tick':'tasks:approve','/api/ack':'dashboard:read','/api/channel':'dashboard:read'}
   if route in permissions and not auth.allowed(user,permissions[route]):return self.send({'error':'Недостаточно прав'},403)
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
    return self.send({'id':ident,'status':'saved','message':'Вопрос сохранён в системе; внешняя доставка не подключена'})
   if route=='/api/profile':
    if not auth.allowed(user,'self:update'):return self.send({'error':'Нет доступа'},403)
    patch=self.body();sid=user['specialist_id']
    allowed={'city','roles','equipment','mobility'}
    if not set(patch)<=allowed|{'key'}:raise ValueError('Unknown profile field')
    with core.connect() as c:
     r=c.execute('SELECT profile FROM specialist WHERE id=?',(sid,)).fetchone()
     if not r:return self.send({'error':'Профиль не найден'},404)
     old=json.loads(r['profile']);merged={**old,**{k:v for k,v in patch.items() if k in allowed}};p=core.validate(merged)
     changed=any(old.get(k)!=p.get(k) for k in ['roles','skills','portfolio','portfolio_role'])
     c.execute('UPDATE specialist SET profile=?,verified=CASE WHEN ? THEN 0 ELSE verified END WHERE id=?',(json.dumps(p,ensure_ascii=False),int(changed),sid))
    return self.send({'status':'saved','message':'Профиль сохранён'})
   if user['role']=='employee' and route not in ['/api/block','/api/block-update','/api/respond','/api/workspace','/api/discuss','/api/manager']:return self.send({'error':'Нет доступа'},403)
   if route in ['/api/block','/api/block-update','/api/respond','/api/discuss','/api/manager','/api/select']:
    p=self.body();actor=user.get('specialist_id') if user['role']=='employee' else 'owner'
    if user['role']=='employee':
     if p.get('actor',actor)!=actor:return self.send({'error':'Чужой профиль'},403)
     p['actor']=actor
    elif route in ['/api/select','/api/discuss']:p['actor']='owner'
    else:
     # Manager may not impersonate an employee's acceptance or availability.
     if route in ['/api/respond','/api/manager']:
      if not user.get('specialist_id') or p.get('actor',user['specialist_id'])!=user['specialist_id']:return self.send({'error':'Подтверждает сам специалист'},403)
      p['actor']=user['specialist_id']
    raw=json.dumps(p).encode();self.rfile=io.BytesIO(raw);self.headers.replace_header('Content-Length',str(len(raw)))
   return self._local_post()
  except (ValueError,KeyError,TypeError):return self.send({'error':'Запрос отклонён. Проверьте данные и права.'},400)
