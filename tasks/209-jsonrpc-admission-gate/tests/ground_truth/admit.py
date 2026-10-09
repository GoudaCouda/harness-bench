"""Trusted recomputation of the Harborline JSON-RPC admission gate.

This module is grader-only. It never imports the agent-visible controller and
never reads candidate-authored artifacts as evidence.
"""

from __future__ import annotations

import json
from typing import Any

DECISION_ADMITTED = "admitted"
DECISION_FROZEN = "frozen"
DECISION_METHOD_NOT_FOUND = "method_not_found"
DECISION_TENANT_DENIED = "tenant_denied"
DECISION_INVALID_PARAMS = "invalid_params"
DECISION_MALFORMED = "malformed"

DECISIONS = (
    DECISION_ADMITTED,
    DECISION_FROZEN,
    DECISION_METHOD_NOT_FOUND,
    DECISION_TENANT_DENIED,
    DECISION_INVALID_PARAMS,
    DECISION_MALFORMED,
)

ERROR_CODES = {
    DECISION_MALFORMED: -32600,
    DECISION_METHOD_NOT_FOUND: -32601,
    DECISION_INVALID_PARAMS: -32602,
    DECISION_FROZEN: -32001,
    DECISION_TENANT_DENIED: -32002,
}


def is_notification(item: dict[str, Any]) -> bool:
    return "id" not in item


def malformed_reason(item: Any) -> str | None:
    if not isinstance(item, dict):
        return "not_an_object"
    if item.get("jsonrpc") != "2.0":
        return "bad_jsonrpc"
    method = item.get("method")
    if not isinstance(method, str) or not method.strip():
        return "missing_method"
    if "params" in item and not isinstance(item.get("params"), dict):
        return "params_not_object"
    tenant = item.get("tenant_id")
    if not isinstance(tenant, str) or not tenant.strip():
        return "missing_tenant"
    return None


def _error_response(item: dict[str, Any], decision: str, reason: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "error": {
            "code": ERROR_CODES[decision],
            "message": reason,
            "data": {"decision": decision},
        },
        "id": item.get("id"),
    }


def _result_response(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "result": {"status": "queued", "method": item.get("method")},
        "id": item.get("id"),
    }


def decide_one(
    item: Any,
    catalog: dict[str, Any],
    tenants: dict[str, Any],
    freeze: dict[str, Any],
    seen_ids: set[Any],
) -> dict[str, Any]:
    """Apply published precedence. The first matching rule wins."""

    envelope = item if isinstance(item, dict) else {}
    method = envelope.get("method") if isinstance(envelope, dict) else None
    tenant_id = envelope.get("tenant_id") if isinstance(envelope, dict) else None
    request_id = envelope.get("id") if isinstance(envelope, dict) else None
    notification = is_notification(envelope) if isinstance(envelope, dict) else False

    reason = malformed_reason(item)
    if reason is None and not notification and request_id in seen_ids:
        reason = "duplicate_id"
    if reason is not None:
        return {
            "method": method,
            "tenant_id": tenant_id,
            "id": request_id,
            "notification": notification,
            "decision": DECISION_MALFORMED,
            "reason": reason,
        }

    assert isinstance(envelope, dict)
    frozen = set(freeze.get("frozen_methods") or [])
    lifted = set(freeze.get("lifted_methods") or [])
    if method in frozen - lifted:
        return {
            "method": method,
            "tenant_id": tenant_id,
            "id": request_id,
            "notification": notification,
            "decision": DECISION_FROZEN,
            "reason": "method_frozen_by_overlay",
        }

    methods = catalog.get("methods") if isinstance(catalog, dict) else {}
    spec = methods.get(method) if isinstance(methods, dict) else None
    if not isinstance(spec, dict):
        return {
            "method": method,
            "tenant_id": tenant_id,
            "id": request_id,
            "notification": notification,
            "decision": DECISION_METHOD_NOT_FOUND,
            "reason": "method_absent_from_catalog",
        }

    capability = spec.get("capability")
    granted = tenants.get("tenants", {}).get(tenant_id) if isinstance(tenants, dict) else None
    if not isinstance(granted, list) or capability not in granted:
        return {
            "method": method,
            "tenant_id": tenant_id,
            "id": request_id,
            "notification": notification,
            "decision": DECISION_TENANT_DENIED,
            "reason": "tenant_lacks_capability",
        }

    params = envelope.get("params") if isinstance(envelope.get("params"), dict) else {}
    required = spec.get("required_params") or []
    missing = [name for name in required if name not in params]
    if missing:
        return {
            "method": method,
            "tenant_id": tenant_id,
            "id": request_id,
            "notification": notification,
            "decision": DECISION_INVALID_PARAMS,
            "reason": "missing_required_params",
            "missing": missing,
        }

    return {
        "method": method,
        "tenant_id": tenant_id,
        "id": request_id,
        "notification": notification,
        "decision": DECISION_ADMITTED,
        "reason": "passed_admission_gate",
    }


def plan(
    batch: list[Any],
    catalog: dict[str, Any],
    tenants: dict[str, Any],
    freeze: dict[str, Any],
) -> dict[str, Any]:
    decisions: list[dict[str, Any]] = []
    responses: list[dict[str, Any]] = []
    seen_ids: set[Any] = set()
    forwarded: list[str] = []

    for index, item in enumerate(batch):
        decision = decide_one(item, catalog, tenants, freeze, seen_ids)
        decision["index"] = index
        decisions.append(decision)
        envelope = item if isinstance(item, dict) else {}
        if not decision["notification"] and "id" in envelope:
            seen_ids.add(envelope.get("id"))
        if decision["decision"] == DECISION_ADMITTED:
            forwarded.append(str(decision.get("method")))
            if not decision["notification"]:
                responses.append(_result_response(envelope))
        elif not decision["notification"]:
            responses.append(
                _error_response(envelope, decision["decision"], str(decision["reason"]))
            )

    counts = {name: 0 for name in DECISIONS}
    for entry in decisions:
        counts[entry["decision"]] += 1

    return {
        "decisions": decisions,
        "counts": counts,
        "response_batch": responses,
        "forwarded_methods": forwarded,
        "admitted_count": counts[DECISION_ADMITTED],
        "response_count": len(responses),
        "frozen_never_forwarded": True,
    }
