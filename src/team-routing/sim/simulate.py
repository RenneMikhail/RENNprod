"""Synthetic client, manager and employee bots that run full cycles against a throwaway database.
Nothing is sent to Telegram: bot updates go through bot.process_update, the website through local HTTP.
Usage: python3 sim/simulate.py --cycles 3 --out <folder>
"""
import argparse, http.client, json, os, pathlib, secrets, sys, tempfile, threading, uuid
from http.server import ThreadingHTTPServer

HERE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

def boot(tmp):
    os.environ['RENN_DATA_DIR'] = tmp
    import core, auth, server, bot
    core.init(); auth.init()  # no demo seed: offers must go to the simulated employees only
    return core, auth, server, bot

class Site:
    def __init__(self, server):
        self.server = server
        self.http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        self.port = self.http.server_port
        threading.Thread(target=self.http.serve_forever, daemon=True).start()
    def close(self):
        self.http.shutdown(); self.http.server_close()
    def call(self, path, body=None, cookie=None, local=False):
        c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=15)
        headers = {'Host': '127.0.0.1:%d' % self.port}
        if body is not None: headers['Content-Type'] = 'application/json'
        if cookie: headers['Cookie'] = cookie
        headers['X-Local-Session'] = self.server.SESSION
        c.request('POST' if body is not None else 'GET', path, json.dumps(body) if body is not None else None, headers)
        r = c.getresponse(); raw = r.read(); set_cookie = r.getheader('Set-Cookie'); c.close()
        try: data = json.loads(raw)
        except Exception: data = raw.decode('utf-8', 'replace')
        return r.status, data, set_cookie

class Findings:
    def __init__(self): self.items = []
    def step(self, cycle, actor, name, ok, detail=''):
        import re
        text = re.sub(r'(Временный пароль: )\S+', r'\1[скрыто]', str(detail))  # never keep test passwords in reports
        self.items.append({'cycle': cycle, 'actor': actor, 'step': name, 'ok': bool(ok), 'detail': text[:300]})
    def friction(self, cycle, actor, name, detail):
        self.step(cycle, actor, name, False, detail)

def tg_update(bot, uid, text=None, data=None, msg_id=1):
    if data is not None:
        return bot.process_update({'update_id': uid_seq(), 'callback_query': {'id': str(uuid.uuid4()), 'from': {'id': uid}, 'data': data, 'message': {'message_id': msg_id, 'chat': {'id': uid, 'type': 'private'}}}})
    return bot.process_update({'update_id': uid_seq(), 'message': {'chat': {'id': uid, 'type': 'private'}, 'from': {'id': uid, 'username': 'sim%d' % uid}, 'text': text}})

_seq = [1_000_000]
def uid_seq():
    _seq[0] += 1; return _seq[0]

def parse_creds(reply):
    text = reply['text'] if isinstance(reply, dict) else str(reply)
    out = {}
    for line in text.split('\n'):
        if ': ' in line:
            k, v = line.split(': ', 1); out[k] = v
    return out.get('Логин'), out.get('Временный пароль')

ANSWERS = {'name': 'Тест Сотрудник', 'city': 'Москва', 'roles': 'camera', 'skills': 'interview', 'tasks': 'shoot',
           'mobility': 'city', 'equipment': 'none', 'rate_unit': 'shift12', 'rate': '10000', 'currency': 'RUB',
           'languages': 'ru', 'email': 'sim@example.invalid', 'phone': '-', 'timezone': 'Europe/Moscow',
           'portfolio': 'https://example.invalid/portfolio', 'portfolio_role': 'camera', 'consent': 'ДА'}

