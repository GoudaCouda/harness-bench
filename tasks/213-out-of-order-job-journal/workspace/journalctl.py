#!/usr/bin/env python3
"""Local out-of-order job-journal controller. Diagnostic only."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parent
JOBS_PATH = WORKSPACE / "state" / "jobs.json"
STREAM_PATH = WORKSPACE / "staging" / "completions.json"
RECEIPT_PATH = WORKSPACE / "state" / "journal_receipt.json"
CLOCK = 1773910800
VALID = {"applied", "replayed", "stale", "held", "blocked", "rejected"}
TERMINAL = {"succeeded", "failed"}


def _load(path: Path) -> Any:
    if not path.is_file():
        raise SystemExit(f"missing required file: {path.relative_to(WORKSPACE)}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as extra:
        raise SystemExit(f"{path.relative_to(WORKSPACE)} is not valid JSON: {extra}")


def _emit(payload: Any) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def cmd_clock(_: argparse.Namespace) -> int:
    _emit({"journal_clock_epoch": CLOCK})
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    if args.target == "jobs":
        document = _load(JOBS_PATH)
        jobs = document.get("jobs") if isinstance(document, dict) else {}
        if args.selector:
            _emit({"job_id": args.selector, "present": args.selector in jobs, "job": jobs.get(args.selector)})
            return 0
        summary = [
            {
                "job_id": job_id,
                "seq": job.get("seq"),
                "status": job.get("status"),
                "attempt": job.get("attempt"),
                "depends_on": job.get("depends_on"),
            }
            for job_id, job in sorted(jobs.items(), key=lambda item: int(item[1].get("seq") or 0))
            if isinstance(job, dict)
        ]
        _emit({"count": len(summary), "jobs": summary})
        return 0
    stream = _load(STREAM_PATH)
    events = stream.get("events") if isinstance(stream, dict) else []
    if args.selector:
        for event in events:
            if event.get("event_id") == args.selector or event.get("job_id") == args.selector:
                _emit(event)
                return 0
        _emit({"selector": args.selector, "present": False})
        return 0
    _emit({"count": len(events), "event_ids": [event.get("event_id") for event in events]})
    return 0


def cmd_deps(args: argparse.Namespace) -> int:
    jobs = (_load(JOBS_PATH) or {}).get("jobs") or {}
    job = jobs.get(args.job_id)
    if not isinstance(job, dict):
        _emit({"job_id": args.job_id, "present": False})
        return 0
    deps = []
    for dep in job.get("depends_on") or []:
        record = jobs.get(dep) if isinstance(jobs.get(dep), dict) else {}
        deps.append({"job_id": dep, "status": record.get("status")})
    _emit({"job_id": args.job_id, "depends_on": deps})
    return 0


def cmd_validate(_: argparse.Namespace) -> int:
    failures: list[dict[str, Any]] = []
    document = _load(JOBS_PATH)
    jobs = document.get("jobs") if isinstance(document, dict) else {}
    if not isinstance(jobs, dict):
        failures.append({"check": "jobs_schema", "detail": "jobs must be a JSON object"})
        jobs = {}
    for job_id, job in jobs.items():
        if not isinstance(job, dict):
            continue
        for dep in job.get("depends_on") or []:
            parent = jobs.get(dep)
            if job.get("status") == "succeeded" and not (isinstance(parent, dict) and parent.get("status") == "succeeded"):
                failures.append({"check": "dependency_integrity", "detail": f"{job_id} succeeded while {dep} has not"})
    receipt = None
    if RECEIPT_PATH.is_file():
        try:
            receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError as extra:
            failures.append({"check": "receipt_schema", "detail": f"invalid JSON: {extra}"})
    else:
        failures.append({"check": "receipt_schema", "detail": "state/journal_receipt.json is missing"})
    if isinstance(receipt, dict):
        decisions = receipt.get("decisions")
        if not isinstance(decisions, list):
            failures.append({"check": "receipt_schema", "detail": "decisions must be an array"})
        else:
            recomputed = {name: 0 for name in sorted(VALID)}
            for entry in decisions:
                if not isinstance(entry, dict) or entry.get("decision") not in VALID:
                    failures.append({"check": "receipt_schema", "detail": "unknown decision"})
                    break
                recomputed[entry["decision"]] += 1
            if receipt.get("counts") != recomputed:
                failures.append({"check": "receipt_internal_totals", "detail": "counts disagree with decisions"})
    failed = sorted({str(item["check"]) for item in failures})
    _emit({"status": "pass" if not failed else "fail", "checks_failed": failed, "failures": failures})
    return 0 if not failed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("clock").set_defaults(func=cmd_clock)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("target", choices=["jobs", "completions"])
    inspect.add_argument("selector", nargs="?")
    inspect.set_defaults(func=cmd_inspect)
    deps = sub.add_parser("deps")
    deps.add_argument("job_id")
    deps.set_defaults(func=cmd_deps)
    sub.add_parser("validate").set_defaults(func=cmd_validate)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
