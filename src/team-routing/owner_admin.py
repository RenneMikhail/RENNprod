"""Owner-only management: staff archive, account deactivation, order economics, safe order deletion.
Every write checks the owner role again; nothing here is reachable by manager or employee accounts."""
import json, math
import auth, core

def require_owner(actor):
    if not actor or actor.get('role') != 'owner':
        raise PermissionError('Только владелец')

def staff_list(c):
    rows = c.execute('SELECT id,name,profile,verified,telegram_id FROM specialist ORDER BY name').fetchall()
    out = []
    for r in rows:
        profile = json.loads(r['profile'])
        out.append({'id': r['id'], 'name': r['name'], 'roles': profile.get('roles', []), 'city': profile.get('city', ''),
                    'verified': bool(r['verified']), 'telegram': r['telegram_id'] is not None,
                    'archived': bool(profile.get('archived'))})
    return out

def archive_staff(c, actor, sid):
    require_owner(actor)
    row = c.execute('SELECT profile FROM specialist WHERE id=?', (sid,)).fetchone()
    if not row:
        raise ValueError('Сотрудник не найден')
    active = c.execute("SELECT 1 FROM assignment a JOIN role_slot s ON s.id=a.slot_id JOIN orders o ON o.id=s.order_id "
                       "WHERE a.specialist_id=? AND o.end>?", (sid, core.now())).fetchone()
    if active:
        raise ValueError('Нельзя убрать сотрудника с активным назначением')
    profile = json.loads(row['profile']); profile['archived'] = True
    old = c.execute('SELECT telegram_id FROM specialist WHERE id=?', (sid,)).fetchone()[0]
    if old is not None: profile['archived_telegram_id'] = old
    c.execute('UPDATE specialist SET profile=?, telegram_id=NULL WHERE id=?', (json.dumps(profile, ensure_ascii=False), sid))
    c.execute("UPDATE offer SET status='withdrawn' WHERE specialist_id=? AND status IN ('pending','responded')", (sid,))
    c.execute('UPDATE availability SET active=0 WHERE specialist_id=?', (sid,))
    return {'status': 'archived', 'id': sid}

def restore_staff(c, actor, sid):
    require_owner(actor)
    row = c.execute('SELECT profile FROM specialist WHERE id=?', (sid,)).fetchone()
    if not row:
        raise ValueError('Сотрудник не найден')
    profile = json.loads(row['profile']); profile.pop('archived', None)
    tg = profile.pop('archived_telegram_id', None)
    if tg is not None and c.execute('SELECT 1 FROM specialist WHERE telegram_id=? AND id<>?', (tg, sid)).fetchone() is None:
        c.execute('UPDATE specialist SET profile=?, telegram_id=? WHERE id=?', (json.dumps(profile, ensure_ascii=False), tg, sid))
        return {'status': 'restored', 'id': sid, 'telegram': True}
    c.execute('UPDATE specialist SET profile=? WHERE id=?', (json.dumps(profile, ensure_ascii=False), sid))
    return {'status': 'restored', 'id': sid, 'telegram': False, 'note': 'Telegram нужно привязать заново'}

def deactivate_account(actor, account_id, path=None):
    require_owner(actor)
    if account_id == actor['id']:
        raise ValueError('Нельзя отключить свой аккаунт')
    with auth.connect(path) as a:
        row = a.execute('SELECT role FROM account WHERE id=?', (account_id,)).fetchone()
        if not row:
            raise ValueError('Аккаунт не найден')
        if row['role'] == 'owner':
            raise ValueError('Владельца нельзя отключить')
        a.execute('UPDATE account SET active=0 WHERE id=?', (account_id,))
        a.execute('DELETE FROM session WHERE user_id=?', (account_id,))
    return {'status': 'deactivated', 'id': account_id}

def payout_groups(terms_list):
    groups = {}
    for terms in terms_list:
        t = json.loads(terms)
        key = (t.get('currency') or '?', t.get('fee_unit') or '?')
        groups[key] = groups.get(key, 0.0) + float(t.get('fee') or 0)
    return groups

def combined_payout(groups):
    """One comparable number only when every payout shares one currency and is per task; otherwise None."""
    if not groups:
        return 0.0
    if len(groups) == 1:
        (currency, unit), total = next(iter(groups.items()))
        if unit == 'За задачу':
            return total
    return None

def order_economics(c, order_id):
    order = c.execute('SELECT id,title,brief FROM orders WHERE id=?', (order_id,)).fetchone()
    if not order:
        raise ValueError('Заказ не найден')
    brief = json.loads(order['brief'] or '{}')
    client_price = brief.get('client_price')
    budget = c.execute('SELECT COALESCE(SUM(budget),0) FROM role_slot WHERE order_id=?', (order_id,)).fetchone()[0]
    groups = payout_groups(r['terms'] for r in c.execute(
        "SELECT o.terms FROM assignment a JOIN offer o ON o.id=a.offer_id JOIN role_slot s ON s.id=a.slot_id WHERE s.order_id=?", (order_id,)))
    payouts = combined_payout(groups)
    margin = (float(client_price) - payouts) if (payouts is not None and isinstance(client_price, (int, float))) else None
    return {'order_id': order_id, 'title': order['title'], 'client_price': client_price,
            'slot_budget_total': budget, 'payouts_assigned': payouts,
            'payouts_by_currency_and_unit': [{'currency': k[0], 'unit': k[1], 'total': v} for k, v in groups.items()], 'margin': margin}

