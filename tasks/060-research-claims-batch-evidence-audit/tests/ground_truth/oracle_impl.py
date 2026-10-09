from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

TASK_DIR = Path(__file__).resolve().parents[2]
_COHORTS = {
    "headline_and_methods": {"CL-01", "CL-03", "CL-04", "CL-10", "CL-12", "CL-14"},
    "subgroup_results": {"CL-02", "CL-09", "CL-11"},
    "operational_and_safety": {"CL-06", "CL-07"},
    "reproducibility_gaps": {"CL-05", "CL-08"},
    "generalization_scope": {"CL-13"},
}
_CASE_WEIGHTS = {
    "headline_and_methods": 0.20,
    "subgroup_results": 0.15,
    "operational_and_safety": 0.15,
    "reproducibility_gaps": 0.20,
    "generalization_scope": 0.10,
    "cross_source_traceability": 0.10,
    "audit_integrity": 0.10,
}


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _row_text(row: Any) -> str:
    return json.dumps(row, ensure_ascii=False).lower()


def _predicate_polarities(text: str, pattern: str) -> set[str]:
    low = _norm(text)
    polarities: set[str] = set()
    for match in re.finditer(pattern, low):
        clause_prefix = re.split(r"[.!?;\n]", low[: match.start()])[-1][-96:]
        negated = bool(
            re.search(
                r"\b(?:not|never|without|cannot|can't|won't|"
                r"(?:do|does|did|will|would|can|could|should|must|"
                r"is|was|has|have)\s+not|no)\b"
                r"(?:\W+\w+){0,4}\W*$",
                clause_prefix,
            )
        ) and not bool(re.search(r"\bnot\s+only\W*$", clause_prefix))
        polarities.add("negative" if negated else "positive")
    return polarities


def _has_all(text: str, tokens: list[str]) -> bool:
    low = _norm(text).replace("_", " ").replace("-", " ")
    aliases = {
        "not supplied": ("not supplied", "missing", "not provided", "absent"),
        "does not contain": ("does not contain", "missing", "absent", "not included"),
        "raw/events.parquet": ("raw/events.parquet", "raw events", "raw event bundle"),
        "analysis_config.yaml": ("analysis_config.yaml", "analysis config", "config"),
        "run_analysis.py": (
            "run_analysis.py",
            "analysis driver",
            "driver script",
            "main driver",
        ),
    }
    if not all(
        any(
            _norm(alternative).replace("_", " ").replace("-", " ") in low
            for alternative in aliases.get(_norm(token), (token,))
        )
        for token in tokens
    ):
        return False
    if "corrected" in {_norm(token) for token in tokens}:
        return _predicate_polarities(text, r"\bcorrected\b") == {"positive"}
    return True


def _source_matches(actual: Any, expected: Any) -> bool:
    if isinstance(expected, list):
        return any(_source_matches(actual, option) for option in expected)
    got = _norm(actual).replace("\\", "/")
    want = _norm(expected).replace("\\", "/")
    got_base = got.rsplit("/", 1)[-1]
    want_base = want.rsplit("/", 1)[-1]
    return (
        got == want
        or got.endswith("/" + want)
        or want.endswith("/" + got)
        or got_base == want_base
    )


def _source_in_text(text: str, expected: str) -> bool:
    text_n = _norm(text).replace("\\", "/")
    want = _norm(expected).replace("\\", "/")
    want_base = want.rsplit("/", 1)[-1]
    return want in text_n or want_base in text_n


def _source_path(source: Any) -> Path | None:
    raw = str(source or "").strip().replace("\\", "/")
    if not raw or raw.startswith("/") or ".." in Path(raw).parts:
        return None
    root = TASK_DIR / "workspace"
    direct = root / raw
    if direct.is_file():
        return direct
    matches = [
        candidate for candidate in root.rglob(Path(raw).name) if candidate.is_file()
    ]
    return matches[0] if len(matches) == 1 else None


