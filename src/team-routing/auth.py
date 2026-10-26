"""Local accounts and opaque revocable sessions. Never publish data/."""
import argparse,contextlib,getpass,hashlib,hmac,json,os,secrets,sqlite3,time,uuid
from pathlib import Path
DB=Path(__file__).parent/'data'/'auth.sqlite'
BASE={'owner':{'*'},'manager':{'dashboard:read','employees:read','employees:update','tasks:read'},'employee':{'self:read','self:update','offers:respond','availability:self'}}
DELEGATE={'employees:approve','employees:add','tasks:approve'}
@contextlib.contextmanager
def connect(path=None):
 p=Path(path or DB);p.parent.mkdir(parents=True,exist_ok=True);c=sqlite3.connect(p);c.row_factory=sqlite3.Row
 os.chmod(p,0o600)
 try:
  with c:yield c
 finally:c.close()
def init(path=None):
 with connect(path) as c:c.executescript('''CREATE TABLE IF NOT EXISTS account(id TEXT PRIMARY KEY,username TEXT UNIQUE,salt TEXT,password TEXT,role TEXT,permissions TEXT,specialist_id TEXT,active INTEGER DEFAULT 1);CREATE TABLE IF NOT EXISTS session(token TEXT PRIMARY KEY,user_id TEXT,expires REAL);CREATE TABLE IF NOT EXISTS attempt(username TEXT PRIMARY KEY,failures INTEGER,until REAL);''')
def digest(password,salt):return hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
def create_user(username,password,role,permissions=(),specialist_id=None,path=None):
 username=username.casefold().strip()
 if role not in BASE or not 2<=len(username)<=80 or len(password)<12 or not set(permissions)<=DELEGATE:raise ValueError('Invalid account details; password needs at least 12 characters')
 if role=='employee' and not specialist_id:raise ValueError('Employee needs a specialist profile')
 init(path);salt=secrets.token_hex(16);ident=str(uuid.uuid4())
 with connect(path) as c:c.execute('INSERT INTO account VALUES(?,?,?,?,?,?,?,1)',(ident,username.casefold().strip(),salt,digest(password,salt),role,json.dumps(sorted(set(permissions))),specialist_id))
 return ident
def user(row):
 return {'id':row['id'],'username':row['username'],'role':row['role'],'permissions':sorted(BASE[row['role']]|set(json.loads(row['permissions']))),'specialist_id':row['specialist_id']}
def login(username,password,path=None):
 username=str(username).casefold().strip()
 with connect(path) as c:
  a=c.execute('SELECT * FROM attempt WHERE username=?',(username,)).fetchone()
  if a and a['until']>time.time():raise ValueError('Повторите вход позже')
  r=c.execute('SELECT * FROM account WHERE username=? AND active=1',(username,)).fetchone()
  # Always perform the expensive KDF, including for unknown users.
  calculated=digest(str(password),r['salt'] if r else '00'*16)
  ok=r is not None and hmac.compare_digest(calculated,r['password'])
  if not ok:
   failures=(a['failures'] if a else 0)+1;until=time.time()+300 if failures>=5 else 0
   c.execute('INSERT INTO attempt VALUES(?,?,?) ON CONFLICT(username) DO UPDATE SET failures=excluded.failures,until=excluded.until',(username,failures,until))
  else:
   c.execute('DELETE FROM attempt WHERE username=?',(username,));token=secrets.token_urlsafe(32)
   c.execute('DELETE FROM session WHERE expires<?',(time.time(),));c.execute('INSERT INTO session VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),r['id'],time.time()+28800))
 if not ok:raise ValueError('Неверное имя или пароль')
 return token,user(r)
def principal(token,path=None):
 if not token or len(token)>256:return None
 with connect(path) as c:
  r=c.execute('SELECT a.* FROM account a JOIN session s ON a.id=s.user_id WHERE s.token=? AND s.expires>? AND a.active=1',(hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
 return user(r) if r else None
def logout(token,path=None):
 with connect(path) as c:c.execute('DELETE FROM session WHERE token=?',(hashlib.sha256(token.encode()).hexdigest(),))
def allowed(p,permission):return bool(p and ('*' in p['permissions'] or permission in p['permissions']))
def delegate(actor,target,permissions,path=None):
 if not actor or actor['role']!='owner':raise ValueError('Owner required')
 if not set(permissions)<=DELEGATE:raise ValueError('Unknown permission')
 with connect(path) as c:
  r=c.execute('SELECT role FROM account WHERE id=?',(target,)).fetchone()
  if not r or r['role']!='manager':raise ValueError('Select a manager account')
  c.execute('UPDATE account SET permissions=? WHERE id=?',(json.dumps(sorted(set(permissions))),target))
def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['create-user']);p.add_argument('--username',required=True);p.add_argument('--role',choices=list(BASE),required=True);p.add_argument('--specialist-id');p.add_argument('--permission',action='append',default=[]);a=p.parse_args()
 password=getpass.getpass('Password (12+ characters): ')
 if password!=getpass.getpass('Repeat password: '):raise SystemExit('Passwords differ')
 create_user(a.username,password,a.role,a.permission,a.specialist_id);print('Account created; password not logged.')
if __name__=='__main__':main()
