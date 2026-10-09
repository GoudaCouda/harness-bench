from __future__ import annotations

import json
import csv
from pathlib import Path
from typing import Any

TASK_DIR = Path(__file__).resolve().parents[2]


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _token_groups(
    expectation: dict[str, Any],
    *,
    groups_key: str,
    terms_key: str,
) -> list[list[str]]:
    groups = expectation.get(groups_key)
    if isinstance(groups, list):
        return [
            [str(token) for token in group]
            for group in groups
            if isinstance(group, list) and group
        ]
    return [[str(token)] for token in expectation.get(terms_key, [])]


def _groups_match(text: object, groups: list[list[str]]) -> bool:
    normalized = _norm(text)
    return all(any(_norm(token) in normalized for token in group) for group in groups)


def _reason_matches(value: object, expectation: dict[str, Any]) -> bool:
    normalized = _norm(value)
    accepted = {expectation["reason_code"], *expectation.get("reason_aliases", [])}
    if normalized in {_norm(item) for item in accepted}:
        return True

    def words(text: object) -> set[str]:
        tokens = str(text or "").casefold().replace("-", "_").split("_")
        return {
            token.rstrip("sed")
            for token in tokens
            if len(token) >= 4 and token not in {"with", "from", "that"}
        }

    expected_words = words(expectation["reason_code"])
    actual_words = words(normalized.replace(" ", "_"))
    overlap = expected_words & actual_words
    return len(overlap) >= 2 and len(overlap) / max(len(expected_words), 1) >= 0.4


def _missing_matches(value: object, expectation: dict[str, Any]) -> bool:
    if not isinstance(value, list):
        return False
    groups = _token_groups(
        expectation,
        groups_key="missing_term_groups",
        terms_key="missing_terms",
    )
    if bool(value) != bool(groups):
        return False
    return _groups_match(" ".join(map(str, value)), groups)


def _as_nonnegative_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 and str(value).strip() == str(parsed) else None