def run_cycle(n, site, core, auth, bot, owner_cookie, findings):
    tag = 'c%d' % n
    base_tg = 5000 + n * 10
    # 1. Manager gets an invite through the owner, activates via bot, changes the temporary password.
    s, inv, _ = site.call('/api/owner/invite', {'role': 'manager', 'permissions': ['tasks:approve', 'employees:approve', 'contacts:read']}, cookie=owner_cookie)
    findings.step(n, 'owner', 'create manager invite', s == 200, inv if s != 200 else 'ok')
    reply = tg_update(bot, base_tg + 1, text='/invite ' + inv['code'])
    login, temp = parse_creds(reply)
    findings.step(n, 'manager-bot', 'accept invite (/invite)', bool(login), reply.get('text') if isinstance(reply, dict) else reply)
    mgr_cookie = _login(site, login, temp, findings, n, 'manager')
    new_pass = 'sim-manager-' + secrets.token_hex(6)
    s, body, _ = site.call('/api/account/password', {'current_password': temp, 'new_password': new_pass}, cookie=mgr_cookie)
    findings.step(n, 'manager-bot', 'change temporary password', s == 200, body)
    mgr_cookie = _login(site, login, new_pass, findings, n, 'manager', final=True)

    # 2. Employee fills the questionnaire in the bot, owner verifies, employee activates via invite.
    emp_tg = base_tg + 2
    reply = tg_update(bot, emp_tg, text='/start')
    for field in [f for f, _ in bot.FIELDS]:
        if field == 'consent':
            continue
        reply = tg_update(bot, emp_tg, text=ANSWERS[field])
        if isinstance(reply, str) and reply.startswith('Ответ не принят'):
            findings.friction(n, 'employee-bot', 'questionnaire ' + field, reply)
    reply = tg_update(bot, emp_tg, text=ANSWERS['consent'])
    findings.step(n, 'employee-bot', 'questionnaire saved', 'сохранена' in str(reply), reply if not isinstance(reply, dict) else reply.get('text'))
    with core.connect() as c:
        sid = c.execute('SELECT id FROM specialist WHERE telegram_id=?', (emp_tg,)).fetchone()
    sid = sid[0] if sid else None
    if sid:
        s, body, _ = site.call('/api/verify', {'id': sid, 'verified': True}, cookie=owner_cookie)
        findings.step(n, 'owner', 'verify employee', s == 200, body)
    s, inv2, _ = site.call('/api/owner/invite', {'role': 'employee'}, cookie=owner_cookie)
    reply = tg_update(bot, emp_tg, text='/invite ' + inv2['code'])
    elogin, etemp = parse_creds(reply)
    findings.step(n, 'employee-bot', 'accept employee invite', bool(elogin), reply.get('text') if isinstance(reply, dict) else reply)

    # 3. Client leaves a request on the website form.
    rid = 'sim-' + uuid.uuid4().hex
    s, body, _ = site.call('/api/intake', {'kind': 'client', 'source': 'shooting-landing', 'service': 'reels', 'locale': 'ru',
                                           'idea': 'Тестовый ролик ' + tag, 'contact': '@sim_client_' + tag, 'city': 'Москва', 'request_id': rid}, local=True)
    findings.step(n, 'client', 'submit request on site', s == 200 and isinstance(body, dict) and body.get('status') == 'saved', body)
    intake_id = body.get('id') if isinstance(body, dict) else None

    # 4. Manager sees the request and turns it into a project.
    s, lst, _ = site.call('/api/intakes', cookie=mgr_cookie)
    seen = isinstance(lst, list) and any(i.get('id') == intake_id for i in lst)
    findings.step(n, 'manager-site', 'see new request in list', seen, '' if seen else lst)
    start, end = '2026-12-01T10:00', '2026-12-01T18:00'
    s, body, _ = site.call('/api/intake/project', {'id': intake_id, 'title': 'Проект ' + tag, 'start': start, 'end': end, 'timezone': 'Europe/Moscow'}, cookie=mgr_cookie)
    findings.step(n, 'manager-site', 'turn request into project', s == 200, body)
    order = body.get('order_id') if isinstance(body, dict) else None

    # 5. Routing. A project created from a request has no roles yet: find out whether the manager can add them.
    s, body, _ = site.call('/api/route', {'order': order}, cookie=mgr_cookie) if order else (0, None, None)
    with core.connect() as c:
        slots = c.execute('SELECT COUNT(*) FROM role_slot WHERE order_id=?', (order,)).fetchone()[0] if order else 0
        status = c.execute('SELECT status FROM orders WHERE id=?', (order,)).fetchone()[0] if order else None
    if slots == 0:
        findings.friction(n, 'manager-site', 'project has no roles', 'Проект из заявки без ролей (статус %s): распределение не начнётся, пока не добавлена роль.' % status)
        s2, body2, _ = site.call('/api/owner/role', {'order': order, 'role': 'camera', 'skills': ['interview'], 'budget': 18000}, cookie=mgr_cookie)
        findings.step(n, 'manager-site', 'add role to project (website)', s2 == 200, body2)
    s, body, _ = site.call('/api/route', {'order': order}, cookie=mgr_cookie)
    if s != 200:
        import traceback
        try:
            core.route(order)
            body = str(body) + ' (direct call did not fail)'
        except Exception:
            body = str(body) + ' | ' + traceback.format_exc().strip().splitlines()[-3:][0].strip() + ' ... ' + traceback.format_exc().strip().splitlines()[-1]
    findings.step(n, 'manager-site', 'route project to candidates', s == 200, body)

    # 6. Employee sees the offer in the bot and accepts it.
    offers = tg_update(bot, emp_tg, text='/offers')
    kb = offers.get('reply_markup', {}).get('inline_keyboard', []) if isinstance(offers, dict) else []
    if not kb:
        with core.connect() as c:
            dbg = 'offers_total=%d candidates_for_slot=%s' % (c.execute('SELECT COUNT(*) FROM offer WHERE specialist_id=?', (sid,)).fetchone()[0],
                [x['id'] for x in core.candidates(c, c.execute('SELECT * FROM role_slot WHERE order_id=? LIMIT 1', (order,)).fetchone())] if order else None)
        offers = str(offers) + ' | ' + dbg
    findings.step(n, 'employee-bot', 'see offers (/offers)', bool(kb), offers.get('text') if isinstance(offers, dict) else offers)
    if kb:
        accept = kb[0][0]['callback_data']
        r = tg_update(bot, emp_tg, data=accept)
        findings.step(n, 'employee-bot', 'accept offer', 'принят' in str(r).lower() or 'отклик' in str(r).lower(), r if not isinstance(r, dict) else r.get('text'))
    with core.connect() as c:
        offer = c.execute("SELECT id,status FROM offer WHERE specialist_id=? ORDER BY rowid DESC LIMIT 1", (sid,)).fetchone() if sid else None
    if offer:
        s, body, _ = site.call('/api/select', {'offer': offer['id'], 'actor': 'owner', 'key': 'sim-sel-' + tag}, cookie=owner_cookie)
        findings.step(n, 'owner', 'select accepted offer', s == 200, body)
        if s != 200:
            findings.friction(n, 'owner', 'select accepted offer', 'Выбор отклика вернул ошибку: %s' % body)
        with core.connect() as c:
            assigned = c.execute('SELECT COUNT(*) FROM assignment a JOIN offer o ON o.id=a.offer_id WHERE o.id=?', (offer['id'],)).fetchone()[0]
        findings.step(n, 'system', 'assignment created', assigned == 1, 'assignments=%d' % assigned)

