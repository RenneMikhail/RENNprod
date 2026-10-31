import pathlib,tempfile,unittest
from unittest.mock import patch
import core,question_delivery

class QuestionDeliveryTests(unittest.TestCase):
 def test_only_assigned_manager_retry_and_no_private_text(self):
  with tempfile.TemporaryDirectory() as d,patch.object(core,'DB',pathlib.Path(d)/'test.db'):
   core.init();core.seed()
   with core.connect() as c:
    people=c.execute('SELECT id FROM specialist LIMIT 2').fetchall()
    employee,manager=[p[0] for p in people]
    c.execute('UPDATE specialist SET telegram_id=4242 WHERE id=?',(manager,))
    slot=c.execute('SELECT id,order_id FROM role_slot LIMIT 1').fetchone()
    c.execute('INSERT INTO offer VALUES(?,?,?,?,?,?,?)',('q-offer',slot['id'],employee,1,'{}','2099-01-01','pending'))
    question_delivery.schema(c)
    c.execute('INSERT INTO employee_question VALUES(?,?,?,?,?,?)',('question1',employee,'q-offer','PRIVATE QUESTION',core.now(),'key'))
   with patch.object(question_delivery.bot,'call') as send:
    question_delivery.flush();send.assert_not_called()
   with core.connect() as c:
    c.execute("DELETE FROM manager_acceptance WHERE order_id=?",(slot['order_id'],))
    c.execute('INSERT INTO manager_acceptance VALUES(?,?,?,?)',('manager-q',slot['order_id'],manager,'accepted'))
   with patch.object(question_delivery.bot,'call',side_effect=RuntimeError('offline')):
    self.assertEqual(question_delivery.flush()['sent'],0)
   with patch.object(question_delivery.bot,'call',return_value={}) as send:
    self.assertEqual(question_delivery.flush()['sent'],1)
    self.assertEqual(send.call_args.args[1]['chat_id'],4242)
    self.assertNotIn('PRIVATE QUESTION',send.call_args.args[1]['text'])
    question_delivery.flush();self.assertEqual(send.call_count,1)

class QuestionVisibilityTests(unittest.TestCase):
 def test_owner_assigned_manager_and_sensitive_text(self):
  with tempfile.TemporaryDirectory() as d,patch.object(core,'DB',pathlib.Path(d)/'test.db'):
   core.init();core.seed()
   with core.connect() as c:
    employee,manager=[p[0] for p in c.execute('SELECT id FROM specialist LIMIT 2')]
    slot=c.execute('SELECT id,order_id FROM role_slot LIMIT 1').fetchone()
    c.execute('INSERT INTO offer VALUES(?,?,?,?,?,?,?)',('visible-offer',slot['id'],employee,1,'{}','2099-01-01','pending'))
    question_delivery.schema(c)
    c.execute('INSERT INTO employee_question VALUES(?,?,?,?,?,?)',('visible-question',employee,'visible-offer','PRIVATE QUESTION',core.now(),'key'))
    c.execute('DELETE FROM manager_acceptance WHERE order_id=?',(slot['order_id'],))
    c.execute('INSERT INTO manager_acceptance VALUES(?,?,?,?)',('assigned',slot['order_id'],manager,'accepted'))
    owner={'role':'owner','permissions':['*']}
    actor={'role':'manager','specialist_id':manager,'permissions':['tasks:read']}
    self.assertEqual(question_delivery.list_questions(c,owner)[0]['body'],'PRIVATE QUESTION')
    rows=question_delivery.list_questions(c,actor)
    self.assertEqual(len(rows),1);self.assertNotIn('body',rows[0]);self.assertIn('city',rows[0])
    actor['permissions']+=['contacts:read','finances:read']
    self.assertEqual(question_delivery.list_questions(c,actor)[0]['body'],'PRIVATE QUESTION')
    actor['specialist_id']='other'
    self.assertEqual(question_delivery.list_questions(c,actor),[])
    self.assertEqual(question_delivery.list_questions(c,{'role':'employee','permissions':['*']}),[])
