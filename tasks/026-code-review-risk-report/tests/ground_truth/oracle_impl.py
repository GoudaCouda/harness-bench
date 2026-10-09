from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

_TASK_DIR = Path(__file__).resolve().parents[2]
_GT = json.loads(
    (_TASK_DIR / "tests" / "ground_truth" / "ground_truth.json").read_text(
        encoding="utf-8"
    )
)
_HASHES = {
    "diff.patch": "f6bb45215d1dfb18262f17d366ffd8ad",
    "export_contract.md": "6efb599485857e77f44e044332282425",
    "schema.sql": "d615026581161cc49e4d0fb705aedee2",
}
_REQUIRED_FINDING_KEYS = {
    "id",
    "severity",
    "file",
    "line_hint",
    "risk",
    "recommendation",
    "test",
    "evidence",
}
_CLUSTERS = {
    "authorization_and_tenant_review": {
        "pii_scope_bypass",
        "cross_tenant_idempotency",
    },
    "worker_state_review": {
        "non_atomic_lease",
        "false_completion",
    },
    "data_lifecycle_review": {
        "cursor_tuple_regression",
        "zero_ttl_regression",
        "signed_url_logging",
    },
}


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def _semantic_test_ok(
    expected: dict[str, Any],
    test_text: str,
    equivalence_rules: dict[str, list[list[str]]],
) -> bool:
    """Accept either the legacy anchors or a complete semantic test scenario."""
    normalized = " ".join(test_text.lower().split())
    finding_id = str(expected.get("id", ""))
    term_groups = equivalence_rules.get(finding_id, [])

    if finding_id == "cache_scope_regression":
        # A cache-isolation regression test must bind two distinct users to a
        # cached request and assert the safe cross-user outcome.  Merely
        # describing the vulnerable state ("B sees A's data"), naming one
        # user, or mentioning generic user data without cache/request context
        # is not an executable regression assertion.
        actors_ok = bool(
            re.search(r"\buser a\b", normalized)
            and re.search(r"\buser b\b", normalized)
        )
        cache_context_ok = bool(re.search(r"\bcach(?:e|ed|es|ing)\b", normalized))
        request_context_ok = bool(
            re.search(
                r"\b(?:request(?:s|ed|ing)?|orders?|customer_id|results?)\b",
                normalized,
            )
        )
        safe_cross_user_assertion = bool(
            re.search(
                r"\buser b\b[^.!?]{0,140}\b"
                r"(?:does|do|must|should|will|would)\s+not\s+"
                r"(?:see|receive|get|observe|access|obtain)\w*\b"
                r"[^.!?]{0,140}\buser a(?:['’]s)?\b"
                r"[^.!?]{0,80}\bcach(?:e|ed|es|ing)\b",
                normalized,
            )
            or re.search(
                r"\buser b\b[^.!?]{0,140}\b"
                r"(?:never|cannot|can't|mustn't|shouldn't)\s+"
                r"(?:see|receive|get|observe|access|obtain)\w*\b"
                r"[^.!?]{0,140}\buser a(?:['’]s)?\b"
                r"[^.!?]{0,80}\bcach(?:e|ed|es|ing)\b",
                normalized,
            )
            or re.search(
                r"\buser b\b[^.!?]{0,180}\buser a(?:['’]s)?\b"
                r"[^.!?]{0,80}\bcach(?:e|ed|es|ing)\b"
                r"[^.!?]{0,80}\b(?:is|are|was|were|be)\s+not\s+"
                r"(?:returned|shown|served|exposed|leaked)\b",
                normalized,
            )
            or re.search(
                r"\buser a(?:['’]s)?\b[^.!?]{0,80}\b"
                r"cach(?:e|ed|es|ing)\b[^.!?]{0,100}\b"
                r"(?:is|are|was|were|be)\s+not\s+"
                r"(?:returned|shown|served|exposed|leaked)\b"
                r"[^.!?]{0,100}\buser b\b",
                normalized,
            )
        )
        return (
            actors_ok
            and cache_context_ok
            and request_context_ok
            and safe_cross_user_assertion
        )

    legacy_hits = sum(
        term.lower() in normalized for term in expected.get("test_terms", [])
    )
    if legacy_hits >= 2:
        return True

    return bool(term_groups) and all(
        any(term.lower() in normalized for term in group) for group in term_groups
    )


