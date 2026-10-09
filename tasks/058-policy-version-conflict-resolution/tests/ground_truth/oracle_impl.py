from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

TASK_DIR = Path(__file__).resolve().parents[2]


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _contains_all(text: str, tokens: list[str]) -> bool:
    return all(_evidence_concept(text, token) for token in tokens)


def _expiry_is_contradicted(text: str) -> bool:
    low = " ".join(_norm(text).replace("_", " ").replace("-", " ").split())
    return bool(
        re.search(
            r"\b(?:no|without)\s+(?:applicable\s+)?(?:expiry|expiration)\b"
            r"|\b(?:not|never)\s+(?:yet\s+)?expired\b"
            r"|\b(?:does|did|will|would|has|have|is|was)\s+not\s+expir\w*\b"
            r"|\b(?:expiry|expiration)\s+(?:does|did|will|would)\s+not\b"
            r"|\b(?:remains?|still)\s+(?:effective|in\s+force|valid)\b",
            low,
        )
    )


def _expiry_concept(text: str) -> bool:
    low = " ".join(_norm(text).replace("_", " ").replace("-", " ").split())
    if _expiry_is_contradicted(low):
        return False
    return any(
        term in low
        for term in (
            "expired",
            "expires",
            "expiry",
            "expiration",
            "no longer effective",
            "not effective",
            "ended",
            "outside the effective",
        )
    )


def _evidence_concept(text: str, token: str) -> bool:
    low = " ".join(_norm(text).replace("_", " ").replace("-", " ").split())
    key = " ".join(_norm(token).replace("_", " ").replace("-", " ").split())
    if key == "expired":
        return _expiry_concept(low)
    alternatives = {
        "above": ("above", "over", "exceed", "more than", "greater than"),
        "pre approval": (
            "pre approval",
            "prior approval",
            "approved in advance",
            "advance approval",
        ),
        "missing": (
            "missing",
            "not provided",
            "not supplied",
            "unavailable",
            "absent",
            "insufficient",
        ),
        "threshold": (
            "threshold",
            "limit",
            "amount",
            "gift schedule",
            "policy fact",
        ),
    }
    return any(term in low for term in alternatives.get(key, (key,)))


def _source_equivalent(actual: Any, expected: str) -> bool:
    got = str(actual or "").strip().replace("\\", "/").lower()
    want = expected.replace("\\", "/").lower()
    return (
        got == want
        or got.endswith("/" + want)
        or (got.rsplit("/", 1)[-1] == want.rsplit("/", 1)[-1])
    )


def _scope_concept(text: str, token: str) -> bool:
    low = " ".join(_norm(text).replace("_", " ").replace("-", " ").split())
    key = " ".join(_norm(token).replace("_", " ").replace("-", " ").split())
    if key == "expired":
        return _expiry_concept(low)
    alternatives = {
        "global": ("global", "company wide", "default policy", "general policy"),
        "meal": ("meal", "dinner", "food"),
        "window": ("window", "period", "date range", "effective date"),
        "remote engineering": (
            "remote engineering",
            "remote engineer",
            "engineering staff",
        ),
        "not apply": (
            "not apply",
            "inapplicable",
            "not covered",
            "outside scope",
            "doesn't apply",
            "does not apply",
        ),
        "pre approval": ("pre approval", "prior approval", "approved in advance"),
        "then": ("then", "at that time", "effective at", "in force"),
        "france": ("france", "french"),
        "not change": (
            "not change",
            "does not override",
            "remains governed",
            "still applies",
        ),
        "missing": (
            "missing",
            "not provided",
            "not supplied",
            "unavailable",
            "absent",
            "insufficient",
        ),
        "threshold": (
            "threshold",
            "limit",
            "amount",
            "gift schedule",
            "policy fact",
        ),
    }
    return any(term in low for term in alternatives.get(key, (key,)))


def _scope_fraction(text: str, tokens: list[str]) -> float:
    return (
        sum(_scope_concept(text, token) for token in tokens) / len(tokens)
        if tokens
        else 1.0
    )


