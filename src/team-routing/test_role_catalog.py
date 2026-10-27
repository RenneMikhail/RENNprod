"""Synthetic role/keyboard/matching tests. No real DB or Telegram transport."""
import json,pathlib,tempfile,unittest
from unittest.mock import patch
import core,bot
EXTRA={'designer':'Дизайнер','gaffer':'Гаффер','lighting':'Осветитель','driver':'Водитель','costume':'Костюмер','makeup':'Гримёр'}
EXPECTED=['camera','editor','sound','manager','generative','event','cg','fpv',*EXTRA]
class RoleCatalogTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir=core.ROOT);self.db=pathlib.Path(self.tmp.name)/'synthetic.sqlite';core.init(self.db);core.seed(self.db)
  self.dp=patch.object(core,'DB',self.db);self.dp.start();self.transport=patch.object(bot,'call');self.mock=self.transport.start()
 def tearDown(self):
  self.mock.assert_not_called();self.transport.stop();self.dp.stop();self.tmp.cleanup()
 def profile(self,role):
  return {'name':'TEST '+role,'city':'Другой тестовый город','roles':[role],'skills':['cg'],'tasks':['shoot','edit','generate','event'],'mobility':'remote','equipment':'none','rate':10000,'currency':'RUB','languages':['ru'],'email':'synthetic@example.invalid','timezone':'UTC','portfolio':'https://example.invalid/portfolio','portfolio_role':role}
 def test_catalog_labels_and_profile_validation(self):
  self.assertEqual(core.ROLES,EXPECTED);self.assertEqual(len(set(core.ROLES)),14);self.assertEqual(bot.choices('roles'),EXPECTED)
  for role in EXPECTED:self.assertEqual(core.ROLE_LABELS[role],bot.LABELS[role])
  for role,label in EXTRA.items():
   with self.subTest(role=role):self.assertEqual(bot.LABELS[role],label);self.assertEqual(core.validate(self.profile(role))['roles'],[role])
  with self.assertRaises(ValueError):core.validate(self.profile('invented-role'))
 def test_remote_designer_cg_ai_editor_but_no_physical_crew(self):
  for role in EXPECTED:
   with self.subTest(role=role):
    sid=core.register(self.profile(role));slot={'id':'synthetic','order_id':'simple','role':role,'skills':'["cg"]','budget':12000}
    with core.connect() as c:
     c.execute('UPDATE specialist SET verified=1 WHERE id=?',(sid,));ids=[s['id'] for s in core.candidates(c,slot)]
    self.assertEqual(sid in ids,role in ['editor','generative','cg','designer'])
 def test_remote_designer_keeps_verification_budget_conflict_checks(self):
  sid=core.register(self.profile('designer'));slot={'id':'synthetic','order_id':'simple','role':'designer','skills':'["cg"]','budget':12000}
  def eligible():
   with core.connect() as c:return sid in [s['id'] for s in core.candidates(c,slot)]
  self.assertFalse(eligible())
  with core.connect() as c:c.execute('UPDATE specialist SET verified=1 WHERE id=?',(sid,))
  self.assertTrue(eligible());slot['budget']=9999;self.assertFalse(eligible());slot['budget']=12000
  core.block(sid,'2026-12-01T08:00','2026-12-01T09:00','UTC');self.assertFalse(eligible())
 def test_new_roles_multiselect_done_duplicate_stale_and_wrong_actor(self):
  with core.connect() as c:
   c.execute('INSERT INTO bot_state VALUES(42,2,?)',(json.dumps({'name':'TEST','city':'Москва'}),));ui=bot.prompt(42,c)
  texts=[r[0]['text'] for r in ui['reply_markup']['inline_keyboard']]
  for label in EXTRA.values():self.assertIn(label,texts)
  self.assertIn('Готово →',texts);nonce=ui['reply_markup']['inline_keyboard'][0][0]['callback_data'].split(':')[0]
  def click(i,action,actor=42):
   event={'update_id':i,'callback_query':{'id':'test-'+str(i),'from':{'id':actor},'message':{'message_id':100,'chat':{'id':42,'type':'private'}},'data':nonce+':'+action}}
   return event,bot.process_update(event)
  click(100,'8',99)
  with core.connect() as c:self.assertEqual(json.loads(c.execute('SELECT payload FROM bot_state WHERE telegram_id=42').fetchone()[0])['_selected'],[])
  for i,role in enumerate(EXTRA,101):
   event,reply=click(i,str(core.ROLES.index(role)));self.assertEqual(bot.process_update(event),reply)
  event,reply=click(120,'done');self.assertEqual(bot.process_update(event),reply)
  with core.connect() as c:
   row=c.execute('SELECT * FROM bot_state WHERE telegram_id=42').fetchone();self.assertEqual(row['step'],3);self.assertEqual(json.loads(row['payload'])['roles'],list(EXTRA))
  _,reply=click(121,'done');self.assertIn('устарела',reply)
  with core.connect() as c:self.assertEqual(c.execute('SELECT step FROM bot_state WHERE telegram_id=42').fetchone()[0],3)
if __name__=='__main__':unittest.main(verbosity=2)
