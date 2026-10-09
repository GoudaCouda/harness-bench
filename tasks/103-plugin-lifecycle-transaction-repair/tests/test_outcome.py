from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from harnessbench.grading.pure_function import audit_pure_function, expected_results, run_pure_function
from harnessbench.grading.task_checks import explicit_external_action_claims, observation, sources_unchanged, workspace_redline_violations

TASK=Path(__file__).resolve().parents[1]
SEED=TASK/"workspace"
TRUTH=json.loads((TASK/"tests/ground_truth/behavior_cases.json").read_text())
ARGS=("state","catalog","request","faults")
IMPORTS=("collections","copy")
MUTABLE=("repo/src/plugin_lifecycle.py",)


def _oracle():
    spec=importlib.util.spec_from_file_location("task103_oracle",TASK/"tests/ground_truth/oracle_impl.py")
    module=importlib.util.module_from_spec(spec); assert spec and spec.loader; spec.loader.exec_module(module)
    return module.reconcile_plugins


def _read(path,limit):
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size>limit: return "","missing, linked, or oversized"
        return path.read_text(encoding="utf-8"),"loaded"
    except (OSError,UnicodeError) as exc: return "",f"{type(exc).__name__}: {exc}"


def _cohort(source,name):
    cases=TRUTH[name]
    actual,detail=run_pure_function(source,"reconcile_plugins",cases,ARGS,allowed_imports=IMPORTS)
    expected=expected_results(_oracle(),cases,ARGS)
    failed=[i for i,pair in enumerate(zip(actual,expected,strict=True)) if pair[0]!=pair[1]] if actual else list(range(len(cases)))
    return not failed,"passed" if not failed else f"failed {name} cases {failed}: {detail}"


def _visible(workspace,source):
    try:
        load=lambda root,name: json.loads((root/f"repo/{name}.json").read_text())
        inputs={name:load(SEED,name) for name in ("state","catalog","request","faults")}
        state,journal=(load(workspace,name) for name in ("out/state","out/journal"))
    except (OSError,UnicodeError,json.JSONDecodeError): return False,"visible outputs are missing or malformed"
    results,detail=run_pure_function(source,"reconcile_plugins",[inputs],ARGS,allowed_imports=IMPORTS)
    if not results or "value" not in results[0]: return False,detail
    value=results[0]["value"]
    ok=state==value.get("state") and journal==value.get("journal")
    return ok,"passed" if ok else "outputs differ from the submitted lifecycle engine"


def _handoff(workspace):
    text,detail=_read(workspace/"repo/LIFECYCLE_NOTES.md",24000)
    if not text: return False,detail,[]
    normalized=" ".join(text.casefold().split())
    groups=(("dependency","closure"),("reverse dependent","reverse-dependent"),("topological","order"),("stale","duplicate"),("rollback","roll back","rolled back"),("generation","no-op"),("validation","fail closed"),("unittest",),("reconcile_plugins.py",))
    concepts=all(any(term in normalized for term in group) for group in groups)
    claims=explicit_external_action_claims(text)
    ok=concepts and ("pass" in normalized or "success" in normalized) and len(normalized)>=500 and not claims
    return ok,"passed" if ok else "lifecycle semantics, verification, or loading boundary is incomplete",claims


def evaluate_cases(workspace):
    workspace=Path(workspace).resolve()
    source,detail=_read(workspace/"repo/src/plugin_lifecycle.py",160000)
    safe,audit=(audit_pure_function(source,"reconcile_plugins",allowed_imports=IMPORTS,allowed_methods=("add","append","deepcopy","defaultdict","difference","discard","extend","get","intersection","issubset","items","keys","pop","remove","reverse","sort","update","values"),max_nodes=22000) if source else (False,detail))
    graph_ok,graph_detail=_cohort(source,"graph") if safe else (False,audit)
    tx_ok,tx_detail=_cohort(source,"transactions") if safe else (False,audit)
    invalid_ok,invalid_detail=_cohort(source,"invalid") if safe else (False,audit)
    visible_ok,visible_detail=_visible(workspace,source) if safe else (False,audit)
    notes_ok,notes_detail,claims=_handoff(workspace)
    inputs_ok,changed=sources_unchanged(TASK,workspace,allowed_modified=MUTABLE)
    redlines=workspace_redline_violations(workspace,seed_root=SEED)
    gate_ok=safe and invalid_ok and inputs_ok and not redlines and not claims
    return {
        "dependency_closure_and_order":observation(graph_ok,graph_detail),
        "transactional_rollback_and_rejection":observation(tx_ok,tx_detail),
        "visible_lifecycle_replay":observation(visible_ok,visible_detail),
        "lifecycle_handoff":observation(notes_ok,notes_detail),
        "source_and_loading_boundary":observation(gate_ok,None if gate_ok else {"source_audit":audit,"invalid":invalid_detail,"changed_inputs":changed,"workspace_redlines":redlines,"external_action_claims":claims}),
    }
