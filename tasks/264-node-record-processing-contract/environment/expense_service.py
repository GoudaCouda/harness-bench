"""Bounded Unix RPC adapter over case17's unchanged, scoped public tool API."""
import argparse
import json
from pathlib import Path
import socketserver
import subprocess
import sys

ALLOWED={
 'read-expense':set(), 'list-contacts':set(),
 'create-payment-request':{'--participant-id','--recipient-account-id','--amount-fen','--note'},
 'write-status-report':{'--content-json'},
}


def validate(args):
    if not isinstance(args,list) or not args or not all(isinstance(v,str) for v in args):
        raise ValueError('Invalid arguments')
    command=args[0]
    if command not in ALLOWED or len(args)!=1+2*len(ALLOWED[command]):
        raise ValueError('Unsupported command shape')
    if set(args[1::2])!=ALLOWED[command]: raise ValueError('Unsupported flags')
    if any(len(v)>32000 for v in args): raise ValueError('Argument too large')
    return args


def main():
    p=argparse.ArgumentParser();p.add_argument('--socket',required=True)
    p.add_argument('--workspace',required=True);p.add_argument('--tools',required=True)
    a=p.parse_args()
    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            self.connection.settimeout(10)
            try:
                raw=self.rfile.readline(65538)
                if not raw.endswith(b'\n') or len(raw)>65536: raise ValueError('Request size')
                args=validate(json.loads(raw))
                r=subprocess.run([sys.executable,a.tools,'--workspace',a.workspace,*args],
                    capture_output=True,timeout=10,text=True)
                reply={'returncode':r.returncode,'stdout':r.stdout[:262144]}
            except (ValueError,OSError,subprocess.SubprocessError):
                reply={'returncode':2,'stdout':'{"status":"error","error":"invalid_request"}\n'}
            self.wfile.write(json.dumps(reply).encode()+b'\n')
    with socketserver.UnixStreamServer(a.socket,Handler) as server:
        Path(a.socket).chmod(0o666)
        server.serve_forever()


if __name__=='__main__': main()
