"""Trusted bridge to original code graders. Candidate code executes only in owned containers."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
sys.path.insert(0,'/code')

PARENT=os.environ['CPUQ_CONTAINER']
CASE=Path(os.environ['G20_CASE'])
ROOT=Path(os.environ['G20_RUNTIME'])
IMAGE=os.environ['G20_CODE_IMAGE']
NUMBER=int(os.environ['G20_CASE_NUMBER'])
HOSTROOT=Path(os.environ.get('G20_HOST_RUNTIME',str(ROOT)))
OWNED=[]


def dump(p,v): p.write_text(json.dumps(v,ensure_ascii=False,indent=2))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def run(argv,name,timeout=240):
    with (ROOT/(name+'.stdout')).open('w') as o,(ROOT/(name+'.stderr')).open('w') as e:
        r=subprocess.run([str(x) for x in argv],stdout=o,stderr=e,timeout=timeout,text=True)
    dump(ROOT/(name+'.command.json'),{'argv':[str(x) for x in argv],'returncode':r.returncode})
    return r.returncode
def py(path,*args,name='command',timeout=240):
    return run([sys.executable,CASE/path,*args],name,timeout)
def docker(args):
    r=subprocess.run(['docker',*map(str,args)],capture_output=True,text=True,timeout=40)
    if r.returncode: raise RuntimeError('Docker '+str(args[0])+': '+r.stderr[-500:])
    return r.stdout.strip()
def create(args,name):
    args=['create','--name',PARENT+'-'+name,'--label','cpuq.parent='+PARENT,*args]
    dump(ROOT/(name+'-creation.json'),args)
    cid=docker(args);OWNED.append(cid);dump(ROOT/'owned.json',OWNED)
    docker(['start',cid]);return cid,PARENT+'-'+name
def module(path):
    spec=importlib.util.spec_from_file_location('trusted_adapter_module',CASE/path)
    mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod);return mod
def common(user,cpus,memory,pids):
    return ['--user',user,'--cpus',str(cpus),'--memory',str(memory),'--memory-swap',str(memory),
        '--pids-limit',str(pids),'--network','none','--read-only','--cap-drop','ALL',
        '--security-opt','no-new-privileges']


def run_model(case,root,hostroot,number,workspace):
    source=Path('/native-input')
    # Preserve reset-owned immutable inode/mode identity for unchanged inputs.
    for p in sorted(workspace.rglob('*'),key=lambda x:len(x.parts),reverse=True):
        if not (source/p.relative_to(workspace)).exists():
            if p.is_dir():p.rmdir()
            else:p.unlink()
    for p in source.rglob('*'):
        if p.name=='.hb_gold20_execution.json':continue
        if p.is_symlink():raise RuntimeError('linked candidate')
        target=workspace/p.relative_to(source)
        if p.is_dir():target.mkdir(parents=True,exist_ok=True)
        elif not target.exists() or target.read_bytes()!=p.read_bytes():
            target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():target.chmod(0o644)
            shutil.copyfile(p,target)
            os.chown(target,2048,2048);target.chmod(0o644)


def eight(mode):
    w=ROOT/'submitted';runtime=ROOT/'execution';runtime.mkdir()
    if py('environment/reset.py','--fixture-root',CASE/'fixtures/repository','--workspace',w,name='reset'):
        raise RuntimeError('Reset failed')
    initial=(ROOT/'reset.stdout').read_text().strip()
    try: initial=json.loads(initial)['state_sha256']
    except (ValueError,KeyError,TypeError): pass
    if mode=='reference' and py('oracle/apply_oracle.py','--workspace',w,name='oracle'):
        raise RuntimeError('Oracle install failed')
    if mode=='model':
        run_model(CASE,ROOT,HOSTROOT,NUMBER,w)
    c,h=module('tests/create_sandbox.py').read_contract(CASE/'environment/sandbox_contract.json')
    labels={'agent_sft.run_id':PARENT,'agent_sft.task_id':'case08','agent_sft.case_id':'case_08',
        'agent_sft.variant':c['variant'],'agent_sft.host_alias':os.environ['CPUQ_NODES'],
        'agent_sft.attempt_id':mode,'agent_sft.role':c['role'],'agent_sft.sandbox_contract_sha256':h}
    args=common(c['user'],c['cpu_cores'],c['memory_bytes'],c['pids_limit'])
    for k,v in labels.items(): args+=['--label',k+'='+v]
    s=c['tmpfs'][0]
    args+=['--ulimit','fsize=67108864:67108864','--ulimit','nofile=128:128',
           '--tmpfs','/scratch:'+','.join(s['options'])+',size='+str(s['size_bytes']),
           '--mount',f'type=bind,src={runtime},dst=/workspace,bind-propagation=rprivate','-w','/workspace']
    for k,v in {'HOME':'/nonexistent','TMPDIR':'/scratch','PYTHONDONTWRITEBYTECODE':'1',
                'PYTHONHASHSEED':'0','LANG':'C.UTF-8','LC_ALL':'C.UTF-8','TZ':'UTC'}.items(): args+=['-e',k+'='+v]
    cid,name=create([*args,IMAGE],'c08-'+mode)
    cmd=['verifier/controller.py','--run-id',PARENT,'--task-id','case08','--host-alias',os.environ['CPUQ_NODES'],
         '--attempt-id',mode,'--container-id',cid,'--container-name',name,'--image-id',IMAGE,
         '--submitted-workspace',w,'--sandbox-contract',CASE/'environment/sandbox_contract.json',
         '--runtime-root',ROOT,'--runtime-workspace',runtime,'--fixture-root',CASE/'fixtures/repository',
         '--initial-state-sha256',initial,'--output',ROOT/'verdict.json']
    return py(cmd[0],*cmd[1:],name='verify')


def nine(mode):
    w=ROOT/'submitted';scratch=ROOT/'scratch'
    if py('environment/reset.py','--case-root',CASE,'--workspace',w,name='reset'): raise RuntimeError('Reset failed')
    if mode=='reference' and py('oracle/solve.py','--case-root',CASE,'--workspace',w,name='oracle'): raise RuntimeError('Oracle failed')
    if mode=='model':
        run_model(CASE,ROOT,HOSTROOT,NUMBER,w)
    c=json.loads((CASE/'environment/candidate_sandbox_contract.json').read_text())
    labels={**c['ownership']['static_labels'],'agent_sft.sandbox_contract_sha256':c['contract_sha256'],
            'agent_sft.run_id':PARENT,'agent_sft.host_alias':os.environ['CPUQ_NODES'],'agent_sft.task_id':'case09'}
    args=common(c['user'],2,c['resources']['memory_bytes'],c['resources']['pids_limit'])
    for k,v in labels.items(): args+=['--label',k+'='+v]
    args+=['--tmpfs','/submission:'+c['tmpfs']['options'],'-w','/submission']
    for m in c['fixture_mounts']:
        args+=['--mount',f'type=bind,src={CASE/m["case_relative_path"]},dst={m["container_path"]},readonly']
    cid,name=create([*args,IMAGE,*c['init_command']],'c09-'+mode)
    return py('verifier/verify.py','--case-root',CASE,'--workspace',w,'--scratch-root',scratch,
        '--sandbox-container',cid,'--sandbox-name',name,'--host-case-root',CASE,
        '--run-id',PARENT,'--host-alias',os.environ['CPUQ_NODES'],'--task-id','case09',
        '--result-json',ROOT/'verdict.json',name='verify')


def ten(mode):
    c=json.loads((CASE/'environment/candidate_sandbox_contract.json').read_text())
    submission=ROOT/'submission';submission.mkdir();shm=ROOT/'immutable_shm';shm.mkdir();shm.chmod(0o555)
    (ROOT/'candidates').mkdir()
    candidate=ROOT/'candidates/submission'
    if mode=='model':
        authoring=ROOT/'authoring'
        if py('environment/prepare_agent_workspace.py','--allowed-root',ROOT,'--workspace',authoring,
            '--agent-uid','2048','--agent-gid','2048','--controller-uid','0','--controller-gid','4007',name='reset'):
            raise RuntimeError('Authoring workspace preparation failed')
        run_model(CASE,ROOT,HOSTROOT,NUMBER,authoring)
        if py('environment/freeze_submission.py','--allowed-root',ROOT,'--workspace',authoring,'--submission',candidate,
              '--owner-uid','0','--owner-gid','4007','--agent-stopped',name='freeze'):
            dump(ROOT/'verdict.json',{'verdict':'reject','reason':'submission_failed_frozen_admission'})
            return 1
    elif py('environment/reset.py','--allowed-root',ROOT,'--destination',candidate,name='reset'): raise RuntimeError('Reset failed')
    if mode=='reference' and py('oracle/run_oracle.py','--submission',candidate,name='oracle'): raise RuntimeError('Oracle failed')
    labels={'agent_sft.run_id':PARENT,'agent_sft.task_id':'case10','agent_sft.case_id':'case_10',
        'agent_sft.host_alias':os.environ['CPUQ_NODES'],'agent_sft.attempt_id':mode,
        'agent_sft.purpose':'nami_work_gold20','cpuq.parent':PARENT}
    manifest='artifacts/resource_governance/case_10/resource_manifest.json'
    extra={'agent_sft.runtime_role':c['runtime_role'],'agent_sft.sandbox_contract_sha256':c['contract_sha256'],
           'agent_sft.resource_manifest_path':manifest}
    args=common(c['identity']['user'],1,c['resources']['memory_bytes'],16)
    for k,v in {**labels,**extra}.items(): args+=['--label',k+'='+v]
    for k,v in c['security']['required_config_environment'].items(): args+=['-e',k+'='+v]
    args+=['--ulimit','fsize=1048576:1048576','--ulimit','nofile=64:64','--ipc','private','--shm-size','65536',
        '--mount',f'type=bind,src={HOSTROOT}/submission,dst=/workspace,readonly',
        '--mount',f'type=bind,src={HOSTROOT}/immutable_shm,dst=/dev/shm,readonly',
        '-w','/workspace','--entrypoint','node',IMAGE,*c['process']['command']]
    cid,name=create(args,'c10-'+mode)
    plan={'schema_version':'nami_work_candidate_runtime_ownership_v2','case_id':'case_10',
        'run_id':PARENT,'task_id':'case10','host_alias':os.environ['CPUQ_NODES'],'hostname':os.environ['CPUQ_NODES'],
        'attempt_id':mode,'host_runtime_root':str(HOSTROOT),'controller_runtime_root':'/runtime',
        'submission_relative_path':'submission','contract_sha256':c['contract_sha256'],'resource_manifest_path':manifest,
        'candidate_container':{'name':name,'exact_id':cid,'status':'running'},
        'controller_container':{'name':os.environ['G20_CONTROLLER_NAME'],'exact_id':(ROOT/'controller-id').read_text().strip(),'status':'running'},
        'dynamic_labels':labels}
    dump(ROOT/'plan.json',plan)
    verifier=module('verifier/verify.py')
    verifier.inspect_owned(plan,c,require_running=True)
    verdict=verifier.verify_candidate(ROOT/'plan.json',candidate)
    dump(ROOT/'verdict.json',verdict)
    return 0 if verdict['verdict']=='accept' else 1 if verdict['verdict']=='reject' else 2


def eleven(mode):
    for name in ['attempts','evidence','control','case_11']:
        path=ROOT/name;path.mkdir();os.chown(path,0,4007);path.chmod(0o2770)
    cpath=CASE/'environment/sandbox_contract.json';c=json.loads(cpath.read_text())
    manifest=ROOT/'case_11/resource_manifest.json';dump(manifest,{'resources':{'containers':[]},'container_creation_records':[]})
    labels={'agent_sft.run_id':PARENT,'agent_sft.task_id':'case11','agent_sft.case_id':'case_11',
        'agent_sft.host_alias':os.environ['CPUQ_NODES'],'agent_sft.purpose':'nami_work_gold20','cpuq.parent':PARENT}
    plan={'schema_version':'case11_execution_ownership_plan_v2','runtime_root':str(ROOT),
        'attempts_root':str(ROOT/'attempts'),'evidence_root':str(ROOT/'evidence'),
        'resource_manifest_path':str(manifest),'contract_sha256':sha(cpath),'image_digest':IMAGE,'labels':labels}
    pp=ROOT/'control/ownership_plan.json';dump(pp,plan)
    if py('environment/reset.py','--plan',pp,'--workspace-id','submitted','--variant','primary',name='reset'): raise RuntimeError('Reset failed')
    w=ROOT/'attempts/submitted';script=w/'submission/generate_brief.py'
    if mode in ['reference','model']:
        if mode=='model':
            run_model(CASE,ROOT,HOSTROOT,NUMBER,w)
            required=['submission/generate_brief.py','output/summary.json','output/weekly_brief.md']
            if any(not (w/f).is_file() or (w/f).is_symlink() for f in required):
                dump(ROOT/'verdict.json',{'verdict':'reject','reason':'missing_or_unsafe_required_deliverable'})
                return 1
        else:
            shutil.copy2(CASE/'oracle/reference_generator.py',script)
            script.chmod(0o640)
            if py('environment/sandbox_controller.py','--contract',cpath,'--plan',pp,
                  '--attempt-id','submitted','--invocation-id','generate-reference',name='generate'):
                raise RuntimeError('Reference generation sandbox failed')
        rc=py('verifier/evaluate_submission.py','--plan',pp,'--submission-workspace',w,
              '--evaluation-id','grade-reference','--result',ROOT/'evidence/evaluations/grade-reference/result.json',
              name='verify',timeout=600)
        result=ROOT/'evidence/evaluations/grade-reference/result.json'
        if result.exists(): shutil.copy2(result,ROOT/'verdict.json')
        return rc
    # No submitted script is an explicit missing-deliverable reject, not a model execution.
    dump(ROOT/'verdict.json',{'verdict':'reject','reason':'missing_required_submission','checks':[]})
    return 1


def main():
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['reference','pristine','model'],required=True);a=p.parse_args()
    ROOT.mkdir(parents=True,exist_ok=True)
    result={'case':NUMBER,'mode':a.mode,'status':'error','score':None}
    try:
        rc={8:eight,9:nine,10:ten,11:eleven}[NUMBER](a.mode)
        verdict=json.loads((ROOT/'verdict.json').read_text())
        signals=[verdict[k] for k in ['accepted','passed'] if type(verdict.get(k)) is bool]
        ok=(rc==0 and (any(signals) or verdict.get('verdict')=='accept' or verdict.get('status')=='passed'))
        valid=(rc in [0,1] and verdict.get('verdict') not in ['invalid','error'] and verdict.get('status') not in ['invalid','error'])
        status=('finished' if valid else 'infrastructure_error') if a.mode=='model' else ('expected' if valid and ok==(a.mode=='reference') else 'unexpected')
        result.update(verifier_exit=rc,verdict=verdict,status=status,score=int(ok) if valid else None)
    except Exception as exc:
        result['error']=type(exc).__name__+': '+str(exc)
    finally:
        if NUMBER==11 and (ROOT/'case_11/resource_manifest.json').exists():
            for r in json.loads((ROOT/'case_11/resource_manifest.json').read_text()).get('resources',{}).get('containers',[]):
                OWNED.append(r['container_id'])
        for cid in dict.fromkeys(OWNED):
            try:
                check=subprocess.run(['docker','inspect',cid,'--format','{{index .Config.Labels "cpuq.parent"}}'],capture_output=True,text=True,timeout=40)
                if check.returncode and 'no such object' in check.stderr.lower():continue
                if check.returncode or check.stdout.strip()!=PARENT:raise RuntimeError('Refusing cleanup: wrong CPUQ parent')
                docker(['rm','-f',cid])
            except Exception as exc:
                result.setdefault('cleanup_errors',[]).append(str(exc))
                result.update(status='infrastructure_error',score=None)
        if a.mode=='model':
            if (ROOT/'model-result.json').exists():result.update(json.loads((ROOT/'model-result.json').read_text()))
            result.update(task_id=237+NUMBER,backend='cpuq-docker-code-v2')
        dump(ROOT/('result.json' if a.mode=='model' else 'qualification.json'),result)
        # Export only top-level reports; do not rewrite the graded workspace's
        # owner/mode metadata after the oracle recorded its integrity checks.
        for path in ROOT.iterdir():
            if not path.is_symlink() and path.is_file():
                os.chown(path,2048,2048);path.chmod(0o600)
    print(json.dumps({k:v for k,v in result.items() if k!='verdict'}),flush=True)
    raise SystemExit(0 if result['status'] in ['expected','finished'] else 1)


if __name__=='__main__': main()
