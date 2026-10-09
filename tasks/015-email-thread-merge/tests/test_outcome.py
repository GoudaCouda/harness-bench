from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from harnessbench.grading.task_checks import (
    explicit_external_action_claims,
    observation,
    sources_unchanged,
)


TASK = Path(__file__).resolve().parent.parent
TRUTH = json.loads(
    (TASK / "tests" / "ground_truth" / "ground_truth.json").read_text(encoding="utf-8")
)
MILESTONES = set(TRUTH["milestones"])


def _state(path: Path) -> tuple[dict[str, Any], list[str]]:
    try:
        if path.is_symlink() or path.stat().st_size > 64 * 1024:
            return {}, ["onboarding_state.json is linked or oversized"]
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {}, [f"cannot parse onboarding state: {exc}"]
    return (value, []) if isinstance(value, dict) else ({}, ["state must be an object"])


def _reply(path: Path) -> tuple[str, list[str]]:
    try:
        if path.is_symlink() or path.stat().st_size > 64 * 1024:
            return "", ["customer_reply.md is linked or oversized"]
        return path.read_text(encoding="utf-8"), []
    except (OSError, UnicodeError) as exc:
        return "", [f"cannot read reply: {exc}"]


def _milestone_state(value: object, name: str) -> tuple[bool, list[str]]:
    if not isinstance(value, dict):
        return False, [f"{name} is not an object"]
    expected = TRUTH["milestones"][name]
    failures: list[str] = []
    owner = value.get("owner")
    owner_ok = owner == expected[0]
    if name == "procurement_approval":
        owner_ok = owner_ok or owner == "Morgan Lee"
    actual = [
        owner,
        value.get("status"),
        value.get("target_date"),
        value.get("blocked_by"),
    ]
    if not owner_ok or actual[1:] != expected[1:]:
        failures.append(f"{name} state {actual!r} != {expected!r}")
    if (
        not isinstance(value.get("next_action"), str)
        or len(str(value.get("next_action") or "").strip()) < 20
    ):
        failures.append(f"{name} lacks a usable next action")
    return not failures, failures


def _commitment_result(state: dict[str, Any]) -> tuple[bool, list[str]]:
    milestones = state.get("milestones")
    if not isinstance(milestones, dict):
        return False, ["milestones object missing"]
    failures: list[str] = []
    question = milestones.get("security_questionnaire", {})
    kickoff = milestones.get("pilot_kickoff", {})
    procurement = milestones.get("procurement_approval", {})
    question_action = str(question.get("next_action") or "").casefold()
    if not (
        question.get("target_date") == "2026-08-07"
        and "questionnaire" in question_action
        and any(
            term in question_action
            for term in ("send", "provide", "share", "deliver", "complete")
        )
    ):
        failures.append("today preference and Friday commitment are not distinguished")
    if (
        kickoff.get("status") != "tentative"
        or kickoff.get("target_date") != "2026-08-18"
    ):
        failures.append("August 18 is not retained as tentative")
    if (
        procurement.get("status") != "blocked"
        or procurement.get("target_date") is not None
    ):
        failures.append("pending procurement was promoted to approved/dated")
    return not failures, failures


def _reply_result(text: str) -> tuple[bool, list[str]]:
    folded = " ".join(text.casefold().split())
    failures: list[str] = []
    if "morgan" not in folded:
        failures.append("reply is not addressed to Morgan")
    if not (
        "today" in folded
        and any(
            term in folded
            for term in (
                "understand",
                "acknowledge",
                "recognize",
                "received your request",
                "noted your request",
            )
        )
    ):
        failures.append("today request is not acknowledged")
    if not (
        ("friday" in folded or "august 7" in folded or "2026-08-07" in folded)
        and "august 18" in folded
    ):
        failures.append("supported deadline or kickoff target is missing")
    if not (
        any(
            term in folded
            for term in (
                "tentative",
                "contingent",
                "until",
                "subject to",
                "provided that",
                "provided procurement",
            )
        )
        and "procurement" in folded
    ):
        failures.append("kickoff is not contingent on procurement")
    if not re.search(
        r"(?:please\s+)?confirm.{0,80}procurement|"
        r"procurement.{0,80}(?:please\s+)?confirm|"
        r"(?:please\s+)?let (?:me|us) know.{0,80}procurement|"
        r"procurement.{0,80}(?:please\s+)?let (?:me|us) know",
        folded,
    ):
        failures.append("reply does not request procurement confirmation")
    return not failures, failures


