"""Trusted recomputation of the Ridgeway out-of-order job journal."""

from __future__ import annotations

import json
from typing import Any

DECISION_APPLIED = "applied"
DECISION_REPLAYED = "replayed"
DECISION_STALE = "stale"
DECISION_HELD = "held"
DECISION_BLOCKED = "blocked"
DECISION_REJECTED = "rejected"

DECISIONS = (
    DECISION_APPLIED,
    DECISION_REPLAYED,
    DECISION_STALE,
    DECISION_HELD,
    DECISION_BLOCKED,
    DECISION_REJECTED,
)

STATUS_PENDING = "pending"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"


def deps_satisfied(job: dict[str, Any], jobs: dict[str, Any]) -> bool:
    for dep in job.get("depends_on") or []:
        record = jobs.get(dep)
        if not isinstance(record, dict) or record.get("status") != STATUS_SUCCEEDED:
            return False
    return True


def deps_failed(job: dict[str, Any], jobs: dict[str, Any]) -> bool:
    for dep in job.get("depends_on") or []:
        record = jobs.get(dep)
        if isinstance(record, dict) and record.get("status") == STATUS_FAILED:
            return True
    return False


def apply_completion(jobs: dict[str, Any], event: dict[str, Any], clock: int) -> dict[str, Any]:
    job_id = event.get("job_id")
    attempt = event.get("attempt")
    status = event.get("status")
    job = jobs.get(job_id)
    if not isinstance(job, dict):
        return {
            "job_id": job_id,
            "attempt": attempt,
            "decision": DECISION_REJECTED,
            "reason": "unknown_job",
        }
    if status not in {STATUS_SUCCEEDED, STATUS_FAILED}:
        return {
            "job_id": job_id,
            "attempt": attempt,
            "decision": DECISION_REJECTED,
            "reason": "unknown_status",
        }
    current_attempt = int(job.get("attempt") or 0)
    current_status = str(job.get("status") or STATUS_PENDING)

    if current_status in {STATUS_SUCCEEDED, STATUS_FAILED}:
        if int(attempt or 0) == current_attempt and status == current_status:
            return {
                "job_id": job_id,
                "attempt": attempt,
                "decision": DECISION_REPLAYED,
                "reason": "duplicate_ack_of_terminal_attempt",
            }
        return {
            "job_id": job_id,
            "attempt": attempt,
            "decision": DECISION_STALE,
            "reason": "job_already_terminal",
        }

    if not isinstance(attempt, int) or attempt < current_attempt:
        return {
            "job_id": job_id,
            "attempt": attempt,
            "decision": DECISION_STALE,
            "reason": "attempt_superseded",
        }

    if deps_failed(job, jobs):
        return {
            "job_id": job_id,
            "attempt": attempt,
            "decision": DECISION_BLOCKED,
            "reason": "dependency_failed",
        }
    if not deps_satisfied(job, jobs):
        return {
            "job_id": job_id,
            "attempt": attempt,
            "decision": DECISION_HELD,
            "reason": "dependency_not_yet_succeeded",
            "status": status,
        }

    job["status"] = status
    job["attempt"] = attempt
    job["updated_at"] = clock
    return {
        "job_id": job_id,
        "attempt": attempt,
        "decision": DECISION_APPLIED,
        "reason": "dependencies_met",
        "status": status,
    }


def drain_holds(
    jobs: dict[str, Any],
    holds: list[dict[str, Any]],
    clock: int,
) -> list[dict[str, Any]]:
    applied: list[dict[str, Any]] = []
    while True:
        progressed = False
        next_remaining: list[dict[str, Any]] = []
        for event in list(holds):
            result = apply_completion(jobs, event, clock)
            if result["decision"] == DECISION_HELD:
                next_remaining.append(event)
            else:
                applied.append(result)
                if result["decision"] == DECISION_APPLIED:
                    progressed = True
        holds[:] = next_remaining
        if not progressed:
            break
    return applied


def plan(
    seed_jobs: dict[str, Any],
    completions: list[dict[str, Any]],
    clock: int,
) -> dict[str, Any]:
    jobs = json.loads(json.dumps(seed_jobs))
    holds: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    for event in completions:
        result = apply_completion(jobs, event, clock)
        if result["decision"] == DECISION_HELD:
            holds.append(
                {
                    "job_id": event.get("job_id"),
                    "attempt": event.get("attempt"),
                    "status": event.get("status"),
                }
            )
            decisions.append(result)
            released = drain_holds(jobs, holds, clock)
            decisions.extend(released)
        else:
            decisions.append(result)
            if result["decision"] == DECISION_APPLIED:
                released = drain_holds(jobs, holds, clock)
                decisions.extend(released)

    counts = {name: 0 for name in DECISIONS}
    for entry in decisions:
        counts[entry["decision"]] += 1

    return {
        "final_jobs": {key: jobs[key] for key in sorted(jobs)},
        "decisions": decisions,
        "counts": counts,
        "held_remaining": holds,
        "succeeded": sorted(
            job_id for job_id, job in jobs.items() if job.get("status") == STATUS_SUCCEEDED
        ),
        "failed": sorted(
            job_id for job_id, job in jobs.items() if job.get("status") == STATUS_FAILED
        ),
    }
