import tempfile,pathlib,unittest
from unittest.mock import patch
import core,auth,bot,telegram_link

class TelegramLinkTests(unittest.TestCase):
 def requests(self,ident=42,chat=42):
  return bot.handle({'from':{'id':ident},'chat':{'id':chat,'type':'private'},'text':'/requests'})
 def test_requests_shared_queue_private_and_revoked(self):
  code=telegram_link.issue(self.actor)['code']
  with core.connect() as c:
   telegram_link.consume(code,42,c)
   for n in range(12):
    import json
    c.execute('INSERT INTO intake VALUES(?,?,?,?)',(f'request-{n:02}','client',json.dumps({'city':'Москва','service':'reels','contact':'SECRET_PHONE','idea':'PRIVATE_BRIEF','budget':999999}),f'2026-10-{n+1:02}'))
  reply=self.requests()['text']
  self.assertIn('request-11',reply);self.assertNotIn('request-00',reply)
  self.assertEqual(reply.count('Москва'),10)
  for secret in ('SECRET_PHONE','PRIVATE_BRIEF','999999'):self.assertNotIn(secret,reply)
  self.assertNotIn('request-11',self.requests(43,43))
  self.assertIsNone(self.requests(42,99))
  with auth.connect() as c:c.execute("UPDATE account SET role='manager',permissions='[]'")
  self.assertIn('request-11',self.requests())
  with auth.connect() as c:c.execute("UPDATE account SET role='employee',permissions='[\"tasks:read\"]'")
  self.assertNotIn('request-11',self.requests())
  with auth.connect() as c:c.execute("UPDATE account SET role='owner'")
  with auth.connect() as c:c.execute('UPDATE account SET active=0')
  self.assertNotIn('request-11',self.requests())
 def test_request_status_buttons_permissions_and_stale_clicks(self):
  import intake_delivery
  with core.connect() as c:
   telegram_link.consume(telegram_link.issue(self.actor)['code'],42,c)
   c.execute('INSERT INTO intake VALUES(?,?,?,?)',('client-id','client','{}',core.now()))
   c.execute('INSERT INTO intake VALUES(?,?,?,?)',('private-id','employee','{}',core.now()))
  def click(data):
   with core.connect() as c:
    return bot.callback({'from':{'id':42},'message':{'chat':{'id':42,'type':'private'}},'data':data},c)
  reply=self.requests()
  self.assertIsInstance(reply,dict)
  action=reply['reply_markup']['inline_keyboard'][0][0]['callback_data']
  self.assertLessEqual(len(action.encode()),64)
  with auth.connect() as c:c.execute("UPDATE account SET role='manager',permissions='[]'")
  self.assertIsInstance(self.requests(),str)
  click(action)
  with core.connect() as c:self.assertEqual(intake_delivery.list_intakes(c)[0]['status'],'new')
  with auth.connect() as c:c.execute("UPDATE account SET permissions='[\"tasks:approve\"]'")
  click(action)
  with core.connect() as c:
   self.assertEqual(next(r for r in intake_delivery.list_intakes(c) if r['id']=='client-id')['status'],'working')
  click(action)  # old keyboard must not archive a request
  next_action=self.requests()['reply_markup']['inline_keyboard'][0][0]['callback_data']
  click(next_action)
  click(action)  # must not reopen an archived request
  click(action.replace('client-id','private-id'))
  with core.connect() as c:
   statuses={r['id']:r['status'] for r in intake_delivery.list_intakes(c)}
   self.assertEqual(statuses['client-id'],'archive')
   self.assertEqual(statuses['private-id'],'new')
 def test_request_callback_update_replay_and_private_boundary(self):
  import intake_delivery
  with core.connect() as c:
   telegram_link.consume(telegram_link.issue(self.actor)['code'],42,c)
   c.execute('INSERT INTO intake VALUES(?,?,?,?)',('replay-client','client','{}',core.now()))
  action=self.requests()['reply_markup']['inline_keyboard'][0][0]['callback_data']
  query={'from':{'id':42},'message':{'chat':{'id':99,'type':'private'}},'data':action}
  bot.process_update({'update_id':900,'callback_query':query})
  with core.connect() as c:self.assertEqual(intake_delivery.list_intakes(c)[0]['status'],'new')
  query['message']['chat']['id']=42
  update={'update_id':901,'callback_query':query}
  first=bot.process_update(update)
  self.assertEqual(bot.process_update(update),first)
  with core.connect() as c:self.assertEqual(intake_delivery.list_intakes(c)[0]['status'],'working')
  archive=self.requests()['reply_markup']['inline_keyboard'][0][0]['callback_data']
  with auth.connect() as c:c.execute('UPDATE account SET active=0')
  query['data']=archive
  bot.process_update({'update_id':902,'callback_query':query})
  with core.connect() as c:self.assertEqual(intake_delivery.list_intakes(c)[0]['status'],'working')
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.patches=[patch.object(core,'DB',pathlib.Path(self.tmp.name)/'routing.db'),patch.object(auth,'DB',pathlib.Path(self.tmp.name)/'auth.db')]
  for p in self.patches:p.start()
  core.init();auth.init()
  auth.create_user('owner','secure-password-123','owner')
  with auth.connect() as c:self.actor=auth.user(c.execute('SELECT * FROM account').fetchone())
 def tearDown(self):
  for p in reversed(self.patches):p.stop()
  self.tmp.cleanup()
 def test_single_use_hash_only_and_bot_identity(self):
  code=telegram_link.issue(self.actor)['code']
  with core.connect() as c:
   self.assertNotIn(code,str([tuple(r) for r in c.execute('SELECT * FROM telegram_link_code')]))
  message={'from':{'id':42},'chat':{'id':99,'type':'private'},'text':'/link '+code}
  self.assertIsNone(bot.handle(message))
  message['chat']['id']=42
  self.assertIn('привязан',bot.handle(message)['text'])
  self.assertTrue(telegram_link.status(self.actor)['linked'])
  with core.connect() as c:
   with self.assertRaises(ValueError):telegram_link.consume(code,43,c)
 def test_expiry_reissue_conflict_and_unlink(self):
  old=telegram_link.issue(self.actor)['code'];fresh=telegram_link.issue(self.actor)['code']
  with core.connect() as c:
   with self.assertRaises(ValueError):telegram_link.consume(old,42,c)
   with patch.object(telegram_link.time,'time',return_value=10**12):
    with self.assertRaises(ValueError):telegram_link.consume(fresh,42,c)
   telegram_link.consume(fresh,42,c)
  auth.create_user('other','secure-password-123','manager')
  with auth.connect() as c:other=auth.user(c.execute('SELECT * FROM account WHERE username=?',('other',)).fetchone())
  code=telegram_link.issue(other)['code']
  with core.connect() as c:
   with self.assertRaises(ValueError):telegram_link.consume(code,42,c)
  telegram_link.unlink(self.actor)
  self.assertFalse(telegram_link.status(self.actor)['linked'])
 def test_disabled_account_cannot_link(self):
  code=telegram_link.issue(self.actor)['code']
  with auth.connect() as c:c.execute('UPDATE account SET active=0')
  with core.connect() as c:
   with self.assertRaises(ValueError):telegram_link.consume(code,42,c)

 def test_specialist_ownership_and_unlink(self):
  with core.connect() as c:
   c.execute("INSERT INTO specialist VALUES(?,?,?,0,NULL,?)",('staff','Test','{}',core.now()))
  with auth.connect() as c:
   c.execute('UPDATE account SET specialist_id=? WHERE id=?',('staff',self.actor['id']))
  self.actor['specialist_id']='staff'
  code=telegram_link.issue(self.actor)['code']
  with core.connect() as c:
   telegram_link.consume(code,42,c)
   self.assertEqual(c.execute('SELECT telegram_id FROM specialist WHERE id=?',('staff',)).fetchone()[0],42)
  telegram_link.unlink(self.actor)
  with core.connect() as c:
   self.assertIsNone(c.execute('SELECT telegram_id FROM specialist WHERE id=?',('staff',)).fetchone()[0])
   c.execute('UPDATE specialist SET telegram_id=99 WHERE id=?',('staff',))
  code=telegram_link.issue(self.actor)['code']
  with core.connect() as c:
   with self.assertRaises(ValueError):telegram_link.consume(code,42,c)
   self.assertEqual(c.execute('SELECT telegram_id FROM specialist WHERE id=?',('staff',)).fetchone()[0],99)
  self.assertFalse(telegram_link.status(self.actor)['linked'])

 def test_late_failure_rolls_back_binding_and_preserves_code(self):
  import sqlite3
  code=telegram_link.issue(self.actor)['code']
  with core.connect() as c:
   c.execute("CREATE TRIGGER fail_link BEFORE DELETE ON bot_state BEGIN SELECT RAISE(ABORT, 'test failure'); END")
   c.execute("INSERT INTO bot_state VALUES(?,?,?)",(42,'name','{}'))
   with self.assertRaises(sqlite3.IntegrityError):telegram_link.consume(code,42,c)
   self.assertEqual(c.execute('SELECT count(*) FROM telegram_account').fetchone()[0],0)
   self.assertEqual(c.execute('SELECT count(*) FROM telegram_link_code').fetchone()[0],1)
   c.execute('DROP TRIGGER fail_link')
   telegram_link.consume(code,42,c)
  self.assertTrue(telegram_link.status(self.actor)['linked'])