def _login(site, login, password, findings, n, actor, final=False):
    s, body, cookie = site.call('/api/login', {'username': login, 'password': password})
    ok = s == 200 and cookie
    findings.step(n, actor + '-site', 'log in' + (' after password change' if final else ''), ok, body if not ok else 'ok')
    return cookie.split(';')[0] if ok else None


PERSONAS = [
    # name, roles, skills, tasks, rate, budget-role, accept chance
    ('fpv-pilot', ['fpv'], ['fpv'], ['shoot'], 15000, 'fpv', 0.8),
    ('camera-op', ['camera'], ['interview', 'multicam'], ['shoot'], 10000, 'camera', 0.6),
    ('editor', ['editor'], ['editing', 'color'], ['edit'], 8000, 'editor', 0.7),
    ('sound', ['sound'], ['sound'], ['shoot'], 7000, 'sound', 0.5),
    ('ai-gen', ['generative'], ['generation'], ['generate'], 9000, 'generative', 0.9),
]
SERVICES = ['professional', 'reels', 'commercial', 'art', 'editing', 'graphics', 'cg', 'ai']
TASK_OF = {'professional': 'shoot', 'reels': 'shoot', 'commercial': 'shoot', 'art': 'shoot',
           'editing': 'edit', 'graphics': 'generate', 'cg': 'generate', 'ai': 'generate'}
ROLE_OF_TASK = {'shoot': 'camera', 'edit': 'editor', 'generate': 'generative'}

def persona_answers(i, persona):
    name, roles, skills, tasks, rate, _, _ = persona
    a = dict(ANSWERS)
    a.update({'name': 'Персона %s %d' % (name, i), 'roles': ','.join(roles), 'skills': ','.join(skills),
              'tasks': ','.join(tasks), 'rate': str(rate), 'email': '%s-%d@example.invalid' % (name, i)})
    return a

