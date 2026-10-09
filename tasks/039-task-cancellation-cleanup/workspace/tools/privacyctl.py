#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ROOT = Path.cwd()
JOB = ROOT / "control/job_state.json"
QUEUE = ROOT / "control/queue.json"
LEASES = ROOT / "control/worker_leases.json"
FANOUT = ROOT / "control/fanout_state.json"
INDEX = ROOT / "control/fanout_index.json"
EVENTS = ROOT / "audit/events.jsonl"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def notice():
    return load(ROOT / "cancellation_notice.json")


def event_ids():
    return {json.loads(line)["event_id"] for line in EVENTS.read_text().splitlines() if line.strip()}


def emit(event_id, event_type, **values):
    if event_id not in event_ids():
        event = {"event_id": event_id, "at": "2026-07-30T10:15:00Z", "request_id": notice()["request_id"], "type": event_type, **values}
        with EVENTS.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, separators=(",", ":")) + "\n")


def targets():
    scoped = set(notice()["scope"]["jobs"])
    if notice()["scope"].get("include_child_attempts"):
        changed = True
        while changed:
            changed = False
            for edge in load(INDEX).get("edges", []):
                if edge.get("parent_job_id") in scoped and edge.get("child_job_id") not in scoped:
                    scoped.add(edge["child_job_id"])
                    changed = True
    return scoped


def fence():
    state = load(FANOUT)
    if state.get("accepting_children"):
        state["accepting_children"] = False
        state["generation"] = int(state["generation"]) + 1
        state["fence_notice_id"] = notice()["notice_id"]
        state["updated_at"] = "2026-07-30T10:15:00Z"
        dump(FANOUT, state)
    emit("AUD-703", "fanout_fenced", generation=state["generation"], job_ids=sorted(targets()))


def quiesce():
    if load(FANOUT).get("accepting_children"):
        raise ValueError("fanout still accepts children; fence the request first")
    leases = load(LEASES)
    for lease in leases["leases"]:
        if lease.get("job_id") in targets() and lease.get("status") == "active":
            lease["status"] = "draining"
            lease["drain_notice_id"] = notice()["notice_id"]
    dump(LEASES, leases)
    emit("AUD-704", "worker_drain_requested", job_ids=sorted(targets()))


def confirm_checkpoints():
    if load(FANOUT).get("accepting_children"):
        raise ValueError("fanout must be fenced before checkpoint confirmation")
    leases = load(LEASES)
    scoped = [lease for lease in leases["leases"] if lease.get("job_id") in targets()]
    required_lease_ids = {
        job["lease_id"] for job in load(JOB)["jobs"]
        if job.get("job_id") in targets() and job.get("lease_id")
    }
    if {lease.get("lease_id") for lease in scoped} != required_lease_ids:
        raise ValueError("scoped lease inventory is incomplete")
    if any(lease.get("status") == "active" for lease in scoped):
        raise ValueError("active lease remains; request drain before confirming checkpoints")
    for lease in scoped:
        if lease.get("status") == "draining":
            lease["status"] = "released"
            lease["release_reason"] = notice()["notice_id"]
            lease["checkpoint_confirmed"] = True
    dump(LEASES, leases)
    emit("AUD-705", "worker_checkpoints_confirmed", lease_ids=sorted(lease["lease_id"] for lease in scoped))


def cancel():
    if load(FANOUT).get("accepting_children"):
        raise ValueError("fanout is not fenced")
    scoped_leases = [lease for lease in load(LEASES)["leases"] if lease.get("job_id") in targets()]
    required_lease_ids = {
        job["lease_id"] for job in load(JOB)["jobs"]
        if job.get("job_id") in targets() and job.get("lease_id")
    }
    if {lease.get("lease_id") for lease in scoped_leases} != required_lease_ids:
        raise ValueError("scoped lease inventory is incomplete")
    if any(lease.get("status") != "released" or not lease.get("checkpoint_confirmed") for lease in scoped_leases):
        raise ValueError("all scoped leases require checkpoint-confirmed release")
    jobs = load(JOB)
    for job in jobs["jobs"]:
        if job.get("job_id") in targets():
            job["status"] = "cancelled"
            job["cancel_notice_id"] = notice()["notice_id"]
    jobs["updated_at"] = "2026-07-30T10:15:00Z"
    dump(JOB, jobs)
    queue = load(QUEUE)
    for transfer in queue["transfers"]:
        if transfer.get("job_id") in targets() and transfer.get("status") in ("pending", "preparing"):
            transfer["status"] = "withdrawn"
            transfer["withdraw_notice_id"] = notice()["notice_id"]
    dump(QUEUE, queue)
    emit("AUD-706", "jobs_cancelled", job_ids=sorted(targets()))
    withdrawn = sorted(t["transfer_id"] for t in queue["transfers"] if t.get("job_id") in targets() and t.get("status") == "withdrawn")
    emit("AUD-707", "transfers_withdrawn", transfer_ids=withdrawn)


