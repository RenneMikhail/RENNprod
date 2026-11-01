"""Transactional intake/outbox; Telegram transport uses environment variables only."""
import json,os,urllib.request,threading
_flush_lock=threading.Lock()
import core,auth

def schema(c):
    c.execute('CREATE TABLE IF NOT EXISTS intake_request(key TEXT PRIMARY KEY,intake_id TEXT NOT NULL)')
    c.execute("CREATE TABLE IF NOT EXISTS intake_outbox(intake_id TEXT PRIMARY KEY,status TEXT NOT NULL DEFAULT 'queued',attempts INTEGER NOT NULL DEFAULT 0)")

def recipients(c):
    chat=os.environ.get("RENN_MANAGER_CHAT_ID")
    if chat:return [str(chat)]
    if not c.execute("SELECT 1 FROM sqlite_master WHERE name='telegram_account'").fetchone() or not auth.DB.exists():return []
    with auth.connect() as accounts:
        active={r[0] for r in accounts.execute("SELECT id FROM account WHERE active=1 AND role IN ('owner','manager')")}
    return sorted({str(r[1]) for r in c.execute("SELECT account_id,telegram_id FROM telegram_account") if r[0] in active and r[1]>0})

def delivery_status(c):
    schema(c)
    counts=c.execute("SELECT COALESCE(SUM(status='queued' AND attempts<10),0),COALESCE(SUM(status='queued' AND attempts>=10),0),COALESCE(SUM(status='sent'),0) FROM intake_outbox").fetchone()
    return dict(configured=bool(os.environ.get('TELEGRAM_BOT_TOKEN') and recipients(c)),queued=counts[0],retry_exhausted=counts[1],sent=counts[2])

def retry_delivery(c,ident):
    if not isinstance(ident,str) or not 1<=len(ident)<=100:raise ValueError('Invalid intake id')
    schema(c)
    result=c.execute("UPDATE intake_outbox SET attempts=0 WHERE intake_id=? AND status='queued' AND attempts>=10",(ident,))
    if result.rowcount!=1:raise ValueError('No exhausted notification for this intake')

def list_intakes(c):
    c.execute("CREATE TABLE IF NOT EXISTS intake_lifecycle(intake_id TEXT PRIMARY KEY REFERENCES intake(id),status TEXT NOT NULL,updated_at TEXT NOT NULL)")
    c.execute('CREATE TABLE IF NOT EXISTS intake_project(intake_id TEXT PRIMARY KEY REFERENCES intake(id),order_id TEXT UNIQUE NOT NULL REFERENCES orders(id))')
    return [dict(r) for r in c.execute("SELECT i.*,COALESCE(l.status,'new') AS status,p.order_id FROM intake i LEFT JOIN intake_lifecycle l ON l.intake_id=i.id LEFT JOIN intake_project p ON p.intake_id=i.id ORDER BY i.created_at DESC")]

def set_status(c,ident,status):
    if status not in ('new','working','archive'):raise ValueError('Invalid status')
    if not c.execute('SELECT 1 FROM intake WHERE id=?',(ident,)).fetchone():raise ValueError('Intake not found')
    list_intakes(c)
    c.execute('INSERT INTO intake_lifecycle VALUES(?,?,?) ON CONFLICT(intake_id) DO UPDATE SET status=excluded.status,updated_at=excluded.updated_at',(ident,status,core.now()))

def create_project(c,p):
    title=p.get('title')
    if not isinstance(title,str) or not 1<=len(title.strip())<=160:raise ValueError('Project title required')
    if any(not isinstance(p.get(k),str) or not p[k].strip() for k in ('id','start','end','timezone')):raise ValueError('Schedule required')
    try:a,b=core.normalize_interval(p['start'],p['end'],p['timezone'])
    except (ValueError,KeyError,OverflowError):raise ValueError('Invalid schedule') from None
    list_intakes(c)
    c.execute('BEGIN IMMEDIATE')
    try:
        previous=c.execute('SELECT order_id FROM intake_project WHERE intake_id=?',(p['id'],)).fetchone()
        if previous:c.commit();return previous[0]
        row=c.execute('SELECT * FROM intake WHERE id=?',(p['id'],)).fetchone()
        if not row or row['kind']!='client':raise ValueError('Client intake required')
        state=c.execute('SELECT status FROM intake_lifecycle WHERE intake_id=?',(p['id'],)).fetchone()
        if state and state[0]=='archive':raise ValueError('Archived intake')
        payload=json.loads(row['payload']);city=payload.get('city','')
        if not isinstance(city,str) or not 1<=len(city.strip())<=120:raise ValueError('City required')
        ident=core.uid()
        brief=json.dumps({'intake_id':p['id'],'task':payload.get('idea','')},ensure_ascii=False)
        c.execute('INSERT INTO orders(id,title,kind,city,start,end,brief) VALUES(?,?,?,?,?,?,?)',(ident,title.strip(),task_kind(payload.get('service')),city.strip(),a,b,brief))
        c.execute('INSERT INTO intake_project VALUES(?,?)',(p['id'],ident))
        set_status(c,p['id'],'working')
        c.commit();return ident
    except Exception:
        c.rollback();raise

