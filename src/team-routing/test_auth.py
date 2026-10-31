import unittest,tempfile,pathlib,sqlite3,json,time
import auth
class AuthTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=pathlib.Path(self.tmp.name)/'auth.sqlite';auth.init(self.path)
 def tearDown(self):self.tmp.cleanup()
 def test_roles(self):
  auth.create_user('owner','test-password-long','owner',path=self.path)
  auth.create_user('manager','test-password-long','manager',path=self.path)
  auth.create_user('employee','test-password-long','employee',specialist_id='s1',path=self.path)
  for name in ['owner','manager','employee']:
   token,p=auth.login(name,'test-password-long',path=self.path)
   self.assertEqual(auth.principal(token,path=self.path)['role'],name)
   self.assertEqual(auth.allowed(p,'employees:approve'),name=='owner')
   self.assertEqual(auth.allowed(p,'dashboard:read'),name!='employee')
 def test_revocation_and_failure(self):
  auth.create_user('owner','test-password-long','owner',path=self.path)
  with self.assertRaises(ValueError):auth.login('owner','wrong',path=self.path)
  token,_=auth.login('owner','test-password-long',path=self.path)
  auth.logout(token,path=self.path);self.assertIsNone(auth.principal(token,path=self.path))
  self.assertIsNone(auth.principal('forged',path=self.path))
 def test_delegated_permissions(self):
  auth.create_user('manager','test-password-long','manager',['employees:approve'],path=self.path)
  _,p=auth.login('manager','test-password-long',path=self.path)
  self.assertTrue(auth.allowed(p,'employees:approve'));self.assertFalse(auth.allowed(p,'employees:add'))
 def test_invalid_accounts(self):
  with self.assertRaises(ValueError):auth.create_user('bad','short','owner',path=self.path)
  with self.assertRaises(ValueError):auth.create_user('bad','test-password-long','root',path=self.path)
 def test_password_change_revokes_sessions(self):
  auth.create_user('owner','test-password-long','owner',path=self.path)
  first,p=auth.login('owner','test-password-long',path=self.path)
  second,_=auth.login('owner','test-password-long',path=self.path)
  auth.change_password(p,'test-password-long','replacement-password-long',path=self.path)
  self.assertIsNone(auth.principal(first,path=self.path))
  self.assertIsNone(auth.principal(second,path=self.path))
  with self.assertRaises(ValueError):auth.login('owner','test-password-long',path=self.path)
  _,current=auth.login('owner','replacement-password-long',path=self.path)
  self.assertEqual(current['id'],p['id'])
 def test_invalid_password_change_preserves_session(self):
  auth.create_user('owner','test-password-long','owner',path=self.path)
  token,p=auth.login('owner','test-password-long',path=self.path)
  for old,new in [('wrong','replacement-password-long'),('test-password-long','short'),('test-password-long','test-password-long')]:
   with self.assertRaises(ValueError):auth.change_password(p,old,new,path=self.path)
  self.assertIsNotNone(auth.principal(token,path=self.path))
if __name__=='__main__':unittest.main()