def expected_actions():
    result = {}
    for item in load(ROOT / "export_manifest.json")["artifacts"]:
        retain = item.get("legal_hold") or item["class"] == "audit_receipt"
        result[item["path"]] = ("retain" if retain else "purge", item["evidence_id"])
    return result


def cleanup(path):
    rows = list(csv.DictReader(path.open(encoding="utf-8", newline="")))
    by_path = {row.get("path"): row for row in rows}
    expected = expected_actions()
    if set(by_path) != set(expected):
        raise ValueError("cleanup plan must classify every manifest artifact exactly once")
    if any(by_path[path].get("action") != action or evidence not in by_path[path].get("evidence_id", "") or not by_path[path].get("reason") for path, (action, evidence) in expected.items()):
        raise ValueError("cleanup plan conflicts with retention policy or omits evidence")
    if any(job.get("status") != "cancelled" for job in load(JOB)["jobs"] if job.get("job_id") in targets()):
        raise ValueError("cancel every reconciled job before cleanup")
    purged = []
    for artifact_path, (action, _) in expected.items():
        candidate = ROOT / artifact_path
        if action == "purge" and candidate.exists():
            candidate.unlink()
            purged.append(artifact_path)
    emit("AUD-708", "staging_cleanup_applied", purged=sorted(purged), retained=sorted(path for path, (action, _) in expected.items() if action == "retain"))


def verify():
    scoped = targets()
    fanout = load(FANOUT)
    jobs = load(JOB)["jobs"]
    queue = load(QUEUE)["transfers"]
    leases = load(LEASES)["leases"]
    expected = expected_actions()
    scoped_transfers = [item for item in queue if item.get("job_id") in scoped]
    required_lease_ids = {job["lease_id"] for job in jobs if job.get("job_id") in scoped and job.get("lease_id")}
    scoped_leases = [lease for lease in leases if lease.get("job_id") in scoped]
    return all((
        not fanout.get("accepting_children") and fanout.get("fence_notice_id") == notice()["notice_id"],
        all(job.get("status") == "cancelled" for job in jobs if job.get("job_id") in scoped),
        {lease.get("lease_id") for lease in scoped_leases} == required_lease_ids,
        all(lease.get("status") == "released" and lease.get("checkpoint_confirmed") for lease in scoped_leases),
        all(item.get("status") == "withdrawn" for item in scoped_transfers if item["transfer_id"] in {"xfer-901", "xfer-902", "xfer-904"}),
        all(item.get("status") == "delivered_receipt" for item in scoped_transfers if item["transfer_id"] in {"xfer-899", "xfer-903"}),
        next(item for item in queue if item["transfer_id"] == "xfer-850")["status"] == "completed",
        all((ROOT / path).exists() == (action == "retain") for path, (action, _) in expected.items()),
        set(f"AUD-{number}" for number in range(700, 709)).issubset(event_ids()),
    ))


def main():
    parser = argparse.ArgumentParser(description="Deterministic offline privacy-export containment controller")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "fence", "quiesce", "confirm-checkpoints", "cancel", "verify"):
        sub.add_parser(name)
    clean = sub.add_parser("apply-cleanup")
    clean.add_argument("plan", type=Path)
    args = parser.parse_args()
    if args.command == "status":
        print(json.dumps({"targets": sorted(targets()), "fanout": load(FANOUT), "jobs": load(JOB), "queue": load(QUEUE), "leases": load(LEASES), "manifest": load(ROOT / "export_manifest.json")}, indent=2))
        return 0
    if args.command == "fence":
        fence()
    elif args.command == "quiesce":
        quiesce()
    elif args.command == "confirm-checkpoints":
        confirm_checkpoints()
    elif args.command == "cancel":
        cancel()
    elif args.command == "apply-cleanup":
        cleanup(args.plan)
    ok = verify()
    print("PASS" if ok else "INCOMPLETE")
    return 0 if args.command != "verify" or ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
