from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from harnessbench.grading.structured_io import (
    StructuredDataError,
    contains_control_or_format,
    portable_identifier,
    read_json_file,
    read_strict_csv,
    spreadsheet_formula_text,
)


TESTS = Path(__file__).resolve().parent
TRUTH = json.loads(
    (TESTS / "ground_truth" / "entities.json").read_text(encoding="utf-8")
)
INPUT_HASHES = json.loads(
    (TESTS / "ground_truth" / "input_hashes.json").read_text(encoding="utf-8")
)
HEADER = [
    "source_record_id",
    "canonical_report_id",
    "study_id",
    "normalized_doi",
    "record_status",
    "eligibility_decision",
    "exclusion_reason",
    "evidence",
]
FLOW_FIELDS = {
    "records_identified",
    "duplicate_records_removed",
    "reports_sought_for_retrieval",
    "reports_not_retrieved",
    "reports_assessed_for_eligibility",
    "reports_excluded",
    "included_reports",
    "included_studies",
    "flow_closes",
}
EXPECTED_REPORTS = {frozenset(report["members"]): report for report in TRUTH["reports"]}
EXPECTED_STUDIES = {frozenset(group) for group in TRUTH["studies"]}
SOURCE_IDS = set(TRUTH["source_ids"])
SOURCE_LOCATORS = {
    source_id: (
        f"pubmed_export.csv#{source_id}"
        if source_id.startswith("P")
        else f"scopus_export.ris#{source_id}"
    )
    for source_id in SOURCE_IDS
}
EVIDENCE_REQUIREMENTS = TRUTH["evidence_requirements"]
MAX_JSON_DEPTH = 64
MAX_JSON_NODES = 4096


def _observation(passed: bool, detail: object) -> dict[str, Any]:
    return {"pass": bool(passed), "detail": None if passed else detail}


def _unsafe_unicode(value: object) -> bool:
    stack: list[tuple[object, int]] = [(value, 0)]
    visited = 0
    while stack:
        item, depth = stack.pop()
        visited += 1
        if depth > MAX_JSON_DEPTH or visited > MAX_JSON_NODES:
            return True
        if isinstance(item, str):
            if contains_control_or_format(item):
                return True
        elif isinstance(item, dict):
            stack.extend((part, depth + 1) for pair in item.items() for part in pair)
        elif isinstance(item, list):
            stack.extend((part, depth + 1) for part in item)
    return False


def _artifact_safety_errors(path: Path, *, max_bytes: int, label: str) -> list[str]:
    """Identify transport hazards without treating ordinary schema errors as gates."""
    try:
        if path.is_symlink():
            return [f"{label} is a symbolic link"]
        if not path.is_file():
            return []
        if path.stat().st_size > max_bytes:
            return [f"{label} exceeds the bounded reader size"]
        raw = path.read_bytes()
    except OSError as exc:
        return [f"{label} safety audit failed: {type(exc).__name__}"]
    errors: list[str] = []
    if b"\x00" in raw:
        errors.append(f"{label} contains a NUL control byte")
    return errors


def _read_ledger(
    path: Path,
) -> tuple[dict[str, dict[str, str]], list[str], list[str]]:
    rows: dict[str, dict[str, str]] = {}
    errors: list[str] = []
    safety_errors = _artifact_safety_errors(path, max_bytes=64 * 1024, label="ledger")
    try:
        raw_rows = read_strict_csv(path, header=HEADER, max_bytes=64 * 1024)
        for line_number, raw in enumerate(raw_rows, start=2):
            if any(spreadsheet_formula_text(value) for value in raw.values()):
                safety_errors.append(f"row {line_number} has an unsafe CSV cell")
            source_id = raw["source_record_id"].strip()
            if not source_id or source_id in rows:
                errors.append(f"missing or duplicate source_record_id {source_id!r}")
                continue
            rows[source_id] = {field: raw[field].strip() for field in HEADER}
    except StructuredDataError as exc:
        errors.append(f"cannot parse ledger: {exc}")
    errors.extend(safety_errors)
    if set(rows) != SOURCE_IDS:
        errors.append(
            f"source coverage differs: missing={sorted(SOURCE_IDS - set(rows))}, "
            f"extra={sorted(set(rows) - SOURCE_IDS)}"
        )
    return rows, errors, safety_errors


