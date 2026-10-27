"""Outbound polling only; only responds to inbound private user messages. Token never logged."""
import json, os, sys, time, urllib.request, urllib.error, fcntl, secrets
import core
def token():
    direct=os.environ.get('TELEGRAM_BOT_TOKEN','').strip()
    if direct:return direct
    explicit=os.environ.get('RENN_PROD_ENV_FILE')
    env_path=core.Path(explicit).expanduser() if explicit else core.ROOT.parent.parent/'.env'
    try:
        for line in env_path.read_text().splitlines():
            if line.startswith('TELEGRAM_BOT_TOKEN='):
                value=line.split('=',1)[1].strip().strip('"').strip("'")
                if value:return value
    except OSError:pass
    raise RuntimeError('Telegram credentials unavailable. Set TELEGRAM_BOT_TOKEN or RENN_PROD_ENV_FILE outside the repository; never commit secrets.')

def call(method,payload=None):
    req=urllib.request.Request('https://api.telegram.org/bot'+token()+'/'+method,data=json.dumps(payload or {}).encode(),headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=40) as r:j=json.load(r)
        if not j.get('ok'):raise RuntimeError('Telegram API rejected request')
        return j['result']
    except urllib.error.HTTPError as e:
        try:description=json.loads(e.read()).get('description','')
        except Exception:description=''
        if method=='editMessageText' and e.code==400 and 'message is not modified' in description:return True
        raise RuntimeError('Telegram transport/API failure (details suppressed)') from None
    except Exception:raise RuntimeError('Telegram transport/API failure (details suppressed)') from None
FIELDS=[('name','Как вас зовут?'),('city','Ваш город?'),('roles','Роли (коды через запятую): '+', '.join(core.ROLES)),('skills','Навыки (коды через запятую): '+', '.join(core.SKILLS)),('tasks','Типы задач (коды через запятую): '+', '.join(core.TASKS)),('mobility','Формат: city / travel / remote'),('equipment','Техника: none / camera / camera_audio / studio'),('rate','Ориентир за смену или задачу — число. Точные условия подтверждаются в предложении.'),('currency','Валюта: RUB / EUR / USD'),('languages','Языки через запятую: ru, en, es, ka'),('email','Email для резерва (обязателен, подтверждение пока не подключено)'),('phone','Телефон (необязательно; отправьте - для пропуска)'),('timezone','Часовой пояс: Europe/Moscow, Europe/Madrid, Asia/Tbilisi, America/New_York или UTC'),('portfolio','Ссылка на портфолио (https://...)'),('portfolio_role','Ваша собственная роль в работах портфолио'),('consent','Согласны сохранить анкету в локальной базе RENN Prod для рассмотрения проектного сотрудничества? Ответьте ДА. Контакты не подтверждаются автоматически, квалификацию проверит человек; задания/доход не гарантируются.')]
def parse_field(field,text):
    t=text.strip()
    if len(t)>2500:raise ValueError('Слишком длинный ответ')
    allowed={'roles':core.ROLES,'skills':core.SKILLS,'tasks':core.TASKS,'languages':['ru','en','es','ka']}
    if field in allowed:
        xs=[x.strip() for x in t.split(',') if x.strip()]
        if not xs or not set(xs)<=set(allowed[field]):raise ValueError('Выберите перечисленные коды через запятую')
        return xs
    if field in ['mobility','equipment','currency']:
        values={'mobility':['city','travel','remote'],'equipment':['none','camera','camera_audio','studio'],'currency':['RUB','EUR','USD']}
        if t not in values[field]:raise ValueError('Выберите один из перечисленных вариантов')
    if field=='rate':
        if float(t)<=0:raise ValueError('Нужно положительное число')
    if field=='email' and '@' not in t:raise ValueError('Укажите email')
    if field=='timezone':core.ZoneInfo(t)
    if field=='portfolio' and not t.startswith(('https://','http://')):raise ValueError('Нужна https:// ссылка')
    if field=='consent' and t.upper() not in ['ДА','YES']:raise ValueError('Для сохранения нужно ДА; для удаления черновика /cancel')
    if not t:raise ValueError('Пустой ответ')
    return '' if field=='phone' and t=='-' else t

