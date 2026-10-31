import pathlib,tempfile,unittest
from unittest.mock import patch
import core,staff_delivery

class StaffDeliveryTests(unittest.TestCase):
 def test_retry_private_delivery_and_expiry(self):
  with tempfile.TemporaryDirectory() as d,patch.object(core,'DB',pathlib.Path(d)/'test.db'):
   core.init();core.seed()
   with core.connect() as c:
    sid=c.execute('SELECT id FROM specialist LIMIT 1').fetchone()[0]
    c.execute('UPDATE specialist SET telegram_id=42 WHERE id=?',(sid,))
    slot=c.execute('SELECT id FROM role_slot LIMIT 1').fetchone()[0]
    c.execute('INSERT INTO offer VALUES(?,?,?,?,?,?,?)',('delivery-test',slot,sid,1,'{}','2099-01-01','pending'))
    core.enqueue(c,'order-test',sid,'offer:delivery-test','2099-01-01')
   calls=[]
   def send(method,payload):
    calls.append(payload)
    with core.connect() as other:other.execute('CREATE TABLE IF NOT EXISTS transport_probe(id INTEGER)')
    if len(calls)==1:raise RuntimeError('offline')
    return {}
   with patch.object(staff_delivery.bot,'call',side_effect=send):
    staff_delivery.flush();staff_delivery.flush();staff_delivery.flush()
   self.assertEqual(len(calls),2)
   self.assertEqual(calls[0]['chat_id'],42)
   self.assertEqual(calls[0]['reply_markup']['inline_keyboard'][0][0]['callback_data'],'offer:delivery-test:1:a')
   with core.connect() as c:
    self.assertEqual(c.execute('SELECT status FROM notification').fetchone()[0],'sent')
    c.execute("UPDATE notification SET status='queued'")
    c.execute("UPDATE offer SET status='expired'")
   with patch.object(staff_delivery.bot,'call') as transport:
    staff_delivery.flush();transport.assert_not_called()
