from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


TASK = Path(__file__).resolve().parents[2]
GT = json.loads(
    (Path(__file__).parent / "ground_truth.json").read_text(encoding="utf-8")
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def add(
    checks: list[dict[str, Any]], check_id: str, passed: bool, detail: Any = None
) -> None:
    checks.append(
        {
            "id": check_id,
            "label": check_id.replace("_", " "),
            "pass": bool(passed),
            "weight": 1.0,
            "detail": detail,
        }
    )


def normalize(text: str) -> str:
    return " ".join(re.sub(r"[_`*:/-]+", " ", text.casefold()).split())


def scoped_gate_matches(gate: dict[str, Any]) -> tuple[bool, dict[str, bool]]:
    expected = GT["expected_gate"]
    exact_keys = {
        "project",
        "review_id",
        "gate",
        "effective_date",
        "authorized_scope",
        "approved_budget_musd",
        "primary_operator",
        "customer_cohort",
    }
    exact_fields = all(gate.get(key) == expected[key] for key in exact_keys)

    blockers = gate.get("blockers")
    blocker_signals = (
        [normalize(value) for value in blockers] if isinstance(blockers, list) else []
    )
    legal_blocker = bool(
        len(blocker_signals) == 1
        and "legal" in blocker_signals[0].split()
        and "ct9" in blocker_signals[0].replace(" ", "")
        and any(
            token in blocker_signals[0].split()
            for token in ("approval", "approved", "pending")
        )
    )

    deferred = gate.get("deferred_scope")
    deferred_signals = (
        [normalize(value) for value in deferred] if isinstance(deferred, list) else []
    )
    airport_only = bool(
        deferred_signals
        and all(
            "airport" in value.split()
            and bool({"connector", "connectors"} & set(value.split()))
            for value in deferred_signals
        )
    )
    # A single aggregate airport-connectors scope or both inherited trip IDs
    # describe the same deferred business boundary.
    complete_deferred_scope = bool(
        airport_only
        and (
            len(deferred_signals) == 1
            and not deferred_signals[0].endswith((" a", " b"))
            or {"airport connector a", "airport connector b"}.issubset(
                set(deferred_signals)
            )
        )
    )
    detail = {
        "exact_scoped_fields": exact_fields,
        "legal_approval_blocker": legal_blocker,
        "complete_deferred_airport_scope": complete_deferred_scope,
    }
    return all(detail.values()), detail


def score_workspace(
    workspace: Path, *, ground_truth_path: Path | None = None
) -> dict[str, Any]:
    del ground_truth_path
    root = Path(workspace).resolve()
    checks: list[dict[str, Any]] = []

    gate: dict[str, Any] = {}
    try:
        value = load_json(root / "control/launch_gate.json")
        gate = value if isinstance(value, dict) else {}
    except Exception:
        gate = {}
    scoped_ok, scoped_detail = scoped_gate_matches(gate)
    add(checks, "scoped_gate", scoped_ok, {**scoped_detail, "actual": gate})

    queue: dict[str, Any] = {}
    try:
        value = load_json(root / "control/action_queue.json")
        queue = value if isinstance(value, dict) else {}
    except Exception:
        queue = {}
    rows = queue.get("actions") if isinstance(queue.get("actions"), list) else []
    by_id = {
        row.get("action_id"): row
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("action_id"), str)
    }
    seed_queue = load_json(TASK / "workspace/control/action_queue.json")
    seed_by_id = {row["action_id"]: row for row in seed_queue["actions"]}
    expected_status = GT["expected_action_status"]
    identities_ok = len(rows) == len(by_id) == len(seed_by_id) and set(by_id) == set(
        seed_by_id
    )
    status_ok = identities_ok and all(
        by_id[action_id].get("status") == status
        for action_id, status in expected_status.items()
    )
    unrelated_ok = identities_ok and all(
        {key: value for key, value in by_id[action_id].items() if key != "status"}
        == {
            key: value
            for key, value in seed_by_id[action_id].items()
            if key != "status"
        }
        for action_id in seed_by_id
    )
    add(
        checks,
        "action_queue",
        status_ok and unrelated_ok,
        {
            "identities_ok": identities_ok,
            "status_ok": status_ok,
            "unrelated_fields_preserved": unrelated_ok,
        },
    )

    history_ok = False
    history_detail: dict[str, Any] = {}
    try:
        candidate_text = (root / "control/decision_events.jsonl").read_text(
            encoding="utf-8"
        )
        seed_text = (TASK / "workspace/control/decision_events.jsonl").read_text(
            encoding="utf-8"
        )
        seed_lines = seed_text.splitlines()
        lines = candidate_text.splitlines()
        events = [json.loads(line) for line in lines]
        prefix_ok = lines[:2] == seed_lines and candidate_text.endswith("\n")
        current = events[2] if len(events) == 3 and isinstance(events[2], dict) else {}
        evidence = current.get("evidence")
        required_evidence = {
            "briefs/signed_regulator_notice.md",
            "briefs/audited_finance_extract.md",
            "briefs/operations_log.md",
            "briefs/vendor_contract_addendum.md",
        }
        decision = normalize(str(current.get("decision", "")))
        decision_ok = bool(
            "hold" in decision.split()
            and ("legal" in decision.split() or "launch" in decision.split())
        )
        event_ok = bool(
            current.get("event_id") == "KST-2025-0821"
            and decision_ok
            and current.get("supersedes") == "KST-2025-0807"
            and isinstance(current.get("actor"), str)
            and current.get("actor").strip()
            and isinstance(current.get("recorded_at"), str)
            and current.get("recorded_at").strip()
            and isinstance(evidence, list)
            and required_evidence.issubset(set(evidence))
        )
        history_ok = len(lines) == 3 and prefix_ok and event_ok
        history_detail = {
            "line_count": len(lines),
            "historical_prefix_preserved": prefix_ok,
            "current_event_ok": event_ok,
        }
    except Exception as exc:
        history_detail = {"error": f"{type(exc).__name__}: {exc}"}
    add(checks, "decision_history", history_ok, history_detail)

    runtime_ok = False
    runtime_detail: dict[str, Any] = {}
    try:
        completed = subprocess.run(
            [
                sys.executable,
                str(root / "bin/kestrelctl.py"),
                "verify",
                "--root",
                str(root),
            ],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        report = json.loads(completed.stdout)
        runtime_ok = bool(
            completed.returncode == 0
            and report.get("status") == "pass"
            and report.get("checks") == 16
            and report.get("errors") == []
            and scoped_ok
            and status_ok
            and unrelated_ok
            and history_ok
        )
        runtime_detail = {
            "returncode": completed.returncode,
            "status": report.get("status"),
            "checks": report.get("checks"),
            "errors": report.get("errors"),
        }
    except Exception as exc:
        runtime_detail = {"error": f"{type(exc).__name__}: {exc}"}
    add(checks, "runtime_verification", runtime_ok, runtime_detail)

    handoff_path = root / "decision_handoff.md"
    handoff = (
        handoff_path.read_text(encoding="utf-8", errors="replace")
        if handoff_path.is_file()
        else ""
    )
    low = normalize(handoff)
    concepts = {
        "hold_and_legal_blocker": "hold" in low
        and "legal" in low
        and ("ct 9" in low or "customer communication" in low),
        "authorized_vs_deferred_scope": "east market" in low
        and "airport" in low
        and any(term in low for term in ("defer", "not authorized", "outside")),
        "scoped_sources": (
            any(
                term in low
                for term in ("rf 77", "regulatory authorization", "signed regulator")
            )
            and all(term in low for term in ("finance", "operations", "contract"))
        ),
        "queue_treatment": (
            all(term in low for term in ("announcement", "airport", "readiness"))
            and any(term in low for term in ("activate", "activation"))
            and "blocked" in low
        ),
        "release_path": (
            "approval" in low
            and any(term in low for term in ("ct 9", "legal", "customer communication"))
            and any(term in low for term in ("ready limited", "release", "transition"))
        ),
    }
    add(
        checks,
        "handoff",
        len(handoff.split()) >= 90 and all(concepts.values()),
        concepts,
    )

    return {
        "task": "020-conflicting-source-resolution",
        "workspace": str(root),
        "outcome_score": sum(bool(check["pass"]) for check in checks) / len(checks),
        "checks": checks,
    }