def handle(message,connection=None):
    if message.get('chat',{}).get('type')!='private' or message.get('from',{}).get('is_bot'):return None
    ident=message['from']['id'];text=message.get('text','').strip()
    if not text:return 'Отправьте текстовый ответ или /start.'
    with (core.nullcontext(connection) if connection else core.connect()) as c:
        if text.split(' ')[0] in ['/start','/cancel']:
            c.execute('DELETE FROM bot_state WHERE telegram_id=?',(ident,))
            if text=='/cancel':return 'Черновик удалён. Сохранённый профиль остаётся в базе; удаление через владельца. /start — начать заново.'
            p={'telegram':'@'+message['from'].get('username','') if message['from'].get('username') else '', 'contact_verified':False}
            c.execute('INSERT INTO bot_state VALUES(?,0,?)',(ident,json.dumps(p)))
            return 'RENN Prod · проектное сотрудничество. Анкета сохраняется на локальном Mac владельца. /cancel — удалить черновик; /profile — статус. '+FIELDS[0][1]
        if text=='/blocks':
            person=c.execute('SELECT id FROM specialist WHERE telegram_id=?',(ident,)).fetchone()
            if not person:return 'Сначала заполните анкету: /start'
            rows=c.execute('SELECT id,start,end,timezone FROM availability WHERE specialist_id=? AND active=1',(person[0],)).fetchall()
            return ('\n'.join(' | '.join(str(v) for v in r) for r in rows) or 'Нет блокировок. Это не подтверждение доступности.')+'\nДобавить: /busy 2026-12-01T10:00|2026-12-01T12:00|Europe/Moscow; отмена: /unblock ID. Для изменения отмените и добавьте новый.'
        if text.startswith('/busy ') or text.startswith('/unblock '):
            person=c.execute('SELECT id FROM specialist WHERE telegram_id=?',(ident,)).fetchone()
            if not person:return 'Сначала заполните анкету: /start'
            try:
                if text.startswith('/busy '):
                    a,b,tz=text[6:].split('|');a,b=core.normalize_interval(a.strip(),b.strip(),tz.strip())
                    if core.busy(c,person[0],a,b):return 'Интервал пересекает занятость или подтверждённое назначение.'
                    bid=core.uid();c.execute('INSERT INTO availability VALUES(?,?,?,?,?,1)',(bid,person[0],a,b,tz.strip()));return 'Занятость сохранена: '+bid
                bid=text[9:].strip();r=c.execute('UPDATE availability SET active=0 WHERE id=? AND specialist_id=?',(bid,person[0]));return 'Блокировка отменена.' if r.rowcount else 'Блокировка не найдена.'
            except Exception:return 'Формат: /busy 2026-12-01T10:00|2026-12-01T12:00|Europe/Moscow или /unblock ID'
        if text=='/profile':
            s=c.execute('SELECT name,verified FROM specialist WHERE telegram_id=?',(ident,)).fetchone()
            return (s['name']+' · '+('квалификация проверена владельцем' if s['verified'] else 'ожидает проверки квалификации')+'; контакты не подтверждены') if s else 'Анкеты ещё нет. /start'
        st=c.execute('SELECT * FROM bot_state WHERE telegram_id=?',(ident,)).fetchone()
        if not st:return 'Для анкеты отправьте /start. Задания и доход не гарантируются.'
        step=st['step'];p=json.loads(st['payload']);field=FIELDS[step][0]
        try:p[field]=parse_field(field,text)
        except Exception:return 'Ответ не принят. '+FIELDS[step][1]
        if step==len(FIELDS)-1:
            p.pop('consent',None)
            for key in ['_ui_nonce','_ui_step','_selected']:p.pop(key,None)
            try:sid=core.register(p,telegram_id=ident,dbconn=c)
            except Exception:return 'Анкета не сохранена. Проверьте поля или начните /start.'
            c.execute('DELETE FROM bot_state WHERE telegram_id=?',(ident,))
            return 'Анкета сохранена в локальной базе RENN Prod. ID: '+sid+'. Квалификацию проверит человек; контакты не подтверждены. Спасибо! /profile — статус.'
        c.execute('UPDATE bot_state SET step=?,payload=? WHERE telegram_id=?',(step+1,json.dumps(p,ensure_ascii=False),ident))
        return FIELDS[step+1][1]

