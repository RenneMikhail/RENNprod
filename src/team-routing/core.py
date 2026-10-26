"""Ren Prod local routing domain. No external dependencies."""
import sqlite3, json, uuid
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
ROOT = Path(__file__).resolve().parent
DB = ROOT / 'data' / 'routing.sqlite3'
ROLES = ['camera','editor','sound','manager','generative','event','cg','fpv']
SKILLS = ['interview','multicam','color','sound','editing','generation','coordination','cg','fpv']
TASKS = ['shoot','edit','generate','event']
def now(): return datetime.now(timezone.utc).isoformat()
def uid(): return str(uuid.uuid4())
class Connection(sqlite3.Connection):
    def __exit__(self,*args):
        try:return super().__exit__(*args)
        finally:self.close()
def connect(path=None):
    c=sqlite3.connect(str(path or DB),timeout=20,isolation_level=None,factory=Connection)
    c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');c.execute('PRAGMA journal_mode=WAL');return c
def init(path=None):
    (ROOT/'data').mkdir(exist_ok=True)
    with connect(path) as c: c.executescript('''
    CREATE TABLE IF NOT EXISTS specialist(id TEXT PRIMARY KEY,name TEXT NOT NULL,profile TEXT NOT NULL,verified INTEGER NOT NULL DEFAULT 0,telegram_id INTEGER UNIQUE,created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS skill(code TEXT PRIMARY KEY);
    CREATE TABLE IF NOT EXISTS availability(id TEXT PRIMARY KEY,specialist_id TEXT REFERENCES specialist(id),start TEXT,end TEXT,timezone TEXT,active INTEGER DEFAULT 1,CHECK(start<end));
    CREATE TABLE IF NOT EXISTS orders(id TEXT PRIMARY KEY,title TEXT,kind TEXT,city TEXT,start TEXT,end TEXT,brief TEXT,auto_assign INTEGER DEFAULT 0,status TEXT DEFAULT 'open',version INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS role_slot(id TEXT PRIMARY KEY,order_id TEXT REFERENCES orders(id),role TEXT,skills TEXT,budget INTEGER,status TEXT DEFAULT 'open');
    CREATE TABLE IF NOT EXISTS offer(id TEXT PRIMARY KEY,slot_id TEXT REFERENCES role_slot(id),specialist_id TEXT REFERENCES specialist(id),version INTEGER,terms TEXT,deadline TEXT,status TEXT DEFAULT 'pending',UNIQUE(slot_id,specialist_id,version));
    CREATE TABLE IF NOT EXISTS assignment(id TEXT PRIMARY KEY,slot_id TEXT UNIQUE REFERENCES role_slot(id),specialist_id TEXT REFERENCES specialist(id),offer_id TEXT UNIQUE REFERENCES offer(id),confirmed_at TEXT);
    CREATE TABLE IF NOT EXISTS manager_acceptance(id TEXT PRIMARY KEY,order_id TEXT REFERENCES orders(id),specialist_id TEXT REFERENCES specialist(id),status TEXT DEFAULT 'pending',UNIQUE(order_id,specialist_id));
    CREATE UNIQUE INDEX IF NOT EXISTS one_manager ON manager_acceptance(order_id) WHERE status='accepted';
    CREATE TABLE IF NOT EXISTS workspace(id TEXT PRIMARY KEY,order_id TEXT UNIQUE REFERENCES orders(id),created_at TEXT);
    CREATE TABLE IF NOT EXISTS membership(workspace_id TEXT REFERENCES workspace(id),specialist_id TEXT REFERENCES specialist(id),role TEXT,PRIMARY KEY(workspace_id,specialist_id));
    CREATE TABLE IF NOT EXISTS notification(id TEXT PRIMARY KEY,order_id TEXT,specialist_id TEXT,event_key TEXT UNIQUE,channel TEXT,status TEXT DEFAULT 'queued',ack_at TEXT,deadline TEXT);
    CREATE TABLE IF NOT EXISTS command(id TEXT PRIMARY KEY,result TEXT);
    CREATE TABLE IF NOT EXISTS message(id TEXT PRIMARY KEY,workspace_id TEXT,specialist_id TEXT,body TEXT,created_at TEXT);
    CREATE TABLE IF NOT EXISTS intake(id TEXT PRIMARY KEY,kind TEXT,payload TEXT,created_at TEXT);
    CREATE TABLE IF NOT EXISTS bot_state(telegram_id INTEGER PRIMARY KEY,step INTEGER,payload TEXT);
    CREATE TABLE IF NOT EXISTS bot_meta(key TEXT PRIMARY KEY,value TEXT);
    '''); c.executemany('INSERT OR IGNORE INTO skill VALUES(?)',[(x,) for x in SKILLS])