def save(c,p):
    if p.get('kind') not in ('client','brief','question'): raise ValueError('Invalid intake kind')
    if p.get('source')=='shooting-landing':
        if p.get('kind')!='client' or p.get('service') not in core_services or p.get('locale') not in ('ru','en'):
            raise ValueError('Invalid shooting enquiry')
        for key,limit in [('idea',1200),('contact',240),('city',120)]:
            if not isinstance(p.get(key),str) or not 1<=len(p[key].strip())<=limit: raise ValueError(key+' required')
        p={k:p[k] for k in ('kind','source','service','locale','idea','contact','city','test','request_id') if k in p}
    key=p.get('request_id')
    if key is not None and (not isinstance(key,str) or not 16<=len(key)<=100): raise ValueError('Invalid request_id')
    schema(c)
    c.execute('BEGIN IMMEDIATE')
    try:
        previous=c.execute('SELECT intake_id FROM intake_request WHERE key=?',(key,)).fetchone() if key else None
        if previous:
            stored=json.loads(c.execute('SELECT payload FROM intake WHERE id=?',(previous[0],)).fetchone()[0])
            if stored!=p: raise ValueError('request_id already used for different content')
            c.commit();return previous[0]
        ident=core.uid()
        c.execute('INSERT INTO intake VALUES(?,?,?,?)',(ident,p['kind'],json.dumps(p,ensure_ascii=False),core.now()))
        if key:c.execute('INSERT INTO intake_request VALUES(?,?)',(key,ident))
        c.execute('INSERT INTO intake_outbox(intake_id) VALUES(?)',(ident,))
        c.commit();return ident
    except Exception:
        c.rollback();raise

core_services=('professional','reels','commercial','art','editing','graphics','cg','ai')
# Proposed mapping (owner to confirm): a website service becomes a task type the routing understands.
SERVICE_TO_TASK={'professional':'shoot','reels':'shoot','commercial':'shoot','art':'shoot','editing':'edit','graphics':'generate','cg':'generate','ai':'generate'}
def task_kind(service):
    if service is None:return 'shoot'
    if not isinstance(service,str) or service not in SERVICE_TO_TASK:raise ValueError('Неизвестная услуга')
    return SERVICE_TO_TASK[service]

def flush():
    if not _flush_lock.acquire(blocking=False):return {'status':'busy','sent':0}
    try:return _flush()
    finally:_flush_lock.release()

def _flush():
    token=os.environ.get('TELEGRAM_BOT_TOKEN')
    if not token:return {'status':'unconfigured','sent':0}
    sent=0
    with core.connect() as c:
        schema(c)
        c.execute('CREATE TABLE IF NOT EXISTS intake_recipient_delivery(intake_id TEXT,chat_id TEXT,PRIMARY KEY(intake_id,chat_id))')
        chats=recipients(c)
        if not chats:return {'status':'unconfigured','sent':0}
        for row in c.execute("SELECT intake_id FROM intake_outbox WHERE status='queued' AND attempts<10 LIMIT 10").fetchall():
            ident=row[0]
            c.execute("UPDATE intake_outbox SET attempts=attempts+1 WHERE intake_id=?",(ident,))
            # Successful recipients are not retried when another recipient is offline.
            for chat in chats:
                if c.execute('SELECT 1 FROM intake_recipient_delivery WHERE intake_id=? AND chat_id=?',(ident,chat)).fetchone():continue
                payload=json.dumps({'chat_id':chat,'text':'RENN Prod · Новая заявка '+ident+'\nОткройте CRM для просмотра.'}).encode()
                try:
                    req=urllib.request.Request('https://api.telegram.org/bot'+token+'/sendMessage',data=payload,headers={'Content-Type':'application/json'})
                    with urllib.request.urlopen(req,timeout=10) as response: result=json.load(response)
                    if result.get('ok'):c.execute('INSERT OR IGNORE INTO intake_recipient_delivery VALUES(?,?)',(ident,chat))
                except Exception:pass  # Never log token-bearing URLs or transport errors.
            if all(c.execute('SELECT 1 FROM intake_recipient_delivery WHERE intake_id=? AND chat_id=?',(ident,chat)).fetchone() for chat in chats):
                c.execute("UPDATE intake_outbox SET status='sent' WHERE intake_id=?",(ident,));sent+=1
    return {'status':'processed','sent':sent}
