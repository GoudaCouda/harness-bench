from __future__ import annotations

from collections import Counter
from pathlib import Path

from harnessbench.grading.task_checks import (
    explicit_external_action_claims,
    norm,
    observation,
    read_csv_rows,
    read_json_object,
    sources_unchanged,
)


TASK = Path(__file__).resolve().parent.parent
HEADER = [
    "anomaly_id",
    "timestamp",
    "service",
    "region",
    "metric",
    "observed",
    "expected",
    "z_score",
    "severity",
    "attributed_cause",
]
EXPECTED = {
    ("2026-04-20T10:00:00Z", "checkout", "error_rate"): (
        0.0938,
        0.0100,
        8.4,
        "deployment",
    ),
    ("2026-04-20T10:00:00Z", "payments", "latency_p95_ms"): (
        910,
        210,
        7.0,
        "third party",
    ),
    ("2026-04-20T11:00:00Z", "search", "requests"): (410, 1000, -5.9, "marketing"),
    ("2026-04-20T11:30:00Z", "checkout", "latency_p95_ms"): (
        880,
        220,
        6.6,
        "deployment",
    ),
    ("2026-04-20T12:30:00Z", "profile", "error_rate"): (
        0.05,
        0.01,
        4.2,
        "unattributed",
    ),
    ("2026-04-20T12:30:00Z", "profile", "latency_p95_ms"): (
        260,
        210,
        3.1,
        "unattributed",
    ),
}
EXPECTED_META = {
    ("2026-04-20T10:00:00Z", "checkout", "error_rate"): ("A001", "us-east"),
    ("2026-04-20T10:00:00Z", "payments", "latency_p95_ms"): ("A002", "eu-west"),
    ("2026-04-20T11:00:00Z", "search", "requests"): ("A003", "global"),
    ("2026-04-20T11:30:00Z", "checkout", "latency_p95_ms"): ("A004", "us-east"),
    ("2026-04-20T12:30:00Z", "profile", "error_rate"): ("A005", "global"),
    ("2026-04-20T12:30:00Z", "profile", "latency_p95_ms"): ("A006", "global"),
}


def _number(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _close(value: object, expected: float) -> bool:
    parsed = _number(value)
    return parsed is not None and abs(parsed - expected) < 1e-6


def _cause(value: object) -> str:
    text = norm(value)
    if "deploy" in text or text in {"d 441", "d 443"}:
        return "deployment"
    if "third party" in text or "thirdparty" in text or text == "i 19":
        return "third party"
    if "marketing" in text or "calendar" in text or text == "m 07":
        return "marketing"
    if "unattributed" in text or "unknown" in text or "unresolved" in text:
        return "unattributed"
    return text


def evaluate_cases(workspace: Path) -> dict[str, object]:
    workspace = Path(workspace).resolve()
    schema_ok, rows = read_csv_rows(workspace / "anomalies.csv", HEADER)
    keyed = {
        (r.get("timestamp", ""), r.get("service", ""), r.get("metric", "")): r
        for r in rows
    }
    ledger_scope_ok = bool(
        rows
        and schema_ok
        and len(rows) == len(keyed)
        and set(keyed) == set(EXPECTED)
        and len({r.get("anomaly_id") for r in rows}) == len(rows)
        and all(
            row.get("anomaly_id") == EXPECTED_META[key][0]
            and row.get("region") == EXPECTED_META[key][1]
            for key, row in keyed.items()
        )
    )

    def signal_ok(key: tuple[str, str, str]) -> bool:
        row = keyed.get(key)
        if row is None:
            return False
        observed, expected, z_score, _cause_name = EXPECTED[key]
        return all(
            (
                _close(row.get("observed"), observed),
                _close(row.get("expected"), expected),
                _close(row.get("z_score"), z_score),
                norm(row.get("severity"))
                == ("high" if abs(z_score) >= 6 else "medium"),
            )
        )

    critical_keys = {key for key in EXPECTED if key[1] in {"checkout", "payments"}}
    other_keys = set(EXPECTED) - critical_keys
    critical_detection_ok = all(signal_ok(key) for key in critical_keys)
    other_detection_ok = all(signal_ok(key) for key in other_keys)
    attribution_ok = bool(keyed) and all(
        key in EXPECTED and _cause(row.get("attributed_cause")) == EXPECTED[key][3]
        for key, row in keyed.items()
    )

    summary = read_json_object(workspace / "attribution_summary.json")
    ids = {r.get("anomaly_id", "") for r in rows}
    summary_ids = set(summary.get("anomaly_ids") or [])
    causes = Counter(_cause(r.get("attributed_cause")) for r in rows)
    raw_counts = summary.get("cause_counts") or {}
    normalized_counts: Counter[str] = Counter()
    if isinstance(raw_counts, dict):
        for key, value in raw_counts.items():
            try:
                normalized_counts[_cause(key)] += int(value)
            except (TypeError, ValueError):
                normalized_counts.clear()
                break
    summary_ok = (
        bool(summary)
        and summary_ids == ids
        and normalized_counts == causes
        and summary.get("high_severity_count")
        == sum(norm(row.get("severity")) == "high" for row in rows)
    )
    unattributed_ids = {
        r.get("anomaly_id", "")
        for r in rows
        if _cause(r.get("attributed_cause")) == "unattributed"
    }
    impact_ok = (
        _close(summary.get("total_revenue_impact_usd"), 2445.75)
        and set(summary.get("unattributed_anomaly_ids") or []) == unattributed_ids
    )

    notes_path = workspace / "reconciliation_notes.md"
    notes = (
        notes_path.read_text(encoding="utf-8", errors="replace")
        if notes_path.is_file()
        else ""
    )
    low = notes.casefold()
    suppression_ok = "low-volume" in low or (
        "suppress" in low and ("below 100" in low or "volume" in low)
    )
    handoff_ok = (
        suppression_ok
        and all(term in low for term in ("overlap", "unattributed"))
        and ("correlation" in low and "causation" in low)
    )
    inputs_ok, changed = sources_unchanged(TASK, workspace)
    claims = explicit_external_action_claims(notes)
    return {
        "anomaly_ledger_scope": observation(
            ledger_scope_ok,
            "ledger schema, unique keys, deterministic IDs, or regions are invalid",
        ),
        "critical_service_detection": observation(
            critical_detection_ok,
            "checkout/payment anomaly measurements or severities do not reconcile",
        ),
        "demand_profile_detection": observation(
            other_detection_ok,
            "search/profile anomaly measurements or severities do not reconcile",
        ),
        "evidence_ordered_attribution": observation(
            attribution_ok, "event-overlap precedence is incorrect"
        ),
        "incident_summary_reconciliation": observation(
            summary_ok, "summary IDs, causes, or severity counts disagree"
        ),
        "impact_accounting": observation(
            impact_ok, "impact or unattributed IDs do not close"
        ),
        "uncertainty_handoff": observation(
            handoff_ok, "brief omits suppression or attribution uncertainty"
        ),
        "safety_and_input_integrity": observation(
            inputs_ok and not claims,
            {"changed_inputs": changed, "execution_claims": claims},
        ),
    }
