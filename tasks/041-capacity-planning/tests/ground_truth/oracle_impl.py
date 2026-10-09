from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path
from typing import Any

_TASK_DIR = Path(__file__).resolve().parents[2]
_GT = json.loads(
    (_TASK_DIR / "tests" / "ground_truth" / "ground_truth.json").read_text(
        encoding="utf-8"
    )
)


def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _close(value: Any, expected: float, tolerance: float = 0.001) -> bool:
    parsed = _num(value)
    return parsed is not None and abs(parsed - expected) <= tolerance


def _unchanged(workspace: Path) -> bool:
    original_root = _TASK_DIR / "workspace"
    return all(
        (workspace / path.relative_to(original_root)).is_file()
        and (workspace / path.relative_to(original_root)).read_bytes()
        == path.read_bytes()
        for path in original_root.rglob("*")
        if path.is_file()
    )


def _zones_ok(value: Any, min_zones: int, count: int) -> bool:
    if not isinstance(value, dict) or set(value) != {
        f"zone-{chr(97 + i)}" for i in range(min_zones)
    }:
        return False
    counts = list(value.values())
    return (
        all(
            isinstance(item, int) and not isinstance(item, bool) and item >= 1
            for item in counts
        )
        and sum(counts) == count
        and max(counts) - min(counts) <= 1
    )


def _concept(text: str, *alternatives: str) -> bool:
    return any(term in text for term in alternatives)


def _number_mentioned(text: str, value: float) -> bool:
    """Accept ordinary comma/currency/zero-padding presentation variants."""
    compact = text.replace(",", "")
    for match in re.finditer(r"(?<![\w.])-?\d+(?:\.\d+)?", compact):
        try:
            if abs(float(match.group()) - value) <= 0.001:
                return True
        except ValueError:
            continue
    return False


def _affirmative_cost_equivalence(text: str) -> bool:
    low = " ".join(text.casefold().split())
    patterns = (
        r"\b(?:same|equal|identical)\s+cost\b",
        r"\bcosts?\s+(?:is|are|was|were)\s+(?:the\s+)?"
        r"(?:same|equal|identical)\b",
        r"\bcosts?\s+the\s+(?:same|equal|identical)\b",
        r"\b(?:equally|identically)\s+priced\b",
        r"\bcost\s+tie\b",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, low):
            prefix = low[max(0, match.start() - 28) : match.start()]
            if not re.search(r"\b(?:not|never|no)\b[^.!?;]{0,20}$", prefix):
                return True
    numeric_tie = re.compile(
        r"\b(?:(?:would|does|did|will|can|could)\s+)?also\s+"
        r"(?:cost(?:s|ed)?|be\s+priced(?:\s+at)?)\s+"
        r"(?:usd\s*)?\$?\s*0*\.4560*\b"
    )
    for match in numeric_tie.finditer(low):
        prefix = low[max(0, match.start() - 40) : match.start()]
        if re.search(r"\bnot\s+only\b[^.!?;]{0,24}$", prefix):
            return True
        if not re.search(
            r"\b(?:not|never|no|without)\b(?:\W+\w+){0,4}\W*$",
            prefix,
        ):
            return True
    return False


def _compatibility_rejection_present(rows: list[dict[str, str]]) -> bool:
    for row in rows:
        text = " ".join(str(value).casefold() for value in row.values())
        mitigation = str(row.get("mitigation") or "").casefold()
        compatibility = "incompatib" in text or "compatibility flag" in text
        rejected = any(
            term in text
            for term in (
                "reject",
                "not approved",
                "exclude",
                "unsupported",
                "compatible=false",
            )
        )
        approved_only_mitigation = (
            "approved" in mitigation
            and "instance" in mitigation
            and any(
                term in mitigation
                for term in ("adhere", "adherence", "only", "restrict", "limit")
            )
        )
        if compatibility and (rejected or approved_only_mitigation):
            return True
    return False


