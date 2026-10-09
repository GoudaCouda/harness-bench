"""Trusted recomputation of the Northharbor RPC circuit breaker.

This module is grader-only. It never imports the agent-visible controller and
never reads candidate-authored artifacts as evidence.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

THRESHOLD = 3
COOLDOWN_SEC = 30
PROBE_BUDGET = 1
DECISIONS = ("executed", "short_circuited", "probed")


def _counts(decisions: list[dict[str, Any]]) -> dict[str, int]:
    tallies = {name: 0 for name in DECISIONS}
    tallies.update(Counter(str(row["decision"]) for row in decisions))
    return tallies


def plan(events: list[dict[str, Any]]) -> dict[str, Any]:
    states: dict[str, dict[str, Any]] = {}
    decisions: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        service = str(event["service"])
        ts = int(event["epoch"])
        kind = str(event["outcome"])
        state = states.setdefault(
            service,
            {"mode": "closed", "fails": 0, "opened_at": None, "probes": 0},
        )
        if (
            state["mode"] == "open"
            and state["opened_at"] is not None
            and ts >= int(state["opened_at"]) + COOLDOWN_SEC
        ):
            state["mode"] = "half_open"
            state["probes"] = 0
        if state["mode"] == "open":
            decision = "short_circuited"
        elif state["mode"] == "half_open":
            if int(state["probes"]) >= PROBE_BUDGET:
                decision = "short_circuited"
            else:
                state["probes"] = int(state["probes"]) + 1
                decision = "probed"
                if kind == "success":
                    state.update(mode="closed", fails=0, opened_at=None, probes=0)
                else:
                    state.update(mode="open", fails=0, opened_at=ts, probes=0)
        else:
            decision = "executed"
            if kind == "success":
                state["fails"] = 0
            else:
                state["fails"] = int(state["fails"]) + 1
                if int(state["fails"]) >= THRESHOLD:
                    state["mode"] = "open"
                    state["opened_at"] = ts
        decisions.append(
            {
                "index": index,
                "event_id": event["event_id"],
                "service": service,
                "decision": decision,
                "mode_after": state["mode"],
            }
        )
    forwarded = [
        row["event_id"]
        for row in decisions
        if row["decision"] in {"executed", "probed"}
    ]
    return {
        "decisions": decisions,
        "counts": _counts(decisions),
        "forwarded_event_ids": forwarded,
        "breaker_mode": {name: st["mode"] for name, st in states.items()},
    }