def _source_exists(source: Any) -> bool:
    return _source_path(source) is not None


def _has_csv_locator(source: Any, location: Any) -> bool:
    source_name = str(source or "").strip().casefold().replace("\\", "/")
    locator = _norm(location)
    return source_name.endswith(".csv") and bool(
        re.search(r"\b(?:rows?|columns?|cols?)\s*(?:#|:)?\s*\d+\b", locator)
    )


def _csv_locator_text(source: Any, location: Any) -> str:
    path = _source_path(source)
    if path is None or path.suffix.casefold() != ".csv":
        return ""
    locator = _norm(location)
    row_numbers = [
        int(number) for number in re.findall(r"\brows?\s*(?:#|:)?\s*(\d+)\b", locator)
    ]
    column_numbers = [
        int(number)
        for number in re.findall(
            r"\b(?:columns?|cols?)\s*(?:#|:)?\s*(\d+)\b",
            locator,
        )
    ]
    header_requested = "header" in locator
    if not row_numbers and not column_numbers and not header_requested:
        return ""
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            columns = list(reader.fieldnames or [])
    except Exception:
        return ""
    if header_requested:
        return " ".join(columns).lower()
    if any(number < 1 or number > len(rows) for number in row_numbers):
        return ""
    if any(number < 1 or number > len(columns) for number in column_numbers):
        return ""
    resolved: list[str] = []
    for number in row_numbers:
        row = rows[number - 1]
        resolved.extend(f"{key} {value}" for key, value in row.items())
    for number in column_numbers:
        column = columns[number - 1]
        resolved.append(column)
        resolved.extend(str(row.get(column, "")) for row in rows)
    return " ".join(resolved).lower()


def _located_source_text(source: Any, location: Any) -> str:
    path = _source_path(source)
    if path is None:
        return ""
    if path.suffix.casefold() == ".csv":
        resolved = _csv_locator_text(source, location)
        if resolved:
            return resolved
        locator = _norm(location)
        table_text = path.read_text(encoding="utf-8-sig", errors="replace").casefold()
        # Business users commonly identify a CSV record as
        # ``Row metric/cohort`` rather than by physical row number.  Resolve
        # that compound key against the table instead of requiring a hidden
        # spelling such as ``metric=... cohort=...``.
        logical_row = re.fullmatch(
            r"(?:row\s+)?([a-z0-9_.-]+)\s*/\s*([a-z0-9_.-]+)",
            locator,
        )
        if logical_row:
            metric, cohort = logical_row.groups()
            try:
                with path.open("r", encoding="utf-8-sig", newline="") as handle:
                    rows = list(csv.DictReader(handle))
            except Exception:
                return ""
            matches = [
                row
                for row in rows
                if _norm(row.get("metric")) == metric
                and _norm(row.get("cohort")) == cohort
            ]
            if len(matches) == 1:
                return " ".join(
                    f"{key} {value}" for key, value in matches[0].items()
                ).casefold()
        tokens = [
            token.split("=", 1)[-1]
            for token in re.findall(r"[a-z0-9_./=-]+", locator)
            if token not in {"cohort", "metric", "value", "field", "column"}
        ]
        meaningful = [token for token in tokens if len(token) >= 3]
        if meaningful and sum(token in table_text for token in meaningful) >= min(
            2, len(meaningful)
        ):
            return table_text
        return ""

    locator = " ".join(str(location or "").strip().casefold().split())
    if not locator:
        return ""
    content = path.read_text(encoding="utf-8", errors="replace")
    paragraphs = [
        block.strip()
        for block in re.split(r"\n\s*\n", content)
        if block.strip() and not block.lstrip().startswith("#")
    ]
    paragraph_match = re.search(r"\bparagraph\s+(\d+)\b", locator)
    if paragraph_match:
        index = int(paragraph_match.group(1)) - 1
        return paragraphs[index].casefold() if 0 <= index < len(paragraphs) else ""

    low = content.casefold()
    if "package inventory" in locator and "deposited package contains" in low:
        start = low.find("deposited package contains")
        return low[start : start + 900]
    anchor_candidates = {
        locator,
        re.sub(r"^(?:section|review)\s+", "", locator),
    }
    positions = [low.find(anchor) for anchor in anchor_candidates if anchor]
    positions = [position for position in positions if position >= 0]
    if not positions:
        distinctive_tokens = [
            token
            for token in re.findall(r"[a-z0-9_./-]+", locator)
            if len(token) >= 4
            and token not in {"section", "paragraph", "package", "inventory"}
        ]
        positions = [low.find(token) for token in distinctive_tokens]
        positions = [position for position in positions if position >= 0]
    if not positions:
        return ""
    start = min(positions)
    return low[start : start + 900]


