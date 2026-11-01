"""Document store for contracts, appendices, acts, invoices, KPP, call sheets.
Files live in data/documents with random names; metadata lives in the routing DB.
Only the owner and managers with tasks:approve can read or write."""
import base64, hashlib, json, uuid, os
from pathlib import Path
import core

KINDS = ('contract', 'appendix', 'act', 'invoice', 'kpp', 'call_sheet', 'other')
MAX_BYTES = 10 * 1024 * 1024
STORE = (Path(os.environ['RENN_DATA_DIR']) if os.environ.get('RENN_DATA_DIR') else core.ROOT / 'data') / 'documents'

def _allowed(actor):
    # Managers handle the paperwork; employees never see documents.
    return bool(actor) and (actor.get('role') == 'owner' or (actor.get('role') == 'manager' and 'tasks:approve' in actor.get('permissions', [])))

def schema_orders(c):
    c.execute('CREATE TABLE IF NOT EXISTS order_manager(order_id TEXT PRIMARY KEY,account_id TEXT NOT NULL,assigned_at TEXT NOT NULL)')
    c.execute('CREATE TABLE IF NOT EXISTS order_transfer(id TEXT PRIMARY KEY,order_id TEXT NOT NULL,from_account TEXT,to_account TEXT NOT NULL,at TEXT NOT NULL)')

def assign_order_manager(c, order_id, account_id):
    """The manager who creates a project from a request keeps it; documents follow the project."""
    schema_orders(c)
    c.execute('INSERT OR IGNORE INTO order_manager VALUES(?,?,?)', (order_id, account_id, core.now()))

def _manages(c, actor, order_id):
    if actor and actor.get('role') == 'owner':
        return True
    schema_orders(c)
    return bool(actor) and bool(c.execute('SELECT 1 FROM order_manager WHERE order_id=? AND account_id=?', (order_id, actor['id'])).fetchone())

def _can_see_doc(c, actor, row):
    if actor and actor.get('role') == 'owner':
        return True
    if row['owner_kind'] != 'order':
        return False
    return _manages(c, actor, row['owner_id'])

def transfer_order(c, actor, order_id, to_account):
    """Owner or the current manager hands a project and its documents to another manager."""
    if not actor or actor.get('role') not in ('owner', 'manager'):raise PermissionError('Нет доступа')
    if not c.execute('SELECT 1 FROM orders WHERE id=?', (order_id,)).fetchone():raise ValueError('Заказ не найден')
    if not _manages(c, actor, order_id):raise PermissionError('Передавать может владелец или текущий менеджер проекта')
    import auth
    with auth.connect() as acc:
        target = acc.execute("SELECT id,role FROM account WHERE id=? AND active=1", (to_account,)).fetchone()
    if not target or target['role'] != 'manager':raise ValueError('Передать можно только активному менеджеру')
    schema_orders(c)
    current = c.execute('SELECT account_id FROM order_manager WHERE order_id=?', (order_id,)).fetchone()
    c.execute('INSERT OR REPLACE INTO order_manager VALUES(?,?,?)', (order_id, to_account, core.now()))
    c.execute('INSERT INTO order_transfer VALUES(?,?,?,?,?)', (uuid.uuid4().hex, order_id, current[0] if current else None, to_account, core.now()))
    return {'status': 'transferred', 'order_id': order_id, 'to': to_account}

def schema(c):
    c.execute('CREATE TABLE IF NOT EXISTS document(id TEXT PRIMARY KEY,owner_kind TEXT NOT NULL,owner_id TEXT NOT NULL,kind TEXT NOT NULL,title TEXT NOT NULL,filename TEXT NOT NULL,size INTEGER NOT NULL,sha256 TEXT NOT NULL,stored_as TEXT NOT NULL,uploaded_by TEXT,created_at TEXT NOT NULL)')

def upload(c, actor, owner_kind, owner_id, kind, title, filename, content_b64):
    if not _allowed(actor):raise PermissionError('Нет доступа к документам')
    if kind not in KINDS:raise ValueError('Неизвестный тип документа')
    if owner_kind not in ('order', 'specialist', 'account', 'general'):raise ValueError('Неизвестная привязка')
    if owner_kind == 'order':
        if not c.execute('SELECT 1 FROM orders WHERE id=?', (owner_id,)).fetchone():raise ValueError('Заказ не найден')
        if not _manages(c, actor, owner_id):raise PermissionError('Документы можно добавлять только к своим проектам')
    if owner_kind != 'order' and actor.get('role') != 'owner':raise PermissionError('Общие документы добавляет владелец')
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 160:raise ValueError('Название документа: 1–160 символов')
    if not isinstance(filename, str) or not filename or '/' in filename or '\\' in filename or len(filename) > 200:raise ValueError('Неверное имя файла')
    try:data = base64.b64decode(content_b64, validate=True)
    except Exception:raise ValueError('Файл не распознан')
    if not data:raise ValueError('Пустой файл')
    if len(data) > MAX_BYTES:raise ValueError('Файл больше 10 МБ')
    schema(c)
    STORE.mkdir(parents=True, exist_ok=True)
    doc_id = uuid.uuid4().hex; stored = doc_id + '.bin'
    (STORE / stored).write_bytes(data); os.chmod(STORE / stored, 0o600)
    c.execute('INSERT INTO document VALUES(?,?,?,?,?,?,?,?,?,?,?)',
              (doc_id, owner_kind, str(owner_id), kind, title.strip(), filename, len(data), hashlib.sha256(data).hexdigest(), stored, actor['id'], core.now()))
    return {'id': doc_id, 'size': len(data)}

def listing(c, actor, owner_id=None):
    if not _allowed(actor):raise PermissionError('Нет доступа к документам')
    schema(c); schema_orders(c)
    if owner_id:
        rows = c.execute('SELECT id,owner_kind,owner_id,kind,title,filename,size,sha256,created_at FROM document WHERE owner_id=? ORDER BY created_at DESC', (str(owner_id),)).fetchall()
    else:
        rows = c.execute('SELECT id,owner_kind,owner_id,kind,title,filename,size,sha256,created_at FROM document ORDER BY created_at DESC').fetchall()
    return [dict(r) for r in rows if _can_see_doc(c, actor, r)][:500]

def download(c, actor, doc_id):
    if not _allowed(actor):raise PermissionError('Нет доступа к документам')
    schema(c)
    row = c.execute('SELECT * FROM document WHERE id=?', (doc_id,)).fetchone()
    if not row or not _can_see_doc(c, actor, row):raise ValueError('Документ не найден')
    try:data = (STORE / row['stored_as']).read_bytes()
    except OSError:raise ValueError('Файл не найден в хранилище')
    if hashlib.sha256(data).hexdigest() != row['sha256']:raise ValueError('Файл повреждён: контрольная сумма не совпала')
    return {'filename': row['filename'], 'content_base64': base64.b64encode(data).decode('ascii')}