def _read_flow(path: Path) -> tuple[dict[str, object], list[str], list[str]]:
    errors: list[str] = []
    safety_errors = _artifact_safety_errors(path, max_bytes=16 * 1024, label="flow")
    try:
        raw = read_json_file(path, max_bytes=16 * 1024)
    except StructuredDataError as exc:
        return {}, [f"cannot parse flow: {exc}"], safety_errors
    if not isinstance(raw, dict):
        return {}, ["flow is not an object"], safety_errors
    if set(raw) != FLOW_FIELDS:
        errors.append(
            f"flow fields differ: missing={sorted(FLOW_FIELDS - set(raw))}, "
            f"extra={sorted(set(raw) - FLOW_FIELDS)}"
        )
    if _unsafe_unicode(raw):
        safety_errors.append("flow contains unsafe Unicode or excessive JSON nesting")
    for field in FLOW_FIELDS - {"flow_closes"}:
        value = raw.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            errors.append(f"{field} must be a non-negative integer")
    if not isinstance(raw.get("flow_closes"), bool):
        errors.append("flow_closes must be boolean")
    errors.extend(safety_errors)
    return raw, errors, safety_errors


def _partition(rows: dict[str, dict[str, str]], field: str) -> set[frozenset[str]]:
    groups: dict[str, set[str]] = defaultdict(set)
    for source_id, row in rows.items():
        groups[row[field]].add(source_id)
    return {frozenset(group) for key, group in groups.items() if key}


def _report_resolution(
    rows: dict[str, dict[str, str]], ledger_errors: list[str]
) -> tuple[bool, list[str], set[frozenset[str]]]:
    errors = list(ledger_errors)
    partition = _partition(rows, "canonical_report_id")
    if any(
        not portable_identifier(row["canonical_report_id"]) for row in rows.values()
    ):
        errors.append("report IDs must be non-empty safe identifiers")
    if partition != set(EXPECTED_REPORTS):
        errors.append("report partition differs from the evidence partition")
    for members, expected in EXPECTED_REPORTS.items():
        if not members.issubset(rows):
            continue
        report_rows = [rows[source_id] for source_id in members]
        statuses = [row["record_status"] for row in report_rows]
        if (
            statuses.count("canonical") != 1
            or statuses.count("duplicate") != len(members) - 1
        ):
            errors.append(f"report {sorted(members)} lacks one canonical occurrence")
        if any(
            row["normalized_doi"].casefold() != expected["normalized_doi"]
            for row in report_rows
        ):
            errors.append(f"report {sorted(members)} has a wrong normalized DOI")
        for row in report_rows:
            if row["record_status"] == "duplicate" and (
                row["eligibility_decision"] != "duplicate_record"
                or row["exclusion_reason"] != "duplicate_source_record"
            ):
                errors.append(
                    f"report {sorted(members)} has malformed duplicate semantics"
                )
    return not errors, errors, partition


def _study_disposition(
    rows: dict[str, dict[str, str]], ledger_errors: list[str]
) -> tuple[bool, list[str]]:
    errors = list(ledger_errors)
    if any(not portable_identifier(row["study_id"]) for row in rows.values()):
        errors.append("study IDs must be non-empty safe identifiers")
    if _partition(rows, "study_id") != EXPECTED_STUDIES:
        errors.append("study partition differs from the evidence partition")
    for members, expected in EXPECTED_REPORTS.items():
        if not members.issubset(rows):
            continue
        canonical = [
            rows[item] for item in members if rows[item]["record_status"] == "canonical"
        ]
        if len(canonical) != 1:
            errors.append(f"report {sorted(members)} has no unique decision row")
            continue
        row = canonical[0]
        if row["eligibility_decision"] != expected["decision"]:
            errors.append(f"report {sorted(members)} has a wrong disposition")
        if row["exclusion_reason"] != expected["reason"]:
            errors.append(f"report {sorted(members)} violates reason precedence")
    return not errors, errors


def _derived_flow(
    rows: dict[str, dict[str, str]], report_partition: set[frozenset[str]]
) -> dict[str, object]:
    canonical = [row for row in rows.values() if row["record_status"] == "canonical"]
    included = [row for row in canonical if row["eligibility_decision"] == "include"]
    not_retrieved = sum(
        row["eligibility_decision"] == "not_retrieved" for row in canonical
    )
    excluded = sum(row["eligibility_decision"] == "exclude" for row in canonical)
    identified = len(rows)
    duplicates = sum(row["record_status"] == "duplicate" for row in rows.values())
    sought = len(report_partition)
    assessed = sought - not_retrieved
    closes = (
        identified - duplicates == sought
        and sought - not_retrieved == assessed
        and assessed - excluded == len(included)
    )
    return {
        "records_identified": identified,
        "duplicate_records_removed": duplicates,
        "reports_sought_for_retrieval": sought,
        "reports_not_retrieved": not_retrieved,
        "reports_assessed_for_eligibility": assessed,
        "reports_excluded": excluded,
        "included_reports": len(included),
        "included_studies": len({row["study_id"] for row in included}),
        "flow_closes": closes,
    }