def set_client_price(c, actor, order_id, price):
    require_owner(actor)
    if isinstance(price, bool) or not isinstance(price, (int, float)) or not math.isfinite(price) or price < 0:
        raise ValueError('Цена клиента: неотрицательное число')
    row = c.execute('SELECT brief FROM orders WHERE id=?', (order_id,)).fetchone()
    if not row:
        raise ValueError('Заказ не найден')
    brief = json.loads(row['brief'] or '{}'); brief['client_price'] = price
    c.execute('UPDATE orders SET brief=? WHERE id=?', (json.dumps(brief, ensure_ascii=False), order_id))
    return {'status': 'saved', 'order_id': order_id, 'client_price': price}

def delete_order(c, actor, order_id):
    require_owner(actor)
    if not c.execute('SELECT 1 FROM orders WHERE id=?', (order_id,)).fetchone():
        raise ValueError('Заказ не найден')
    if c.execute('SELECT 1 FROM assignment a JOIN role_slot s ON s.id=a.slot_id WHERE s.order_id=?', (order_id,)).fetchone():
        raise ValueError('Нельзя удалить заказ с назначениями. Сначала снимите назначения.')
    if c.execute('SELECT 1 FROM workspace WHERE order_id=?', (order_id,)).fetchone():
        raise ValueError('Нельзя удалить заказ с созданным пространством')
    import documents
    documents.schema(c)
    if c.execute("SELECT 1 FROM document WHERE owner_kind='order' AND owner_id=?", (order_id,)).fetchone():
        raise ValueError('Нельзя удалить заказ с документами: сначала архивируйте документы')
    c.execute('DELETE FROM offer WHERE slot_id IN (SELECT id FROM role_slot WHERE order_id=?)', (order_id,))
    c.execute('DELETE FROM manager_acceptance WHERE order_id=?', (order_id,))
    import intake_delivery
    intake_delivery.list_intakes(c)  # creates the intake_project link table if missing
    c.execute('DELETE FROM intake_project WHERE order_id=?', (order_id,))
    c.execute('DELETE FROM role_slot WHERE order_id=?', (order_id,))
    c.execute('DELETE FROM orders WHERE id=?', (order_id,))
    return {'status': 'deleted', 'order_id': order_id}

ROLE_CODES = ('camera','editor','sound','manager','generative','event','cg','fpv','designer','gaffer','lighting','driver','costume','makeup')
def add_role_slot(c, actor, order_id, role, skills, budget):
    """Owner or manager with tasks:approve adds a role with a budget to a project so it can be routed."""
    if not actor or actor.get('role') not in ('owner','manager') or not (actor.get('role')=='owner' or 'tasks:approve' in actor.get('permissions',[])):
        raise PermissionError('Нет права добавлять роли')
    if role not in ROLE_CODES:raise ValueError('Неизвестная роль')
    if not isinstance(skills,list) or not all(isinstance(x,str) for x in skills):raise ValueError('Навыки: список кодов')
    if isinstance(budget,bool) or not isinstance(budget,(int,float)) or not math.isfinite(budget) or budget<=0 or float(budget)!=int(budget):raise ValueError('Бюджет: целое положительное число')
    if not c.execute('SELECT 1 FROM orders WHERE id=?',(order_id,)).fetchone():raise ValueError('Заказ не найден')
    slot_id=core.uid()
    c.execute("INSERT INTO role_slot(id,order_id,role,skills,budget,status) VALUES(?,?,?,?,?,'open')",(slot_id,order_id,role,json.dumps(skills,ensure_ascii=False),int(budget)))
    c.execute("UPDATE orders SET status='open' WHERE id=? AND status='human_review'",(order_id,))
    return {'status':'saved','slot_id':slot_id}

def economics_summary(c, limit=500):
    """One pass for the owner dashboard: totals over all orders and the first `limit` rows."""
    terms_by_order = {}
    for r in c.execute("SELECT s.order_id, o.terms FROM assignment a JOIN offer o ON o.id=a.offer_id JOIN role_slot s ON s.id=a.slot_id"):
        terms_by_order.setdefault(r[0], []).append(r[1])
    payouts = {}
    not_comparable = 0
    for oid, terms_list in terms_by_order.items():
        total = combined_payout(payout_groups(terms_list))
        if total is None:
            not_comparable += 1
        else:
            payouts[oid] = total
    budgets = {r[0]: r[1] or 0 for r in c.execute('SELECT order_id, SUM(budget) FROM role_slot GROUP BY order_id')}
    totals = {'orders': 0, 'priced': 0, 'client_price': 0.0, 'payouts': 0.0, 'payouts_all_units_raw': 0.0, 'budget': 0.0, 'margin': 0.0}
    raw_by_order = {oid: sum(float(json.loads(t).get('fee') or 0) for t in lst) for oid, lst in terms_by_order.items()}
    items = []
    for row in c.execute('SELECT id, title, brief FROM orders ORDER BY rowid'):
        brief = json.loads(row['brief'] or '{}')
        price = brief.get('client_price')
        # No assignments means zero payouts; mixed currencies or units mean no comparable number.
        paid = payouts[row['id']] if row['id'] in payouts else (None if row['id'] in terms_by_order else 0.0)
        totals['payouts_all_units_raw'] += raw_by_order.get(row['id'], 0.0)
        totals['orders'] += 1
        totals['budget'] += float(budgets.get(row['id'], 0))
        if paid is not None:
            totals['payouts'] += paid
        if isinstance(price, (int, float)):
            totals['priced'] += 1
            totals['client_price'] += float(price)
            if paid is not None:
                totals['margin'] += float(price) - paid
        if len(items) < limit:
            items.append({'order_id': row['id'], 'title': row['title'], 'client_price': price,
                          'payouts': paid, 'margin': (float(price) - paid) if (isinstance(price, (int, float)) and paid is not None) else None})
    totals['not_comparable'] = not_comparable  # orders whose payouts mix currencies or units: no margin, raw sum shown separately
    return {'totals': totals, 'items': items, 'shown': len(items)}
