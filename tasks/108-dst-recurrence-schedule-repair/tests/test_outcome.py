from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from harnessbench.grading.pure_function import audit_pure_function, expected_results, run_pure_function
from harnessbench.grading.task_checks import explicit_external_action_claims, observation, sources_unchanged, workspace_redline_violations

TASK=Path(__file__).resolve().parents[1]; SEED=TASK/"workspace"
TRUTH=json.loads((TASK/"tests/ground_truth/behavior_cases.json").read_text())
ARGS=("schedules","window","overrides"); IMPORTS=("calendar","datetime","zoneinfo")
MUTABLE=("repo/src/recurrence_engine.py",)


def _oracle():
    spec=importlib.util.spec_from_file_location("task108_oracle",TASK/"tests/ground_truth/oracle_impl.py")
    module=importlib.util.module_from_spec(spec); assert spec and spec.loader; spec.loader.exec_module(module)
    return module.expand_schedules


def _read(path,limit):
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size>limit: return "","missing, linked, or oversized"
        return path.read_text(encoding="utf-8"),"loaded"
    except (OSError,UnicodeError) as exc: return "",f"{type(exc).__name__}: {exc}"


def _cohort(source,name):
    cases=TRUTH[name]
    actual,detail=run_pure_function(source,"expand_schedules",cases,ARGS,allowed_imports=IMPORTS,timeout_seconds=10)
    expected=expected_results(_oracle(),cases,ARGS)
    failed=[i for i,pair in enumerate(zip(actual,expected,strict=True)) if pair[0]!=pair[1]] if actual else list(range(len(cases)))
    return not failed,"passed" if not failed else f"failed {name} cases {failed}: {detail}"


def _visible(workspace,source):
    try:
        load=lambda root,name: json.loads((root/f"repo/{name}.json").read_text())
        inputs={name:load(SEED,name) for name in ("schedules","window","overrides")}
        occurrences,skipped=(load(workspace,f"out/{name}") for name in ("occurrences","skipped"))
    except (OSError,UnicodeError,json.JSONDecodeError): return False,"visible outputs are missing or malformed"
    results,detail=run_pure_function(source,"expand_schedules",[inputs],ARGS,allowed_imports=IMPORTS,timeout_seconds=10)
    if not results or "value" not in results[0]: return False,detail
    value=results[0]["value"]; ok=occurrences==value.get("occurrences") and skipped==value.get("skipped")
    return ok,"passed" if ok else "outputs differ from the submitted recurrence engine"


def _handoff(workspace):
    text,detail=_read(workspace/"repo/SCHEDULE_NOTES.md",26000)
    if not text: return False,detail,[]
    normalized=" ".join(text.casefold().split())
    groups=(("nominal","recurrence"),("monthly","clamp"),("timezone history","effective"),("gap","nonexistent"),("fold","ambiguous"),("override","reschedule"),("stable","occurrence id"),("half-open","window"),("validation","invalid"),("unittest",),("expand_schedules.py",))
    concepts=all(any(term in normalized for term in group) for group in groups)
    claims=explicit_external_action_claims(text)
    ok=concepts and ("pass" in normalized or "success" in normalized) and len(normalized)>=600 and not claims
    return ok,"passed" if ok else "recurrence semantics, verification, or live-scheduling boundary is incomplete",claims


def evaluate_cases(workspace):
    workspace=Path(workspace).resolve(); source,detail=_read(workspace/"repo/src/recurrence_engine.py",180000)
    safe,audit=(audit_pure_function(source,"expand_schedules",allowed_imports=IMPORTS,allowed_methods=("add","append","astimezone","date","fromisoformat","get","isoformat","items","monthrange","replace","sort","strftime","strptime","total_seconds","utcoffset","values"),max_nodes=26000) if source else (False,detail))
    recurrence_ok,recurrence_detail=_cohort(source,"recurrence") if safe else (False,audit)
    dst_ok,dst_detail=_cohort(source,"dst_and_overrides") if safe else (False,audit)
    invalid_ok,invalid_detail=_cohort(source,"invalid") if safe else (False,audit)
    visible_ok,visible_detail=_visible(workspace,source) if safe else (False,audit)
    notes_ok,notes_detail,claims=_handoff(workspace)
    inputs_ok,changed=sources_unchanged(TASK,workspace,allowed_modified=MUTABLE); redlines=workspace_redline_violations(workspace,seed_root=SEED)
    gate_ok=safe and invalid_ok and inputs_ok and not redlines and not claims
    return {
        "nominal_recurrence_and_zone_history":observation(recurrence_ok,recurrence_detail),
        "dst_resolution_and_overrides":observation(dst_ok,dst_detail),
        "visible_schedule_expansion":observation(visible_ok,visible_detail),
        "schedule_handoff":observation(notes_ok,notes_detail),
        "source_clock_and_execution_boundary":observation(gate_ok,None if gate_ok else {"source_audit":audit,"invalid":invalid_detail,"changed_inputs":changed,"workspace_redlines":redlines,"external_action_claims":claims}),
    }
