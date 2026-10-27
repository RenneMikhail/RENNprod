import json, secrets, argparse, threading, time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse,parse_qs
from pathlib import Path
import core,auth
from access import AccessMixin
SESSION=secrets.token_urlsafe(24)
class Handler(AccessMixin,BaseHTTPRequestHandler):
    def session_value(self):return SESSION
    def log_message(self,*a):pass
    def send(self,data,status=200,typ='application/json'):
        raw=(json.dumps(data,ensure_ascii=False) if typ=='application/json' else data).encode();self.send_response(status);self.send_header('Content-Type',typ+'; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(raw)
    def authorized(self):return self.headers.get('X-Local-Session')==SESSION
    def _local_get(self):
        u=urlparse(self.path);q=parse_qs(u.query)
        if u.path in ['/shooting','/crm']:
            self.send_response(303);self.send_header('Location',u.path+'/'+('?' + u.query if u.query else ''));self.end_headers();return
        if u.path=='/shooting' or u.path.startswith('/shooting/'):
            if self.headers.get('Host')!='127.0.0.1:'+str(self.server.server_port):
                return self.send({'error':'Loopback host required'},403)
            files={'/shooting':'index.html','/shooting/':'index.html','/shooting/index.html':'index.html',
                   '/shooting/styles.css':'styles.css','/shooting/app.js':'app.js','/shooting/locales.js':'locales.js'}
            if u.path.startswith('/shooting/'):
                extra=['experience.js','media-manifest.js','cg.html','media/1.jpg','media/2.jpg','media/3.jpg','media/4.jpg','site.css','site.js','services.js','professional.html','reels.html','commercial.html','art.html','editing.html','graphics.html','ai.html','assets/renn-prod-eye-vector.svg','media/1.mp4','media/2.mp4','media/3.mp4','media/4.mp4']
                files.update({'/shooting/'+x:x for x in extra})
            filename=files.get(u.path)
            if not filename:return self.send({'error':'Not found'},404)
            root=core.ROOT.parent/'shooting-landing'
            file=root/filename
            if file.is_symlink() or not file.is_file() or not file.resolve().is_relative_to(root.resolve()):
                return self.send({'error':'Not found'},404)
            if filename.endswith(('.mp4','.jpg')):
                raw=file.read_bytes();self.send_response(200);self.send_header('Content-Type','image/jpeg' if filename.endswith('.jpg') else 'video/mp4');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw);return
            content=file.read_text()
            if filename.endswith('.html'):
                content=content.replace('__SESSION__',SESSION).replace('href="styles.css"','href="/shooting/styles.css"')
                for asset in ['app.js','locales.js','site.js','services.js']:
                    content=content.replace('src="'+asset+'"','src="/shooting/'+asset+'"')
            typ='image/svg+xml' if filename.endswith('.svg') else 'text/html' if filename.endswith('.html') else 'text/css' if filename.endswith('.css') else 'text/javascript'
            return self.send(content,200,typ)
        if u.path=='/crm' or u.path.startswith('/crm/'):
            # Explicit filenames only: never expose project roots, secrets or data.
            if self.headers.get('Host')!='127.0.0.1:'+str(self.server.server_port):
                return self.send({'error':'Loopback host required'},403)
            files={'/crm':'index.html','/crm/':'index.html','/crm/index.html':'index.html',
                   '/crm/style.css':'style.css','/crm/app.js':'app.js',
                   '/crm/team-api-adapter.js':'team-api-adapter.js',
                   '/crm/locales.js':'locales.js','/crm/i18n.js':'i18n.js'}
            filename=files.get(u.path)
            if not filename:return self.send({'error':'Not found'},404)
            root=core.ROOT.parent/'crm-prototype'
            file=root/filename
            if file.is_symlink() or not file.is_file() or file.resolve().parent!=root.resolve():
                return self.send({'error':'Not found'},404)
            content=file.read_text()
            if filename=='index.html':
                content=content.replace('__RP_LOCAL_SESSION__',SESSION)
                # Absolute local mount paths work for both /crm and /crm/.
                content=content.replace('href="style.css"','href="/crm/style.css"')
                for asset in ['app.js','team-api-adapter.js','locales.js','i18n.js']:
                    content=content.replace('src="'+asset+'"','src="/crm/'+asset+'"')
            typ='text/html' if filename.endswith('.html') else 'text/css' if filename.endswith('.css') else 'text/javascript'
            return self.send(content,200,typ)
        if u.path in ['/','/join','/client','/brief','/panel']:
            return self.send((core.ROOT/'index.html').read_text().replace('__SESSION__',SESSION),200,'text/html')
        if u.path in ['/locales/ru.json','/locales/en.json']:return self.send(json.loads((core.ROOT/u.path.lstrip('/')).read_text()))
        if u.path=='/api/catalog':return self.send({'roles':core.ROLES,'skills':core.SKILLS,'tasks':core.TASKS})
        if not self.authorized():return self.send({'error':'Local session required'},403)
        try:
            with core.connect() as c:
                if u.path=='/api/specialists' or u.path.startswith('/api/specialists/'):
                    ident=u.path.split('/')[-1] if u.path!='/api/specialists' else None
                    rows=c.execute('SELECT * FROM specialist WHERE id=?',(ident,)) if ident else c.execute('SELECT * FROM specialist ORDER BY created_at DESC')
                    data=[dict(x) for x in rows]
                    for x in data:x['profile']=json.loads(x['profile'])
                    return self.send(data[0] if ident and data else data)
                if u.path=='/api/state':
                    data={t:[dict(r) for r in c.execute('SELECT * FROM '+t)] for t in ['specialist','orders','role_slot','offer','assignment','manager_acceptance','availability','notification','intake']}
                    for s in data['specialist']:s['profile']=json.loads(s['profile'])
                    c.execute('CREATE TABLE IF NOT EXISTS employee_question(id TEXT PRIMARY KEY,specialist_id TEXT,offer_id TEXT,body TEXT,created_at TEXT,command_key TEXT,UNIQUE(specialist_id,command_key))')
                    for question in c.execute('SELECT q.*,s.name FROM employee_question q JOIN specialist s ON s.id=q.specialist_id ORDER BY q.created_at'):
                        data['intake'].append({'id':question['id'],'kind':'Вопрос сотрудника','created_at':question['created_at'],'payload':json.dumps({'name':question['name'],'question':question['body'],'task':question['offer_id']},ensure_ascii=False)})
                    return self.send(data)
                if u.path=='/api/workspace':return self.send(core.workspace_view(q['order'][0],q['actor'][0]))
            return self.send({'error':'Not found'},404)
        except (ValueError,KeyError) as e:self.send({'error':str(e)},400)
    def _local_post(self):
        if self.headers.get('Origin') and self.headers['Origin']!='http://'+self.headers.get('Host',''):return self.send({'error':'Origin rejected'},403)
        if not self.authorized():return self.send({'error':'Local session required'},403)
        try:
            n=int(self.headers.get('Content-Length',0))
            if n>65536:raise ValueError('Request too large')
            p=json.loads(self.rfile.read(n));action=urlparse(self.path).path
            if action=='/api/register':result={'id':core.register(p)}
            elif action=='/api/route':core.route(p['order']);result={'status':'routed'}
            elif action=='/api/respond':result=core.respond(p['offer'],p['actor'],p['decision'],p['version'],p['key'])
            elif action=='/api/manager':result=core.manager_accept(p['invitation'],p['actor'],p['key'])
            elif action=='/api/select':result=core.select_offer(p['offer'],p['actor'],p['key'])
            elif action=='/api/tick':result=core.tick()
            elif action=='/api/block':result={'id':core.block(p['actor'],p['start'],p['end'],p['timezone'])}
            elif action=='/api/block-update':core.update_block(p['id'],p['actor'],p.get('start'),p.get('end'),p.get('timezone'));result={'status':'updated'}
            elif action in ['/api/verify','/api/auto','/api/ack','/api/channel','/api/intake','/api/discuss']:
                with core.connect() as c:
                    if action=='/api/verify':c.execute('UPDATE specialist SET verified=? WHERE id=?',(int(p['verified']),p['id']))
                    elif action=='/api/auto':c.execute('UPDATE orders SET auto_assign=? WHERE id=?',(int(p['enabled']),p['order']))
                    elif action=='/api/ack':c.execute("UPDATE notification SET ack_at=?,status='acknowledged' WHERE id=?",(core.now(),p['id']))
                    elif action=='/api/channel':
                        if p['channel'] not in ['telegram','email','web']:raise ValueError('Unknown channel')
                        c.execute("UPDATE notification SET channel=?,status='queued' WHERE id=?",(p['channel'],p['id']))
                    elif action=='/api/intake':
                        if p.get('source')=='shooting-landing':
                            if p.get('kind')!='client' or p.get('service') not in ['professional','reels','commercial','art','editing','graphics','cg','ai'] or p.get('locale') not in ['ru','en']:
                                raise ValueError('Invalid shooting enquiry')
                            if not isinstance(p.get('idea'),str) or not 1<=len(p['idea'].strip())<=1200:
                                raise ValueError('Idea required; maximum 1200 characters')
                            p={k:p[k] for k in ['kind','source','service','locale','idea','test'] if k in p}
                        intake_id=core.uid()
                        c.execute('INSERT INTO intake VALUES(?,?,?,?)',(intake_id,p['kind'],json.dumps(p,ensure_ascii=False),core.now()))
                    else:
                        view=core.workspace_view(p['order'],p['actor'])
                        if not p['body'].strip():raise ValueError('Пустое сообщение')
                        # Prototype prevents accidental finance posts with an explicit acknowledgement.
                        if not p.get('no_finance'):raise ValueError('Подтвердите отсутствие финансовых данных')
                        c.execute('INSERT INTO message VALUES(?,?,?,?,?)',(core.uid(),view['id'],p['actor'],p['body'][:2000],core.now()))
                result={'status':'saved'}
                if action=='/api/intake':result['id']=intake_id
            else:return self.send({'error':'Not found'},404)
            self.send(result)
        except (ValueError,KeyError,TypeError,core.sqlite3.IntegrityError) as e:self.send({'error':str(e)},400)
        except Exception:self.send({'error':'Internal error; no private data logged'},500)
def notification_clock():
    while True:
        try:core.tick()
        except Exception:pass  # No personal details or transport secrets in logs.
        time.sleep(30)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8766);args=parser.parse_args();auth.init();core.init();core.seed();threading.Thread(target=notification_clock,daemon=True).start();print(f'Ren Prod local: http://127.0.0.1:{args.port}',flush=True);ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
if __name__=='__main__':main()
