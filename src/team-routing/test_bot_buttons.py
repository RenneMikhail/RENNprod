import unittest,tempfile,pathlib,json
from unittest.mock import patch
import core,bot
class ButtonTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.db=pathlib.Path(self.tmp.name)/'t.sqlite';core.init(self.db);self.p=patch.object(core,'DB',self.db);self.p.start();self.i=0
 def tearDown(self):self.p.stop();self.tmp.cleanup()
 def send(self,text):
  self.i+=1;return bot.process_update({'update_id':self.i,'message':{'chat':{'id':42,'type':'private'},'from':{'id':42},'text':text}})
 def state(self):
  with core.connect() as c:return dict(c.execute('SELECT * FROM bot_state WHERE telegram_id=42').fetchone())
 def click(self,action,nonce=None,ident=42):
  self.i+=1;p=json.loads(self.state()['payload']);q={'id':str(self.i),'from':{'id':ident},'message':{'message_id':100,'chat':{'id':42,'type':'private'}},'data':(nonce or p['_ui_nonce'])+':'+action};u={'update_id':self.i,'callback_query':q};return bot.process_update(u),u
 def roles(self):self.send('/start');self.send('TEST');self.send('Москва')
 def test_multiselect_and_repeat(self):
  self.roles();before=self.state()['step'];result,u=self.click('0');self.assertEqual(bot.process_update(u),result)
  self.assertEqual(json.loads(self.state()['payload'])['_selected'],['camera']);self.assertEqual(self.state()['step'],before)
  self.click('done');self.assertEqual(json.loads(self.state()['payload'])['roles'],['camera']);self.assertEqual(self.state()['step'],before+1)
 def test_empty_stale_and_other_actor(self):
  self.roles();nonce=json.loads(self.state()['payload'])['_ui_nonce'];step=self.state()['step'];self.click('done');self.assertEqual(self.state()['step'],step)
  self.click('0',ident=99);self.assertEqual(json.loads(self.state()['payload'])['_selected'],[])
  self.send('/start');self.send('TEST');self.send('Москва');self.click('0',nonce=nonce);self.assertEqual(json.loads(self.state()['payload'])['_selected'],[])
 def test_new_roles_and_keyboard(self):
  self.roles()
  with core.connect() as c:ui=bot.prompt(42,c)
  texts=[r[0]['text'] for r in ui['reply_markup']['inline_keyboard']]
  for name in ['CG-специалист','AI-генератор','FPV-дронщик']:self.assertIn(name,texts)
  self.assertEqual(bot.parse_field('roles','cg,fpv,generative'),['cg','fpv','generative'])
if __name__=='__main__':unittest.main()