def score_workspace(workspace: Path) -> dict[str, Any]:
    w = Path(workspace).resolve()
    gt = json.loads(
        (TASK_DIR / "tests" / "ground_truth" / "ground_truth.json").read_text(
            encoding="utf-8"
        )
    )
    path = w / "case_rulings.json"
    summary_path = w / "ruling_summary.csv"
    checks: list[dict[str, Any]] = []
    format_score = coverage_score = clause_score = decision_score = reason_score = (
        quote_score
    ) = secondary_score = blocking_score = missing_score = line_item_score = (
        summary_score
    ) = 0.0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = data if isinstance(data, list) else data.get("rulings", [])
        row_dicts = [row for row in rows if isinstance(row, dict)]
        row_ids = [str(row.get("case_id")) for row in row_dicts]
        by_id = {
            str(row.get("case_id")): row
            for row in row_dicts
            if row_ids.count(str(row.get("case_id"))) == 1
        }
        required = {
            "case_id",
            "applicable_clause",
            "decision",
            "reason_code",
            "quote_or_signal",
            "secondary_clauses",
            "blocking_condition",
            "missing_information",
        }
        format_score = (
            1.0
            if (
                isinstance(rows, list)
                and bool(rows)
                and len(row_dicts) == len(rows)
                and len(set(row_ids)) == len(row_ids)
                and all(required.issubset(row) for row in row_dicts)
            )
            else 0.0
        )
        expected_ids = set(gt["cases"])
        coverage_score = (
            1.0
            if set(by_id) == expected_ids
            else len(set(by_id) & expected_ids) / len(expected_ids)
        )
        clause_hits = decision_hits = reason_hits = quote_hits = secondary_hits = (
            blocking_hits
        ) = missing_hits = 0
        for cid, exp in gt["cases"].items():
            row = by_id.get(cid, {})
            clause_hits += int(
                str(row.get("applicable_clause", "")).strip()
                == exp["applicable_clause"]
            )
            decision_hits += int(
                str(row.get("decision", "")).strip() == exp["decision"]
            )
            reason_hits += int(_reason_matches(row.get("reason_code"), exp))
            quote_groups = _token_groups(
                exp,
                groups_key="quote_token_groups",
                terms_key="tokens",
            )
            quote_hits += int(_groups_match(row.get("quote_or_signal"), quote_groups))
            secondary = row.get("secondary_clauses", [])
            if not isinstance(secondary, list):
                secondary = []
            secondary_hits += int(
                sorted(map(str, secondary)) == sorted(exp.get("secondary_clauses", []))
            )
            blocking = _norm(
                " ".join(
                    [
                        str(row.get("blocking_condition", "")),
                        str(row.get("quote_or_signal", "")),
                        " ".join(map(str, row.get("missing_information", [])))
                        if isinstance(row.get("missing_information"), list)
                        else "",
                    ]
                )
            )
            blocking_hits += int(
                all(
                    any(_norm(token) in blocking for token in group)
                    for group in exp.get("blocking_token_groups", [])
                )
            )
            missing_hits += int(_missing_matches(row.get("missing_information"), exp))
        n = len(expected_ids)
        clause_score = clause_hits / n
        decision_score = decision_hits / n
        reason_score = reason_hits / n
        quote_score = quote_hits / n
        secondary_score = secondary_hits / n
        blocking_score = blocking_hits / n
        missing_score = missing_hits / n
        line_field_hits = {
            "applicable_clause": 0,
            "decision": 0,
            "reason_code": 0,
            "quote_or_signal": 0,
            "secondary_clauses": 0,
            "blocking_condition": 0,
            "missing_information": 0,
        }
        line_total = len(gt.get("line_items", {}))
        for key, exp in gt.get("line_items", {}).items():
            cid, line_id = key.split(":", 1)
            parent = by_id.get(cid, {})
            line_rows = parent.get("line_item_rulings", [])
            if not isinstance(line_rows, list):
                line_rows = []
            row = next(
                (item for item in line_rows if str(item.get("line_id")) == line_id), {}
            )
            secondary = row.get("secondary_clauses", [])
            if not isinstance(secondary, list):
                secondary = []
            line_field_hits["applicable_clause"] += int(
                str(row.get("applicable_clause", "")).strip()
                == exp["applicable_clause"]
            )
            line_field_hits["decision"] += int(
                str(row.get("decision", "")).strip() == exp["decision"]
            )
            line_field_hits["reason_code"] += int(
                str(row.get("reason_code", "")).strip() == exp["reason_code"]
            )
            line_field_hits["quote_or_signal"] += int(
                _groups_match(
                    row.get("quote_or_signal"),
                    _token_groups(
                        exp,
                        groups_key="quote_token_groups",
                        terms_key="tokens",
                    ),
                )
            )
            line_field_hits["secondary_clauses"] += int(
                sorted(map(str, secondary)) == sorted(exp.get("secondary_clauses", []))
            )
            blocking_evidence = " ".join(
                [
                    str(row.get("blocking_condition", "")),
                    str(row.get("quote_or_signal", "")),
                    " ".join(map(str, row.get("missing_information", [])))
                    if isinstance(row.get("missing_information"), list)
                    else "",
                ]
            )
            line_field_hits["blocking_condition"] += int(
                _groups_match(
                    blocking_evidence,
                    exp.get("blocking_token_groups", []),
                )
            )
            line_field_hits["missing_information"] += int(
                _missing_matches(row.get("missing_information"), exp)
            )
        line_possible = line_total * len(line_field_hits)
        line_hits = sum(line_field_hits.values())
        line_item_score = line_hits / max(line_possible, 1)
        checks.extend(
            [
                {
                    "id": "format",
                    "label": "case_rulings.json has required schema",
                    "pass": bool(format_score),
                    "weight": 0.06,
                    "detail": None,
                },
                {
                    "id": "coverage",
                    "label": "all and only cases covered",
                    "pass": coverage_score == 1.0,
                    "weight": 0.10,
                    "detail": sorted(by_id),
                },
                {
                    "id": "clauses",
                    "label": "applicable clauses correct",
                    "pass": clause_score >= 0.8,
                    "weight": 0.14,
                    "detail": {"hits": clause_hits},
                },
                {
                    "id": "decisions",
                    "label": "decisions correct",
                    "pass": decision_score >= 0.8,
                    "weight": 0.24,
                    "detail": {"hits": decision_hits},
                },
                {
                    "id": "reason_codes",
                    "label": "reason codes correct",
                    "pass": reason_score >= 0.8,
                    "weight": 0.14,
                    "detail": {"hits": reason_hits},
                },
                {
                    "id": "quotes",
                    "label": "quote_or_signal supports ruling",
                    "pass": quote_score >= 0.8,
                    "weight": 0.08,
                    "detail": {"hits": quote_hits},
                },
                {
                    "id": "secondary_clauses",
                    "label": "secondary clauses capture exception rules",
                    "pass": secondary_score >= 0.8,
                    "weight": 0.08,
                    "detail": {"hits": secondary_hits},
                },
                {
                    "id": "blocking_conditions",
                    "label": "blocking conditions explain deny/review decisions",
                    "pass": blocking_score >= 0.8,
                    "weight": 0.10,
                    "detail": {"hits": blocking_hits},
                },
                {
                    "id": "missing_information",
                    "label": "missing_information captures absent evidence without inventing approvals",
                    "pass": missing_score >= 0.8,
                    "weight": 0.06,
                    "detail": {"hits": missing_hits},
                },
                {
                    "id": "line_item_rulings",
                    "label": "mixed-packet line-item fields follow their controlling and secondary clauses",
                    "pass": line_item_score >= 0.80,
                    "weight": 0.10,
                    "detail": {
                        "field_hits": line_field_hits,
                        "fields_per_line": len(line_field_hits),
                        "lines": line_total,
                        "score": round(line_item_score, 4),
                    },
                },
            ]
        )
    except Exception as exc:
        checks.append(
            {
                "id": "parse_error",
                "label": "case_rulings.json parseable",
                "pass": False,
                "weight": 1.0,
                "detail": str(exc),
            }
        )
    try:
        expected_header = [
            "case_id",
            "case_decision",
            "denied_lines",
            "review_lines",
            "approved_lines",
            "controlling_clause",
            "summary_reason",
        ]
        with summary_path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            fieldnames = list(reader.fieldnames or [])
            summary_rows = list(reader)
        summary_ids = [row.get("case_id", "") for row in summary_rows]
        summary_by_id = {
            row.get("case_id", ""): row
            for row in summary_rows
            if summary_ids.count(row.get("case_id", "")) == 1
        }
        schema_ok = fieldnames == expected_header and all(
            set(row) == set(expected_header)
            and all(isinstance(row.get(key), str) for key in expected_header)
            for row in summary_rows
        )
        covers_all = len(summary_rows) == len(gt["cases"]) and set(
            summary_by_id
        ) == set(gt["cases"])
        decision_ok = covers_all and all(
            summary_by_id[cid]["case_decision"] == exp["decision"]
            for cid, exp in gt["cases"].items()
        )
        zero_counts_ok = covers_all and all(
            [
                _as_nonnegative_int(summary_by_id[cid][column])
                for column in (
                    "denied_lines",
                    "review_lines",
                    "approved_lines",
                )
            ]
            == [0, 0, 0]
            for cid in gt["cases"]
            if cid != "T110"
        )
        mixed_counts_ok = covers_all and [
            _as_nonnegative_int(summary_by_id["T110"][column])
            for column in (
                "denied_lines",
                "review_lines",
                "approved_lines",
            )
        ] == [1, 2, 0]
        controlling_ok = covers_all and all(
            summary_by_id[cid]["controlling_clause"] == exp["applicable_clause"]
            for cid, exp in gt["cases"].items()
        )
        reason_ok = covers_all and all(
            _reason_matches(summary_by_id[cid]["summary_reason"], exp)
            for cid, exp in gt["cases"].items()
        )
        summary_facts = {
            "schema": schema_ok,
            "coverage": covers_all,
            "case_decisions": decision_ok,
            "single_case_zero_counts": zero_counts_ok,
            "mixed_packet_counts": mixed_counts_ok,
            "controlling_clauses": controlling_ok,
            "summary_reasons": reason_ok,
        }
        summary_score = (
            0.15 * schema_ok
            + 0.15 * covers_all
            + 0.20 * decision_ok
            + 0.20 * zero_counts_ok
            + 0.15 * mixed_counts_ok
            + 0.075 * controlling_ok
            + 0.075 * reason_ok
        )
        checks.append(
            {
                "id": "ruling_summary",
                "label": "ruling_summary.csv enforces case coverage and explicit-line counts",
                "pass": summary_score >= 0.85,
                "weight": 0.08,
                "detail": {
                    **summary_facts,
                    "score": round(summary_score, 4),
                },
            }
        )
    except Exception as exc:
        checks.append(
            {
                "id": "ruling_summary_parse",
                "label": "ruling_summary.csv parseable",
                "pass": False,
                "weight": 0.08,
                "detail": str(exc),
            }
        )

    total = (
        0.05 * format_score
        + 0.08 * coverage_score
        + 0.12 * clause_score
        + 0.20 * decision_score
        + 0.12 * reason_score
        + 0.06 * quote_score
        + 0.07 * secondary_score
        + 0.08 * blocking_score
        + 0.04 * missing_score
        + 0.10 * line_item_score
        + 0.08 * summary_score
    )
    caps = []
    if coverage_score < 1.0:
        caps.append(0.72)
    if decision_score < 0.9:
        caps.append(0.78)
    if reason_score < 0.8:
        caps.append(0.74)
    if blocking_score < 0.8:
        caps.append(0.78)
    if line_item_score < 0.8:
        caps.append(0.74)
    if summary_score < 0.85:
        caps.append(0.78)
    if caps:
        total = min(total, min(caps))
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
        "task": "022-policy-clause-retrieval",
        "workspace": str(w),
        "outcome_score": round(float(total), 4),
        "level": level,
        "checks": checks,
    }
