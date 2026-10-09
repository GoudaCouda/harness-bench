"""Trusted recomputation of the settlement idempotency ledger recovery.

This module is grader-only. It never imports the agent-visible controller and
never reads candidate-authored artifacts as evidence: it recomputes the
canonical outcome from the protected seed state and the published policy rules.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

KEY_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")
TRIMMED = " \t"

DECISION_REPLAYED = "replayed"
DECISION_CONFLICT = "conflict"
DECISION_EXECUTED = "executed"
DECISION_DEFERRED = "deferred"
DECISION_REJECTED = "rejected"

DECISIONS = (
    DECISION_REPLAYED,
    DECISION_CONFLICT,
    DECISION_EXECUTED,
    DECISION_DEFERRED,
    DECISION_REJECTED,
)


def canonical_body(body: Any) -> str:
    """Canonical JSON form used by the published fingerprint rule."""

    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fingerprint(method: str, path: str, body: Any) -> str:
    payload = f"{method}\n{path}\n{canonical_body(body)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalize_key(raw: object) -> str | None:
    """Return the canonical idempotency key, or None when it is unusable."""

    if not isinstance(raw, str):
        return None
    candidate = raw.strip(TRIMMED)
    if not KEY_PATTERN.match(candidate):
        return None
    return candidate


def settlement_response(key: str, body: Any) -> dict[str, Any]:
    invoice = body.get("invoice") if isinstance(body, dict) else None
    amount = body.get("amount_cents") if isinstance(body, dict) else None
    return {
        "invoice": invoice,
        "status": "settled",
        "amount_cents": amount,
        "receipt_id": f"RCP-{key}",
    }


def reclaim(ledger: dict[str, Any], clock: int, ttl_seconds: int) -> dict[str, Any]:
    """Bring the crashed ledger back to a usable state.

    Records whose retention window has closed are dropped. `in_flight` records
    whose lease has expired are released, because the worker that held them is
    gone. `in_flight` records with a live lease stay untouched: another worker
    may still own them.
    """

    kept: dict[str, Any] = {}
    dropped_expired: list[str] = []
    released_leases: list[str] = []
    for key in sorted(ledger):
        record = ledger[key]
        created_at = int(record.get("created_at") or 0)
        status = str(record.get("status") or "")
        if clock - created_at >= ttl_seconds:
            dropped_expired.append(key)
            continue
        if status == "in_flight":
            lease = int(record.get("lease_expires_at") or 0)
            if clock >= lease:
                released_leases.append(key)
                continue
        kept[key] = json.loads(json.dumps(record))
    return {
        "ledger": kept,
        "dropped_expired": dropped_expired,
        "released_leases": released_leases,
    }


def decide(
    ledger: dict[str, Any],
    request: dict[str, Any],
    clock: int,
) -> dict[str, Any]:
    """Apply the published precedence to one queued request."""

    raw_key = request.get("idempotency_key")
    key = normalize_key(raw_key)
    if key is None:
        return {
            "request_id": request.get("request_id"),
            "idempotency_key": raw_key,
            "decision": DECISION_REJECTED,
            "reason": "malformed_idempotency_key",
        }

    method = str(request.get("method") or "")
    path = str(request.get("path") or "")
    body = request.get("body")
    request_fingerprint = fingerprint(method, path, body)
    record = ledger.get(key)

    if record is not None and str(record.get("status")) == "completed":
        if str(record.get("fingerprint")) == request_fingerprint:
            return {
                "request_id": request.get("request_id"),
                "idempotency_key": key,
                "decision": DECISION_REPLAYED,
                "reason": "stored_response_replayed",
                "response": json.loads(json.dumps(record.get("response"))),
            }
        return {
            "request_id": request.get("request_id"),
            "idempotency_key": key,
            "decision": DECISION_CONFLICT,
            "reason": "fingerprint_mismatch_for_reused_key",
        }

    if record is not None and str(record.get("status")) == "in_flight":
        return {
            "request_id": request.get("request_id"),
            "idempotency_key": key,
            "decision": DECISION_DEFERRED,
            "reason": "live_lease_held_by_another_worker",
        }

    response = settlement_response(key, body)
    ledger[key] = {
        "status": "completed",
        "fingerprint": request_fingerprint,
        "created_at": clock,
        "response": response,
    }
    return {
        "request_id": request.get("request_id"),
        "idempotency_key": key,
        "decision": DECISION_EXECUTED,
        "reason": "no_usable_prior_record",
        "response": json.loads(json.dumps(response)),
    }


def plan(seed_ledger: dict[str, Any], queue: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    """Recompute the whole recovery outcome from protected inputs."""

    clock = int(policy["recovery_clock_epoch"])
    ttl_seconds = int(policy["record_ttl_seconds"])

    reclaimed = reclaim(json.loads(json.dumps(seed_ledger)), clock, ttl_seconds)
    ledger = reclaimed["ledger"]

    decisions: list[dict[str, Any]] = []
    settled_total = 0
    for request in queue:
        decision = decide(ledger, request, clock)
        decisions.append(decision)
        if decision["decision"] == DECISION_EXECUTED:
            amount = decision.get("response", {}).get("amount_cents")
            settled_total += int(amount or 0)

    counts = {name: 0 for name in DECISIONS}
    for decision in decisions:
        counts[decision["decision"]] += 1

    return {
        "final_ledger": {key: ledger[key] for key in sorted(ledger)},
        "decisions": decisions,
        "dropped_expired": reclaimed["dropped_expired"],
        "released_leases": reclaimed["released_leases"],
        "counts": counts,
        "settled_total_cents": settled_total,
    }