def score_workspace(workspace: Path) -> dict[str, Any]:
    w = Path(workspace).resolve()
    weights = _GT["scoring"]["weights"]
    checks: list[dict[str, Any]] = []

    def add(cid: str, ok: bool, weight: float, detail: Any = None) -> None:
        checks.append({"id": cid, "pass": bool(ok), "weight": weight, "detail": detail})

    plan_score = 0.0
    critical_plan_ok = False
    forecast_requirements_ok = False
    capacity_selection_ok = False
    plan_costs_ok = False
    assumptions_ok = False
    plan_package_ok = False
    plan_services: set[str] = set()
    plan_total: float | None = None
    plan_path = w / "capacity_plan.json"
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        entries = plan.get("services")
        by_service = (
            {
                row.get("service"): row
                for row in entries
                if isinstance(row, dict) and isinstance(row.get("service"), str)
            }
            if isinstance(entries, list)
            else {}
        )
        checkout = by_service.get("checkout-api", {})
        pricing = by_service.get("pricing-worker", {})
        plan_services = set(by_service)
        plan_total = _num(plan.get("total_hourly_cost_usd"))
        checkout_count = checkout.get("on_demand_count")
        pricing_count = (pricing.get("on_demand_count"), pricing.get("spot_count"))
        assertions = [
            set(by_service) == {"checkout-api", "pricing-worker"} and len(entries) == 2,
            checkout.get("region") == "us-east" and checkout.get("min_zones") == 2,
            _zones_ok(checkout.get("zone_counts"), 2, 3),
            _close(checkout.get("forecast_peak_rps"), 2391.2),
            _close(checkout.get("required_headroom_pct"), 0.30),
            _close(checkout.get("required_capacity_rps"), 3108.56),
            checkout.get("selected_instance_type") == "c7g.xlarge",
            checkout_count == 3 and checkout.get("spot_count") == 0,
            _close(checkout.get("provided_capacity_rps"), 3660),
            _close(checkout.get("hourly_cost_usd"), 0.456),
            _close(checkout.get("slo_headroom_rps"), 551.44),
            pricing.get("region") == "us-east" and pricing.get("min_zones") == 1,
            _zones_ok(pricing.get("zone_counts"), 1, 1),
            _close(pricing.get("forecast_peak_rps"), 575),
            _close(pricing.get("required_headroom_pct"), 0.20),
            _close(pricing.get("required_capacity_rps"), 690),
            pricing.get("selected_instance_type") == "m7i.large",
            pricing_count == (1, 0),
            _close(pricing.get("provided_capacity_rps"), 700),
            _close(pricing.get("hourly_cost_usd"), 0.096),
            _close(pricing.get("slo_headroom_rps"), 10),
            _close(plan.get("total_hourly_cost_usd"), 0.552),
            isinstance(plan.get("assumptions"), (dict, list, str))
            and bool(plan.get("assumptions")),
        ]
        critical_plan_ok = all(
            [
                set(by_service) == {"checkout-api", "pricing-worker"}
                and len(entries) == 2,
                checkout.get("selected_instance_type") == "c7g.xlarge",
                checkout_count == 3 and checkout.get("spot_count") == 0,
                _zones_ok(checkout.get("zone_counts"), 2, 3),
                _close(checkout.get("required_capacity_rps"), 3108.56),
                _close(checkout.get("provided_capacity_rps"), 3660),
                _close(checkout.get("hourly_cost_usd"), 0.456),
                pricing.get("selected_instance_type") == "m7i.large",
                pricing_count == (1, 0),
                _zones_ok(pricing.get("zone_counts"), 1, 1),
                _close(pricing.get("required_capacity_rps"), 690),
                _close(pricing.get("provided_capacity_rps"), 700),
                _close(pricing.get("hourly_cost_usd"), 0.096),
                _close(plan.get("total_hourly_cost_usd"), 0.552),
            ]
        )
        forecast_requirements_ok = all(
            [
                set(by_service) == {"checkout-api", "pricing-worker"}
                and len(entries) == 2,
                checkout.get("region") == "us-east" and checkout.get("min_zones") == 2,
                _close(checkout.get("forecast_peak_rps"), 2391.2),
                _close(checkout.get("required_headroom_pct"), 0.30),
                _close(checkout.get("required_capacity_rps"), 3108.56),
                pricing.get("region") == "us-east" and pricing.get("min_zones") == 1,
                _close(pricing.get("forecast_peak_rps"), 575),
                _close(pricing.get("required_headroom_pct"), 0.20),
                _close(pricing.get("required_capacity_rps"), 690),
            ]
        )
        capacity_selection_ok = all(
            [
                checkout.get("selected_instance_type") == "c7g.xlarge",
                checkout_count == 3 and checkout.get("spot_count") == 0,
                _zones_ok(checkout.get("zone_counts"), 2, 3),
                _close(checkout.get("provided_capacity_rps"), 3660),
                _close(checkout.get("slo_headroom_rps"), 551.44),
                pricing.get("selected_instance_type") == "m7i.large",
                pricing_count == (1, 0),
                _zones_ok(pricing.get("zone_counts"), 1, 1),
                _close(pricing.get("provided_capacity_rps"), 700),
                _close(pricing.get("slo_headroom_rps"), 10),
            ]
        )
        plan_costs_ok = all(
            [
                _close(checkout.get("hourly_cost_usd"), 0.456),
                _close(pricing.get("hourly_cost_usd"), 0.096),
                _close(plan.get("total_hourly_cost_usd"), 0.552),
            ]
        )
        assumptions_ok = bool(
            isinstance(plan.get("assumptions"), (dict, list, str))
            and plan.get("assumptions")
        )
        plan_package_ok = bool(
            plan_services == {"checkout-api", "pricing-worker"}
            and plan_total is not None
            and _close(
                plan_total,
                sum(
                    _num(row.get("hourly_cost_usd")) or 0.0
                    for row in by_service.values()
                ),
            )
        )
        plan_score = sum(assertions) / len(assertions)
        add(
            "capacity_plan",
            plan_score >= 0.95 and critical_plan_ok,
            weights["capacity_plan"],
            {"score": round(plan_score, 4), "critical_plan_ok": critical_plan_ok},
        )
    except Exception as exc:
        add("capacity_plan", False, weights["capacity_plan"], str(exc))
    add(
        "forecast_requirements",
        forecast_requirements_ok,
        0.0,
        "service forecast, headroom, region, or redundancy requirement differs",
    )
    add(
        "capacity_selection",
        capacity_selection_ok,
        0.0,
        "selected instance plan is not the required lowest-cost feasible plan",
    )

    notes_score = 0.0
    cost_accounting_ok = False
    notes_package_ok = False
    notes_path = w / "cost_notes.md"
    if notes_path.is_file():
        text = notes_path.read_text(encoding="utf-8", errors="replace").lower()
        notes_package_ok = bool(
            all(service in text for service in ("checkout-api", "pricing-worker"))
        )
        service_coverage = (
            sum(name in text for name in ("checkout-api", "pricing-worker")) / 2
        )
        calculation_coverage = (
            sum(
                (
                    _concept(
                        text,
                        "latest seven",
                        "most recent seven",
                        "recent 7",
                        "last seven",
                        "last 7",
                    ),
                    _concept(text, "maximum", "max ", "peak"),
                    _concept(text, "multiplier", "multiply", "×", "1.22", "1.15"),
                    _concept(text, "headroom", "capacity margin", "reserve margin"),
                )
            )
            / 4
        )
        selection_coverage = (
            sum(
                (
                    _concept(text, "c7g.xlarge", "three on-demand", "3 on-demand"),
                    _concept(text, "m7i.large", "one on-demand", "1 on-demand"),
                    _number_mentioned(text, 0.456),
                    _number_mentioned(text, 0.096),
                )
            )
            / 4
        )
        governance_coverage = (
            sum(
                (
                    _concept(text, "budget", "cost limit", "spending limit"),
                    _concept(
                        text,
                        "reject",
                        "alternative",
                        "instead",
                        "would cost",
                        "not selected",
                    ),
                    _affirmative_cost_equivalence(text),
                )
            )
            / 3
        )
        notes_score = (
            0.20 * service_coverage
            + 0.30 * calculation_coverage
            + 0.30 * selection_coverage
            + 0.20 * governance_coverage
        )
        cost_accounting_ok = bool(
            plan_costs_ok
            and assumptions_ok
            and all(service in text for service in ("checkout-api", "pricing-worker"))
            and all(
                _number_mentioned(text, value)
                for value in (
                    1960,
                    1.22,
                    2391.2,
                    3108.56,
                    0.456,
                    500,
                    1.15,
                    575,
                    690,
                    0.096,
                )
            )
            and _concept(text, "headroom", "capacity margin", "reserve margin")
            and _concept(text, "budget", "cost limit", "spending limit")
            and _concept(
                text,
                "reject",
                "alternative",
                "instead",
                "would cost",
                "not selected",
            )
        )
    add(
        "cost_notes",
        notes_score >= 0.85,
        weights["cost_notes"],
        {"score": round(notes_score, 4)},
    )
    add(
        "cost_accounting_complete",
        cost_accounting_ok,
        0.0,
        "plan costs, assumptions, or required cost explanation is incomplete",
    )

    risk_score = 0.0
    risk_package_ok = False
    risk_path = w / _GT["risk_tradeoffs_path"]
    try:
        with risk_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
        header_ok = reader.fieldnames == ["service", "tradeoff", "risk", "mitigation"]
        row_ok = all(
            all(str(row.get(field, "")).strip() for field in reader.fieldnames or [])
            for row in rows
        )
        text = json.dumps(rows, ensure_ascii=False).lower()
        coverage_hits = sum(
            (
                _compatibility_rejection_present(rows)
                if term == "incompatible"
                else term in text
            )
            for term in _GT["risk_terms"]
        )
        coverage = coverage_hits / len(_GT["risk_terms"])
        risk_score = (
            0.25 * header_ok + 0.25 * (len(rows) >= 4 and row_ok) + 0.50 * coverage
        )
        risk_package_ok = bool(
            header_ok
            and row_ok
            and {row.get("service") for row in rows}
            >= {"checkout-api", "pricing-worker"}
        )
    except Exception:
        risk_score = 0.0
    add(
        "risk_tradeoffs",
        risk_score >= 0.95,
        weights["risk_tradeoffs"],
        {"score": round(risk_score, 4)},
    )

    planning_handoff = bool(plan_package_ok and notes_package_ok and risk_package_ok)
    add(
        "planning_handoff",
        planning_handoff,
        weights["planning_handoff"],
        {
            "plan_cost_reconciles": plan_package_ok,
            "notes_cover_services_and_total": notes_package_ok,
            "risk_table_covers_services": risk_package_ok,
        },
    )

    unchanged = _unchanged(w)
    add("source_unchanged", unchanged, 0.0)
    case_results = {
        "capacity_plan": plan_score >= 0.95 and critical_plan_ok,
        "cost_notes": notes_score >= 0.85,
        "risk_tradeoffs": risk_score >= 0.95,
        "planning_handoff": planning_handoff,
    }
    total = sum(weights[case_id] for case_id, passed in case_results.items() if passed)
    if not unchanged:
        total = 0.0
    thresholds = _GT["scoring"]["thresholds"]
    level = (
        "excellent"
        if total >= thresholds["excellent"]
        else "good"
        if total >= thresholds["good"]
        else "pass"
        if total >= thresholds["pass"]
        else "fail"
    )
    return {
        "task": "041-capacity-planning",
        "workspace": str(w),
        "outcome_score": round(total, 4),
        "level": level,
        "checks": checks,
    }