LABELS={**core.ROLE_LABELS, **{'interview': 'Интервью', 'multicam': 'Мультикамера', 'color': 'Цвет', 'editing': 'Монтаж', 'generation': 'AI-генерация', 'coordination': 'Координация', 'shoot': 'Съёмка', 'edit': 'Монтаж', 'generate': 'Генерация', 'city': 'В своём городе', 'travel': 'Готов к выездам', 'remote': 'Удалённо', 'none': 'Без своей техники', 'camera_audio': 'Камера и звук', 'studio': 'Студия', 'ru': 'Русский', 'en': 'Английский', 'es': 'Испанский', 'ka': 'Грузинский', 'ДА': 'Согласен'}}
MULTI={'roles','skills','tasks','languages'}
def choices(field):
    return {'roles':core.ROLES,'skills':core.SKILLS,'tasks':core.TASKS,'languages':['ru','en','es','ka'],'mobility':['city','travel','remote'],'equipment':['none','camera','camera_audio','studio'],'currency':['RUB','EUR','USD'],'timezone':['Europe/Moscow','Europe/Madrid','Asia/Tbilisi','America/New_York','UTC'],'consent':['ДА']}.get(field,[])
def prompt(ident,connection):
    st=connection.execute('SELECT * FROM bot_state WHERE telegram_id=?',(ident,)).fetchone()
    if not st:return None
    p=json.loads(st['payload']);field=FIELDS[st['step']][0];xs=choices(field)
    if not xs:return None
    if '_ui_nonce' not in p:
        p['_ui_nonce']=secrets.token_hex(6);p['_ui_step']=st['step'];p['_selected']=[]
        connection.execute('UPDATE bot_state SET payload=? WHERE telegram_id=?',(json.dumps(p,ensure_ascii=False),ident))
    nonce=p['_ui_nonce'];selected=p.get('_selected',[])
    keyboard=[[{'text':('✓ ' if x in selected else '')+('Камера' if field=='equipment' and x=='camera' else LABELS.get(x,x)), 'callback_data':nonce+':'+str(i)}] for i,x in enumerate(xs)]
    if field in MULTI:keyboard.append([{'text':'Готово →','callback_data':nonce+':done'}])
    keyboard.append([{'text':'Отмена','callback_data':nonce+':cancel'}])
    title={'roles':'Выберите ваши роли','skills':'Выберите навыки','tasks':'Какие задачи берёте?','languages':'На каких языках работаете?','mobility':'Где готовы работать?','equipment':'Какая техника есть?','currency':'Выберите валюту','timezone':'Ваш часовой пояс','consent':FIELDS[st['step']][1]}[field]
    return {'text':title+(' · можно выбрать несколько' if field in MULTI else ''),'reply_markup':{'inline_keyboard':keyboard}}