def _priority_kind_matches(value: Any, expected: str) -> bool:
    text = " ".join(_norm(value).replace("_", " ").replace("-", " ").split())
    alternatives = {
        "version": (
            "version",
            "newer",
            "latest",
            "more recent",
            "effective date",
        ),
        "scope": (
            "scope",
            "scoped",
            "exception",
            "coverage",
            "priority order",
        ),
        "effective_date": (
            "effective date",
            "effective",
            "in force",
            "expiry",
            "expiration",
            "window",
        ),
    }
    return any(term in text for term in alternatives[expected])


def _check(
    cid: str,
    label: str,
    score: float,
    threshold: float,
    weight: float,
    detail: Any = None,
) -> dict[str, Any]:
    return {
        "id": cid,
        "label": label,
        "pass": score >= threshold,
        "weight": weight,
        "detail": detail,
    }


def score_workspace(workspace: Path) -> dict[str, Any]:
    w = Path(workspace).resolve()
    gt = json.loads(
        (TASK_DIR / "tests" / "ground_truth" / "ground_truth.json").read_text(
            encoding="utf-8"
        )
    )
    rulings_path = w / "policy_rulings.json"
    audit_path = w / "conflict_audit.csv"
    checks: list[dict[str, Any]] = []

    # A conflict is one cross-artifact business fact. Authors may keep the
    # complete losing-source trace in the dedicated audit ledger rather than
    # duplicate it in every JSON ruling.
    audit_by_case: dict[str, dict[str, str]] = {}
    try:
        with audit_path.open("r", encoding="utf-8", newline="") as fh:
            audit_by_case = {
                str(row.get("case_id", "")).strip(): row
                for row in csv.DictReader(fh)
                if isinstance(row, dict)
            }
    except Exception:
        audit_by_case = {}

    if not rulings_path.is_file():
        return {
            "task": "058-policy-version-conflict-resolution",
            "workspace": str(w),
            "outcome_score": 0.0,
            "level": "fail",
            "checks": [
                {
                    "id": "missing",
                    "pass": False,
                    "weight": 1.0,
                    "detail": "policy_rulings.json missing",
                }
            ],
        }

    format_score = coverage_score = decision_score = source_score = evidence_score = (
        conflict_score
    ) = scope_score = insuff_score = forbidden_score = audit_score = 0.0
    try:
        data = json.loads(rulings_path.read_text(encoding="utf-8"))
        rows = data if isinstance(data, list) else []
        required = {
            "case_id",
            "decision",
            "applicable_policy",
            "evidence_id",
            "quote_or_signal",
            "conflict_resolution",
            "coverage_scope",
            "caveat",
        }
        format_score = (
            1.0
            if isinstance(rows, list)
            and all(isinstance(r, dict) and required.issubset(r) for r in rows)
            else 0.0
        )
        by_id = {
            str(r.get("case_id", "")).strip(): r for r in rows if isinstance(r, dict)
        }
        expected_ids = set(gt["rulings"])
        coverage_score = len(set(by_id) & expected_ids) / len(expected_ids)
        if len(rows) == len(by_id) == len(expected_ids) and set(by_id) == expected_ids:
            coverage_score = 1.0
        elif set(by_id) == expected_ids:
            coverage_score = 0.0

        decision_hits = source_hits = evidence_hits = conflict_hits = scope_hits = (
            insuff_hits
        ) = forbidden_hits = 0
        for cid, exp in gt["rulings"].items():
            row = by_id.get(cid, {})
            decision = _norm(row.get("decision"))
            if decision == exp["decision"]:
                decision_hits += 1
            source = str(row.get("applicable_policy") or "").strip()
            if _source_equivalent(source, exp["source"]):
                source_hits += 1
            evidence_text = " ".join(
                [
                    str(row.get("evidence_id", "")),
                    str(row.get("quote_or_signal", "")),
                    str(row.get("coverage_scope", "")),
                    str(row.get("caveat", "")),
                    str(
                        row.get("conflict_resolution", {}).get("reason", "")
                        if isinstance(row.get("conflict_resolution"), dict)
                        else ""
                    ),
                ]
            )
            if _contains_all(evidence_text, exp["evidence_tokens"]):
                evidence_hits += 1
            cr = (
                row.get("conflict_resolution")
                if isinstance(row.get("conflict_resolution"), dict)
                else {}
            )
            superseded = (
                [str(x).strip() for x in cr.get("superseded_sources", [])]
                if isinstance(cr.get("superseded_sources", []), list)
                else []
            )
            conflict_text = " ".join(
                superseded
                + [
                    str(cr.get("reason", "")),
                    str(row.get("coverage_scope", "")),
                    str(row.get("caveat", "")),
                    str(audit_by_case.get(cid, {}).get("losing_sources", "")),
                ]
            )
            if all(
                any(_source_equivalent(item, src) for item in superseded)
                or src.rsplit("/", 1)[-1].casefold()
                in str(audit_by_case.get(cid, {}).get("losing_sources", "")).casefold()
                or (
                    src.rsplit("/", 1)[-1].lower() in conflict_text.lower()
                    and any(
                        (
                            _expiry_concept(conflict_text),
                            "inapplicable" in conflict_text.lower(),
                            "outside scope" in conflict_text.lower(),
                            "not apply" in conflict_text.lower(),
                            "supersed" in conflict_text.lower(),
                            "older" in conflict_text.lower(),
                        )
                    )
                )
                for src in exp["superseded"]
            ):
                conflict_hits += 1
            scope_text = f"{row.get('coverage_scope', '')} {cr.get('reason', '')} {row.get('caveat', '')}"
            expiry_contradiction = "expired" in exp[
                "scope_tokens"
            ] and _expiry_is_contradicted(scope_text)
            if (
                not expiry_contradiction
                and _scope_fraction(scope_text, exp["scope_tokens"]) >= 0.5
            ):
                scope_hits += 1
            if exp["decision"] == "insufficient_evidence":
                insuff_text = scope_text + " " + evidence_text
                if (
                    decision == "insufficient_evidence"
                    and not source
                    and _evidence_concept(insuff_text, "missing")
                    and _evidence_concept(insuff_text, "gift")
                    and _evidence_concept(insuff_text, "schedule")
                ):
                    insuff_hits += 1
            else:
                insuff_hits += 1
            forbidden = gt.get("forbidden_final_tokens", {}).get(cid, [])
            final_text = json.dumps(
                {
                    "decision": row.get("decision"),
                    "applicable_policy": row.get("applicable_policy"),
                    "quote_or_signal": row.get("quote_or_signal"),
                },
                ensure_ascii=False,
            ).lower()
            if not any(tok.lower() in final_text for tok in forbidden):
                forbidden_hits += 1

        n = len(expected_ids)
        decision_score = decision_hits / n
        source_score = source_hits / n
        evidence_score = evidence_hits / n
        conflict_score = conflict_hits / n
        scope_score = scope_hits / n
        insuff_score = insuff_hits / n
        forbidden_score = forbidden_hits / n
        checks.extend(
            [
                _check(
                    "format",
                    "policy_rulings.json has required schema",
                    format_score,
                    1.0,
                    0.10,
                    {"rows": len(by_id)},
                ),
                _check(
                    "coverage",
                    "all and only expected cases are covered",
                    coverage_score,
                    1.0,
                    0.10,
                    sorted(by_id),
                ),
                _check(
                    "decisions",
                    "case decisions match policy/version rules",
                    decision_score,
                    0.88,
                    0.22,
                    {"hits": decision_hits, "total": n},
                ),
                _check(
                    "sources",
                    "applicable_policy cites governing source",
                    source_score,
                    0.88,
                    0.14,
                    {"hits": source_hits},
                ),
                _check(
                    "evidence",
                    "evidence signals include clause-specific tokens",
                    evidence_score,
                    0.80,
                    0.14,
                    {"hits": evidence_hits},
                ),
                _check(
                    "conflicts",
                    "superseded conflicting sources are recorded",
                    conflict_score,
                    0.75,
                    0.12,
                    {"hits": conflict_hits},
                ),
                _check(
                    "scope",
                    "coverage_scope preserves scoped exceptions and expiry",
                    scope_score,
                    0.75,
                    0.10,
                    {"hits": scope_hits},
                ),
                _check(
                    "insufficient",
                    "insufficient evidence case is not fabricated",
                    insuff_score,
                    1.0,
                    0.08,
                    {"hits": insuff_hits},
                ),
                _check(
                    "forbidden",
                    "stale or contradicted final outcomes are absent",
                    forbidden_score,
                    1.0,
                    0.05,
                    {"hits": forbidden_hits},
                ),
            ]
        )
    except Exception as exc:
        checks.append(
            {
                "id": "parse",
                "label": "policy_rulings.json parseable",
                "pass": False,
                "weight": 0.95,
                "detail": str(exc),
            }
        )

    try:
        with audit_path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
        expected_header = [
            "case_id",
            "claim_axis",
            "winning_source",
            "losing_sources",
            "priority_rule",
            "coverage_scope",
        ]
        cols_ok = reader.fieldnames == expected_header
        audit_format_ok = bool(
            cols_ok
            and rows
            and all(
                all(str(row.get(column, "")).strip() for column in expected_header)
                for row in rows
            )
        )
        checks.append(
            _check(
                "audit_format",
                "conflict_audit.csv has the requested usable schema",
                float(audit_format_ok),
                1.0,
                0.0,
                {"rows": len(rows), "header": reader.fieldnames},
            )
        )

        by_case = {
            str(row.get("case_id", "")).strip(): row
            for row in rows
            if isinstance(row, dict)
        }
        exact_cases = bool(
            len(rows) == len(by_case) == len(gt["conflict_cases"])
            and set(by_case) == set(gt["conflict_cases"])
        )
        source_hits = losing_hits = priority_hits = scope_hits = 0
        for case_id in gt["conflict_cases"]:
            row = by_case.get(case_id, {})
            expected = gt["rulings"][case_id]
            if _source_equivalent(row.get("winning_source"), expected["source"]):
                source_hits += 1
            losing_text = str(row.get("losing_sources", ""))
            if all(
                source.rsplit("/", 1)[-1].casefold() in losing_text.casefold()
                for source in expected["superseded"]
            ):
                losing_hits += 1
            if _priority_kind_matches(
                row.get("priority_rule"), gt["audit_priority_kinds"][case_id]
            ):
                priority_hits += 1
            if str(row.get("coverage_scope", "")).strip():
                scope_hits += 1

        count = len(gt["conflict_cases"])
        audit_score = (
            0.20 * audit_format_ok
            + 0.20 * exact_cases
            + 0.20 * (source_hits / count)
            + 0.20 * (losing_hits / count)
            + 0.10 * (priority_hits / count)
            + 0.10 * (scope_hits / count)
        )
        checks.append(
            _check(
                "conflict_audit",
                "conflict_audit.csv covers conflict cases and priority rules",
                audit_score,
                1.0,
                0.05,
                {
                    "score": round(audit_score, 4),
                    "exact_cases": exact_cases,
                    "source_hits": source_hits,
                    "losing_hits": losing_hits,
                    "priority_hits": priority_hits,
                    "scope_hits": scope_hits,
                },
            )
        )
    except Exception as exc:
        checks.extend(
            [
                {
                    "id": "audit_format",
                    "label": "conflict_audit.csv has the requested usable schema",
                    "pass": False,
                    "weight": 0.0,
                    "detail": str(exc),
                },
                {
                    "id": "conflict_audit_parse",
                    "label": "conflict_audit.csv parseable",
                    "pass": False,
                    "weight": 0.05,
                    "detail": str(exc),
                },
            ]
        )

    total = (
        0.08 * format_score
        + 0.08 * coverage_score
        + 0.22 * decision_score
        + 0.14 * source_score
        + 0.14 * evidence_score
        + 0.11 * conflict_score
        + 0.09 * scope_score
        + 0.07 * insuff_score
        + 0.04 * forbidden_score
        + 0.03 * audit_score
    )
    th = gt["scoring"]["thresholds"]
    level = (
        "excellent"
        if total >= th["excellent"]
        else "good"
        if total >= th["good"]
        else "pass"
        if total >= th["pass"]
        else "fail"
    )
    return {
        "task": "058-policy-version-conflict-resolution",
        "workspace": str(w),
        "outcome_score": round(float(total), 4),
        "level": level,
        "checks": checks,
    }
