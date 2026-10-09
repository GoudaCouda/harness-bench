"""Trusted recomputation of the Westbridge sliding-window quota ledger."""

from __future__ import annotations

import json
from typing import Any

DECISION_EXECUTED = "executed"
DECISION_BURST_EXCEEDED = "burst_exceeded"
DECISION_DAILY_EXCEEDED = "daily_exceeded"
DECISION_REFUND_EXPIRED = "refund_expired"
DECISION_REJECTED = "rejected"

DECISIONS = (
    DECISION_EXECUTED,
    DECISION_BURST_EXCEEDED,
    DECISION_DAILY_EXCEEDED,
    DECISION_REFUND_EXPIRED,
    DECISION_REJECTED,
)

KIND_DEBIT = "debit"
KIND_REFUND = "refund"


def in_window(event_at: int, clock: int, window: int) -> bool:
    return clock - int(event_at) < window and int(event_at) <= clock


def window_state(events: list[dict[str, Any]], tenant: str, clock: int, burst_s: int, daily_s: int) -> dict[str, Any]:
    burst_count = 0
    daily_net = 0
    by_id = {str(event.get("event_id")): event for event in events if event.get("tenant_id") == tenant}
    for event in events:
        if event.get("tenant_id") != tenant:
            continue
        when = int(event.get("at") or 0)
        amount = int(event.get("amount_cents") or 0)
        kind = event.get("kind")
        if kind == KIND_DEBIT and in_window(when, clock, burst_s):
            burst_count += 1
        if not in_window(when, clock, daily_s):
            continue
        if kind == KIND_DEBIT:
            daily_net += amount
        elif kind == KIND_REFUND:
            original = by_id.get(str(event.get("refund_of")))
            if (
                isinstance(original, dict)
                and original.get("kind") == KIND_DEBIT
                and in_window(int(original.get("at") or 0), clock, daily_s)
            ):
                daily_net -= amount
    return {"burst_count": burst_count, "daily_net_cents": daily_net}


def decide_one(
    request: dict[str, Any],
    events: list[dict[str, Any]],
    clock: int,
    burst_s: int,
    daily_s: int,
    burst_max: int,
    daily_max: int,
) -> dict[str, Any]:
    request_id = request.get("request_id")
    tenant = request.get("tenant_id")
    kind = request.get("kind")
    amount = request.get("amount_cents")
    if not isinstance(tenant, str) or not tenant:
        return {
            "request_id": request_id,
            "decision": DECISION_REJECTED,
            "reason": "missing_tenant",
        }
    if any(event.get("source_request_id") == request_id for event in events):
        return {
            "request_id": request_id,
            "tenant_id": tenant,
            "decision": DECISION_EXECUTED,
            "reason": "already_recorded",
            "amount_cents": 0,
        }
    if kind not in {KIND_DEBIT, KIND_REFUND} or not isinstance(amount, int) or amount <= 0:
        return {
            "request_id": request_id,
            "tenant_id": tenant,
            "decision": DECISION_REJECTED,
            "reason": "malformed_request",
        }

    if kind == KIND_REFUND:
        original_id = request.get("refund_of")
        original = next(
            (
                event
                for event in events
                if event.get("event_id") == original_id and event.get("tenant_id") == tenant
            ),
            None,
        )
        if not isinstance(original, dict) or original.get("kind") != KIND_DEBIT:
            return {
                "request_id": request_id,
                "tenant_id": tenant,
                "decision": DECISION_REJECTED,
                "reason": "refund_target_missing",
            }
        if not in_window(int(original.get("at") or 0), clock, daily_s):
            return {
                "request_id": request_id,
                "tenant_id": tenant,
                "decision": DECISION_REFUND_EXPIRED,
                "reason": "original_debit_left_daily_window",
            }
        events.append(
            {
                "event_id": f"evt-{request_id}",
                "tenant_id": tenant,
                "kind": KIND_REFUND,
                "amount_cents": amount,
                "at": clock,
                "refund_of": original_id,
                "source_request_id": request_id,
            }
        )
        return {
            "request_id": request_id,
            "tenant_id": tenant,
            "decision": DECISION_EXECUTED,
            "reason": "refund_applied",
            "amount_cents": amount,
        }

    state = window_state(events, tenant, clock, burst_s, daily_s)
    if state["burst_count"] >= burst_max:
        return {
            "request_id": request_id,
            "tenant_id": tenant,
            "decision": DECISION_BURST_EXCEEDED,
            "reason": "burst_window_full",
            "burst_count": state["burst_count"],
        }
    if state["daily_net_cents"] + amount > daily_max:
        return {
            "request_id": request_id,
            "tenant_id": tenant,
            "decision": DECISION_DAILY_EXCEEDED,
            "reason": "daily_cap_exceeded",
            "daily_net_cents": state["daily_net_cents"],
        }
    events.append(
        {
            "event_id": f"evt-{request_id}",
            "tenant_id": tenant,
            "kind": KIND_DEBIT,
            "amount_cents": amount,
            "at": clock,
            "source_request_id": request_id,
        }
    )
    return {
        "request_id": request_id,
        "tenant_id": tenant,
        "decision": DECISION_EXECUTED,
        "reason": "within_windows",
        "amount_cents": amount,
    }


def plan(
    seed_events: list[dict[str, Any]],
    pending: list[dict[str, Any]],
    policy: dict[str, Any],
) -> dict[str, Any]:
    clock = int(policy["quota_clock_epoch"])
    burst_s = int(policy["burst_window_seconds"])
    daily_s = int(policy["daily_window_seconds"])
    burst_max = int(policy["burst_max_debits"])
    daily_max = int(policy["daily_max_cents"])
    events = json.loads(json.dumps(seed_events))
    decisions: list[dict[str, Any]] = []
    executed_cents = 0
    for request in pending:
        decision = decide_one(request, events, clock, burst_s, daily_s, burst_max, daily_max)
        decisions.append(decision)
        if decision["decision"] == DECISION_EXECUTED and request.get("kind") == KIND_DEBIT:
            if decision.get("reason") == "already_recorded":
                continue
            executed_cents += int(request.get("amount_cents") or 0)

    counts = {name: 0 for name in DECISIONS}
    for entry in decisions:
        counts[entry["decision"]] += 1

    tenants = sorted({str(event.get("tenant_id")) for event in events})
    snapshots = {
        tenant: window_state(events, tenant, clock, burst_s, daily_s) for tenant in tenants
    }
    return {
        "final_events": events,
        "decisions": decisions,
        "counts": counts,
        "executed_debit_cents": executed_cents,
        "snapshots": snapshots,
    }
