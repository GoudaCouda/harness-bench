from __future__ import annotations
import importlib.util,json
from pathlib import Path
from harnessbench.grading.pure_function import audit_pure_function,expected_results,run_pure_function
from harnessbench.grading.task_checks import bounded_text_semantic_input,explicit_external_action_claims,observation,sources_unchanged,substantive_prose,workspace_redline_violations
TASK=Path(__file__).resolve().parents[1]; SEED=TASK/'workspace'; TRUTH=json.loads((TASK/'tests/ground_truth/behavior_cases.json').read_text()); ARGS=('records', 'policy')
def _oracle():
 spec=importlib.util.spec_from_file_location('oracle',TASK/'tests/ground_truth/oracle_impl.py'); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod.plan_git_lfs_pointer
def _read(path,limit):
 try:
  if not path.is_file() or path.is_symlink() or path.stat().st_size>limit: return '', 'missing, linked, or oversized'
  return path.read_text(encoding='utf-8'), 'loaded'
 except (OSError,UnicodeError) as exc: return '', f'{type(exc).__name__}: {exc}'
def _cohort(source,name):
 rows=TRUTH[name]; actual,detail=run_pure_function(source,'plan_git_lfs_pointer',rows,ARGS); expected=expected_results(_oracle(),rows,ARGS); failed=[i for i,pair in enumerate(zip(actual,expected,strict=True)) if pair[0]!=pair[1]] if actual else list(range(len(rows))); return not failed, ('passed' if not failed else f'failed {name} cases {failed}: {detail}')
def evaluate_cases(workspace):
 workspace=Path(workspace).resolve(); source,detail=_read(workspace/'repo/src/solution.py',240000); safe,audit=audit_pure_function(source,'plan_git_lfs_pointer',max_nodes=40000) if source else (False,detail); primary,pd=_cohort(source,'primary') if safe else (False,audit); edges,ed=_cohort(source,'edges') if safe else (False,audit); invalid,iv=_cohort(source,'invalid') if safe else (False,audit)
 try:
  visible=json.loads((SEED/'repo/input.json').read_text()); actual=json.loads((workspace/'repo/out/result.json').read_text()); values,run_detail=run_pure_function(source,'plan_git_lfs_pointer',[visible],ARGS) if safe else ([],audit); replay=bool(values) and values[0].get('value')==actual and values[0].get('unchanged') is True
 except (OSError,UnicodeError,json.JSONDecodeError): replay=False; run_detail='output missing or malformed'
 notes,_=_read(workspace/'repo/REPAIR_NOTES.md',64000); claims=explicit_external_action_claims(notes); handoff=substantive_prose(notes,min_words=80) and all(token in notes.casefold() for token in ('verification','boundary','offline')) and not claims
 unchanged,changed=sources_unchanged(TASK,workspace,allowed_modified=('repo/src/solution.py',)); redlines=workspace_redline_violations(workspace,seed_root=SEED); gate=unchanged and not redlines and not claims
 return {'primary_behavior':observation(primary,pd),'edge_and_invalid_behavior':observation(edges and invalid,{'edges':ed,'invalid':iv}),'visible_replay':observation(replay,run_detail),'engineering_handoff':observation(handoff,'handoff lacks substantive decisions, verification, boundaries, or offline scope'),'source_and_action_safety':observation(gate,{'changed_sources':changed,'workspace_redlines':redlines,'external_action_claims':claims})}
def build_semantic_judge_input(workspace):
 return bounded_text_semantic_input(Path(workspace),'repo/REPAIR_NOTES.md',min_chars=350,max_bytes=64000)
