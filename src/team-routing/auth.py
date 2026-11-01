"""Local accounts and opaque revocable sessions. Never publish data/."""
import argparse,contextlib,getpass,hashlib,hmac,json,os,secrets,sqlite3,time,uuid
from pathlib import Path
DB=Path(os.environ['RENN_DATA_DIR'])/'auth.sqlite' if os.environ.get('RENN_DATA_DIR') else Path(__file__).parent/'data'/'auth.sqlite'
BASE={'owner':{'*'},'manager':{'dashboard:read','employees:read','employees:update','tasks:read'},'employee':{'self:read','self:update','offers:respond','availability:self'}}
DELEGATE={'employees:approve','employees:add','tasks:approve','finances:read','contacts:read'}
@contextlib.contextmanager
def connect(path=None):
 p=Path(path or DB);p.parent.mkdir(parents=True,exist_ok=True);c=sqlite3.connect(p);c.row_factory=sqlite3.Row
 os.chmod(p,0o600)
 try:
  with c:yield c
 finally:c.close()
def init(path=None):
 with connect(path) as c:c.executescript('''CREATE TABLE IF NOT EXISTS account(id TEXT PRIMARY KEY,username TEXT UNIQUE,salt TEXT,password TEXT,role TEXT,permissions TEXT,specialist_id TEXT,active INTEGER DEFAULT 1);CREATE TABLE IF NOT EXISTS session(token TEXT PRIMARY KEY,user_id TEXT,expires REAL);CREATE TABLE IF NOT EXISTS attempt(username TEXT PRIMARY KEY,failures INTEGER,until REAL);CREATE TABLE IF NOT EXISTS account_profile(user_id TEXT PRIMARY KEY,data TEXT NOT NULL);''')
 with connect(path) as c:_migrate(c)
 with connect(path) as c:  # managers keep document and routing rights on every account
  for r in c.execute("SELECT id,permissions FROM account WHERE role='manager'").fetchall():
   perms=set(json.loads(r['permissions']))|{'tasks:approve'}
   c.execute('UPDATE account SET permissions=? WHERE id=?',(json.dumps(sorted(perms)),r['id']))
def _migrate(c):
 cols={r['name'] for r in c.execute('PRAGMA table_info(account)')}
 if 'must_change' not in cols:c.execute('ALTER TABLE account ADD COLUMN must_change INTEGER NOT NULL DEFAULT 0')
 c.execute('CREATE TABLE IF NOT EXISTS invite(digest TEXT PRIMARY KEY,role TEXT NOT NULL,permissions TEXT NOT NULL,created_by TEXT,expires REAL NOT NULL,used INTEGER NOT NULL DEFAULT 0)')
def digest(password,salt):return hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
def create_user(username,password,role,permissions=(),specialist_id=None,path=None):
 username=username.casefold().strip()
 if role not in BASE or not 2<=len(username)<=80 or len(password)<12 or not set(permissions)<=DELEGATE:raise ValueError('Invalid account details; password needs at least 12 characters')
 if role=='employee' and not specialist_id:raise ValueError('Employee needs a specialist profile')
 init(path);salt=secrets.token_hex(16);ident=str(uuid.uuid4())
 with connect(path) as c:c.execute('INSERT INTO account(id,username,salt,password,role,permissions,specialist_id,active) VALUES(?,?,?,?,?,?,?,1)',(ident,username.casefold().strip(),salt,digest(password,salt),role,json.dumps(sorted(set(permissions))),specialist_id))
 return ident