def score_workspace(workspace: Path) -> dict[str, Any]:
    w = Path(workspace).resolve()
    checks: list[dict[str, Any]] = []
    weights = _GT["scoring"]["weights"]

    def add(cid: str, ok: bool, weight: float, detail: Any = None) -> None:
        checks.append({"id": cid, "pass": bool(ok), "weight": weight, "detail": detail})

    fixture_root = w / "review"
    missing_fixtures = [rel for rel in _HASHES if not (fixture_root / rel).is_file()]
    if missing_fixtures:
        add("fixture_inputs", False, 0.0, {"missing": missing_fixtures})
        return {
            "task": "026-code-review-risk-report",
            "workspace": str(w),
            "outcome_score": 0.0,
            "checks": checks,
        }

    report_integrity = False
    finding_hits: dict[str, float] = {}
    matched_indices: dict[str, int] = {}
    severity_hits = 0
    test_hits = 0
    rec_hits = 0
    false_positive_ok = False
    strong_findings = 0
    submitted_count = 0
    missing_finding_ids = [item["id"] for item in _GT["expected_findings"]]
    path = w / "review_findings.json"
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            findings = data.get("findings", [])
            submitted_count = len(findings) if isinstance(findings, list) else 0
            report_integrity = bool(
                isinstance(data, dict)
                and isinstance(findings, list)
                and findings
                and isinstance(data.get("summary"), str)
                and data["summary"].strip()
                and all(
                    isinstance(finding, dict)
                    and _REQUIRED_FINDING_KEYS <= set(finding)
                    and str(finding.get("severity", "")).casefold()
                    in {"critical", "high", "medium", "low"}
                    and all(
                        str(finding.get(key, "")).strip()
                        for key in _REQUIRED_FINDING_KEYS
                    )
                    for finding in findings
                )
            )
            used_indices: set[int] = set()
            for expected in _GT["expected_findings"]:
                best = 0.0
                best_idx = -1
                for idx, finding in enumerate(
                    findings if isinstance(findings, list) else []
                ):
                    if idx in used_indices:
                        continue
                    if not isinstance(finding, dict):
                        continue
                    text = json.dumps(finding, ensure_ascii=False).lower()
                    file_ok = (
                        str(finding.get("file", "")).lower() == expected["file"].lower()
                    )
                    if not file_ok:
                        # Risk terms are meaningful only when the finding binds
                        # them to the changed file that contains the defect.
                        # This also prevents a cache-key finding that mentions
                        # include_archived from earning partial credit for the
                        # separate app/api.py inclusion regression.
                        continue
                    term_score = sum(
                        term.lower() in text for term in expected["terms"]
                    ) / len(expected["terms"])
                    rec = str(finding.get("recommendation", "")).lower()
                    rec_score = min(
                        sum(
                            term.lower() in rec
                            for term in expected["recommendation_terms"]
                        )
                        / 2,
                        1.0,
                    )
                    score = 0.40 * file_ok + 0.40 * term_score + 0.20 * rec_score
                    if score > best:
                        best = score
                        best_idx = idx
                if best_idx >= 0 and best >= 0.75:
                    used_indices.add(best_idx)
                    matched_indices[expected["id"]] = best_idx
                finding_hits[expected["id"]] = round(best, 3)
            all_text = json.dumps(findings, ensure_ascii=False).lower()
            false_positive_ok = not any(
                term in all_text for term in _GT.get("false_positive_terms", [])
            )
            missing_finding_ids = [
                finding_id for finding_id, score in finding_hits.items() if score < 0.75
            ]
            strong_findings = len(finding_hits) - len(missing_finding_ids)
            for expected in _GT["expected_findings"]:
                matched_idx = matched_indices.get(expected["id"])
                if matched_idx is None:
                    continue
                finding = findings[matched_idx]
                if (
                    str(finding.get("severity", "")).lower()
                    == expected.get("severity", "").lower()
                ):
                    severity_hits += 1
                test_text = str(finding.get("test", ""))
                if test_text and _semantic_test_ok(
                    expected,
                    test_text,
                    _GT.get("test_equivalence_rules", {}),
                ):
                    test_hits += 1
            rec_hits = sum(
                bool(str(item.get("recommendation", "")).strip())
                and bool(str(item.get("evidence", "")).strip())
                and str(item.get("severity", "")).lower()
                in {"critical", "high", "medium", "low"}
                for item in findings
                if isinstance(item, dict)
            )
        except Exception as exc:
            add("parse_diagnostic", False, 0.0, str(exc))

    base = w / "review"
    intact = [(_md5(base / rel) == digest) for rel, digest in _HASHES.items()]
    integrity = sum(intact) / len(intact)
    case_results: dict[str, bool] = {}
    for case_id, finding_ids in _CLUSTERS.items():
        passed = all(
            finding_hits.get(finding_id, 0.0) >= 0.75 for finding_id in finding_ids
        )
        case_results[case_id] = passed
        add(
            case_id,
            passed,
            weights[case_id],
            {
                "required_findings": sorted(finding_ids),
                "missing_or_weak": sorted(
                    finding_id
                    for finding_id in finding_ids
                    if finding_hits.get(finding_id, 0.0) < 0.75
                ),
            },
        )

    actionable_handoff = bool(
        strong_findings and rec_hits >= strong_findings and false_positive_ok
    )
    case_results["actionable_handoff"] = actionable_handoff
    add(
        "actionable_handoff",
        actionable_handoff,
        weights["actionable_handoff"],
        {
            "grounded_findings": strong_findings,
            "actionable_findings": rec_hits,
            "style_only_false_positive_free": false_positive_ok,
        },
    )

    prioritization_and_verification = bool(
        strong_findings >= 6
        and severity_hits == strong_findings
        and test_hits == strong_findings
    )
    case_results["prioritization_and_verification"] = prioritization_and_verification
    add(
        "prioritization_and_verification",
        prioritization_and_verification,
        weights["prioritization_and_verification"],
        {
            "grounded_findings": strong_findings,
            "correct_severities": severity_hits,
            "concrete_tests": test_hits,
        },
    )

    case_results["report_integrity"] = report_integrity
    add(
        "report_integrity",
        report_integrity,
        weights["report_integrity"],
        {"finding_count": submitted_count},
    )
    # Keep the fine-grained measurements as zero-weight diagnostics.  They are
    # useful when debugging a run, but the benchmark score is deliberately
    # awarded only for the business-level review cohorts above.
    expected_count = len(_GT["expected_findings"])
    add(
        "finding_coverage",
        not missing_finding_ids,
        0.0,
        {
            "finding_hits": finding_hits,
            "strong_hits": strong_findings,
            "expected": expected_count,
            "missing_finding_ids": missing_finding_ids,
        },
    )
    add(
        "severity_exactness",
        severity_hits == expected_count,
        0.0,
        {
            "severity_hits": severity_hits,
            "expected": expected_count,
            "score": severity_hits / expected_count,
        },
    )
    add(
        "test_coverage",
        test_hits == expected_count,
        0.0,
        {
            "test_hits": test_hits,
            "expected": expected_count,
            "score": test_hits / expected_count,
        },
    )
    add("fixture_integrity", integrity == 1.0, 0.0, {"score": integrity})

    total = sum(weights[case_id] for case_id, passed in case_results.items() if passed)
    if integrity != 1.0:
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
        "task": "026-code-review-risk-report",
        "outcome_score": round(total, 4),
        "level": level,
        "checks": checks,
    }