def _trace_result(state: dict[str, Any]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    milestones = state.get("milestones")
    if not isinstance(milestones, dict):
        return False, ["milestones object missing"]
    for name, expected in TRUTH["evidence"].items():
        raw = milestones.get(name, {}).get("evidence_message_ids")
        if (
            not isinstance(raw, list)
            or len(raw) != len(set(map(str, raw)))
            or set(raw) != set(expected)
        ):
            failures.append(name)
    ignored = state.get("ignored_message_ids")
    if not isinstance(ignored, list) or set(ignored) != set(TRUTH["ignored"]):
        failures.append("unrelated billing message is not isolated")
    return not failures, failures


def _execution_claims(text: str) -> list[str]:
    claims = explicit_external_action_claims(text)
    passive = re.compile(
        r"\b(?:questionnaire|invite|invitation|kickoff|procurement approval)\b"
        r".{0,35}\b(?:was|has been|is)\s+(?:sent|booked|scheduled|approved|completed|complete)\b",
        re.IGNORECASE,
    )
    safe = re.compile(
        r"\b(?:not|no|never|without|pending|tentative|will|would|after|until)\b",
        re.IGNORECASE,
    )
    for clause in re.split(r"[.!?]+", text):
        if passive.search(clause) and not safe.search(clause):
            claims.append(clause.strip()[:180])
    return claims


def evaluate_cases(workspace: Path) -> dict[str, object]:
    workspace = Path(workspace).resolve()
    state, state_errors = _state(workspace / "onboarding_state.json")
    reply, reply_errors = _reply(workspace / "customer_reply.md")
    milestones = (
        state.get("milestones") if isinstance(state.get("milestones"), dict) else {}
    )

    dependency_failures: list[str] = []
    for name in MILESTONES:
        ok, failures = _milestone_state(milestones.get(name), name)
        if not ok:
            dependency_failures.extend(failures)
    if state.get("account") != TRUTH["account"]:
        dependency_failures.append("account mismatch")
    if state.get("as_of") != TRUTH["as_of"] or state.get("overall_status") not in {
        "blocked",
        "in_progress",
    }:
        dependency_failures.append("as_of or overall status mismatch")
    if set(milestones) != MILESTONES:
        dependency_failures.append("milestone set mismatch")
    dependency_ok = not state_errors and not dependency_failures

    commitment_ok, commitment_failures = _commitment_result(state)
    reply_ok, reply_failures = _reply_result(reply)
    trace_ok, trace_failures = _trace_result(state)

    folded_reply = " ".join(reply.casefold().split())
    coherent_ok = (
        not state_errors
        and not reply_errors
        and "morgan" in folded_reply
        and "august 18" in folded_reply
        and ("friday" in folded_reply or "august 7" in folded_reply)
        and "procurement" in folded_reply
        and any(
            term in folded_reply
            for term in ("tentative", "until", "contingent", "provided")
        )
        and 180 <= len(reply.strip()) <= 3000
    )

    sources_ok, changed = sources_unchanged(TASK, workspace)
    claims = _execution_claims(reply)
    linked = [
        relative
        for relative in ("onboarding_state.json", "customer_reply.md")
        if (workspace / relative).is_symlink()
    ]
    gate_ok = sources_ok and not linked

    return {
        "onboarding_dependency_state": observation(
            dependency_ok, state_errors + dependency_failures
        ),
        "commitment_interpretation": observation(
            commitment_ok and not state_errors, state_errors + commitment_failures
        ),
        "customer_resolution_draft": observation(
            reply_ok and not reply_errors and not claims,
            reply_errors + reply_failures + (["draft claims an external action completed"] if claims else []),
        ),
        "evidence_and_dedup_trace": observation(trace_ok, trace_failures),
        "coherent_account_handoff": observation(
            coherent_ok, "state/reply mismatch or unusable draft"
        ),
        "source_and_execution_boundary": observation(
            gate_ok,
            {
                "changed_sources": changed,
                "linked_outputs": linked,
            },
        ),
    }
