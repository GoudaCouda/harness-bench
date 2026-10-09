"""Public JSON/CLI transport. Contains neither evaluator nor private state."""
import argparse
import json
import os
from pathlib import Path
import sys
import urllib.request

def main():
    endpoint=json.loads((Path(os.environ.get('HB_RUNTIME','/runtime'))/'gold20-service.json').read_text())['url']
    if sys.argv[1:2]==['--tool']:
        p=argparse.ArgumentParser();p.add_argument('--tool',required=True);a=p.parse_args()
        raw=sys.stdin.buffer.read(65537)
        if len(raw)>65536:raise ValueError('request too large')
        args=json.loads(raw)
        if not isinstance(args,dict):raise ValueError('arguments must be an object')
        payload={'tool':a.tool,'arguments':args}
    else:payload=sys.argv[1:]
    data=json.dumps(payload,ensure_ascii=False).encode()
    if len(data)>65536:raise ValueError('request too large')
    req=urllib.request.Request(endpoint,data=data,headers={'Content-Type':'application/json'})
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req,timeout=20) as r:reply=json.loads(r.read(4194304))
    if 'returncode' in reply:print(reply['stdout'],end='');return reply['returncode']
    print(json.dumps(reply,ensure_ascii=False));return 0 if reply.get('status')=='ok' else 1

if __name__=='__main__':raise SystemExit(main())
