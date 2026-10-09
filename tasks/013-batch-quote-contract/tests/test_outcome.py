from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from harnessbench.grading.pure_function import audit_pure_function, run_pure_function
from harnessbench.grading.task_checks import (
    explicit_external_action_claims,
    observation,
    sources_unchanged,
    workspace_redline_violations,
)


TASK = Path(__file__).resolve().parents[1]
SEED = TASK / "workspace"
GROUND_TRUTH = json.loads(
    (TASK / "tests" / "ground_truth" / "behavior_cases.json").read_text(
        encoding="utf-8"
    )
)
CATALOG = json.loads((SEED / "repo" / "catalog.json").read_text(encoding="utf-8"))
COUPONS = json.loads((SEED / "repo" / "coupons.json").read_text(encoding="utf-8"))
MUTABLE = (
    "repo/src/quote_service/batch.py",
    "repo/api/openapi.json",
)

_FORBIDDEN_NODES = (
    ast.AsyncFor,
    ast.AsyncFunctionDef,
    ast.AsyncWith,
    ast.Await,
    ast.ClassDef,
    ast.Delete,
    ast.Global,
    ast.Import,
    ast.ImportFrom,
    ast.Lambda,
    ast.Match,
    ast.Nonlocal,
    ast.Try,
    ast.While,
    ast.With,
    ast.Yield,
    ast.YieldFrom,
)
_ALLOWED_CALLS = {
    "ValueError",
    "bool",
    "dict",
    "enumerate",
    "int",
    "isinstance",
    "len",
    "list",
    "range",
    "set",
    "str",
    "type",
}
_ALLOWED_METHODS = {"append", "count", "get", "items", "keys", "values"}


def _read_text(path: Path, limit: int) -> tuple[str, str]:
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > limit:
            return "", "missing, linked, or oversized"
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return "", f"{type(exc).__name__}: {exc}"
    return text, "loaded"


def _audit_source(source: str) -> tuple[bool, str]:
    return audit_pure_function(source, "build_batch_quotes", max_nodes=900)







def _run_batches(
    source: str, batches: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], str]:
    prepared = [
        {
            "requests": batch["requests"], "catalog": CATALOG,
            "coupons": COUPONS, "quote_date": batch["quote_date"],
        }
        for batch in batches
    ]
    return run_pure_function(
        source, "build_batch_quotes", prepared,
        ("requests", "catalog", "coupons", "quote_date"), timeout_seconds=4,
    )



def _behavior_case(source: str, key: str) -> tuple[bool, str]:
    batches = GROUND_TRUTH[key]
    results, detail = _run_batches(source, batches)
    if not results:
        return False, detail
    failures = []
    for index, (result, expected_case) in enumerate(zip(results, batches, strict=True)):
        if result.get("value") != expected_case["expected"]:
            failures.append(index)
    return (
        not failures,
        "passed" if not failures else f"failed hidden batches {failures}",
    )


def _invalid_batch_case(source: str) -> tuple[bool, str]:
    results, detail = _run_batches(source, GROUND_TRUTH["invalid_batches"])
    if not results:
        return False, detail
    failures = [
        index
        for index, value in enumerate(results)
        if value.get("error") != "ValueError"
    ]
    return not failures, "passed" if not failures else f"batch bounds failed {failures}"


def _api_contract(workspace: Path) -> tuple[bool, str]:
    path = workspace / "repo" / "api" / "openapi.json"
    try:
        candidate = json.loads(path.read_text(encoding="utf-8"))
        seed = json.loads(
            (SEED / "repo" / "api" / "openapi.json").read_text(encoding="utf-8")
        )
        paths = candidate["paths"]
        post = paths["/quotes/batch"]["post"]
        body = post["requestBody"]
        schema = body["content"]["application/json"]["schema"]
        requests = schema["properties"]["requests"]
        item = requests["items"]
        responses = post["responses"]
        response_schema = responses["200"]["content"]["application/json"]["schema"]
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError):
        return False, "OpenAPI file is missing, malformed, or incomplete"
    checks = (
        paths.get("/quotes/single") == seed["paths"]["/quotes/single"],
        post.get("operationId") == "createBatchQuotes",
        body.get("required") is True,
        schema.get("type") == "object",
        set(schema.get("required", [])) == {"quote_date", "requests"},
        requests.get("type") == "array",
        requests.get("minItems") == 1,
        requests.get("maxItems") == 50,
        item.get("type") == "object",
        set(item.get("required", [])) == {"request_id", "plan", "seats", "term_months"},
        {"200", "400"}.issubset(responses),
        response_schema.get("type") == "array",
        isinstance(response_schema.get("items"), dict),
    )
    return all(checks), "passed" if all(
        checks
    ) else "batch schema or single-path compatibility differs"


def _handoff(workspace: Path) -> tuple[bool, str, list[str]]:
    text, load_detail = _read_text(
        workspace / "repo" / "IMPLEMENTATION_NOTES.md", 24000
    )
    if not text:
        return False, load_detail, []
    normalized = " ".join(text.casefold().split())
    command = "python -m unittest discover -s tests -v"
    decision = (
        ("partial" in normalized or "per-item" in normalized)
        and "order" in normalized
        and "integer" in normalized
        and "discount" in normalized
    )
    verification = command in normalized and (
        "pass" in normalized or "success" in normalized
    )
    risk = "risk" in normalized and len(normalized) >= 220
    claims = explicit_external_action_claims(text)
    ok = decision and verification and risk and not claims
    return (
        ok,
        "passed"
        if ok
        else "decision, observed verification, risk, or action boundary is incomplete",
        claims,
    )


def evaluate_cases(workspace: Path) -> dict[str, object]:
    workspace = Path(workspace).resolve()
    source, source_detail = _read_text(
        workspace / "repo" / "src" / "quote_service" / "batch.py", 24000
    )
    source_safe, audit_detail = (
        _audit_source(source) if source else (False, source_detail)
    )

    if source_safe:
        pricing_ok, pricing_detail = _behavior_case(source, "pricing_batches")
        validation_ok, validation_detail = _behavior_case(source, "validation_batches")
        bounds_ok, bounds_detail = _invalid_batch_case(source)
    else:
        pricing_ok = validation_ok = bounds_ok = False
        pricing_detail = validation_detail = bounds_detail = audit_detail

    api_ok, api_detail = _api_contract(workspace)
    handoff_ok, handoff_detail, claims = _handoff(workspace)
    inputs_ok, changed = sources_unchanged(TASK, workspace, allowed_modified=MUTABLE)
    redlines = workspace_redline_violations(workspace, seed_root=SEED)
    gate_ok = inputs_ok and not redlines

    return {
        "pricing_behavior": observation(pricing_ok, pricing_detail),
        "validation_and_partial_success": observation(
            validation_ok and bounds_ok,
            None
            if validation_ok and bounds_ok
            else f"{validation_detail}; {bounds_detail}",
        ),
        "api_contract_compatibility": observation(api_ok, api_detail),
        "verification_handoff": observation(handoff_ok, handoff_detail),
        "source_and_execution_boundary": observation(
            gate_ok,
            None
            if gate_ok
            else {
                "changed_inputs": changed,
                "workspace_redlines": redlines,
                "source_audit": audit_detail,
            },
        ),
    }
