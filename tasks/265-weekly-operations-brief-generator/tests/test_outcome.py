"""Read an identity-bound trusted execution receipt, never execute candidate code.

The standard runner publishes this file after the agent is stopped and binds it
through environment_mutations. It is excluded from candidate mutation rights.
Offline references contain the corresponding trusted, frozen execution receipt.
"""
import hashlib
import json
import os
from pathlib import Path
import stat

TASK = Path(__file__).resolve().parents[1]
CONFIG = json.loads((TASK/'tests/ground_truth/native.json').read_text())
RECEIPT = '.hb_gold20_execution.json'

def inventory(root):
    entries = {}; count = 0; size = 0
    def walk(p):
        nonlocal count,size
        for entry in os.scandir(p):
            count += 1
            if count > 4096: raise ValueError('too many entries')
            child=Path(entry.path);name=child.relative_to(root).as_posix()
            info=entry.stat(follow_symlinks=False)
            if stat.S_ISLNK(info.st_mode): raise ValueError('symlink')
            if stat.S_ISDIR(info.st_mode): walk(child)
            elif stat.S_ISREG(info.st_mode):
                size += info.st_size
                if info.st_size>67108864 or size>134217728: raise ValueError('size bound')
                if name!=RECEIPT: entries[name]=hashlib.sha256(child.read_bytes()).hexdigest()
            else: raise ValueError('special file')
    if root.is_symlink() or not root.is_dir(): raise ValueError('invalid workspace')
    walk(root);return entries

def evaluate_cases(workspace):
    def obs(value,detail=''): return {'pass':bool(value),'detail':None if value else detail}
    names=[b[0] for b in CONFIG['blocks']]+['complete_delivery']
    def failure(reason,gate=True):
        return {n:obs(False,reason) for n in names}|{'protected_boundary':obs(gate,reason)}
    workspace=Path(workspace)
    try:
        files=inventory(workspace)
        for name,expected in CONFIG['protected_files'].items():
            if files.get(name)!=expected:return failure('protected input/tool changed',False)
        p=workspace/RECEIPT
        if not p.is_file():return failure('no trusted execution snapshot')
        if p.stat().st_size>4194304:return failure('oversized receipt',False)
        receipt=json.loads(p.read_text())
        identity=hashlib.sha256((TASK/'tests/ground_truth/native.json').read_bytes()).hexdigest()
        if receipt.get('config_sha256')!=identity or receipt.get('workspace_files')!=files:
            return failure('execution snapshot identity mismatch',False)
        if receipt.get('forged_snapshot') or receipt.get('unsafe_workspace'):
            return failure('candidate violated protected execution boundary',False)
        if receipt.get('status')!='finished':raise RuntimeError('trusted execution did not finish')
        checks=receipt.get('checks',{})
        if not isinstance(checks,dict) or any(type(v) is not bool for v in checks.values()):
            return failure('invalid execution check schema',False)
        safe=not any(checks.get(k) is False for k in CONFIG['gates'])
        result={name:obs(all(checks.get(k) is True for k in required.split()),
                        {'failed_or_absent':[k for k in required.split() if checks.get(k) is not True]})
                for name,title,required in CONFIG['blocks']}
        unexpected=set(files)-set(CONFIG['protected_files'])-set(CONFIG['required_artifacts'])
        if CONFIG['case_number']==20:unexpected={p for p in unexpected if not p.startswith('archive/')}
        result['complete_delivery']=obs(receipt.get('legacy_accepted') is True and not unexpected,'original complete-delivery acceptance or final path scope failed')
        result['protected_boundary']=obs(safe,'protected state/integrity violation')
        return result
    except (OSError,ValueError,TypeError,KeyError):return failure('malformed or unsafe candidate',False)
