import unittest,tempfile,pathlib,threading,http.client,json
from unittest.mock import patch
from http.server import ThreadingHTTPServer
import core,auth,server
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
