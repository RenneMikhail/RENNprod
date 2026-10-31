import json,tempfile,pathlib,unittest
from unittest.mock import patch
import core,bot
class BotOfferTests(unittest.TestCase):
 def test_offer_buttons_are_private_and_versioned(self):
  with tempfile.TemporaryDirectory(dir=core.ROOT) as d, patch.object(core,'DB',pathlib.Path(d)/'test.db'):
   core.init();core.seed()
   with core.connect() as c:
    sid=c.execute('SELECT id FROM specialist LIMIT 1').fetchone()[0]
    c.execute('UPDATE specialist SET telegram_id=42 WHERE id=?',(sid,))
    slot=c.execute('SELECT id FROM role_slot LIMIT 1').fetchone()[0]
    c.execute('INSERT INTO offer VALUES(?,?,?,?,?,?,?)',('offer-test',slot,sid,1,'{}','2099-01-01','pending'))
   message={'from':{'id':42},'chat':{'id':42,'type':'private'},'text':'/offers'}
   reply=bot.handle(message)
   self.assertIsInstance(reply,dict)
   data=reply['reply_markup']['inline_keyboard'][0][0]['callback_data']
   def click(actor,update):
    return bot.process_update({'update_id':update,'callback_query':{'from':{'id':actor},'message':{'chat':{'id':actor,'type':'private'}},'data':data}})
   self.assertIn('недоступно',click(99,1).lower())
   self.assertIn('принят',click(42,2).lower())
   self.assertEqual(click(42,2),click(42,2))
   self.assertIn('недоступно',click(42,3).lower())
   message['chat']['type']='group'
   self.assertIsNone(bot.handle(message))
   with core.connect() as c:self.assertEqual(c.execute('SELECT status FROM offer WHERE id=?',('offer-test',)).fetchone()[0],'responded')
