import unittest,tempfile,pathlib,json,concurrent.futures
import core,bot
from unittest.mock import patch
class RoutingTests(unittest.TestCase):
    def setUp(self):
        (core.ROOT/'data').mkdir(exist_ok=True);self.temp=tempfile.TemporaryDirectory(dir=core.ROOT/'data');self.db=pathlib.Path(self.temp.name)/'test.db';core.init(self.db);core.seed(self.db)
    def tearDown(self):self.temp.cleanup()
    def rows(self,sql,args=()):
        with core.connect(self.db) as c:return [dict(r) for r in c.execute(sql,args)]
    def test_auto_and_idempotence(self):
        core.route('simple',self.db);o=self.rows('SELECT * FROM offer')[0]
        a=core.respond(o['id'],o['specialist_id'],'accept',1,'key',self.db)
        self.assertEqual(a,core.respond(o['id'],o['specialist_id'],'accept',1,'key',self.db));self.assertEqual(len(self.rows('SELECT * FROM assignment')),1)
    def test_decline_next_and_timeout(self):
        core.route('simple',self.db);o=self.rows('SELECT * FROM offer')[0];core.respond(o['id'],o['specialist_id'],'decline',1,'decl',self.db)
        self.assertEqual(len(self.rows('SELECT * FROM offer')),2)
        with core.connect(self.db) as c:c.execute("UPDATE offer SET deadline='2000-01-01' WHERE status='pending'")
        core.tick(self.db);self.assertFalse(self.rows("SELECT * FROM offer WHERE status='pending'"))
    def test_busy_interval_edit_cancel(self):
        s=self.rows("SELECT id FROM specialist WHERE name LIKE '%Анна%'")[0]['id'];b=core.block(s,'2026-12-01T10:00','2026-12-01T12:00','Europe/Moscow',self.db)
        core.route('simple',self.db);self.assertNotEqual(self.rows('SELECT * FROM offer')[0]['specialist_id'],s)
        core.update_block(b,s,'2026-12-02T10:00','2026-12-02T12:00','Europe/Moscow',self.db);core.update_block(b,s,path=self.db)
        self.assertEqual(self.rows('SELECT active FROM availability')[0]['active'],0)
    def test_multi_manager_and_finance_privacy(self):
        core.route('crew',self.db);offers=self.rows('SELECT * FROM offer');o=offers[0]
        core.respond(o['id'],o['specialist_id'],'accept',1,'reply',self.db)
        with self.assertRaises(ValueError):core.select_offer(o['id'],'owner','early',self.db)
        m=self.rows('SELECT * FROM manager_acceptance')[0];core.manager_accept(m['id'],m['specialist_id'],'manager',self.db)
        core.select_offer(o['id'],m['specialist_id'],'select',self.db)
        self.assertEqual(self.rows("SELECT status FROM orders WHERE id='crew'")[0]['status'],'staffing')
        v=core.workspace_view('crew',m['specialist_id'],self.db);self.assertNotIn('fee',json.dumps(v));self.assertNotIn('budget',json.dumps(v));self.assertNotIn('rate',json.dumps(v))
        stranger=next(s['id'] for s in self.rows('SELECT * FROM specialist') if s['id'] not in [m['specialist_id'],o['specialist_id']])
        with self.assertRaises(ValueError):core.workspace_view('crew',stranger,self.db)
    def test_race_same_slot(self):
        core.route('crew',self.db);m=self.rows('SELECT * FROM manager_acceptance')[0];core.manager_accept(m['id'],m['specialist_id'],'m',self.db)
        offers=self.rows("SELECT * FROM offer WHERE slot_id='crew-0'")
        for o in offers:core.respond(o['id'],o['specialist_id'],'accept',1,'r'+o['id'],self.db)
        def choose(o):
            try:return core.select_offer(o['id'],m['specialist_id'],'s'+o['id'],self.db)['status']
            except ValueError:return 'rejected'
        with concurrent.futures.ThreadPoolExecutor(2) as pool:r=list(pool.map(choose,offers))
        self.assertEqual(r.count('assigned'),1);self.assertEqual(len(self.rows("SELECT * FROM assignment WHERE slot_id='crew-0'")),1)
    def test_overlap_assignments_and_stale_terms(self):
        core.route('crew',self.db);m=self.rows('SELECT * FROM manager_acceptance')[0];core.manager_accept(m['id'],m['specialist_id'],'m',self.db)
        a=self.rows("SELECT * FROM offer WHERE slot_id='crew-0'")[0];b=self.rows("SELECT * FROM offer WHERE slot_id='crew-1' AND specialist_id=?",(a['specialist_id'],))[0]
        for o in [a,b]:core.respond(o['id'],o['specialist_id'],'accept',1,'r'+o['id'],self.db)
        core.select_offer(a['id'],'owner','a',self.db)
        with self.assertRaises(ValueError):core.select_offer(b['id'],'owner','b',self.db)
        with self.assertRaises(ValueError):core.block(a['specialist_id'],'2026-12-01T11:00','2026-12-01T12:00','Europe/Moscow',self.db)
        core.route('simple',self.db);o=self.rows("SELECT * FROM offer WHERE status='pending' AND slot_id='simple-0'")
        if o:
            with core.connect(self.db) as c:c.execute("UPDATE orders SET version=2 WHERE id='simple'")
            with self.assertRaises(ValueError):core.respond(o[0]['id'],o[0]['specialist_id'],'accept',1,'stale',self.db)
    def test_unknown_and_working_hours(self):
        core.route('unknown',self.db);self.assertEqual(self.rows("SELECT status FROM orders WHERE id='unknown'")[0]['status'],'human_review')
        d=core.deadline_work(1,'Europe/Moscow',core.datetime.fromisoformat('2026-10-23T15:30:00+00:00'));self.assertTrue(d.startswith('2026-10-26'))
    def test_full_bot_registration_and_duplicate_update(self):
        with patch.object(core,'DB',self.db):
            def send(i,text):
                u={'update_id':i,'message':{'chat':{'id':12345,'type':'private'},'from':{'id':12345,'username':'test_only'},'text':text}}
                return bot.process_update(u)
            first=send(100,'/start');self.assertEqual(first,send(100,'/start'))
            answers=['TEST bot','Москва','camera','interview','shoot','city','none','10000','RUB','ru','bot-test@example.invalid','-','Europe/Moscow','https://example.invalid/test','Camera operator','ДА']
            for i,answer in enumerate(answers,101):reply=send(i,answer)
            self.assertIn('Анкета сохранена',reply)
            self.assertEqual(reply,send(116,'ДА'))
            row=self.rows('SELECT * FROM specialist WHERE telegram_id=12345')[0]
            self.assertEqual(row['verified'],0);self.assertFalse(json.loads(row['profile'])['contact_verified'])
            self.assertIn('Занятость сохранена',send(117,'/busy 2026-12-02T10:00|2026-12-02T12:00|Europe/Moscow'))
            block=self.rows('SELECT id FROM availability WHERE specialist_id=?',(row['id'],))[0]['id']
            self.assertIn('отменена',send(118,'/unblock '+block))
    def test_stale_terms_and_unauthorized_reply(self):
        core.route('simple',self.db);o=self.rows('SELECT * FROM offer')[0]
        with self.assertRaises(ValueError):core.respond(o['id'],'stranger','accept',1,'bad-actor',self.db)
        with core.connect(self.db) as c:c.execute("UPDATE orders SET version=2 WHERE id='simple'")
        with self.assertRaises(ValueError):core.respond(o['id'],o['specialist_id'],'accept',1,'old-version',self.db)
    def test_bot_validation(self):
        self.assertEqual(bot.parse_field('roles','camera, editor'),['camera','editor'])
        with self.assertRaises(ValueError):bot.parse_field('roles','#expert')
if __name__=='__main__':unittest.main(verbosity=2)
