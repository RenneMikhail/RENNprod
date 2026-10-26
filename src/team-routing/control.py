"""Local runtime start/stop/status, no launch agent. All logs/PIDs stay here."""
import subprocess,sys,os,signal,time,json,urllib.request
from pathlib import Path
import core
DATA=core.ROOT/'data'
def alive(pid):
    try:os.kill(pid,0);return True
    except PermissionError:return True
    except ProcessLookupError:return False
    except OSError:return False
def main():
    DATA.mkdir(exist_ok=True);action=sys.argv[1] if len(sys.argv)>1 else 'status'
    for name in ['server','bot']:
        file=DATA/(name+'.pid');pid=int(file.read_text()) if file.exists() else None
        if action=='stop':
            if pid and alive(pid):os.kill(pid,signal.SIGTERM)
            file.unlink(missing_ok=True);print(name+': stopped');continue
        if pid and alive(pid):print(name+': running PID '+str(pid));continue
        if action!='start':print(name+': stopped');continue
        if name=='bot':
            import bot
            try:
                if bot.call('getWebhookInfo').get('url'):print('bot: BLOCKED by existing webhook');continue
            except Exception:print('bot: preflight failed (details suppressed)');continue
        log=open(DATA/(name+'.log'),'ab',buffering=0)
        proc=subprocess.Popen([sys.executable,'-u',str(core.ROOT/(name+'.py'))],cwd=core.ROOT,stdout=log,stderr=log,start_new_session=True)
        file.write_text(str(proc.pid));time.sleep(1)
        print(name+(': started PID '+str(proc.pid) if proc.poll() is None else ': failed; inspect local log'))
if __name__=='__main__':main()