def onboard_employee(bot, site, core, findings, n, tg, persona, i, owner_cookie):
    answers = persona_answers(i, persona)
    tg_update(bot, tg, text='/start')
    for field, _ in bot.FIELDS:
        if field == 'consent':
            continue
        r = tg_update(bot, tg, text=answers[field])
        if isinstance(r, str) and r.startswith('Ответ не принят'):
            findings.friction(n, 'employee-bot', 'questionnaire ' + field, r)
    r = tg_update(bot, tg, text='ДА')
    with core.connect() as c:
        row = c.execute('SELECT id FROM specialist WHERE telegram_id=?', (tg,)).fetchone()
    if row:
        site.call('/api/verify', {'id': row[0], 'verified': True}, cookie=owner_cookie)
    s, inv, _ = site.call('/api/owner/invite', {'role': 'employee'}, cookie=owner_cookie)
    rr = tg_update(bot, tg, text='/invite ' + inv['code'])
    login, _ = parse_creds(rr)
    if not login:
        findings.friction(n, 'employee-bot', 'activate ' + persona[0], rr.get('text') if isinstance(rr, dict) else rr)
    return row[0] if row else None

def run_load(args, site, core, auth, bot, owner_cookie, findings):
    import time, collections, random
    t0 = time.time()
    rng = random.Random(args.seed)
    managers = []
    for m in range(args.managers):
        s, inv, _ = site.call('/api/owner/invite', {'role': 'manager', 'permissions': ['tasks:approve', 'employees:approve', 'contacts:read', 'finances:read']}, cookie=owner_cookie)
        reply = tg_update(bot, 9000 + m, text='/invite ' + inv['code'])
        login, temp = parse_creds(reply)
        newp = 'sim-mgr-' + secrets.token_hex(6)
        cookie = _login(site, login, temp, findings, 0, 'manager')
        site.call('/api/account/password', {'current_password': temp, 'new_password': newp}, cookie=cookie)
        managers.append(_login(site, login, newp, findings, 0, 'manager', final=True))
    sids = {}
    for i, persona in enumerate(PERSONAS * args.employees_per_persona):
        tg = 20000 + i
        sids[tg] = (persona, onboard_employee(bot, site, core, findings, 0, tg, persona, i, owner_cookie))
    intake_ids = []
    rejected = collections.Counter()
    for k in range(args.clients):
        svc = SERVICES[k % len(SERVICES)]
        s, body, _ = site.call('/api/intake', {'kind': 'client', 'source': 'shooting-landing', 'service': svc, 'locale': 'ru',
                                               'idea': 'Бриф %d' % k, 'contact': '@client_%d' % k, 'city': 'Москва', 'request_id': 'load-' + uuid.uuid4().hex}, local=True)
        if s == 200 and isinstance(body, dict) and body.get('status') == 'saved':
            intake_ids.append((body['id'], svc))
        else:
            rejected[str(body)[:80]] += 1
    findings.step(0, 'client', '%d requests accepted' % args.clients, len(intake_ids) == args.clients, 'accepted=%d rejected=%s' % (len(intake_ids), dict(rejected)))
    per_day = args.managers * args.projects_each
    cursor = 0
    projects = []
    selected_total = 0
    seen = collections.Counter(); accepted = collections.Counter(); declined = collections.Counter(); refused = collections.Counter()
    for day in range(args.days):
        batch = intake_ids[cursor: cursor + per_day]
        cursor += len(batch)
        for idx, (iid, svc) in enumerate(batch):
            cookie = managers[idx % len(managers)]
            date = '2026-11-%02d' % (1 + (day * per_day + idx) % 28)
            s, body, _ = site.call('/api/intake/project', {'id': iid, 'title': 'Проект %d-%d' % (day, idx), 'start': date + 'T10:00', 'end': date + 'T18:00', 'timezone': 'Europe/Moscow'}, cookie=cookie)
            if s != 200:
                findings.friction(0, 'manager-site', 'turn request into project', str(body)); continue
            order = body['order_id']
            role = ['camera', 'fpv', 'sound'][idx % 3] if TASK_OF[svc] == 'shoot' else ROLE_OF_TASK[TASK_OF[svc]]
            s2, b2, _ = site.call('/api/owner/role', {'order': order, 'role': role, 'skills': [], 'budget': 20000}, cookie=cookie)
            if s2 != 200:
                findings.friction(0, 'manager-site', 'add role', str(b2)); continue
            s3, b3, _ = site.call('/api/route', {'order': order}, cookie=cookie)
            if s3 != 200:
                findings.friction(0, 'manager-site', 'route', str(b3)); continue
            site.call('/api/owner/price', {'order': order, 'price': 25000}, cookie=owner_cookie)
            projects.append(order)
        # Employees answer the offers they got today; each persona has its own acceptance chance.
        for tg, (persona, sid) in sids.items():
            offers = tg_update(bot, tg, text='/offers')
            kb = offers.get('reply_markup', {}).get('inline_keyboard', []) if isinstance(offers, dict) else []
            seen[persona[0]] += len(kb)
            for row in kb:
                if rng.random() < persona[6]:
                    r = tg_update(bot, tg, data=row[0]['callback_data'])
                    if 'принят' in str(r).lower(): accepted[persona[0]] += 1
                    else: refused[persona[0]] += 1  # e.g. overlapping project already accepted
                else:
                    tg_update(bot, tg, data=row[1]['callback_data']); declined[persona[0]] += 1
        # Owner selects today's accepted offers.
        with core.connect() as c:
            pending = [r[0] for r in c.execute("SELECT id FROM offer WHERE status='responded'")]
        for oid in pending:
            s, body, _ = site.call('/api/select', {'offer': oid, 'actor': 'owner', 'key': 'load-sel-' + oid}, cookie=owner_cookie)
            if s == 200: selected_total += 1
            else: findings.friction(0, 'owner', 'select offer', str(body))
        with core.connect() as c:
            waiting = c.execute("SELECT COUNT(*) FROM intake i LEFT JOIN intake_project p ON p.intake_id=i.id WHERE i.kind='client' AND p.intake_id IS NULL").fetchone()[0]
        findings.step(0, 'system', 'day %d: projects %d, selected %d, requests still waiting %d' % (day + 1, len(projects), selected_total, waiting), True, 'day=%d' % (day + 1))
    for persona in PERSONAS:
        findings.step(0, 'employee-bot', 'offers reach ' + persona[0], seen[persona[0]] > 0, 'offers=%d accepted=%d declined=%d refused=%d' % (seen[persona[0]], accepted[persona[0]], declined[persona[0]], refused[persona[0]]))
    with core.connect() as c:
        empty = [o for o in projects if c.execute("SELECT COUNT(*) FROM assignment a JOIN role_slot r ON r.id=a.slot_id WHERE r.order_id=?", (o,)).fetchone()[0] == 0
                 and c.execute("SELECT COUNT(*) FROM offer f JOIN role_slot r ON r.id=f.slot_id WHERE r.order_id=? AND f.status IN ('pending','responded')", (o,)).fetchone()[0] == 0]
        status_of = {o: c.execute('SELECT status FROM orders WHERE id=?', (o,)).fetchone()[0] for o in empty}
    stuck = [o for o in empty if status_of[o] != 'no_candidates']
    if stuck:
        findings.friction(0, 'system', 'projects without candidates and without status', '%d проектов без назначения, без предложения и без статуса no_candidates' % len(stuck))
    findings.step(0, 'system', 'every empty project is marked no_candidates', not stuck, 'empty=%d marked=%d' % (len(empty), len(empty) - len(stuck)))
    with core.connect() as c:
        dup_offers = c.execute("SELECT COUNT(*) FROM (SELECT slot_id,specialist_id,version FROM offer GROUP BY slot_id,specialist_id,version HAVING COUNT(*)>1)").fetchone()[0]
        double_assign = c.execute("SELECT COUNT(*) FROM (SELECT slot_id FROM assignment GROUP BY slot_id HAVING COUNT(*)>1)").fetchone()[0]
        orphan = c.execute("SELECT COUNT(*) FROM assignment a LEFT JOIN offer o ON o.id=a.offer_id WHERE o.id IS NULL").fetchone()[0]
        assigned = c.execute('SELECT COUNT(*) FROM assignment').fetchone()[0]
    expected_waiting = max(0, args.clients - args.managers * args.projects_each * args.days)
    with core.connect() as c:
        waiting_final = c.execute("SELECT COUNT(*) FROM intake i LEFT JOIN intake_project p ON p.intake_id=i.id WHERE i.kind='client' AND p.intake_id IS NULL").fetchone()[0]
    findings.step(0, 'manager-site', 'requests waiting match capacity (clients - managers x projects x days)', waiting_final == expected_waiting, 'waiting=%d expected=%d' % (waiting_final, expected_waiting))
    findings.step(0, 'system', 'data integrity: no duplicate offers, one assignment per slot', dup_offers == 0 and double_assign == 0 and orphan == 0, 'dup_offers=%d double_assign=%d orphan=%d' % (dup_offers, double_assign, orphan))
    findings.step(0, 'system', 'assignments created', assigned == selected_total, 'selected=%d assignments=%d' % (selected_total, assigned))
    s, summary, _ = site.call('/api/owner/economics/summary', {}, cookie=owner_cookie)
    t = summary['totals'] if s == 200 else {}
    if t:
        pct = t['margin'] / t['client_price'] * 100 if t['client_price'] else 0
        findings.step(0, 'owner', 'economics: all clients', True, 'orders=%d priced=%d client_price=%.0f payouts=%.0f margin=%.0f (%.1f%%)' % (t['orders'], t['priced'], t['client_price'], t['payouts'], t['margin'], pct))
        findings.step(0, 'owner', 'economics summary matches orders', abs(t['client_price'] - 25000 * t['priced']) < 1, 'priced orders at 25000 each')
    else:
        findings.friction(0, 'owner', 'economics summary', str(summary))
    findings.step(0, 'system', 'load run time', True, '%.1f s; managers=%d days=%d' % (time.time() - t0, args.managers, args.days))


