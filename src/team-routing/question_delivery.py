"""Question notices to the currently assigned manager; never include private text."""
import threading
import core,bot,auth
_lock=threading.Lock()

def schema(c):
 c.execute('CREATE TABLE IF NOT EXISTS employee_question(id TEXT PRIMARY KEY,specialist_id TEXT,offer_id TEXT,body TEXT,created_at TEXT,command_key TEXT,UNIQUE(specialist_id,command_key))')
 c.execute('CREATE TABLE IF NOT EXISTS question_delivery(question_id TEXT PRIMARY KEY,attempts INTEGER NOT NULL DEFAULT 0,sent INTEGER NOT NULL DEFAULT 0)')

def flush():
 if not _lock.acquire(blocking=False):return {'status':'busy'}
 try:return _flush()
 finally:_lock.release()

def _flush():
 with core.connect() as c:
  schema(c)
  rows=c.execute("SELECT q.id,p.telegram_id FROM employee_question q JOIN offer f ON f.id=q.offer_id AND f.specialist_id=q.specialist_id JOIN role_slot s ON s.id=f.slot_id JOIN manager_acceptance m ON m.order_id=s.order_id AND m.status='accepted' JOIN specialist p ON p.id=m.specialist_id LEFT JOIN question_delivery d ON d.question_id=q.id WHERE COALESCE(d.sent,0)=0 AND COALESCE(d.attempts,0)<10 AND p.telegram_id>0 ORDER BY q.created_at,q.id LIMIT 10").fetchall()
 sent=0
 for row in rows:
  with core.connect() as c:
   c.execute('INSERT INTO question_delivery(question_id,attempts) VALUES(?,1) ON CONFLICT(question_id) DO UPDATE SET attempts=attempts+1',(row['id'],))
  # The question body, employee contacts and financial terms stay in the authenticated CRM.
  try:bot.call('sendMessage',{'chat_id':int(row['telegram_id']),'text':'RENN Prod: новый вопрос сотрудника. Откройте CRM → заявки. Номер: '+row['id']})
  except Exception:continue
  with core.connect() as c:c.execute('UPDATE question_delivery SET sent=1 WHERE question_id=?',(row['id'],))
  sent+=1
 return {'sent':sent}

def list_questions(c,actor):
 """Owner sees all; managers see only their accepted project assignments."""
 if not actor or actor.get('role') not in ('owner','manager'):return []
 if not auth.allowed(actor,'tasks:read'):return []
 schema(c)
 rows=c.execute("""SELECT q.id,q.offer_id,q.body,q.created_at,s.name AS employee,
 o.id AS order_id,o.title AS project,o.city
 FROM employee_question q
 JOIN specialist s ON s.id=q.specialist_id
 JOIN offer f ON f.id=q.offer_id AND f.specialist_id=q.specialist_id
 JOIN role_slot slot ON slot.id=f.slot_id JOIN orders o ON o.id=slot.order_id
 WHERE ? OR EXISTS(SELECT 1 FROM manager_acceptance m
 WHERE m.order_id=o.id AND m.specialist_id=? AND m.status='accepted')
 ORDER BY q.created_at DESC,q.id""",(actor['role']=='owner',actor.get('specialist_id')))
 result=[dict(row) for row in rows]
 if not (auth.allowed(actor,'contacts:read') and auth.allowed(actor,'finances:read')):
  for row in result:row.pop('body',None)
 return result
