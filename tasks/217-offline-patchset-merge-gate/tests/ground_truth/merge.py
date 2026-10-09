"""Trusted recomputation of the Westline offline patchset merge gate.

This module is grader-only. It never imports the agent-visible controller and
never reads candidate-authored artifacts as evidence.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

DECISIONS = (
    "admitted",
    "blocked_checks",
    "blocked_owners",
    "blocked_rebase",
    "malformed",
)


def _counts(decisions: list[dict[str, Any]]) -> dict[str, int]:
    tallies = {name: 0 for name in DECISIONS}
    tallies.update(Counter(str(row["decision"]) for row in decisions))
    return tallies


def _owner_for(path: str, codeowners: dict[str, str]) -> str | None:
    matches = [prefix for prefix in codeowners if path.startswith(prefix)]
    if not matches:
        return None
    matches.sort(key=len, reverse=True)
    return codeowners[matches[0]]


def plan(patches: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    required = list(policy["required_checks"])
    codeowners = dict(policy["codeowners"])
    base_sha = str(policy["current_base_sha"])
    decisions: list[dict[str, Any]] = []
    for index, patch in enumerate(patches):
        checks = patch.get("checks") if isinstance(patch.get("checks"), dict) else {}
        path = str(patch.get("path") or "")
        owner = _owner_for(path, codeowners)
        approvals = {str(item) for item in (patch.get("approvals") or [])}
        if not path or any(name not in checks for name in required):
            decision = "malformed"
        elif any(str(checks.get(name)) != "pass" for name in required):
            decision = "blocked_checks"
        elif owner is None or owner not in approvals:
            decision = "blocked_owners"
        elif str(patch.get("parent_sha") or "") != base_sha:
            decision = "blocked_rebase"
        else:
            decision = "admitted"
        decisions.append(
            {
                "index": index,
                "patch_id": patch.get("patch_id"),
                "path": path,
                "owner": owner,
                "decision": decision,
            }
        )
    admitted = [row["patch_id"] for row in decisions if row["decision"] == "admitted"]
    return {
        "decisions": decisions,
        "counts": _counts(decisions),
        "admitted_ids": admitted,
        "admitted_count": len(admitted),
    }