def _source_report_provenance(
    rows: dict[str, dict[str, str]],
) -> tuple[bool, list[str]]:
    """Validate source-level provenance and duplicate-report occurrence lineage."""
    errors: list[str] = []
    if set(rows) != SOURCE_IDS:
        errors.append("source provenance does not cover the complete source-record set")
    parsed: dict[str, set[str]] = {}
    for source_id, row in rows.items():
        requirement = EVIDENCE_REQUIREMENTS.get(source_id)
        if source_id not in SOURCE_LOCATORS or not isinstance(requirement, dict):
            errors.append(f"{source_id} is not a visible source record")
            continue
        items = [item.strip() for item in row["evidence"].split(";")]
        locators = set(items)
        if not items or any(not item for item in items) or len(locators) != len(items):
            errors.append(f"{source_id} has empty or duplicate evidence locators")
        required = set(requirement["required"])
        allowed = set(requirement["allowed"])
        if not required.issubset(locators):
            errors.append(f"{source_id} omits its source-record evidence")
        if not locators.issubset(allowed):
            errors.append(f"{source_id} contains unrelated evidence")
        parsed[source_id] = locators
    for members in EXPECTED_REPORTS:
        if not members.issubset(rows):
            continue
        canonical = [
            item for item in members if rows[item]["record_status"] == "canonical"
        ]
        if len(canonical) == 1:
            required = {SOURCE_LOCATORS[item] for item in members}
            if not required.issubset(parsed.get(canonical[0], set())):
                errors.append(f"canonical report {sorted(members)} omits an occurrence")
    return not errors, errors


def _crosswalk_study_provenance(
    rows: dict[str, dict[str, str]],
) -> tuple[bool, list[str]]:
    """Validate the registry evidence needed for cross-report study linkage."""
    errors: list[str] = []
    for source_id, requirement in EVIDENCE_REQUIREMENTS.items():
        one_of = [set(group) for group in requirement["one_of"]]
        if not one_of:
            continue
        row = rows.get(source_id)
        if row is None:
            errors.append(f"{source_id} is missing from the crosswalk-dependent ledger")
            continue
        locators = {item.strip() for item in row["evidence"].split(";") if item.strip()}
        if any(locators.isdisjoint(group) for group in one_of):
            errors.append(f"{source_id} omits its registry crosswalk evidence")
    return not errors, errors


def evaluate_cases(workspace: Path) -> dict[str, object]:
    rows, ledger_errors, ledger_safety = _read_ledger(
        workspace / "screening_ledger.csv"
    )
    flow, flow_errors, flow_safety = _read_flow(workspace / "prisma_flow.json")
    reports_ok, report_errors, report_partition = _report_resolution(
        rows, ledger_errors
    )
    studies_ok, study_errors = _study_disposition(rows, ledger_errors)
    derived = _derived_flow(rows, report_partition)
    flow_ok = (
        not flow_errors
        and not ledger_errors
        and flow == derived
        and derived.get("flow_closes") is True
    )
    source_provenance_ok, source_provenance_errors = _source_report_provenance(rows)
    crosswalk_provenance_ok, crosswalk_provenance_errors = _crosswalk_study_provenance(
        rows
    )

    changed_inputs = [
        name
        for name, expected_hash in INPUT_HASHES.items()
        if not (workspace / name).is_file()
        or hashlib.sha256((workspace / name).read_bytes()).hexdigest() != expected_hash
    ]
    safety_errors = [*ledger_safety, *flow_safety]
    if changed_inputs:
        safety_errors.append(f"changed inputs: {changed_inputs}")

    return {
        "report_entity_resolution": _observation(reports_ok, report_errors),
        "study_linkage_and_disposition": _observation(studies_ok, study_errors),
        "closed_prisma_state": _observation(
            flow_ok,
            flow_errors or {"candidate": flow, "ledger_derived": derived},
        ),
        "source_report_provenance": _observation(
            source_provenance_ok, source_provenance_errors
        ),
        "crosswalk_study_provenance": _observation(
            crosswalk_provenance_ok, crosswalk_provenance_errors
        ),
        "safety_and_integrity": _observation(not safety_errors, safety_errors),
    }