def _relation_matches(actual: Any, status: str) -> bool:
    relation = _norm(actual).replace("-", "_").replace(" ", "_")
    aliases = {
        "supported": {"supports", "support"},
        "contradicted": {"refutes", "refute", "contradicts", "contradiction"},
        "overstated": {"limits", "limit", "refutes", "qualifies"},
        "unsupported": {
            "insufficient",
            "refutes",
            "unsupported",
            "missing_evidence",
        },
        "not_reproducible": {
            "reproducibility_gap",
            "not_reproducible",
            "insufficient",
            "refutes",
        },
    }
    return relation in aliases[status]


def _evidence_entries(value: Any) -> list[Any]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return value
    return []


def score_workspace(workspace: Path) -> dict[str, Any]:
    w = Path(workspace).resolve()
    gt = json.loads(
        (TASK_DIR / "tests" / "ground_truth" / "ground_truth.json").read_text(
            encoding="utf-8"
        )
    )
    csv_path = w / "claim_audit.csv"
    json_path = w / "evidence_matrix.json"
    checks: list[dict[str, Any]] = []
    csv_claim_results: dict[str, bool] = {}
    matrix_claim_results: dict[str, bool] = {}
    secondary_results: dict[str, bool] = {}
    matrix_format_ok = False
    if not csv_path.is_file():
        return {
            "task": "060-research-claims-batch-evidence-audit",
            "workspace": str(w),
            "outcome_score": 0.0,
            "level": "fail",
            "checks": [
                {
                    "id": "missing",
                    "pass": False,
                    "weight": 1.0,
                    "detail": "claim_audit.csv missing",
                }
            ],
        }

    format_score = coverage_score = status_score = source_score = location_score = (
        evidence_score
    ) = secondary_score = repro_score = over_score = matrix_score = 0.0
    try:
        with (TASK_DIR / "workspace" / "claims" / "claims.csv").open(
            "r", encoding="utf-8", newline=""
        ) as handle:
            claim_texts = {
                row["claim_id"]: row["claim_text"] for row in csv.DictReader(handle)
            }
        with csv_path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
        header = [
            "claim_id",
            "claim_text",
            "status",
            "primary_source",
            "evidence_location",
            "evidence_signal",
            "secondary_sources",
            "rationale",
        ]
        format_score = (
            1.0
            if rows
            and reader.fieldnames == header
            and all(list(row) == header and None not in row for row in rows)
            else 0.0
        )
        by_id = {str(row.get("claim_id", "")).strip(): row for row in rows}
        expected_ids = set(gt["claims"])
        exact_texts = all(
            by_id.get(cid, {}).get("claim_text") == claim_texts[cid]
            for cid in expected_ids
        )
        coverage_score = (
            1.0
            if len(rows) == len(by_id) == len(expected_ids)
            and set(by_id) == expected_ids
            and exact_texts
            else 0.0
            if set(by_id) == expected_ids
            else len(set(by_id) & expected_ids) / len(expected_ids)
        )
        status_hits = source_hits = location_hits = evidence_hits = secondary_hits = (
            repro_hits
        ) = over_hits = 0
        for cid, exp in gt["claims"].items():
            row = by_id.get(cid, {})
            text = _row_text(row)
            if _norm(row.get("status")) == exp["status"]:
                status_hits += 1
            if _source_matches(row.get("primary_source", ""), exp["primary_source"]):
                source_hits += 1
            resolved_location = _located_source_text(
                row.get("primary_source"),
                row.get("evidence_location"),
            )
            grounded_text = " ".join(
                [
                    _norm(row.get("evidence_location")),
                    _norm(row.get("evidence_signal")),
                    _norm(row.get("rationale")),
                    resolved_location,
                    text,
                ]
            )
            location_ok = bool(resolved_location) and (
                not _has_csv_locator(
                    row.get("primary_source"), row.get("evidence_location")
                )
                or _has_all(resolved_location, exp["location_tokens"])
            )
            evidence_ok = _has_all(grounded_text, exp["tokens"])
            if location_ok:
                location_hits += 1
            if evidence_ok:
                evidence_hits += 1
            sec_text = _norm(row.get("secondary_sources")) + " " + text
            secondary_ok = all(
                _source_in_text(sec_text, source) for source in exp["secondary_sources"]
            )
            secondary_results[cid] = secondary_ok
            if secondary_ok:
                secondary_hits += 1
            csv_claim_results[cid] = bool(
                _norm(row.get("status")) == exp["status"]
                and _source_matches(
                    row.get("primary_source", ""), exp["primary_source"]
                )
                and location_ok
                and evidence_ok
            )
            if exp["status"] == "not_reproducible":
                if any(tok.lower() in text for tok in gt["repro_gap_tokens"]):
                    repro_hits += 1
            else:
                repro_hits += 1
            if exp["status"] == "overstated":
                if any(tok.lower() in text for tok in gt["overstatement_tokens"]):
                    over_hits += 1
            else:
                over_hits += 1
        n = len(expected_ids)
        status_score = status_hits / n
        source_score = source_hits / n
        location_score = location_hits / n
        evidence_score = evidence_hits / n
        secondary_score = secondary_hits / n
        repro_score = repro_hits / n
        over_score = over_hits / n
        checks.extend(
            [
                {
                    "id": "format",
                    "label": "claim_audit.csv header is exact",
                    "pass": format_score == 1.0,
                    "weight": 0.08,
                    "detail": list(rows[0].keys()) if rows else [],
                },
                {
                    "id": "coverage",
                    "label": "all and only claims covered",
                    "pass": coverage_score == 1.0,
                    "weight": 0.08,
                    "detail": sorted(by_id),
                },
                {
                    "id": "status",
                    "label": "claim statuses match evidence",
                    "pass": status_score == 1.0,
                    "weight": 0.24,
                    "detail": {"hits": status_hits},
                },
                {
                    "id": "sources",
                    "label": "primary sources match decisive evidence",
                    "pass": source_score == 1.0,
                    "weight": 0.14,
                    "detail": {"hits": source_hits},
                },
                {
                    "id": "locations",
                    "label": "evidence locations cite sections rows or fields",
                    "pass": location_score == 1.0,
                    "weight": 0.12,
                    "detail": {"hits": location_hits},
                },
                {
                    "id": "signals",
                    "label": "evidence signals contain decisive tokens",
                    "pass": evidence_score == 1.0,
                    "weight": 0.16,
                    "detail": {"hits": evidence_hits},
                },
                {
                    "id": "secondary",
                    "label": "multi-source claims include required secondary sources",
                    "pass": secondary_score == 1.0,
                    "weight": 0.08,
                    "detail": {"hits": secondary_hits},
                },
                {
                    "id": "repro_gaps",
                    "label": "not_reproducible claims cite missing artifacts",
                    "pass": repro_score == 1.0,
                    "weight": 0.05,
                    "detail": {"hits": repro_hits},
                },
                {
                    "id": "overstatement",
                    "label": "overstated claim preserves scope limitation",
                    "pass": over_score == 1.0,
                    "weight": 0.05,
                    "detail": {"hits": over_hits},
                },
            ]
        )
    except Exception as exc:
        checks.append(
            {
                "id": "csv_parse",
                "label": "claim_audit.csv parseable",
                "pass": False,
                "weight": 0.95,
                "detail": str(exc),
            }
        )

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        items = data.get("claims", []) if isinstance(data, dict) else []
        by_id = {
            str(item.get("claim_id", "")).strip(): item
            for item in items
            if isinstance(item, dict)
        }
        text = _row_text(data)
        ids_ok = len(items) == len(by_id) == len(gt["claims"]) and set(by_id) == set(
            gt["claims"]
        )
        matrix_format_ok = bool(
            ids_ok
            and all(
                {"claim_id", "status", "evidence", "reproducibility_note"} <= set(item)
                and bool(_evidence_entries(item.get("evidence")))
                and all(
                    isinstance(entry, dict)
                    and {
                        "source_file",
                        "location",
                        "supports_or_refutes",
                        "signal",
                    }
                    <= set(entry)
                    and all(
                        str(entry.get(field, "")).strip()
                        for field in (
                            "source_file",
                            "location",
                            "supports_or_refutes",
                            "signal",
                        )
                    )
                    for entry in _evidence_entries(item.get("evidence"))
                )
                for item in items
                if isinstance(item, dict)
            )
        )
        evidence_results: list[bool] = []
        for cid, expected in gt["claims"].items():
            item = by_id.get(cid, {})
            evidence = item.get("evidence")
            evidence_entries = _evidence_entries(evidence)
            raw_note = item.get("reproducibility_note")
            note = "" if raw_note is None else str(raw_note).strip()
            # The note is part of the published record schema, but it is not a
            # second mandatory place to repeat evidence.  A reproduction gap is
            # accepted when the cited evidence signal itself identifies the
            # missing artifact; token grounding below still rejects a blank note
            # paired with a vague signal such as "the package is incomplete".
            note_ok = "reproducibility_note" in item
            valid_items = bool(evidence_entries)
            if valid_items:
                valid_items = all(
                    isinstance(entry, dict)
                    and {
                        "source_file",
                        "location",
                        "supports_or_refutes",
                        "signal",
                    }.issubset(entry)
                    and _source_exists(entry.get("source_file"))
                    and str(entry.get("location", "")).strip()
                    and str(entry.get("signal", "")).strip()
                    and _relation_matches(
                        entry.get("supports_or_refutes"),
                        expected["status"],
                    )
                    for entry in evidence_entries
                )
            resolved_locations = [
                _located_source_text(
                    entry.get("source_file"),
                    entry.get("location"),
                )
                for entry in evidence_entries
                if isinstance(entry, dict)
            ]
            evidence_text = (
                _row_text(evidence)
                + " "
                + _norm(note)
                + " "
                + " ".join(resolved_locations)
            )
            explicit_evidence_text = _row_text(evidence) + " " + _norm(note)
            token_grounding_ok = _has_all(evidence_text, expected["tokens"])
            if expected["status"] == "not_reproducible":
                # For an insufficiency ruling, the handoff must say which
                # artifact is missing.  A locator that happens to point at a
                # source paragraph containing the fact is not enough when the
                # submitted signal itself only says "incomplete".
                token_grounding_ok = _has_all(
                    explicit_evidence_text,
                    expected["tokens"],
                )
            location_ok = any(
                resolved
                and (
                    not _has_csv_locator(
                        entry.get("source_file"), entry.get("location")
                    )
                    or _has_all(resolved, expected["location_tokens"])
                )
                for entry, resolved in zip(evidence_entries, resolved_locations)
                if isinstance(entry, dict)
            )
            claim_result = (
                bool(valid_items)
                and note_ok
                and _norm(item.get("status")) == expected["status"]
                and any(
                    isinstance(entry, dict)
                    and _source_matches(
                        entry.get("source_file"),
                        expected["primary_source"],
                    )
                    for entry in evidence_entries
                )
                and location_ok
                and token_grounding_ok
            )
            matrix_claim_results[cid] = bool(claim_result)
            evidence_results.append(bool(claim_result))
        evidence_fraction = (
            sum(evidence_results) / len(evidence_results) if evidence_results else 0.0
        )
        status_hits = sum(
            _norm(by_id.get(cid, {}).get("status")) == exp["status"]
            for cid, exp in gt["claims"].items()
        )
        gap_hits = sum(tok.lower() in text for tok in gt["repro_gap_tokens"])
        matrix_score = (
            0.20 * bool(ids_ok)
            + 0.40 * evidence_fraction
            + 0.25 * (status_hits / len(gt["claims"]))
            + 0.15 * min(gap_hits / len(gt["repro_gap_tokens"]), 1.0)
        )
        checks.append(
            {
                "id": "evidence_matrix_json",
                "label": "evidence_matrix.json mirrors claim statuses with evidence and repro gaps",
                "pass": matrix_score >= 0.85,
                "weight": 0.05,
                "detail": {
                    "score": round(matrix_score, 4),
                    "status_hits": status_hits,
                    "grounded_evidence": sum(evidence_results),
                    "total": len(evidence_results),
                },
            }
        )
    except Exception as exc:
        checks.append(
            {
                "id": "json_parse",
                "label": "evidence_matrix.json parseable",
                "pass": False,
                "weight": 0.05,
                "detail": str(exc),
            }
        )

    case_results: dict[str, bool] = {}
    for case_id, claim_ids in _COHORTS.items():
        missing_or_weak = sorted(
            claim_id
            for claim_id in claim_ids
            if not (
                csv_claim_results.get(claim_id, False)
                and matrix_claim_results.get(claim_id, False)
            )
        )
        case_results[case_id] = not missing_or_weak
        checks.append(
            {
                "id": case_id,
                "label": f"{case_id} claims are correctly adjudicated and grounded",
                "pass": not missing_or_weak,
                "weight": _CASE_WEIGHTS[case_id],
                "detail": {"missing_or_weak": missing_or_weak},
            }
        )

    multi_source_ids = {
        claim_id
        for claim_id, expected in gt["claims"].items()
        if expected["secondary_sources"]
    }
    missing_secondary = sorted(
        claim_id
        for claim_id in multi_source_ids
        if not secondary_results.get(claim_id, False)
    )
    case_results["cross_source_traceability"] = not missing_secondary
    checks.append(
        {
            "id": "cross_source_traceability",
            "label": "multi-source claims retain their secondary evidence trail",
            "pass": not missing_secondary,
            "weight": _CASE_WEIGHTS["cross_source_traceability"],
            "detail": {"missing_secondary": missing_secondary},
        }
    )

    audit_integrity = bool(
        format_score == 1.0 and coverage_score == 1.0 and matrix_format_ok
    )
    case_results["audit_integrity"] = audit_integrity
    checks.append(
        {
            "id": "audit_integrity",
            "label": "CSV and JSON audit records have complete published schemas",
            "pass": audit_integrity,
            "weight": _CASE_WEIGHTS["audit_integrity"],
            "detail": {
                "csv_format": format_score == 1.0,
                "csv_coverage": coverage_score == 1.0,
                "matrix_format": matrix_format_ok,
            },
        }
    )

    total = sum(
        _CASE_WEIGHTS[case_id] for case_id, passed in case_results.items() if passed
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
        "task": "060-research-claims-batch-evidence-audit",
        "workspace": str(w),
        "outcome_score": round(float(total), 4),
        "level": level,
        "checks": checks,
    }