def normalize_interval(start,end,tz):
    zone=ZoneInfo(tz)
    def cv(s):
        d=datetime.fromisoformat(s)
        if d.tzinfo is None:d=d.replace(tzinfo=zone)
        return d.astimezone(timezone.utc).isoformat()
    a,b=cv(start),cv(end)
    if a>=b:raise ValueError('Конец интервала должен быть позже начала')
    return a,b

def validate(p):
    required=['name','city','roles','skills','tasks','mobility','equipment','rate','currency','languages','email','timezone','portfolio','portfolio_role']
    missing=[x for x in required if not p.get(x)]
    if missing:raise ValueError('Заполните: '+', '.join(missing))
    if not set(p['roles'])<=set(ROLES) or not set(p['skills'])<=set(SKILLS) or not set(p['tasks'])<=set(TASKS):raise ValueError('Выберите варианты из справочника')
    if p['mobility'] not in ['city','travel','remote']:raise ValueError('Неверный формат работы')
    if p['currency'] not in ['RUB','EUR','USD']:raise ValueError('Неверная валюта')
    if p['equipment'] not in ['none','camera','camera_audio','studio']:raise ValueError('Неверная техника')
    if float(p['rate'])<=0:raise ValueError('Ставка должна быть положительной')
    if '@' not in p['email']:raise ValueError('Укажите email')
    if not p['portfolio'].startswith(('https://','http://')):raise ValueError('Нужна ссылка на портфолио')
    ZoneInfo(p['timezone'])
    p['contact_verified']=False
    return p

def register(p,telegram_id=None,path=None,dbconn=None):
    p=validate(dict(p));ident=uid()
    with (nullcontext(dbconn) if dbconn else connect(path)) as c:
        if telegram_id:
            old=c.execute('SELECT id FROM specialist WHERE telegram_id=?',(telegram_id,)).fetchone()
            if old:ident=old['id']
        c.execute('INSERT INTO specialist VALUES(?,?,?,0,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,profile=excluded.profile,verified=0',(ident,p['name'],json.dumps(p,ensure_ascii=False),telegram_id,now()))
    return ident

def busy(c,sid,start,end):
    return bool(c.execute("SELECT 1 FROM manager_acceptance m JOIN orders o ON o.id=m.order_id WHERE m.specialist_id=? AND m.status='accepted' AND o.start<? AND o.end>?",(sid,end,start)).fetchone() or c.execute('SELECT 1 FROM availability WHERE specialist_id=? AND active=1 AND start<? AND end>?',(sid,end,start)).fetchone() or c.execute('SELECT 1 FROM assignment a JOIN role_slot s ON s.id=a.slot_id JOIN orders o ON o.id=s.order_id WHERE a.specialist_id=? AND o.start<? AND o.end>?',(sid,end,start)).fetchone())
def block(sid,start,end,tz,path=None):
    a,b=normalize_interval(start,end,tz)
    with connect(path) as c:
        c.execute('BEGIN IMMEDIATE')
        if busy(c,sid,a,b):raise ValueError('Пересечение с занятостью или подтверждённым назначением')
        ident=uid();c.execute('INSERT INTO availability VALUES(?,?,?,?,?,1)',(ident,sid,a,b,tz));c.commit();return ident

def update_block(ident,sid,start=None,end=None,tz=None,path=None):
    with connect(path) as c:
        c.execute('BEGIN IMMEDIATE')
        old=c.execute('SELECT * FROM availability WHERE id=? AND specialist_id=?',(ident,sid)).fetchone()
        if not old:raise ValueError('Интервал не найден')
        c.execute('UPDATE availability SET active=0 WHERE id=?',(ident,))
        if start:
            a,b=normalize_interval(start,end,tz)
            if busy(c,sid,a,b):raise ValueError('Интервал конфликтует с назначением/занятостью')
            c.execute('UPDATE availability SET start=?,end=?,timezone=?,active=1 WHERE id=?',(a,b,tz,ident))
        c.commit()

