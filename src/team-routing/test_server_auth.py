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
  status,body,_=self.request('/api/employee/state',cookie=c);self.assertEqual(status,200);self.assertEqual(json.loads(body)['specialist']['id'],self.sid)
  self.assertEqual(self.request('/api/block',{'actor':'stranger','start':'2027-01-01T10:00','end':'2027-01-01T12:00','timezone':'UTC'},cookie=c)[0],403)
 def test_approval_and_csrf(self):
  c=self.login('manager');self.assertEqual(self.request('/api/verify',{'id':self.sid,'verified':True},cookie=c)[0],403)
  o=self.login('owner');self.assertEqual(self.request('/api/verify',{'id':self.sid,'verified':True},cookie=o,csrf=False)[0],403)
  self.assertEqual(self.request('/api/verify',{'id':self.sid,'verified':True},cookie=o)[0],200)
  self.assertEqual(self.request('/api/state',cookie=o)[0],200)
 def test_origin_and_logout(self):
  c=self.login('owner');self.assertEqual(self.request('/api/logout',{},cookie=c,origin='https://example.invalid')[0],403)
  self.assertEqual(self.request('/api/logout',{},cookie=c)[0],200);self.assertEqual(self.request('/api/state',cookie=c)[0],401)
if __name__=='__main__':unittest.main()
