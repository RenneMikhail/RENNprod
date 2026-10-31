"""Private offer delivery. Bounded retries; transport runs without a DB write lock."""
import json,threading
import core,bot
_lock=threading.Lock()

def flush():
 if not _lock.acquire(blocking=False):return {'status':'busy'}
 try:return _flush()
 finally:_lock.release()

def _flush():
 with core.connect() as c:
  c.execute('CREATE TABLE IF NOT EXISTS notification_delivery(notification_id TEXT PRIMARY KEY,attempts INTEGER NOT NULL DEFAULT 0)')
  rows=c.execute("SELECT n.*,p.telegram_id,COALESCE(d.attempts,0) attempts FROM notification n JOIN specialist p ON p.id=n.specialist_id LEFT JOIN notification_delivery d ON d.notification_id=n.id WHERE n.status='queued' AND n.channel='telegram' AND n.event_key LIKE 'offer:%' AND COALESCE(d.attempts,0)<10 ORDER BY n.rowid LIMIT 10").fetchall()
 sent=0
 for row in rows:
  with core.connect() as c:
   offer=c.execute('SELECT * FROM offer WHERE id=? AND specialist_id=?',(row['event_key'][6:],row['specialist_id'])).fetchone()
   if not offer or offer['status']!='pending' or offer['deadline']<=core.now():
    c.execute("UPDATE notification SET status='expired' WHERE id=? AND status='queued'",(row['id'],));continue
   try:recipient=int(row['telegram_id'])
   except (TypeError,ValueError):continue
   if recipient<=0:continue
   c.execute('INSERT INTO notification_delivery VALUES(?,1) ON CONFLICT(notification_id) DO UPDATE SET attempts=attempts+1',(row['id'],))
   terms=json.loads(offer['terms'])
   label=lambda value:str(value or 'Не указано')[:120]
   text='Новое предложение RENN Prod\n'+ '\n'.join(label(terms.get(k)) for k in ['city','start','deliverable'])+'\nОплата: '+label(terms.get('fee'))+' '+label(terms.get('currency'))+'\nПринятие — отклик; назначение подтверждает менеджер.'
   buttons=[[{'text':'Взять','callback_data':f"offer:{offer['id']}:{offer['version']}:a"},{'text':'Отказаться','callback_data':f"offer:{offer['id']}:{offer['version']}:d"}]]
  try:bot.call('sendMessage',{'chat_id':recipient,'text':text,'reply_markup':{'inline_keyboard':buttons}})
  except Exception:continue
  with core.connect() as c:c.execute("UPDATE notification SET status='sent' WHERE id=? AND status='queued'",(row['id'],))
  sent+=1
 return {'sent':sent}