def candidates(c,slot):
    o=c.execute('SELECT * FROM orders WHERE id=?',(slot['order_id'],)).fetchone();result=[]
    for s in c.execute('SELECT * FROM specialist WHERE verified=1 ORDER BY id'):
        p=json.loads(s['profile'])
        if slot['role'] not in p['roles'] or not set(json.loads(slot['skills']))<=set(p['skills']):continue
        if p['city']!=o['city'] and p['mobility'] not in ['travel','remote']:continue
        if p['mobility']=='remote' and slot['role'] not in ['editor','generative','cg']:continue
        if o['kind'] not in p['tasks'] or p['currency']!='RUB' or float(p['rate'])>slot['budget']:continue
        if busy(c,s['id'],o['start'],o['end']):continue
        result.append(s)
    return result

def enqueue(c,oid,sid,event,deadline):
    c.execute('INSERT OR IGNORE INTO notification VALUES(?,?,?,?,?,\'queued\',NULL,?)',(uid(),oid,sid,event,'telegram',deadline))
def deadline_work(hours=4,tz='Europe/Moscow',base=None):
    d=base or datetime.now(timezone.utc);zone=ZoneInfo(tz);minutes=int(hours*60)
    while minutes:
        d+=timedelta(minutes=1);local=d.astimezone(zone)
        if local.weekday()<5 and 9<=local.hour<18:minutes-=1
    return d.isoformat()

def route(oid,path=None):
    with connect(path) as c:
        c.execute('BEGIN IMMEDIATE');o=c.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone()
        slots=c.execute('SELECT * FROM role_slot WHERE order_id=?',(oid,)).fetchall()
        if not o or o['kind'] not in TASKS or not slots:
            c.execute("UPDATE orders SET status='human_review' WHERE id=?",(oid,));c.commit();return
        complex_order=len(slots)>1
        if complex_order:
            for s in c.execute('SELECT * FROM specialist WHERE verified=1'):
                if 'manager' in json.loads(s['profile'])['roles'] and not busy(c,s['id'],o['start'],o['end']):
                    c.execute('INSERT OR IGNORE INTO manager_acceptance VALUES(?,?,?,\'pending\')',(uid(),oid,s['id']));enqueue(c,oid,s['id'],'manager:'+oid+':'+s['id'],deadline_work())
            c.execute("UPDATE orders SET status='awaiting_manager' WHERE id=? AND status='open'",(oid,))
        for slot in slots:
            if slot['status']=='filled':continue
            pending=c.execute("SELECT 1 FROM offer WHERE slot_id=? AND status IN ('pending','responded')",(slot['id'],)).fetchone()
            if pending and not complex_order:continue
            for s in candidates(c,slot):
                if c.execute('SELECT 1 FROM offer WHERE slot_id=? AND specialist_id=? AND version=?',(slot['id'],s['id'],o['version'])).fetchone():continue
                p=json.loads(s['profile']);ident=uid();deadline=deadline_work(tz=p['timezone'])
                terms={'version':o['version'],'start':o['start'],'end':o['end'],'city':o['city'],'role':slot['role'],'fee':p['rate'],'currency':p['currency'],'deliverable':json.loads(o['brief'])['result']}
                c.execute('INSERT INTO offer VALUES(?,?,?,?,?,?,\'pending\')',(ident,slot['id'],s['id'],o['version'],json.dumps(terms),deadline));enqueue(c,oid,s['id'],'offer:'+ident,deadline)
                if not complex_order:break
        c.commit()

def transact(key,fn,path=None):
    with connect(path) as c:
        c.execute('BEGIN IMMEDIATE');old=c.execute('SELECT result FROM command WHERE id=?',(key,)).fetchone()
        if old:return json.loads(old['result'])
        result=fn(c);c.execute('INSERT INTO command VALUES(?,?)',(key,json.dumps(result)));c.commit();return result

