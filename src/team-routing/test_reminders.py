import unittest, tempfile, pathlib, json, uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
import core, auth, reminders, documents, telegram_link

class ReminderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); r = pathlib.Path(self.tmp.name)
        self.patches = [patch.object(core, 'DB', r / 'core.sqlite'), patch.object(auth, 'DB', r / 'auth.sqlite')]
        for p in self.patches: p.start()
        core.init(); auth.init()
        self.owner = auth.create_user('owner', 'test-password-long', 'owner')
        self.mgr_a = auth.create_user('mgr-a', 'test-password-long', 'manager')
        self.mgr_b = auth.create_user('mgr-b', 'test-password-long', 'manager')
        with core.connect() as c:
            reminders.schema(c); telegram_link.schema(c)
            c.execute("INSERT INTO telegram_account VALUES(?,?)", (self.mgr_a, 7001))
            c.execute("INSERT INTO orders(id,title,kind,city,start,end,brief) VALUES('o1','Проект A','shoot','Москва','2026-12-01T07:00:00+00:00','2026-12-01T15:00:00+00:00','{}')")
            c.execute("INSERT INTO orders(id,title,kind,city,start,end,brief) VALUES('o2','Проект B','shoot','Москва','2026-12-02T07:00:00+00:00','2026-12-02T15:00:00+00:00','{}')")
            documents.assign_order_manager(c, 'o1', self.mgr_a)
            documents.assign_order_manager(c, 'o2', self.mgr_b)
            for i, contact in enumerate(['@same', '@same', '@other']):
                c.execute("INSERT INTO intake(id,kind,payload,created_at) VALUES(?,?,?,?)", ('i%d' % i, 'client', json.dumps({'contact': contact}), core.now()))
            c.commit()

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.tmp.cleanup()

    def test_offer_window_is_two_weeks(self):
        d = datetime.fromisoformat(core.offer_deadline())
        self.assertAlmostEqual((d - datetime.now(timezone.utc)).total_seconds(), 14 * 86400, delta=60)

    def test_default_time_and_validation(self):
        with core.connect() as c:
            self.assertEqual(reminders.get_time(c, self.mgr_a), '10:00')
            self.assertEqual(reminders.set_time(c, {'id': self.mgr_a, 'role': 'manager'}, '09:30')['time'], '09:30')
            self.assertEqual(reminders.get_time(c, self.mgr_a), '09:30')
            with self.assertRaises(ValueError): reminders.set_time(c, {'id': self.mgr_a, 'role': 'manager'}, '25:00')
            with self.assertRaises(PermissionError): reminders.set_time(c, {'id': 'x', 'role': 'employee'}, '10:00')

    def test_manager_sees_only_own_projects_and_repeat_contacts(self):
        with core.connect() as c:
            d = reminders.digest(c, {'id': self.mgr_a, 'role': 'manager'})
            self.assertEqual([p['order_id'] for p in d['no_role']], ['o1'])
            self.assertEqual(d['repeats'][0]['contact'], '@same')
            self.assertEqual(d['repeats'][0]['count'], 2)
            owner = reminders.digest(c, {'id': self.owner, 'role': 'owner'})
            self.assertEqual(len(owner['no_role']), 2)

    def test_reminder_is_sent_once_per_day_at_manager_time(self):
        sent = []
        sender = lambda tg, text: sent.append((tg, text))
        before = datetime(2026, 11, 2, 6, 59, tzinfo=timezone.utc)   # 07:59 Moscow
        at = datetime(2026, 11, 2, 7, 0, tzinfo=timezone.utc)        # 10:00 Moscow
        with core.connect() as c:
            self.assertEqual(reminders.flush(c, sender, before), 0)
            self.assertEqual(reminders.flush(c, sender, at), 1)
            self.assertEqual(reminders.flush(c, sender, at + timedelta(minutes=5)), 0)
            self.assertEqual(sent[0][0], 7001)
            self.assertIn('Проекты без роли', sent[0][1])

    def test_failed_send_is_retried(self):
        def broken(tg, text): raise RuntimeError('network')
        at = datetime(2026, 11, 2, 7, 0, tzinfo=timezone.utc)
        with core.connect() as c:
            self.assertEqual(reminders.flush(c, broken, at), 0)
            self.assertEqual(reminders.flush(c, lambda tg, t: None, at), 1)

if __name__ == '__main__':
    unittest.main()