def callback(query,c):
    sender=query.get('from',{});msg=query.get('message',{});ident=sender.get('id')
    if not ident or sender.get('is_bot') or msg.get('chat',{}).get('type')!='private' or msg['chat'].get('id')!=ident:return 'Кнопка недоступна.'
    st=c.execute('SELECT * FROM bot_state WHERE telegram_id=?',(ident,)).fetchone()
    if not st:return 'Анкета уже завершена. /profile — статус.'
    p=json.loads(st['payload']);parts=query.get('data','').split(':');field=FIELDS[st['step']][0];xs=choices(field)
    if len(parts)!=2 or not secrets.compare_digest(parts[0],p.get('_ui_nonce','')) or p.get('_ui_step')!=st['step']:return 'Эта кнопка устарела. Ответьте на текущий вопрос.'
    action=parts[1]
    if action=='cancel':return handle({'chat':msg['chat'],'from':sender,'text':'/cancel'},c)
    if field in MULTI and action!='done':
        try:value=xs[int(action)] if action.isdigit() else None
        except (IndexError,ValueError):value=None
        if value is None:return 'Неизвестный вариант.'
        selected=p.setdefault('_selected',[])
        if value in selected:selected.remove(value)
        else:selected.append(value)
        c.execute('UPDATE bot_state SET payload=? WHERE telegram_id=?',(json.dumps(p,ensure_ascii=False),ident));return 'Выберите варианты и нажмите «Готово».'
    if action=='done':
        if field not in MULTI or not p.get('_selected'):return 'Выберите хотя бы один вариант.'
        text=','.join(p['_selected'])
    else:
        if not action.isdigit() or int(action)>=len(xs):return 'Неизвестный вариант.'
        text=xs[int(action)]
    return handle({'chat':msg['chat'],'from':sender,'text':text},c)
def process_update(update):
    with core.connect() as c:
        c.execute('BEGIN IMMEDIATE');event='tg-update:'+str(update['update_id'])
        cached=c.execute('SELECT result FROM command WHERE id=?',(event,)).fetchone()
        if cached:return json.loads(cached[0])
        query=update.get('callback_query');msg=update.get('message',{});ident=(query or msg).get('from',{}).get('id')
        before=c.execute('SELECT step FROM bot_state WHERE telegram_id=?',(ident,)).fetchone()
        reply=callback(query,c) if query else handle(msg,c)
        after=c.execute('SELECT * FROM bot_state WHERE telegram_id=?',(ident,)).fetchone()
        if after and (not before or before['step']!=after['step'] or msg.get('text','').split(' ')[0]=='/start'):
            p=json.loads(after['payload'])
            for key in ['_ui_nonce','_ui_step','_selected']:p.pop(key,None)
            c.execute('UPDATE bot_state SET payload=? WHERE telegram_id=?',(json.dumps(p,ensure_ascii=False),ident))
        prompt(ident,c)
        c.execute('INSERT INTO command VALUES(?,?)',(event,json.dumps(reply,ensure_ascii=False)));c.commit();return reply

def main():
    core.init();lock=open(core.ROOT/'data'/'bot.lock','w')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:print('STOP: another local poller holds lock');return 2
    info=call('getWebhookInfo')
    if info.get('url'):print('STOP: webhook configured; no changes made');return 2
    me=call('getMe');print('Polling ready for @'+me['username']+'; inbound private registration only',flush=True)
    with core.connect() as c:
        r=c.execute("SELECT value FROM bot_meta WHERE key='offset'").fetchone();offset=int(r[0]) if r else 0
    while True:
        try:
            updates=call('getUpdates',{'offset':offset,'timeout':20,'allowed_updates':['message','callback_query']})
            for u in updates:
                # Store update and state atomically. Transport retries may repeat the cached reply, never advance the form twice.
                reply=process_update(u)
                query=u.get('callback_query');msg=query.get('message',{}) if query else u.get('message',{})
                ident=(query or u.get('message',{})).get('from',{}).get('id')
                if query:call('answerCallbackQuery',{'callback_query_id':query['id']})
                with core.connect() as c:ui=prompt(ident,c)
                if reply and msg.get('chat',{}).get('type')=='private' and msg['chat'].get('id')==ident:
                    payload={'chat_id':msg['chat']['id'],**(ui or {'text':reply})}
                    if query and ui:
                        payload['message_id']=msg['message_id']
                        call('editMessageText',payload)
                    else:call('sendMessage',payload)
                offset=u['update_id']+1
                with core.connect() as c:c.execute("INSERT INTO bot_meta VALUES('offset',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(str(offset),))
        except KeyboardInterrupt:break
        except Exception:print('Polling transport failure; retrying without sensitive details',flush=True);time.sleep(5)
if __name__=='__main__':sys.exit(main())