def assign(c,offer):
    s=c.execute('SELECT * FROM role_slot WHERE id=?',(offer['slot_id'],)).fetchone();o=c.execute('SELECT * FROM orders WHERE id=?',(s['order_id'],)).fetchone()
    if offer['version']!=o['version']:raise ValueError('Условия изменились: нужно новое предложение')
    if c.execute('SELECT 1 FROM assignment WHERE slot_id=?',(s['id'],)).fetchone():raise ValueError('Место уже занято')
    if busy(c,offer['specialist_id'],o['start'],o['end']):raise ValueError('Конфликт занятости')
    if not c.execute('SELECT 1 FROM specialist WHERE id=? AND verified=1',(offer['specialist_id'],)).fetchone():raise ValueError('Нужна проверка квалификации')
    if len(c.execute('SELECT id FROM role_slot WHERE order_id=?',(o['id'],)).fetchall())>1 and not c.execute("SELECT 1 FROM manager_acceptance WHERE order_id=? AND status='accepted'",(o['id'],)).fetchone():raise ValueError('Руководство ещё не принято')
    c.execute('INSERT INTO assignment VALUES(?,?,?,?,?)',(uid(),s['id'],offer['specialist_id'],offer['id'],now()))
    c.execute("UPDATE offer SET status=CASE WHEN id=? THEN 'assigned' ELSE 'closed' END WHERE slot_id=? AND status IN ('pending','responded')",(offer['id'],s['id']))
    c.execute("UPDATE role_slot SET status='filled' WHERE id=?",(s['id'],))
    w=c.execute('SELECT id FROM workspace WHERE order_id=?',(o['id'],)).fetchone()
    if not w:
        wid=uid();c.execute('INSERT INTO workspace VALUES(?,?,?)',(wid,o['id'],now()))
    else:wid=w['id']
    c.execute('INSERT OR IGNORE INTO membership VALUES(?,?,?)',(wid,offer['specialist_id'],s['role']))
    remaining=c.execute("SELECT 1 FROM role_slot WHERE order_id=? AND status!='filled'",(o['id'],)).fetchone()
    c.execute('UPDATE orders SET status=? WHERE id=?',('staffing' if remaining else 'staffed',o['id']))
    enqueue(c,o['id'],offer['specialist_id'],'assigned:'+offer['id'],deadline_work())
    return {'status':'assigned'}

def respond(offer_id,sid,decision,version,key,path=None):
    def run(c):
        x=c.execute('SELECT * FROM offer WHERE id=? AND specialist_id=?',(offer_id,sid)).fetchone()
        if not x or x['status']!='pending':raise ValueError('Предложение недоступно')
        if x['deadline']<=now():raise ValueError('Срок ответа истёк')
        if x['version']!=int(version):raise ValueError('Подтвердите актуальную версию')
        if decision not in ['accept','decline']:raise ValueError('Неверный ответ')
        o=c.execute('SELECT o.* FROM orders o JOIN role_slot s ON o.id=s.order_id WHERE s.id=?',(x['slot_id'],)).fetchone()
        if o['version']!=x['version']:raise ValueError('Условия изменились')
        if decision=='decline':c.execute("UPDATE offer SET status='declined' WHERE id=?",(offer_id,));return {'status':'declined','order_id':o['id']}
        count=c.execute('SELECT count(*) FROM role_slot WHERE order_id=?',(o['id'],)).fetchone()[0]
        if count==1 and o['auto_assign']:return assign(c,x)
        c.execute("UPDATE offer SET status='responded' WHERE id=?",(offer_id,));return {'status':'responded','order_id':o['id']}
    r=transact(key,run,path)
    if r['status']=='declined':route(r['order_id'],path)
    return r

def manager_accept(ident,sid,key,path=None):
    def run(c):
        m=c.execute("SELECT * FROM manager_acceptance WHERE id=? AND specialist_id=? AND status='pending'",(ident,sid)).fetchone()
        if not m:raise ValueError('Приглашение недоступно')
        o=c.execute('SELECT * FROM orders WHERE id=?',(m['order_id'],)).fetchone()
        if busy(c,sid,o['start'],o['end']):raise ValueError('Менеджер занят')
        if c.execute("SELECT 1 FROM manager_acceptance WHERE order_id=? AND status='accepted'",(o['id'],)).fetchone():raise ValueError('Руководитель уже принят')
        c.execute("UPDATE manager_acceptance SET status=CASE WHEN id=? THEN 'accepted' ELSE 'closed' END WHERE order_id=?",(ident,o['id']))
        wid=uid();c.execute('INSERT INTO workspace VALUES(?,?,?)',(wid,o['id'],now()));c.execute('INSERT INTO membership VALUES(?,?,?)',(wid,sid,'manager'));c.execute("UPDATE orders SET status='staffing' WHERE id=?",(o['id'],));return {'status':'accepted'}
    return transact(key,run,path)

