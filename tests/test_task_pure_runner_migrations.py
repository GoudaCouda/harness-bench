from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
TASKS = {
    "002-monorepo-affected-build": ("_audit_source", "plan_affected"),
    "009-safe-archive-extraction": ("_audit_source", "plan_extraction"),
    "010-layered-config-resolution": ("_audit", "resolve_config"),
    "012-feature-flag-retirement": ("_audit", "select_checkout_engine"),
    "013-batch-quote-contract": ("_audit_source", "build_batch_quotes"),
    "017-http-cache-revalidation": ("_audit", "evaluate_cache_request"),
    "019-wheel-install-transaction-recovery": ("_audit", "plan_recovery"),
    "023-oauth-refresh-race-recovery": ("_audit", "reconcile_refresh"),
}


def _load(task_id: str):
    path = ROOT / "tasks" / task_id / "tests" / "test_outcome.py"
    spec = importlib.util.spec_from_file_location(f"migration_{task_id}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("task_id", "audit_name", "function_name"),
    [(task_id, *values) for task_id, values in TASKS.items()],
)
def test_migrated_task_accepts_harmless_python_style(
    task_id: str, audit_name: str, function_name: str
) -> None:
    module = _load(task_id)
    source = (
        "import copy\n"
        "def _clone(value):\n    return copy.deepcopy(value)\n"
        f"def {function_name}(*args):\n"
        "    mapper = lambda value: value\n"
        "    return list(map(mapper, [_clone(args[0])]))[0]\n"
    )
    assert getattr(module, audit_name)(source) == (True, "audited")
