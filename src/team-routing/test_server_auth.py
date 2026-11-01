import unittest,tempfile,pathlib,threading,http.client,json,socket,io
from unittest.mock import patch
from http.server import ThreadingHTTPServer
import core,auth,server,intake_delivery
class HTTPAccessTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();r=pathlib.Path(self.tmp.name);self.patches=[patch.object(core,'DB',r/'core.sqlite'),patch.object(auth,'DB',r/'auth.sqlite')]
  for p in self.patches:p.start()
  core.init();core.seed();auth.init()
  with core.connect() as c:self.sid=c.execute('SELECT id FROM specialist LIMIT 1').fetchone()[0]
  auth.create_user('owner','test-password-long','owner');auth.create_user('manager','test-password-long','manager');auth.create_user('employee','test-password-long','employee',specialist_id=self.sid)
  self.http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler);self.port=self.http.server_port;self.t=threading.Thread(target=self.http.serve_forever,daemon=True);self.t.start()
 def tearDown(self):
  self.http.shutdown();self.http.server_close();self.t.join()
  for p in reversed(self.patches):p.stop()
  self.tmp.cleanup()
 def request(self,path,body=None,cookie=None,csrf=True,origin=None):
  c=http.client.HTTPConnection('127.0.0.1',self.port);headers={}
  if body is not None:headers['Content-Type']='application/json'
  if csrf:headers['X-Local-Session']=server.SESSION
  if cookie:headers['Cookie']=cookie
  if origin:headers['Origin']=origin
  c.request('POST' if body is not None else 'GET',path,json.dumps(body) if body is not None else None,headers);r=c.getresponse();out=(r.status,r.read(),r.getheader('Set-Cookie'));c.close();return out
 def login(self,name):
  status,_,cookie=self.request('/api/login',{'username':name,'password':'test-password-long'},csrf=False);self.assertEqual(status,200);self.assertIn('HttpOnly',cookie);return cookie.split(';')[0]
 def test_questions_do_not_bypass_assignment_through_state(self):
  import question_delivery
  with core.connect() as c:
   slot=c.execute('SELECT id,order_id FROM role_slot LIMIT 1').fetchone()
   c.execute('INSERT INTO offer VALUES(?,?,?,?,?,?,?)',('offer-for-question',slot['id'],self.sid,1,'{}','2099-01-01','pending'))
   question_delivery.schema(c)
   c.execute('INSERT INTO employee_question VALUES(?,?,?,?,?,?)',('private-question',self.sid,'offer-for-question','PRIVATE QUESTION BODY',core.now(),'question-key'))
   c.execute('DELETE FROM manager_acceptance WHERE order_id=?',(slot['order_id'],))
  auth.create_user('questionmanager','test-password-long','manager',permissions=['contacts:read','finances:read'],specialist_id=self.sid)
  manager=self.login('questionmanager');owner=self.login('owner')
  self.assertEqual(json.loads(self.request('/api/questions',cookie=manager)[1]),[])
  raw=self.request('/api/state',cookie=manager)[1]
  self.assertNotIn(b'private-question',raw);self.assertNotIn(b'PRIVATE QUESTION BODY',raw)
  with core.connect() as c:c.execute('INSERT INTO manager_acceptance VALUES(?,?,?,?)',('question-assigned',slot['order_id'],self.sid,'accepted'))
  rows=json.loads(self.request('/api/questions',cookie=manager)[1])
  self.assertEqual(rows[0]['body'],'PRIVATE QUESTION BODY')
  self.assertEqual(json.loads(self.request('/api/questions',cookie=owner)[1])[0]['id'],'private-question')
  self.assertNotIn(b'private-question',self.request('/api/state',cookie=owner)[1])
  with core.connect() as c:c.execute("UPDATE manager_acceptance SET status='declined' WHERE id='question-assigned'")
  self.assertEqual(json.loads(self.request('/api/questions',cookie=manager)[1]),[])
 def test_project_from_intake(self):
  ident=json.loads(self.request('/api/intake',{'kind':'client','city':'TEST City','idea':'TEST brief','contact':'PRIVATE'})[1])['id']
  body={'id':ident,'title':'TEST project','start':'2026-12-01T10:00','end':'2026-12-01T12:00','timezone':'Europe/Moscow'}
  self.assertEqual(self.request('/api/intake/project',body)[0],401)
  for name in ('employee',):  # managers hold tasks:approve by design
   self.assertEqual(self.request('/api/intake/project',body,cookie=self.login(name))[0],403)
  owner=self.login('owner')
  self.assertEqual(self.request('/api/intake/project',body,cookie=owner,csrf=False)[0],403)
  self.assertEqual(self.request('/api/intake/project',{**body,'end':body['start']},cookie=owner)[0],400)
  status,raw,_=self.request('/api/intake/project',body,cookie=owner)
  self.assertEqual(status,200);project=json.loads(raw)['order_id']
  self.assertEqual(json.loads(self.request('/api/intake/project',body,cookie=owner)[1])['order_id'],project)
  with core.connect() as c:
   row=c.execute('SELECT * FROM orders WHERE id=?',(project,)).fetchone()
   self.assertEqual(row['city'],'TEST City');self.assertNotIn('PRIVATE',row['brief'])
   self.assertEqual(c.execute('SELECT COUNT(*) FROM intake_project WHERE intake_id=?',(ident,)).fetchone()[0],1)
   intake=next(r for r in intake_delivery.list_intakes(c) if r['id']==ident)
   self.assertEqual(intake['order_id'],project);self.assertEqual(intake['status'],'working')
 def test_telegram_binding_auth_csrf_and_account_isolation(self):
  self.assertEqual(self.request('/api/account/telegram')[0],401)
  owner=self.login('owner');employee=self.login('employee')
  self.assertEqual(self.request('/api/account/telegram',{},cookie=owner,csrf=False)[0],403)
  status,raw,_=self.request('/api/account/telegram',{},cookie=owner)
  self.assertEqual(status,200)
  import telegram_link
  with core.connect() as c:telegram_link.consume(json.loads(raw)['code'],12345,c)
  self.assertTrue(json.loads(self.request('/api/account/telegram',cookie=owner)[1])['linked'])
  self.assertFalse(json.loads(self.request('/api/account/telegram',cookie=employee)[1])['linked'])
  self.assertEqual(self.request('/api/account/telegram/unlink',{},cookie=employee)[0],200)
  self.assertTrue(json.loads(self.request('/api/account/telegram',cookie=owner)[1])['linked'])
  self.assertEqual(self.request('/api/account/telegram/unlink',{},cookie=owner)[0],200)
 def test_delivery_diagnostics_and_retry_owner_only(self):
  ident=json.loads(self.request('/api/intake',{'kind':'client','contact':'TEST PRIVATE'})[1])['id']
  with core.connect() as c:c.execute('UPDATE intake_outbox SET attempts=10 WHERE intake_id=?',(ident,))
  for cookie in (None,self.login('manager'),self.login('employee')):
   self.assertEqual(self.request('/api/delivery/status',cookie=cookie)[0],403 if cookie else 401)
   self.assertEqual(self.request('/api/delivery/retry',{'id':ident},cookie=cookie)[0],403 if cookie else 401)
  owner=self.login('owner')
  with patch.dict('os.environ',{'TELEGRAM_BOT_TOKEN':'private-token','RENN_MANAGER_CHAT_ID':'private-chat'}):
   code,raw,_=self.request('/api/delivery/status',cookie=owner)
  self.assertEqual(code,200);state=json.loads(raw)
  self.assertEqual(state,{'configured':True,'queued':0,'retry_exhausted':1,'sent':0})
  self.assertNotIn(b'private',raw.lower());self.assertNotIn(b'TEST',raw)
  self.assertEqual(self.request('/api/delivery/retry',{'id':ident},cookie=owner,csrf=False)[0],403)
  self.assertEqual(self.request('/api/delivery/retry',{'id':ident},cookie=owner)[0],200)
  with core.connect() as c:
   self.assertEqual(c.execute('SELECT attempts FROM intake_outbox WHERE intake_id=?',(ident,)).fetchone()[0],0)
   c.execute("UPDATE intake_outbox SET status='sent' WHERE intake_id=?",(ident,))
  self.assertEqual(self.request('/api/delivery/retry',{'id':ident},cookie=owner)[0],400)
  self.assertEqual(self.request('/api/delivery/retry',{'id':'missing'},cookie=owner)[0],400)
 def test_intake_contact_permissions_and_retry(self):
  payload={'kind':'client','source':'shooting-landing','service':'reels','locale':'ru','idea':'TEST budget 10000','contact':'test@example.invalid','city':'TEST City','request_id':'test-request-123456'}
  status,body,_=self.request('/api/intake',payload);self.assertEqual(status,200);ident=json.loads(body)['id']
  self.assertEqual(json.loads(self.request('/api/intake',payload)[1])['id'],ident)
  with core.connect() as c:
   self.assertEqual(c.execute('SELECT count(*) FROM intake').fetchone()[0],1)
   self.assertEqual(c.execute('SELECT count(*) FROM intake_outbox').fetchone()[0],1)
  owner=self.login('owner');manager=self.login('manager')
  raw=self.request('/api/intakes',cookie=owner)[1];self.assertIn(b'test@example.invalid',raw)
  raw=self.request('/api/intakes',cookie=manager)[1];self.assertNotIn(b'test@example.invalid',raw);self.assertNotIn(b'10000',raw)
  self.assertEqual(self.request('/api/intakes',cookie=self.login('employee'))[0],403)
  auth.create_user('privileged','test-password-long','manager',permissions=['contacts:read','finances:read'])
  raw=self.request('/api/intakes',cookie=self.login('privileged'))[1];self.assertIn(b'test@example.invalid',raw)
  with patch.dict('os.environ',{'TELEGRAM_BOT_TOKEN':'fake','RENN_MANAGER_CHAT_ID':'fake'}), patch('urllib.request.urlopen',return_value=io.BytesIO(b'{"ok":true,"result":{"message_id":123}}')) as transport:
   self.assertEqual(intake_delivery.flush()['sent'],1)
   self.assertIn(ident,json.loads(transport.call_args.args[0].data)['text'])
  with core.connect() as c:self.assertEqual(c.execute('SELECT status FROM intake_outbox WHERE intake_id=?',(ident,)).fetchone()[0],'sent')
  del payload['contact'];self.assertEqual(self.request('/api/intake',payload)[0],400)
 def test_intake_status_requires_grant_and_survives_reload(self):
  ident=json.loads(self.request('/api/intake',{'kind':'client','contact':'TEST'})[1])['id']
  payload={'id':ident,'status':'working'}
  self.assertEqual(self.request('/api/intake/status',payload,cookie=self.login('employee'))[0],403)
  self.assertEqual(self.request('/api/intake/status',payload,cookie=self.login('employee'))[0],403)  # managers hold tasks:approve by design
  owner=self.login('owner')
  self.assertEqual(self.request('/api/intake/status',payload,cookie=owner)[0],200)
  self.assertEqual(json.loads(self.request('/api/intakes',cookie=owner)[1])[0]['status'],'working')
  self.assertEqual(self.request('/api/intake/status',{'id':ident,'status':'bad'},cookie=owner)[0],400)

 def test_specialist_finance_and_contact_projection(self):
  manager=self.login('manager')
  rows=json.loads(self.request('/api/specialists',cookie=manager)[1])
  for row in rows:
   self.assertNotIn('telegram_id',row)
   for key in ('rate','email','phone','telegram'):self.assertNotIn(key,row['profile'])
  rows=json.loads(self.request('/api/state',cookie=manager)[1])
  for row in rows['role_slot']:self.assertNotIn('budget',row)
  for row in rows['orders']:self.assertEqual(row['brief'],'{}')
 def test_manager_cannot_spoof_availability_or_owner(self):
  cookie=self.login('manager')
  payload={'actor':self.sid,'start':'2027-01-01T10:00','end':'2027-01-01T12:00','timezone':'UTC'}
  self.assertEqual(self.request('/api/block',payload,cookie=cookie)[0],403)
  with core.connect() as c:self.assertEqual(c.execute('SELECT count(*) FROM availability').fetchone()[0],0)
  auth.create_user('linkedmanager','test-password-long','manager',permissions=['tasks:approve'],specialist_id=self.sid)
  linked=self.login('linkedmanager')
  self.assertEqual(self.request('/api/select',{'actor':'owner','offer':'none','key':'spoof'},cookie=linked)[0],403)
  self.assertEqual(self.request('/api/discuss',{'actor':'owner','order':'crew','body':'spoof'},cookie=linked)[0],403)
  self.assertEqual(self.request('/api/workspace?order=crew&actor=owner',cookie=linked)[0],403)
 def test_duplicate_account_returns_error_and_server_survives(self):
  cookie=self.login('owner')
  self.assertEqual(self.request('/api/accounts/create',{'username':'manager','password':'test-password-long','role':'manager'},cookie=cookie)[0],400)
  self.assertEqual(self.request('/api/me',cookie=cookie)[0],200)
 def test_negative_content_length_rejected(self):
  c=http.client.HTTPConnection('127.0.0.1',self.port,timeout=2)
  try:
   c.request('POST','/api/intake',headers={'Content-Length':'-1','X-Local-Session':server.SESSION})
   r=c.getresponse();self.assertEqual(r.status,400);r.read()
  finally:
   if c.sock:c.sock.shutdown(socket.SHUT_RDWR)
   c.close()
 def test_account_profile_scope_and_csrf(self):
  self.assertEqual(self.request('/api/account/profile')[0],401)
  for role in ['owner','manager','employee']:
   cookie=self.login(role)
   payload={'display_name':role+' имя','bio':'Описание','contact_preference':'telegram'}
   self.assertEqual(self.request('/api/account/profile',payload,cookie=cookie,csrf=False)[0],403)
   self.assertEqual(self.request('/api/account/profile',payload,cookie=cookie,origin='https://example.invalid')[0],403)
   self.assertEqual(self.request('/api/account/profile',{**payload,'role':'owner'},cookie=cookie)[0],400)
   self.assertEqual(self.request('/api/account/profile',payload,cookie=cookie)[0],200)
   status,body,_=self.request('/api/account/profile',cookie=cookie)
   self.assertEqual(status,200);self.assertEqual(json.loads(body)['display_name'],role+' имя')
   self.assertNotIn('password',json.loads(body))
 def test_anonymous_private_denied(self):
  self.assertEqual(self.request('/api/state')[0],401);self.assertEqual(self.request('/crm/')[0],303)
 def test_employee_private_isolation(self):
  c=self.login('employee');self.assertEqual(self.request('/api/state',cookie=c)[0],403);self.assertEqual(self.request('/panel',cookie=c)[0],403)
  status,body,_=self.request('/api/employee/state',cookie=c);self.assertEqual(status,200);self.assertEqual(json.loads(body)['profile']['id'],self.sid)
  self.assertEqual(self.request('/api/block',{'actor':'stranger','start':'2027-01-01T10:00','end':'2027-01-01T12:00','timezone':'UTC'},cookie=c)[0],403)
 def test_approval_and_csrf(self):
  c=self.login('manager');self.assertEqual(self.request('/api/verify',{'id':self.sid,'verified':True},cookie=c)[0],403)
  o=self.login('owner');self.assertEqual(self.request('/api/verify',{'id':self.sid,'verified':True},cookie=o,csrf=False)[0],403)
  self.assertEqual(self.request('/api/verify',{'id':self.sid,'verified':True},cookie=o)[0],200)
  self.assertEqual(self.request('/api/state',cookie=o)[0],200)
 def test_employee_profile_and_question(self):
  core.route('simple')
  with core.connect() as c:
   offer=c.execute('SELECT * FROM offer LIMIT 1').fetchone();sid=offer['specialist_id']
  auth.create_user('performer','test-password-long','employee',specialist_id=sid);cookie=self.login('performer')
  status,_,_=self.request('/api/profile',{'city':'Тест-город','roles':['camera'],'equipment':'camera','mobility':'city'},cookie=cookie);self.assertEqual(status,200)
  self.assertEqual(self.request('/api/profile',{'verified':True},cookie=cookie)[0],400)
  payload={'offer':offer['id'],'body':'Где получить пропуск?','key':'test-question'}
  first=self.request('/api/employee/question',payload,cookie=cookie);second=self.request('/api/employee/question',payload,cookie=cookie)
  self.assertEqual(first[0],200);self.assertEqual(json.loads(first[1])['id'],json.loads(second[1])['id'])
  status,body,_=self.request('/api/employee/state',cookie=cookie);data=json.loads(body)
  self.assertEqual(len(data['questions']),1);self.assertEqual(data['profile']['profile']['city'],'Тест-город')
  self.assertTrue(all(o['specialist_id']==sid for o in data['offers']))
  self.assertEqual(self.request('/api/employee/question',{**payload,'offer':'foreign'},cookie=cookie)[0],403)
 def test_employee_portfolio_and_skills(self):
  cookie=self.login('employee')
  with core.connect() as c:c.execute('UPDATE specialist SET verified=1 WHERE id=?',(self.sid,))
  payload={'roles':['cg'],'skills':['cg','color'],'portfolio':'https://example.invalid/new','portfolio_role':'cg'}
  self.assertEqual(self.request('/api/profile',payload,cookie=cookie)[0],200)
  with core.connect() as c:
   row=c.execute('SELECT profile,verified FROM specialist WHERE id=?',(self.sid,)).fetchone()
   saved=json.loads(row['profile']);self.assertEqual(row['verified'],0)
   self.assertEqual(saved['skills'],['cg','color']);self.assertEqual(saved['portfolio'],payload['portfolio'])
  for bad in [{'skills':'cg'},{'skills':['unknown']},{'portfolio':'javascript:alert(1)'},{'portfolio':'https://'},{'portfolio_role':'camera'}]:
   self.assertEqual(self.request('/api/profile',bad,cookie=cookie)[0],400,bad)
  with core.connect() as c:self.assertEqual(json.loads(c.execute('SELECT profile FROM specialist WHERE id=?',(self.sid,)).fetchone()[0]),saved)
 def test_new_assets_and_manager_question_queue(self):
  for path in ['/shooting/graphics.html','/shooting/site.js?v=test','/shooting/services.js?v=test','/shooting/media/1.jpg']:
   self.assertEqual(self.request(path,csrf=False)[0],200,path)
  self.assertEqual(self.request('/shooting',csrf=False)[0],303)
  cookie=self.login('owner');status,body,_=self.request('/crm/',cookie=cookie)
  self.assertEqual(status,200);self.assertIn(b'data-crm-mode="source"',body)
  self.assertEqual(self.request('/api/state',cookie=cookie)[0],200)
 def test_origin_and_logout(self):
  c=self.login('owner');self.assertEqual(self.request('/api/logout',{},cookie=c,origin='https://example.invalid')[0],403)
  self.assertEqual(self.request('/api/logout',{},cookie=c)[0],200);self.assertEqual(self.request('/api/state',cookie=c)[0],401)
 def test_password_page_and_session_revocation(self):
  self.assertEqual(self.request('/account')[0],303)
  for role in ['owner','manager','employee']:
   cookie=self.login(role)
   status,body,_=self.request('/account',cookie=cookie)
   self.assertEqual(status,200);self.assertIn(b'new-password',body)
   workspace='/employee' if role=='employee' else '/crm/'
   self.assertIn(b'href="/account"',self.request(workspace,cookie=cookie)[1])
   payload={'current_password':'test-password-long','new_password':'replacement-password-long'}
   self.assertEqual(self.request('/api/account/password',payload,cookie=cookie,csrf=False)[0],403)
   self.assertEqual(self.request('/api/account/password',payload,cookie=cookie,origin='https://example.invalid')[0],403)
   self.assertEqual(self.request('/api/account/password',{**payload,'current_password':'wrong'},cookie=cookie)[0],400)
   self.assertEqual(self.request('/api/me',cookie=cookie)[0],200)
   status,_,expired=self.request('/api/account/password',payload,cookie=cookie)
   self.assertEqual(status,200);self.assertIn('Max-Age=0',expired)
   self.assertEqual(self.request('/api/me',cookie=cookie)[0],401)
if __name__=='__main__':unittest.main()