def select_offer(ident,manager,key,path=None):
    def run(c):
        x=c.execute("SELECT * FROM offer WHERE id=? AND status='responded'",(ident,)).fetchone()
        if not x:raise ValueError('Нужен подтверждённый отклик')
        o=c.execute('SELECT order_id FROM role_slot WHERE id=?',(x['slot_id'],)).fetchone()[0]
        if manager!='owner' and not c.execute("SELECT 1 FROM manager_acceptance WHERE order_id=? AND specialist_id=? AND status='accepted'",(o,manager)).fetchone():raise ValueError('Нет прав руководителя')
        return assign(c,x)
    return transact(key,run,path)

def tick(path=None):
    with connect(path) as c:
        c.execute('BEGIN IMMEDIATE')
        ids=[r[0] for r in c.execute("SELECT DISTINCT s.order_id FROM offer f JOIN role_slot s ON s.id=f.slot_id WHERE f.status='pending' AND f.deadline<=?",(now(),))]
        c.execute("UPDATE offer SET status='expired' WHERE status='pending' AND deadline<=?",(now(),))
        c.execute("UPDATE notification SET channel='email',status='queued' WHERE ack_at IS NULL AND channel='telegram' AND deadline<=?",(now(),));c.commit()
    for oid in ids:route(oid,path)
    return {'expired_orders':len(ids)}

def workspace_view(oid,sid,path=None):
    with connect(path) as c:
        w=c.execute('SELECT * FROM workspace WHERE order_id=?',(oid,)).fetchone()
        if not w:raise ValueError('Пространство ещё не создано')
        if sid!='owner' and not c.execute('SELECT 1 FROM membership WHERE workspace_id=? AND specialist_id=?',(w['id'],sid)).fetchone():raise ValueError('Доступ только назначенным участникам')
        o=c.execute('SELECT * FROM orders WHERE id=?',(oid,)).fetchone()
        return {'id':w['id'],'title':o['title'],'start':o['start'],'end':o['end'],'brief':json.loads(o['brief']),'members':[dict(x) for x in c.execute('SELECT s.name,m.role FROM membership m JOIN specialist s ON s.id=m.specialist_id WHERE m.workspace_id=?',(w['id'],))],'discussion':[dict(x) for x in c.execute('SELECT body,created_at FROM message WHERE workspace_id=?',(w['id'],))]}

def seed(path=None):
    with connect(path) as c:
        if c.execute('SELECT 1 FROM orders').fetchone():return
    for i,(name,roles,skills) in enumerate([('Демо · Анна',['camera'],['interview','multicam']),('Демо · Борис',['camera'],['interview']),('Демо · Вера',['editor'],['editing','color']),('Демо · Глеб',['manager'],['coordination'])]):
        p={'name':name,'city':'Москва','roles':roles,'skills':skills,'tasks':TASKS,'mobility':'city','equipment':'camera','rate':12000,'currency':'RUB','languages':['ru'],'email':f'demo{i}@example.invalid','telegram':'','phone':'','timezone':'Europe/Moscow','portfolio':'https://example.invalid/portfolio','portfolio_role':roles[0]}
        sid=register(p,path=path)
        with connect(path) as c:c.execute('UPDATE specialist SET verified=1 WHERE id=?',(sid,))
    with connect(path) as c:
        for oid,title,kind,roles,auto in [('simple','Интервью · один оператор','shoot',['camera'],1),('crew','Событие · команда','shoot',['camera','camera','editor'],0),('unknown','Нестандартная идея','unknown',['generative'],0)]:
            brief={'address':'Демо-студия, ул. Примерная, 1','task':'Записать интервью / событие','result':'Исходники + согласованный ролик','deadline':'2026-12-15','responsible':'Владелец; менеджер после принятия','materials':['Тестовый бриф, реальные файлы не загружены']}
            c.execute('INSERT INTO orders VALUES(?,?,?,?,?,?,?,?,?,1)',(oid,title,kind,'Москва','2026-12-01T07:00:00+00:00','2026-12-01T15:00:00+00:00',json.dumps(brief,ensure_ascii=False),auto,'open'))
            for j,r in enumerate(roles):c.execute('INSERT INTO role_slot VALUES(?,?,?,?,?,\'open\')',(oid+'-'+str(j),oid,r,json.dumps(['editing'] if r=='editor' else ['interview'] if r=='camera' else ['generation']),18000))