def run_human(args, site, core, auth, bot, owner_cookie, findings):
    """Same flow as load, but people make mistakes: double submits, changed minds, unanswered offers,
    double taps, wrong dates, forgotten roles, mid-way transfers. Every unexpected outcome is recorded."""
    import time, collections, random
    t0 = time.time()
    rng = random.Random(args.seed + 1)
    unexpected = collections.Counter()
    def note(kind, detail):
        unexpected[kind] += 1
        if unexpected[kind] <= 3:
            findings.friction(0, 'human', kind, detail)
    managers = []
    for m in range(args.managers):
        s, inv, _ = site.call('/api/owner/invite', {'role': 'manager', 'permissions': ['contacts:read', 'finances:read']}, cookie=owner_cookie)
        reply = tg_update(bot, 9000 + m, text='/invite ' + inv['code'])
        login, temp = parse_creds(reply)
        if not login:
            note('manager invite failed', str(reply)[:160]); continue
        cookie = _login(site, login, temp, findings, 0, 'manager')
        newp = 'sim-mgr-' + secrets.token_hex(6)
        site.call('/api/account/password', {'current_password': temp, 'new_password': newp}, cookie=cookie)
        managers.append(_login(site, login, newp, findings, 0, 'manager', final=True))
    sids = {}
    for i, persona in enumerate(PERSONAS * args.employees_per_persona):
        tg = 20000 + i
        # Some people type a wrong rate first, then correct it.
        if rng.random() < 0.1:
            tg_update(bot, tg, text='/start'); tg_update(bot, tg, text='Тест')
            r = tg_update(bot, tg, text='сколько-то')
            if isinstance(r, str) and r.startswith('Ответ не принят'): unexpected['wrong answer accepted with message'] += 0
        sids[tg] = (persona, onboard_employee(bot, site, core, findings, 0, tg, persona, i, owner_cookie))
    # Clients: double submits (same request id), changed minds (second request later), empty brief.
    intake_ids = []
    for k in range(args.clients):
        svc = SERVICES[k % len(SERVICES)]
        rid = 'human-' + uuid.uuid4().hex
        body = {'kind': 'client', 'source': 'shooting-landing', 'service': svc, 'locale': 'ru', 'idea': 'Бриф %d' % k, 'contact': '@h_%d' % k, 'city': 'Москва', 'request_id': rid}
        if rng.random() < 0.05:
            body['idea'] = '   '
        s, b, _ = site.call('/api/intake', body, local=True)
        if s != 200:
            if body['idea'].strip() == '':
                continue  # expected rejection
            note('valid request rejected', str(b)[:160]); continue
        intake_ids.append((b['id'], svc))
        if rng.random() < 0.15:  # double submit with the same request id must not create a second request
            s2, b2, _ = site.call('/api/intake', body, local=True)
            if s2 != 200 or b2.get('id') != b['id']:
                note('double submit created a second request', str(b2)[:160])
        if rng.random() < 0.08:  # changed mind: a new request from the same person with a new id
            body2 = dict(body, request_id='human-' + uuid.uuid4().hex, idea='Передумал: ' + body['idea'])
            s3, b3, _ = site.call('/api/intake', body2, local=True)
            if s3 == 200: intake_ids.append((b3['id'], svc)); note('same contact sent a second request (manager must merge)', 'contact @h_%d' % k)
    findings.step(0, 'client', 'requests accepted with mistakes', len(intake_ids) > 0, 'accepted=%d' % len(intake_ids))
    per_day = max(1, len(managers)) * args.projects_each
    cursor = 0; projects = []; selected = 0; declined_by_double = 0
    for day in range(args.days):
        batch = intake_ids[cursor: cursor + per_day]; cursor += len(batch)
        for idx, (iid, svc) in enumerate(batch):
            if not managers: break
            cookie = managers[idx % len(managers)]
            date = '2026-11-%02d' % (1 + (day * per_day + idx) % 28)
            end = date + 'T18:00'
            if rng.random() < 0.05: end = date + 'T08:00'  # wrong time: end before start
            s, b, _ = site.call('/api/intake/project', {'id': iid, 'title': 'Проект %d-%d' % (day, idx), 'start': date + 'T10:00', 'end': end, 'timezone': 'Europe/Moscow'}, cookie=cookie)
            if s != 200:
                if end.endswith('T08:00'): continue  # expected rejection
                note('project creation failed', str(b)[:160]); continue
            order = b['order_id']
            if rng.random() < 0.05:  # manager forgets the role; the project waits in the queue
                note('project without role after creation', order)
            else:
                role = ['camera', 'fpv', 'sound'][idx % 3] if TASK_OF[svc] == 'shoot' else ROLE_OF_TASK[TASK_OF[svc]]
                s2, b2, _ = site.call('/api/owner/role', {'order': order, 'role': role, 'skills': [], 'budget': 20000}, cookie=cookie)
                if s2 != 200: note('role add failed', str(b2)[:160]); continue
                s3, b3, _ = site.call('/api/route', {'order': order}, cookie=cookie)
                if s3 != 200: note('route failed', str(b3)[:160]); continue
            if rng.random() < 0.05 and len(managers) > 1:  # mid-way transfer to another manager
                with auth.connect() as acc:
                    newbie = [r['id'] for r in acc.execute("SELECT id FROM account WHERE role='manager' AND active=1").fetchall()]
                me = [r['id'] for r in []]
                with core.connect() as c:
                    import documents
                    documents.schema_orders(c)
                    cur = c.execute('SELECT account_id FROM order_manager WHERE order_id=?', (order,)).fetchone()
                target = next((x for x in newbie if not cur or x != cur[0]), None)
                if target:
                    s4, b4, _ = site.call('/api/orders/transfer', {'order': order, 'to': target}, cookie=cookie)
                    if s4 != 200: note('transfer failed', str(b4)[:160])
            site.call('/api/owner/price', {'order': order, 'price': 25000}, cookie=owner_cookie)
            projects.append(order)
        for tg, (persona, sid) in sids.items():
            offers = tg_update(bot, tg, text='/offers')
            kb = offers.get('reply_markup', {}).get('inline_keyboard', []) if isinstance(offers, dict) else []
            for row in kb:
                roll = rng.random()
                if roll < 0.2:
                    continue  # ignores the offer; it stays pending and expires later
                if roll < 0.3:  # double tap: the second tap must not change the result
                    r1 = tg_update(bot, tg, data=row[0]['callback_data'])
                    r2 = tg_update(bot, tg, data=row[0]['callback_data'])
                    if str(r1) != str(r2) and 'уже' not in str(r2).lower() and 'недоступ' not in str(r2).lower():
                        note('double tap gave a different answer', '%s / %s' % (str(r1)[:60], str(r2)[:60]))
                    continue
                if roll < 0.2 + rng.random() * 0.0:
                    continue
                if rng.random() < persona[6]:
                    r = tg_update(bot, tg, data=row[0]['callback_data'])
                    if 'принят' not in str(r).lower(): note('accept refused for a reason the employee can see', str(r)[:120])
                else:
                    tg_update(bot, tg, data=row[1]['callback_data'])
        with core.connect() as c:
            pending = [r[0] for r in c.execute("SELECT id FROM offer WHERE status='responded'")]
        for oid in pending:
            s, b, _ = site.call('/api/select', {'offer': oid, 'actor': 'owner', 'key': 'human-sel-' + oid}, cookie=owner_cookie)
            if s == 200: selected += 1
            else: note('select failed', str(b)[:160])
    with core.connect() as c:
        ignored = c.execute("SELECT COUNT(*) FROM offer WHERE status='pending'").fetchone()[0]
        no_roles = c.execute("SELECT COUNT(*) FROM orders o WHERE NOT EXISTS (SELECT 1 FROM role_slot r WHERE r.order_id=o.id)").fetchone()[0]
        dup_intakes = c.execute("SELECT COUNT(*) FROM (SELECT contact FROM (SELECT json_extract(payload,'$.contact') AS contact FROM intake WHERE kind='client') GROUP BY contact HAVING COUNT(*)>1)").fetchone()[0]
        dup_offers = c.execute("SELECT COUNT(*) FROM (SELECT slot_id,specialist_id,version FROM offer GROUP BY slot_id,specialist_id,version HAVING COUNT(*)>1)").fetchone()[0]
        double_assign = c.execute("SELECT COUNT(*) FROM (SELECT slot_id FROM assignment GROUP BY slot_id HAVING COUNT(*)>1)").fetchone()[0]
    findings.step(0, 'system', 'data integrity under human mistakes', dup_offers == 0 and double_assign == 0, 'dup_offers=%d double_assign=%d' % (dup_offers, double_assign))
    findings.step(0, 'system', 'offers left pending (ignored by people)', True, 'pending=%d' % ignored)
    findings.step(0, 'system', 'projects without any role', True, 'no_roles=%d' % no_roles)
    findings.step(0, 'system', 'same contact with several requests', True, 'contacts_with_several_requests=%d (manager must merge)' % dup_intakes)
    findings.step(0, 'system', 'selected under human mistakes', True, 'selected=%d' % selected)
    findings.step(0, 'system', 'human run time', True, '%.1f s' % (time.time() - t0))
    findings.step(0, 'system', 'unexpected outcomes', sum(unexpected.values()) == 0, dict(unexpected))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--cycles', type=int, default=3); ap.add_argument('--out', required=True)
    ap.add_argument('--mode', choices=['cycles', 'load', 'human'], default='cycles'); ap.add_argument('--clients', type=int, default=100)
    ap.add_argument('--seed', type=int, default=7); ap.add_argument('--days', type=int, default=1); ap.add_argument('--managers', type=int, default=2); ap.add_argument('--projects-each', type=int, default=5); ap.add_argument('--employees-per-persona', type=int, default=3)
    args = ap.parse_args()
    tmp = tempfile.mkdtemp(prefix='renn-sim-')
    core, auth, server, bot = boot(tmp)
    owner_pass = 'sim-owner-' + secrets.token_hex(8)
    auth.create_user('owner', owner_pass, 'owner')
    site = Site(server)
    findings = Findings()
    try:
        s, body, cookie = site.call('/api/login', {'username': 'owner', 'password': owner_pass})
        owner_cookie = cookie.split(';')[0]
        if args.mode == 'human':
            run_human(args, site, core, auth, bot, owner_cookie, findings)
        elif args.mode == 'load':
            run_load(args, site, core, auth, bot, owner_cookie, findings)
        else:
          for n in range(1, args.cycles + 1):
            try:
                run_cycle(n, site, core, auth, bot, owner_cookie, findings)
            except Exception as e:
                findings.friction(n, 'system', 'cycle crashed', '%s: %s' % (type(e).__name__, e))
    finally:
        site.close()
    out = pathlib.Path(args.out); out.mkdir(parents=True, exist_ok=True)
    (out / 'results.json').write_text(json.dumps(findings.items, ensure_ascii=False, indent=2), encoding='utf-8')
    fails = [f for f in findings.items if not f['ok']]
    title = ('# Симуляция: %d циклов' % args.cycles) if args.mode == 'cycles' else ('# Нагрузка: %d клиентов, %d менеджеров по %d проектов в день, дней: %d' % (args.clients, args.managers, args.projects_each, args.days))
    lines = [title, '', 'Шагов: %d, неуспешных: %d' % (len(findings.items), len(fails)), '']
    for f in fails:
        lines.append('- цикл %d · %s · %s — %s' % (f['cycle'], f['actor'], f['step'], f['detail']))
    (out / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))

if __name__ == '__main__':
    main()
