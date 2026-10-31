import unittest,tempfile,pathlib,json,io
from unittest.mock import patch
import core,intake_delivery
class DeliveryTests(unittest.TestCase):
 def test_project_invalid_or_archived_intake_has_no_partial_write(self):
  with tempfile.TemporaryDirectory() as directory,patch.object(core,'DB',pathlib.Path(directory)/'db'):
   core.init()
   with core.connect() as c:
    ident=intake_delivery.save(c,{'kind':'client','city':'TEST','contact':'PRIVATE'})
    fields={'id':ident,'title':'TEST','start':'2026-12-01T10:00','end':'2026-12-01T11:00','timezone':'Europe/Moscow'}
    for invalid in ({'timezone':'Invalid/Zone'},{'title':''},{'id':'missing'},{'end':fields['start']}):
     with self.assertRaises(ValueError):intake_delivery.create_project(c,{**fields,**invalid})
    intake_delivery.set_status(c,ident,'archive')
    with self.assertRaises(ValueError):intake_delivery.create_project(c,fields)
    self.assertEqual(c.execute('SELECT COUNT(*) FROM orders').fetchone()[0],0)
    self.assertEqual(c.execute('SELECT COUNT(*) FROM intake_project').fetchone()[0],0)
 def test_transport_does_not_hold_database_write_lock(self):
  with tempfile.TemporaryDirectory() as directory, patch.object(core,'DB',pathlib.Path(directory)/'db'):
   core.init()
   with core.connect() as c:intake_delivery.save(c,{'kind':'client','contact':'TEST'})
   def transport(*args,**kwargs):
    with core.connect() as other:
     other.execute('PRAGMA busy_timeout=50')
     intake_delivery.save(other,{'kind':'client','contact':'TEST concurrent'})
    return io.BytesIO(b'{"ok":true}')
   with patch.dict('os.environ',{'TELEGRAM_BOT_TOKEN':'fake','RENN_MANAGER_CHAT_ID':'fake'}), patch('urllib.request.urlopen',side_effect=transport):
    self.assertEqual(intake_delivery.flush()['sent'],1)
   with core.connect() as c:self.assertEqual(c.execute('SELECT count(*) FROM intake').fetchone()[0],2)
 def test_retry_then_deliver_once(self):
  with tempfile.TemporaryDirectory() as directory, patch.object(core,'DB',pathlib.Path(directory)/'db'):
   core.init()
   with core.connect() as c:ident=intake_delivery.save(c,{'kind':'client','contact':'TEST'})
   with patch.dict('os.environ',{'TELEGRAM_BOT_TOKEN':'fake','RENN_MANAGER_CHAT_ID':'fake'}):
    with patch('urllib.request.urlopen',side_effect=OSError('transport')):self.assertEqual(intake_delivery.flush()['sent'],0)
    with patch('urllib.request.urlopen',return_value=io.BytesIO(b'{"ok":true,"result":{"message_id":1}}')) as transport:
     self.assertEqual(intake_delivery.flush()['sent'],1)
     self.assertEqual(intake_delivery.flush()['sent'],0)
     self.assertEqual(transport.call_count,1)
     body=json.loads(transport.call_args.args[0].data);self.assertIn(ident,body['text']);self.assertNotIn('TEST',body['text'])

 def test_retry_key_rejects_changed_payload(self):
  with tempfile.TemporaryDirectory() as directory, patch.object(core,'DB',pathlib.Path(directory)/'db'):
   core.init()
   payload={'kind':'client','contact':'TEST','request_id':'request-test-0001'}
   with core.connect() as c:
    first=intake_delivery.save(c,payload)
    self.assertEqual(intake_delivery.save(c,payload),first)
    with self.assertRaises(ValueError):intake_delivery.save(c,{**payload,'contact':'changed'})
    self.assertEqual(c.execute('SELECT COUNT(*) FROM intake').fetchone()[0],1)
 def test_separate_permissions(self):
  import privacy
  row={'id':'test','name':'TEST','profile':{'city':'TEST','roles':['camera'],'rate':100,'email':'test@example.invalid'}}
  for permission,visible,hidden in [('finances:read','rate','email'),('contacts:read','email','rate')]:
   actor={'role':'manager','permissions':[permission]}
   view=privacy.specialist(row,actor)['profile']
   self.assertIn(visible,view);self.assertNotIn(hidden,view)
   workspace=privacy.workspace({'brief':{'budget':100,'email':'test@example.invalid'},'discussion':[{'body':'private'}]},actor)
   self.assertEqual(workspace['brief'],{});self.assertEqual(workspace['discussion'],[])

 def test_lifecycle_persists_and_rejects_invalid_status(self):
  with tempfile.TemporaryDirectory() as directory, patch.object(core,'DB',pathlib.Path(directory)/'db'):
   core.init()
   with core.connect() as c:
    ident=intake_delivery.save(c,{'kind':'client','contact':'TEST'})
    intake_delivery.set_status(c,ident,'working')
    with self.assertRaises(ValueError):intake_delivery.set_status(c,ident,'unknown')
    with self.assertRaises(ValueError):intake_delivery.set_status(c,'missing','archive')
   with core.connect() as c:
    row=intake_delivery.list_intakes(c)[0]
    self.assertEqual(row['id'],ident)
    self.assertEqual(row['status'],'working')

 def test_linked_accounts_retry_only_failed_recipient(self):
  import auth,telegram_link
  with tempfile.TemporaryDirectory() as directory, patch.object(core,'DB',pathlib.Path(directory)/'db'), patch.object(auth,'DB',pathlib.Path(directory)/'auth'):
   core.init();auth.init()
   owner=auth.create_user('owner','test-password-long','owner')
   manager=auth.create_user('manager','test-password-long','manager')
   disabled=auth.create_user('disabled','test-password-long','manager')
   with core.connect() as c:
    telegram_link.schema(c)
    for account,chat in [(owner,101),(manager,102),(disabled,103)]:c.execute('INSERT INTO telegram_account VALUES(?,?)',(account,chat))
    intake_delivery.save(c,{'kind':'client','contact':'PRIVATE'})
   with auth.connect() as c:c.execute('UPDATE account SET active=0 WHERE id=?',(disabled,))
   calls=[]
   def transport(req,**kwargs):
    body=json.loads(req.data);calls.append(str(body['chat_id']))
    self.assertNotIn('PRIVATE',body['text'])
    if str(body['chat_id'])=='102' and calls.count('102')==1:raise OSError('offline')
    return io.BytesIO(b'{"ok":true}')
   with patch.dict('os.environ',{'TELEGRAM_BOT_TOKEN':'fake','RENN_MANAGER_CHAT_ID':''}),patch('urllib.request.urlopen',side_effect=transport):
    self.assertEqual(intake_delivery.flush()['sent'],0)
    self.assertEqual(intake_delivery.flush()['sent'],1)
    self.assertEqual(intake_delivery.flush()['sent'],0)
   self.assertEqual(calls.count('101'),1);self.assertEqual(calls.count('102'),2);self.assertNotIn('103',calls)