def user(row):
 return {'id':row['id'],'username':row['username'],'role':row['role'],'permissions':sorted(BASE[row['role']]|set(json.loads(row['permissions']))),'specialist_id':row['specialist_id'],'must_change':bool(row['must_change'])}
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
def change_password(actor,current,replacement,path=None):
 if not actor or not isinstance(current,str) or not isinstance(replacement,str) or not 12<=len(replacement)<=1024 or len(current)>1024 or current==replacement:raise ValueError('Invalid password change')
 with connect(path) as c:
  r=c.execute('SELECT * FROM account WHERE id=? AND active=1',(actor['id'],)).fetchone()
  if not r or not hmac.compare_digest(digest(current,r['salt']),r['password']):raise ValueError('Invalid current password')
  salt=secrets.token_hex(16)
  c.execute('UPDATE account SET salt=?,password=?,must_change=0 WHERE id=?',(salt,digest(replacement,salt),r['id']))
  c.execute('DELETE FROM session WHERE user_id=?',(r['id'],))
PROFILE_LIMITS={'display_name':120,'bio':2000,'telegram':100,'email':254,'phone':40,'contact_preference':16}
def profile(actor,path=None):
 if not actor:raise ValueError('Account required')
 with connect(path) as c:
  row=c.execute('SELECT data FROM account_profile WHERE user_id=?',(actor['id'],)).fetchone()
 return json.loads(row['data']) if row else {'display_name':actor['username'],'contact_preference':'telegram'}
def update_profile(actor,patch,path=None):
 if not actor or not isinstance(patch,dict) or not set(patch)<=set(PROFILE_LIMITS):raise ValueError('Invalid profile fields')
 for key,value in patch.items():
  if not isinstance(value,str) or len(value)>PROFILE_LIMITS[key] or any(ord(ch)<32 and ch not in '\n\t' for ch in value):raise ValueError('Invalid profile value')
 if 'contact_preference' in patch and patch['contact_preference'] not in ['telegram','email','call','any']:raise ValueError('Invalid contact preference')
 if 'display_name' in patch and not patch['display_name'].strip():raise ValueError('Name required')
 data=profile(actor,path);data.update({k:v.strip() for k,v in patch.items()})
 with connect(path) as c:
  if not c.execute('SELECT id FROM account WHERE id=? AND active=1',(actor['id'],)).fetchone():raise ValueError('Account unavailable')
  c.execute('INSERT INTO account_profile VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET data=excluded.data',(actor['id'],json.dumps(data,ensure_ascii=False)))
 return data
def delegate(actor,target,permissions,path=None):
 if not actor or actor['role']!='owner':raise ValueError('Owner required')
 if not set(permissions)<=DELEGATE:raise ValueError('Unknown permission')
 with connect(path) as c:
  r=c.execute('SELECT role FROM account WHERE id=?',(target,)).fetchone()
  if not r or r['role']!='manager':raise ValueError('Select a manager account')
  c.execute('UPDATE account SET permissions=? WHERE id=?',(json.dumps(sorted(set(permissions)|{'tasks:approve'})),target))
def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['create-user']);p.add_argument('--username',required=True);p.add_argument('--role',choices=list(BASE),required=True);p.add_argument('--specialist-id');p.add_argument('--permission',action='append',default=[]);a=p.parse_args()
 password=getpass.getpass('Password (12+ characters): ')
 if password!=getpass.getpass('Repeat password: '):raise SystemExit('Passwords differ')
 create_user(a.username,password,a.role,a.permission,a.specialist_id);print('Account created; password not logged.')
if __name__=='__main__':main()

INVITE_TTL=7*24*3600
def _invite_digest(code):return hashlib.sha256(code.encode()).hexdigest()
def create_invite(actor,role,permissions=(),path=None):
 """Owner-only. Returns a one-time code; only its hash is stored."""
 if not actor or actor.get('role')!='owner':raise PermissionError('Только владелец')
 if role not in ('manager','employee'):raise ValueError('Приглашать можно менеджера или сотрудника')
 if not set(permissions)<=DELEGATE:raise ValueError('Unknown permission')
 if role=='employee':permissions=[]
 if role=='manager':permissions=sorted(set(permissions)|{'tasks:approve'})  # managers handle documents and routing
 code=secrets.token_urlsafe(18);expires=time.time()+INVITE_TTL
 with connect(path) as c:
  _migrate(c)
  c.execute('INSERT INTO invite VALUES(?,?,?,?,?,0)',(_invite_digest(code),role,json.dumps(sorted(set(permissions))),actor['id'],expires))
 return {'code':code,'role':role,'expires_at':expires}
