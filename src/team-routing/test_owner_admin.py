import unittest,tempfile,pathlib,threading,http.client,json,socket,io
from unittest.mock import patch
from http.server import ThreadingHTTPServer
import core,auth,server,intake_delivery
class OwnerAdminTests(unittest.TestCase):
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

 def test_owner_routes_require_owner_role(self):
  manager=self.login('manager')
  status,_,_=self.request('/api/owner/staff',{},cookie=manager)
  self.assertEqual(status,403)
  self.assertEqual(self.request('/api/owner/staff',{})[0],401)

 def test_owner_staff_archive_hides_from_state_and_restores(self):
  owner=self.login('owner')
  listed=json.loads(self.request('/api/owner/staff',{},cookie=owner)[1])['staff']
  self.assertTrue(any(s['id']==self.sid for s in listed))
  status,raw,_=self.request('/api/owner/staff/archive',{'id':self.sid},cookie=owner)
  self.assertEqual(status,200,raw)
  state=self.request('/api/state',cookie=owner)[1]
  self.assertNotIn(self.sid.encode(),state)
  self.assertEqual(self.request('/api/owner/staff/restore',{'id':self.sid},cookie=owner)[0],200)

 def test_owner_cannot_archive_staff_with_active_assignment(self):
  owner=self.login('owner')
  with core.connect() as c:
   slot=c.execute('SELECT id,order_id FROM role_slot LIMIT 1').fetchone()
   c.execute("INSERT INTO offer VALUES('o-busy',?,?,1,'{}','2099-01-01','accepted')",(slot['id'],self.sid))
   c.execute("INSERT INTO assignment VALUES('a-busy',?,?,'o-busy',?)",(slot['id'],self.sid,core.now()))
   c.execute("UPDATE orders SET end='2099-01-02T00:00:00+00:00' WHERE id=?",(slot['order_id'],))
  status,raw,_=self.request('/api/owner/staff/archive',{'id':self.sid},cookie=owner)
  self.assertEqual(status,400)
  self.assertIn('назначени'.encode(),raw)

 def test_owner_economics_and_client_price(self):
  owner=self.login('owner')
  with core.connect() as c:order=c.execute('SELECT id FROM orders LIMIT 1').fetchone()[0]
  self.assertEqual(self.request('/api/owner/price',{'order':order,'price':50000},cookie=owner)[0],200)
  self.assertEqual(self.request('/api/owner/price',{'order':order,'price':-1},cookie=owner)[0],400)
  econ=json.loads(self.request('/api/owner/economics',{'order':order},cookie=owner)[1])
  self.assertEqual(econ['client_price'],50000)
  self.assertEqual(econ['payouts_assigned'],0)
  self.assertEqual(econ['margin'],50000)

 def test_owner_deletes_empty_order_only(self):
  owner=self.login('owner')
  with core.connect() as c:order=c.execute('SELECT id FROM orders WHERE id NOT IN (SELECT o.order_id FROM role_slot o JOIN assignment a ON a.slot_id=o.id) LIMIT 1').fetchone()[0]
  self.assertEqual(self.request('/api/owner/order/delete',{'order':order},cookie=owner)[0],200)
  self.assertEqual(self.request('/api/owner/order/delete',{'order':order},cookie=owner)[0],400)

 def test_owner_cannot_deactivate_self_or_owner_account(self):
  owner=self.login('owner')
  with auth.connect() as a:
   owner_id=a.execute("SELECT id FROM account WHERE username='owner'").fetchone()[0]
   mgr_id=a.execute("SELECT id FROM account WHERE username='manager'").fetchone()[0]
  self.assertEqual(self.request('/api/owner/account/deactivate',{'id':owner_id},cookie=owner)[0],400)
  self.assertEqual(self.request('/api/owner/account/deactivate',{'id':mgr_id},cookie=owner)[0],200)
  manager=self.request('/api/login',{'username':'manager','password':'test-password-long'},csrf=False)
  self.assertNotEqual(manager[0],200)

 def test_owner_page_is_served_only_to_owner(self):
  self.assertEqual(self.request('/owner')[0],303)
  self.assertEqual(self.request('/owner',cookie=self.login('manager'))[0],303)
  status,raw,_=self.request('/owner',cookie=self.login('owner'))
  self.assertEqual(status,200)
  self.assertIn('кабинет владельца'.encode(),raw)
  self.assertNotIn(b'__SESSION__',raw)

 def _bot_invite(self,code,ident=777,username='Misha_Test'):
  import bot
  msg={'chat':{'id':ident,'type':'private'},'from':{'id':ident,'username':username},'text':'/invite '+code}
  with core.connect() as c:return bot.handle(msg,c)

 def test_manager_invite_via_bot_then_forced_password_change(self):
  owner=self.login('owner')
  status,raw,_=self.request('/api/owner/invite',{'role':'manager','permissions':['contacts:read']},cookie=owner)
  self.assertEqual(status,200,raw)
  code=json.loads(raw)['code']
  reply=self._bot_invite(code)
  self.assertIsInstance(reply,dict);self.assertTrue(reply.get('_secret'))
  lines=dict(l.split(': ',1) for l in reply['text'].split('\n') if ': ' in l)
  login_name=lines['Логин'];temp=lines['Временный пароль']
  # Code is single-use.
  self.assertIn('не принято',self._bot_invite(code,ident=778))
  status,_,cookie_resp=self.request('/api/login',{'username':login_name,'password':temp},csrf=False)
  self.assertEqual(status,200)
  cookie=cookie_resp.split(';')[0]
  self.assertEqual(self.request('/api/owner/staff',{},cookie=cookie)[0],403)
  self.assertEqual(self.request('/api/state',cookie=cookie)[0],403)
  self.assertEqual(self.request('/api/account/password',{'current_password':temp,'new_password':'brand-new-password-1'},cookie=cookie)[0],200)
  self.assertEqual(self.request('/api/state',cookie=cookie)[0],401)  # password change signs the old session out
  status,_,cookie2=self.request('/api/login',{'username':login_name,'password':'brand-new-password-1'},csrf=False)
  self.assertEqual(status,200)
  self.assertEqual(self.request('/api/state',cookie=cookie2.split(';')[0])[0],200)

 def test_invite_rejects_bad_role_expired_and_non_owner(self):
  manager=self.login('manager')
  self.assertEqual(self.request('/api/owner/invite',{'role':'manager'},cookie=manager)[0],403)
  owner=self.login('owner')
  self.assertEqual(self.request('/api/owner/invite',{'role':'owner'},cookie=owner)[0],400)
  self.assertEqual(self.request('/api/owner/invite',{'role':'manager','permissions':['*']},cookie=owner)[0],400)

 def test_employee_invite_requires_questionnaire_first(self):
  owner=self.login('owner')
  code=json.loads(self.request('/api/owner/invite',{'role':'employee'},cookie=owner)[1])['code']
  self.assertIn('не принято',self._bot_invite(code,ident=779))
  with auth.connect() as a:linked={r[0] for r in a.execute('SELECT specialist_id FROM account WHERE specialist_id IS NOT NULL')}
  with core.connect() as c:
   free=[r[0] for r in c.execute('SELECT id FROM specialist') if r[0] not in linked][0]
   c.execute('UPDATE specialist SET telegram_id=779 WHERE id=?',(free,))
   c.commit()
  reply=self._bot_invite(code,ident=779,username='anna')
  self.assertTrue(reply.get('_secret'))
  with auth.connect() as a:
   row=a.execute("SELECT role,specialist_id,must_change FROM account WHERE username LIKE 'anna-%'").fetchone()
  self.assertEqual((row['role'],row['must_change']),('employee',1))

 def test_secret_is_not_cached_in_command_table(self):
  owner=self.login('owner')
  import bot
  code=json.loads(self.request('/api/owner/invite',{'role':'manager'},cookie=owner)[1])['code']
  update={'update_id':91001,'message':{'chat':{'id':780,'type':'private'},'from':{'id':780,'username':'x'},'text':'/invite '+code}}
  reply=bot.process_update(update)
  self.assertIn('Временный пароль',reply['text'])
  with core.connect() as c:
   cached=c.execute("SELECT result FROM command WHERE id='tg-update:91001'").fetchone()[0]
  self.assertNotIn('Временный пароль',cached)

 def test_economics_summary_is_owner_only_and_matches_orders(self):
  owner=self.login('owner')
  self.assertEqual(self.request('/api/owner/economics/summary',{},cookie=self.login('manager'))[0],403)
  with core.connect() as c:order=c.execute('SELECT id FROM orders LIMIT 1').fetchone()[0]
  self.request('/api/owner/price',{'order':order,'price':40000},cookie=owner)
  status,raw,_=self.request('/api/owner/economics/summary',{},cookie=owner)
  self.assertEqual(status,200)
  body=json.loads(raw)
  self.assertGreaterEqual(body['totals']['orders'],1)
  self.assertEqual(body['totals']['priced'],sum(1 for i in body['items'] if i['client_price'] is not None))
  self.assertGreaterEqual(body['totals']['client_price'],40000)

 def test_documents_follow_project_and_employees_are_blocked(self):
  import base64, documents
  owner=self.login('owner'); manager=self.login('manager'); employee=self.login('employee')
  with auth.connect() as a0:a0.execute("UPDATE account SET permissions='[\"tasks:approve\"]' WHERE username='manager'")
  with auth.connect() as a:mgr_id=a.execute("SELECT id FROM account WHERE username='manager'").fetchone()[0]
  with core.connect() as c:
   order=c.execute('SELECT id FROM orders LIMIT 1').fetchone()[0]
   documents.assign_order_manager(c,order,mgr_id)
   c.commit()
  payload=base64.b64encode(b'%PDF-1.4 test contract').decode()
  body={'owner_kind':'order','owner_id':order,'kind':'contract','title':'Тестовый договор','filename':'contract.pdf','content_base64':payload}
  status,raw,_=self.request('/api/documents/upload',body,cookie=manager)
  self.assertEqual(status,200,raw)
  doc_id=json.loads(raw)['id']
  self.assertTrue(any(d['id']==doc_id for d in json.loads(self.request('/api/documents/list',{},cookie=manager)[1])['documents']))
  self.assertTrue(any(d['id']==doc_id for d in json.loads(self.request('/api/documents/list',{},cookie=owner)[1])['documents']))
  got=json.loads(self.request('/api/documents/download',{'id':doc_id},cookie=manager)[1])
  self.assertEqual(base64.b64decode(got['content_base64']),b'%PDF-1.4 test contract')
  # General documents belong to the owner: a manager neither adds nor sees them.
  general={'owner_kind':'general','owner_id':'general','kind':'act','title':'Общий акт','filename':'act.pdf','content_base64':payload}
  self.assertEqual(self.request('/api/documents/upload',general,cookie=manager)[0],403)
  self.assertEqual(self.request('/api/documents/list',{},cookie=employee)[0],403)
  self.assertEqual(self.request('/documents',cookie=employee)[0],303)
  self.assertEqual(self.request('/documents',cookie=manager)[0],200)

 def test_transfer_moves_project_documents_to_new_manager(self):
  import base64, documents
  owner=self.login('owner')
  with auth.connect() as a1:a1.execute("UPDATE account SET permissions='[\"tasks:approve\"]' WHERE username='manager'")
  old=self.login('manager')
  with auth.connect() as a:
   old_id=a.execute("SELECT id FROM account WHERE username='manager'").fetchone()[0]
   new_id=auth.create_user('second','test-password-long','manager',['tasks:approve'])
  with core.connect() as c:
   order=c.execute('SELECT id FROM orders LIMIT 1').fetchone()[0]
   documents.assign_order_manager(c,order,old_id); c.commit()
  payload=base64.b64encode(b'doc').decode()
  self.assertEqual(self.request('/api/documents/upload',{'owner_kind':'order','owner_id':order,'kind':'invoice','title':'Счёт','filename':'i.pdf','content_base64':payload},cookie=old)[0],200)
  second=self.login('second')
  self.assertEqual(json.loads(self.request('/api/documents/list',{},cookie=second)[1])['documents'],[])
  self.assertEqual(self.request('/api/orders/transfer',{'order':order,'to':new_id},cookie=old)[0],200)
  self.assertEqual(len(json.loads(self.request('/api/documents/list',{},cookie=second)[1])['documents']),1)
  self.assertEqual(self.request('/api/orders/transfer',{'order':order,'to':old_id},cookie=old)[0],403)  # no longer the manager

if __name__=="__main__":unittest.main()
