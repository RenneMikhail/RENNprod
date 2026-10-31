import os,unittest,importlib
import access

class DeployConfigTests(unittest.TestCase):
    def tearDown(self):
        for k in ('RENN_SECURE','RENN_ALLOWED_HOSTS'):os.environ.pop(k,None)
        importlib.reload(access)
    def test_default_is_loopback_only_and_not_secure(self):
        self.assertEqual(access.allowed_hosts(8766),{'127.0.0.1:8766'})
        self.assertEqual(access.secure_cookie('a=b; HttpOnly'),'a=b; HttpOnly')
        self.assertEqual(access.SCHEME,'http')
    def test_env_adds_public_host_and_secure_cookie(self):
        os.environ['RENN_SECURE']='1';os.environ['RENN_ALLOWED_HOSTS']='crm.example.test, other.example.test:8443'
        importlib.reload(access)
        self.assertEqual(access.allowed_hosts(8766),{'127.0.0.1:8766','crm.example.test','other.example.test:8443'})
        self.assertTrue(access.secure_cookie('a=b').endswith('; Secure'))
        self.assertEqual(access.SCHEME,'https')

if __name__=='__main__':unittest.main()