def consume_invite(code,telegram_id,username_hint='',specialist_id=None,path=None):
 """Creates the account for a valid invite. Returns login and a temporary password (shown once, must be changed)."""
 if not isinstance(code,str) or not 20<=len(code)<=80 or isinstance(telegram_id,bool) or not isinstance(telegram_id,int) or telegram_id<=0:raise ValueError('Invalid invite')
 with connect(path) as c:
  _migrate(c)
  c.execute('BEGIN IMMEDIATE')
  row=c.execute('SELECT * FROM invite WHERE digest=?',(_invite_digest(code),)).fetchone()
  if not row or row['used'] or row['expires']<time.time():c.execute('ROLLBACK');raise ValueError('Invalid invite')
  if c.execute('SELECT 1 FROM invite WHERE digest=? AND used=0',(row['digest'],)).fetchone() is None:c.execute('ROLLBACK');raise ValueError('Invalid invite')
  base=''.join(ch for ch in (username_hint or '').casefold() if ch.isalnum() or ch in '._-')[:24] or 'user'
  username=None
  for _ in range(5):
   candidate=base+'-'+secrets.token_hex(4)
   if c.execute('SELECT 1 FROM account WHERE username=?',(candidate,)).fetchone() is None:username=candidate;break
  if username is None:c.execute('ROLLBACK');raise ValueError('Попробуйте ещё раз')
  temp=secrets.token_urlsafe(10)
  salt=secrets.token_hex(16);ident=str(uuid.uuid4())
  if row['role']=='employee' and not specialist_id:c.execute('ROLLBACK');raise ValueError('Сначала заполните анкету')
  if row['role']=='employee' and c.execute('SELECT 1 FROM account WHERE specialist_id=? AND active=1',(specialist_id,)).fetchone():
   c.execute('ROLLBACK');raise ValueError('Анкета уже привязана к аккаунту')
  if row['role']!='employee':specialist_id=None
  c.execute('UPDATE invite SET used=1 WHERE digest=?',(row['digest'],))
  c.execute('INSERT INTO account(id,username,salt,password,role,permissions,specialist_id,active,must_change) VALUES(?,?,?,?,?,?,?,1,1)',
            (ident,username,salt,digest(temp,salt),row['role'],row['permissions'],specialist_id))
  c.execute('COMMIT')
 return {'id':ident,'username':username,'password':temp,'role':row['role'],'digest':row['digest']}
def undo_invite(account_id,digest,path=None):
 """Compensation when the Telegram binding fails after the account was created: the code can be used again."""
 with connect(path) as c:
  c.execute('UPDATE account SET active=0 WHERE id=?',(account_id,))
  c.execute('UPDATE invite SET used=0 WHERE digest=?',(digest,))

def reset_temp_password(actor,account_id,path=None):
    """Owner-only recovery: a new temporary password, forced change at next login, all sessions signed out."""
    if not actor or actor.get('role')!='owner':raise PermissionError('Только владелец')
    temp=secrets.token_urlsafe(10);salt=secrets.token_hex(16)
    with connect(path) as c:
        row=c.execute('SELECT id,username,role FROM account WHERE id=? AND active=1',(account_id,)).fetchone()
        if not row:raise ValueError('Аккаунт не найден')
        if row['role']=='owner':raise ValueError('Пароль владельца меняется в личном кабинете')
        c.execute('UPDATE account SET salt=?,password=?,must_change=1 WHERE id=?',(salt,digest(temp,salt),account_id))
        c.execute('DELETE FROM session WHERE user_id=?',(account_id,))
    return {'username':row['username'],'temp_password':temp}
