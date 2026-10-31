"""One-time website-to-private-Telegram binding. Only token hashes persist."""
import hashlib,secrets,time
from contextlib import contextmanager
import core,auth

def schema(c):
 c.execute('CREATE TABLE IF NOT EXISTS telegram_link_code(digest TEXT PRIMARY KEY,account_id TEXT UNIQUE,expires REAL NOT NULL)')
 c.execute('CREATE TABLE IF NOT EXISTS telegram_account(account_id TEXT PRIMARY KEY,telegram_id INTEGER UNIQUE NOT NULL)')

def principal(ident,c):
 """Resolve current permissions on every command; a binding is not authority."""
 if type(ident) is not int or ident<=0 or not auth.DB.exists():return None
 schema(c)
 link=c.execute('SELECT account_id FROM telegram_account WHERE telegram_id=?',(ident,)).fetchone()
 if not link:return None
 with auth.connect() as accounts:
  row=accounts.execute('SELECT * FROM account WHERE id=? AND active=1',(link['account_id'],)).fetchone()
 return auth.user(row) if row else None

@contextmanager
def atomic(c):
 c.execute('SAVEPOINT telegram_binding')
 try:
  yield
  c.execute('RELEASE telegram_binding')
 except Exception:
  c.execute('ROLLBACK TO telegram_binding');c.execute('RELEASE telegram_binding');raise

def issue(actor):
 code=secrets.token_urlsafe(24);expires=time.time()+600
 with core.connect() as c,atomic(c):
  schema(c)
  c.execute('DELETE FROM telegram_link_code WHERE account_id=? OR expires<?',(actor['id'],time.time()))
  c.execute('INSERT INTO telegram_link_code VALUES(?,?,?)',(hashlib.sha256(code.encode()).hexdigest(),actor['id'],expires))
 return {'code':code,'expires_at':expires,'command':'/link '+code}

def status(actor):
 with core.connect() as c:
  schema(c)
  row=c.execute('SELECT 1 FROM telegram_account WHERE account_id=?',(actor['id'],)).fetchone()
 return {'linked':bool(row)}

def consume(code,ident,c):
 if not isinstance(code,str) or not 20<=len(code)<=80 or type(ident) is not int or ident<=0:raise ValueError('Invalid binding')
 with atomic(c):
  schema(c)
  pending=c.execute('SELECT * FROM telegram_link_code WHERE digest=?',(hashlib.sha256(code.encode()).hexdigest(),)).fetchone()
  if not pending or pending['expires']<=time.time():raise ValueError('Invalid binding')
  with auth.connect() as a:account=a.execute('SELECT * FROM account WHERE id=? AND active=1',(pending['account_id'],)).fetchone()
  if not account:raise ValueError('Invalid binding')
  if c.execute('SELECT 1 FROM telegram_account WHERE account_id=? OR telegram_id=?',(account['id'],ident)).fetchone():raise ValueError('Already bound')
  sid=account['specialist_id']
  person=c.execute('SELECT id,telegram_id FROM specialist WHERE id=?',(sid,)).fetchone() if sid else None
  if sid and not person:raise ValueError('Missing specialist')
  if person and person['telegram_id'] not in (None,ident):raise ValueError('Specialist already bound')
  other=c.execute('SELECT id FROM specialist WHERE telegram_id=?',(ident,)).fetchone()
  if other and other['id']!=sid:raise ValueError('Telegram already bound')
  if sid:
   with auth.connect() as a:
    if a.execute('SELECT 1 FROM account WHERE specialist_id=? AND id<>? AND active=1',(sid,account['id'])).fetchone():raise ValueError('Shared specialist')
   c.execute('UPDATE specialist SET telegram_id=? WHERE id=?',(ident,sid))
  c.execute('INSERT INTO telegram_account VALUES(?,?)',(account['id'],ident))
  c.execute('DELETE FROM telegram_link_code WHERE account_id=?',(account['id'],))
  c.execute('DELETE FROM bot_state WHERE telegram_id=?',(ident,))

def unlink(actor):
 with core.connect() as c,atomic(c):
  schema(c)
  row=c.execute('SELECT telegram_id FROM telegram_account WHERE account_id=?',(actor['id'],)).fetchone()
  if row and actor.get('specialist_id'):
   c.execute('UPDATE specialist SET telegram_id=NULL WHERE id=? AND telegram_id=?',(actor['specialist_id'],row['telegram_id']))
  c.execute('DELETE FROM telegram_account WHERE account_id=?',(actor['id'],))
  c.execute('DELETE FROM telegram_link_code WHERE account_id=?',(actor['id'],))
 return {'linked':False}
