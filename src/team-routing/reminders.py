"""Daily manager reminders and repeat-request view.
Default reminder time is 10:00 (Europe/Moscow); each manager can change it with /remind HH:MM or in the cabinet.
Reminders list projects without roles (managed by this manager) and contacts that sent several requests."""
import re, json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import core, documents

DEFAULT_TIME = '10:00'
ZONE = 'Europe/Moscow'
TIME_RE = re.compile(r'^([01]\d|2[0-3]):[0-5]\d$')

def schema(c):
    c.execute('CREATE TABLE IF NOT EXISTS reminder_setting(account_id TEXT PRIMARY KEY,hhmm TEXT NOT NULL)')
    c.execute('CREATE TABLE IF NOT EXISTS reminder_log(account_id TEXT NOT NULL,day TEXT NOT NULL,PRIMARY KEY(account_id,day))')
    documents.schema_orders(c)

def set_time(c, actor, hhmm):
    if not actor or actor.get('role') not in ('owner', 'manager'):raise PermissionError('Нет доступа')
    if not isinstance(hhmm, str) or not TIME_RE.match(hhmm.strip()):raise ValueError('Время в формате ЧЧ:ММ, например 09:30')
    schema(c)
    c.execute('INSERT INTO reminder_setting VALUES(?,?) ON CONFLICT(account_id) DO UPDATE SET hhmm=excluded.hhmm', (actor['id'], hhmm.strip()))
    return {'status': 'saved', 'time': hhmm.strip()}

def get_time(c, account_id):
    schema(c)
    row = c.execute('SELECT hhmm FROM reminder_setting WHERE account_id=?', (account_id,)).fetchone()
    return row[0] if row else DEFAULT_TIME

def digest(c, actor):
    """What this person must look at: projects without roles they manage, and repeat requests from the same contact."""
    schema(c)
    if actor.get('role') == 'owner':
        scope = c.execute("SELECT o.id,o.title,o.start FROM orders o WHERE NOT EXISTS (SELECT 1 FROM role_slot r WHERE r.order_id=o.id) ORDER BY o.start").fetchall()
    else:
        scope = c.execute("SELECT o.id,o.title,o.start FROM orders o JOIN order_manager m ON m.order_id=o.id WHERE m.account_id=? AND NOT EXISTS (SELECT 1 FROM role_slot r WHERE r.order_id=o.id) ORDER BY o.start", (actor['id'],)).fetchall()
    repeats = c.execute("SELECT json_extract(payload,'$.contact') AS contact, COUNT(*) AS n, GROUP_CONCAT(id) AS ids FROM intake "
                        "WHERE kind='client' GROUP BY contact HAVING COUNT(*)>1 ORDER BY n DESC LIMIT 200").fetchall()
    return {'no_role': [{'order_id': r[0], 'title': r[1], 'start': r[2]} for r in scope],
            'repeats': [{'contact': r[0], 'count': r[1], 'intake_ids': r[2].split(',')} for r in repeats]}

def due(c, now=None):
    """Managers whose reminder time has passed today (their local time) and who have not got today's reminder yet."""
    schema(c)
    now = now or datetime.now(timezone.utc)
    zone = ZoneInfo(ZONE); local = now.astimezone(zone)
    today = local.strftime('%Y-%m-%d'); hhmm_now = local.strftime('%H:%M')
    from auth import connect as auth_connect
    with auth_connect() as a:
        managers = [dict(r) for r in a.execute("SELECT id,username,role,permissions FROM account WHERE role='manager' AND active=1")]
    out = []
    for m in managers:
        if get_time(c, m['id']) > hhmm_now: continue
        if c.execute('SELECT 1 FROM reminder_log WHERE account_id=? AND day=?', (m['id'], today)).fetchone(): continue
        tg = c.execute('SELECT telegram_id FROM telegram_account WHERE account_id=?', (m['id'],)).fetchone()
        if not tg: continue
        d = digest(c, dict(m, permissions=json.loads(m['permissions'] or '[]')))
        if not d['no_role'] and not d['repeats']: 
            c.execute('INSERT OR IGNORE INTO reminder_log VALUES(?,?)', (m['id'], today)); continue
        out.append({'account_id': m['id'], 'telegram_id': tg[0], 'day': today, 'digest': d})
    return out

def text_for(d):
    lines = ['RENN Prod · напоминание на сегодня']
    if d['no_role']:
        lines.append('Проекты без роли (%d):' % len(d['no_role']))
        lines += ['• %s · %s' % (p['title'], (p['start'] or '')[:10]) for p in d['no_role'][:15]]
    if d['repeats']:
        lines.append('Повторные заявки от одного контакта (%d):' % len(d['repeats']))
        lines += ['• %s — заявок: %d' % (r['contact'], r['count']) for r in d['repeats'][:15]]
    lines.append('Время напоминания меняется командой /remind ЧЧ:ММ.')
    return '\n'.join(lines)

def flush(c, sender, now=None):
    """Sends due reminders through sender(telegram_id, text). Marks a day as sent only after the send succeeded."""
    sent = 0
    for item in due(c, now):
        try:
            sender(item['telegram_id'], text_for(item['digest']))
        except Exception:
            continue
        c.execute('INSERT OR IGNORE INTO reminder_log VALUES(?,?)', (item['account_id'], item['day']))
        sent += 1
    return sent
