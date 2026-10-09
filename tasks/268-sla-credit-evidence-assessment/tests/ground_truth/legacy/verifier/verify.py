#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any


CASE_DIR = Path(__file__).resolve().parents[1]
INITIAL_MANIFEST = CASE_DIR / "environment" / "workspace_manifest.json"
DELIVERABLE = "outputs/sla_credit_assessment.json"
MAX_OUTPUT_BYTES = 65536
MAX_JSON_DEPTH = 40
MAX_WORKSPACE_BYTES = 16777216
MAX_WORKSPACE_ENTRIES = 128


class StrictJSONError(ValueError):
    pass


class TreeBudgetError(ValueError):
    pass


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StrictJSONError(f"duplicate key: {key}")
        result[key] = value
    return result


def reject_constant(value: str) -> Any:
    raise StrictJSONError(f"non-finite JSON constant: {value}")


def check_json_depth(text: str, maximum: int = MAX_JSON_DEPTH) -> None:
    depth = 0
    in_string = False
    escaped = False
    for character in text:
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character in "[{":
            depth += 1
            if depth > maximum:
                raise StrictJSONError("JSON nesting exceeds the maximum")
        elif character in "]}":
            depth -= 1
            if depth < 0:
                raise StrictJSONError("JSON delimiters are unbalanced")


def load_strict_json(path: Path, *, max_bytes: int = MAX_OUTPUT_BYTES) -> Any:
    size = path.stat().st_size
    if size > max_bytes:
        raise StrictJSONError("JSON exceeds the byte limit")
    text = path.read_text(encoding="utf-8")
    check_json_depth(text)
    try:
        return json.loads(
            text,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_constant,
        )
    except (json.JSONDecodeError, RecursionError, OverflowError) as exc:
        raise StrictJSONError(exc.__class__.__name__) from exc


def scan_tree(root: Path) -> dict[str, Any]:
    directories: dict[str, int] = {}
    files: dict[str, dict[str, Any]] = {}
    unsafe: list[str] = []
    scan_errors: list[str] = []
    entry_count = 0
    declared_bytes = 0

    def visit(directory: Path, prefix: str) -> None:
        nonlocal declared_bytes, entry_count
        try:
            with os.scandir(directory) as entries:
                ordered = sorted(entries, key=lambda entry: entry.name)
        except OSError as exc:
            scan_errors.append(f"{prefix or '.'}:{exc.__class__.__name__}")
            return
        for entry in ordered:
            entry_count += 1
            if entry_count > MAX_WORKSPACE_ENTRIES:
                raise TreeBudgetError(
                    f"entry_count_exceeded:{entry_count}>{MAX_WORKSPACE_ENTRIES}"
                )
            relative = f"{prefix}/{entry.name}" if prefix else entry.name
            try:
                mode = entry.stat(follow_symlinks=False).st_mode
            except OSError as exc:
                scan_errors.append(f"{relative}:{exc.__class__.__name__}")
                continue
            if stat.S_ISDIR(mode):
                directories[relative] = stat.S_IMODE(mode)
                visit(Path(entry.path), relative)
            elif stat.S_ISREG(mode):
                path = Path(entry.path)
                try:
                    size_bytes = entry.stat(follow_symlinks=False).st_size
                    declared_bytes += size_bytes
                    if size_bytes > MAX_WORKSPACE_BYTES:
                        raise TreeBudgetError(f"single_file_bytes_exceeded:{relative}")
                    if declared_bytes > MAX_WORKSPACE_BYTES:
                        raise TreeBudgetError(
                            f"workspace_bytes_exceeded:{declared_bytes}>{MAX_WORKSPACE_BYTES}"
                        )
                    files[relative] = {
                        "path": path,
                        "sha256": file_sha256(path),
                        "size_bytes": size_bytes,
                        "mode": stat.S_IMODE(mode),
                    }
                except OSError as exc:
                    scan_errors.append(f"{relative}:{exc.__class__.__name__}")
            else:
                unsafe.append(relative)
    try:
        visit(root, "")
    except TreeBudgetError as exc:
        scan_errors.append(str(exc))
    return {
        "directories": directories,
        "files": files,
        "unsafe": unsafe,
        "scan_errors": scan_errors,
        "entry_count": entry_count,
        "declared_bytes": declared_bytes,
    }


def exact_object(value: Any, fields: set[str]) -> bool:
    return isinstance(value, dict) and set(value) == fields


def exact_int(value: Any, expected: int) -> bool:
    return type(value) is int and value == expected


def exact_unique_string_set(value: Any, expected: set[str]) -> bool:
    return (
        isinstance(value, list)
        and all(isinstance(item, str) for item in value)
        and len(value) == len(set(value))
        and set(value) == expected
    )


def object_list_map(
    value: Any,
    *,
    id_field: str,
    fields: set[str],
) -> dict[str, dict[str, Any]] | None:
    if not isinstance(value, list):
        return None
    result: dict[str, dict[str, Any]] = {}
    for item in value:
        if not exact_object(item, fields) or not isinstance(item[id_field], str):
            return None
        identifier = item[id_field]
        if identifier in result:
            return None
        result[identifier] = item
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    workspace = args.workspace.resolve(strict=True)
    manifest = load_strict_json(INITIAL_MANIFEST, max_bytes=131072)
    expected_files = {entry["path"]: entry for entry in manifest["files"]}
    expected_directories = {entry["path"]: entry for entry in manifest["directories"]}
    observed = scan_tree(workspace)
    observed_files: dict[str, dict[str, Any]] = observed["files"]
    observed_directories: dict[str, int] = observed["directories"]
    checks: list[dict[str, Any]] = []

    def add(check_id: str, passed: bool, detail: str) -> None:
        checks.append({"check_id": check_id, "passed": bool(passed), "detail": detail})

    add(
        "workspace_tree_scan_complete",
        not observed["scan_errors"],
        f"scan_error_count={len(observed['scan_errors'])}",
    )
    add(
        "workspace_no_unsafe_entries",
        not observed["unsafe"],
        f"unsafe_count={len(observed['unsafe'])}",
    )
    allowed_directories = set(expected_directories) | {"outputs"}
    add(
        "workspace_directories_exact",
        set(observed_directories) == allowed_directories,
        f"unexpected={sorted(set(observed_directories) - allowed_directories)},missing={sorted(allowed_directories - set(observed_directories))}",
    )
    allowed_files = set(expected_files) | {DELIVERABLE}
    add(
        "workspace_files_exact",
        set(observed_files) == allowed_files,
        f"unexpected={sorted(set(observed_files) - allowed_files)},missing={sorted(allowed_files - set(observed_files))}",
    )
    protected_ok = True
    for relative, entry in expected_files.items():
        actual = observed_files.get(relative)
        if actual is None or any(
            actual[field] != entry[field]
            for field in ("sha256", "size_bytes", "mode")
        ):
            protected_ok = False
    for relative, entry in expected_directories.items():
        if observed_directories.get(relative) != entry["mode"]:
            protected_ok = False
    add("protected_inputs_unchanged", protected_ok, "initial bytes, sizes and modes must remain exact")
    total_bytes = sum(int(entry["size_bytes"]) for entry in observed_files.values())
    add(
        "workspace_size_limit",
        total_bytes <= MAX_WORKSPACE_BYTES,
        f"observed_bytes={total_bytes},limit_bytes={MAX_WORKSPACE_BYTES}",
    )

    output_path = workspace / DELIVERABLE
    output_entry = observed_files.get(DELIVERABLE)
    output_regular = output_entry is not None and output_entry["size_bytes"] <= MAX_OUTPUT_BYTES
    add("deliverable_regular_file", output_regular, "required JSON must be a regular file <= 64 KiB")
    output: Any = None
    strict_error = "none"
    if output_regular:
        try:
            output = load_strict_json(output_path)
        except (OSError, UnicodeError, StrictJSONError) as exc:
            strict_error = exc.__class__.__name__
    add(
        "deliverable_strict_json",
        isinstance(output, dict),
        f"strict_parse_error={strict_error}",
    )

    inputs = workspace / "inputs"
    try:
        rules = load_strict_json(inputs / "sla_rules.json", max_bytes=131072)
        projection = load_strict_json(inputs / "nonbinding_sales_projection.json", max_bytes=131072)
        with (inputs / "region_registry.csv").open(encoding="utf-8", newline="") as stream:
            regions = list(csv.DictReader(stream))
        records = [
            json.loads(
                line,
                object_pairs_hook=reject_duplicate_keys,
                parse_constant=reject_constant,
            )
            for line in (inputs / "service_events_2025_q3.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]
        contract_id = str(rules["contract_id"])
        quarter = str(rules["quarter"])
        region_id = str(rules["target_region_id"])
        registry_ok = any(
            row["region_id"] == region_id
            and row["contract_id"] == contract_id
            and row["service_tier"] == "mission_critical"
            and row["active"] == "true"
            for row in regions
        )
        eligibility = rules["eligibility"]
        grace = int(eligibility["per_event_grace_minutes"])
        eligible_details: dict[str, dict[str, Any]] = {}
        excluded_expected: dict[str, str] = {}
        for record in records:
            event_id = str(record["event_id"])
            if record.get("region_id") != region_id:
                excluded_expected[event_id] = "out_of_scope_region"
            elif record.get("validated") is not True:
                excluded_expected[event_id] = "unvalidated_record"
            elif record.get("event_type") != eligibility["included_event_type"]:
                excluded_expected[event_id] = "scheduled_maintenance"
            else:
                duration = int(record["duration_minutes"])
                eligible_details[event_id] = {
                    "event_id": event_id,
                    "severity": str(record["severity"]),
                    "duration_minutes": duration,
                    "grace_minutes": grace,
                    "eligible_minutes": max(0, duration - grace),
                }
        eligible_ids = set(eligible_details)
        eligible_total = sum(item["eligible_minutes"] for item in eligible_details.values())
        p1_ids = {event_id for event_id, item in eligible_details.items() if item["severity"] == "P1"}
        credit_rule = rules["credit"]
        rate = int(credit_rule["rate_cny_per_eligible_minute"])
        base_credit = eligible_total * rate
        repeat_triggered = len(eligible_ids) >= int(credit_rule["repeat_incident_threshold"])
        numerator = int(credit_rule["multiplier_numerator"]) if repeat_triggered else 1
        denominator = int(credit_rule["multiplier_denominator"]) if repeat_triggered else 1
        if denominator <= 0 or (base_credit * numerator) % denominator:
            raise ValueError("invalid exact credit multiplier")
        final_credit = base_credit * numerator // denominator
        credit_rule_ids = {str(credit_rule["base_rule_id"])}
        if repeat_triggered:
            credit_rule_ids.add(str(credit_rule["repeat_rule_id"]))
        remediation_rule = rules["remediation"]
        remediation_triggered = (
            len(p1_ids) >= int(remediation_rule["minimum_p1_events"])
            and eligible_total >= int(remediation_rule["minimum_total_eligible_minutes"])
        )
        expected_level = str(
            remediation_rule["triggered_level"]
            if remediation_triggered
            else remediation_rule["default_level"]
        )
        expected_due = int(
            remediation_rule["triggered_due_business_days"]
            if remediation_triggered
            else remediation_rule["default_due_business_days"]
        )
        expected_ignored = {
            str(item["source_id"]): str(item["reason_code"])
            for item in rules["ignored_sources"]
        }
        projection_ok = projection.get("source_id") in expected_ignored
        environment_valid = registry_ok and projection_ok
    except (
        KeyError,
        TypeError,
        ValueError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        StrictJSONError,
        RecursionError,
    ):
        environment_valid = False
        contract_id = quarter = region_id = expected_level = ""
        eligible_details = {}
        eligible_ids = p1_ids = credit_rule_ids = set()
        excluded_expected = expected_ignored = {}
        eligible_total = rate = base_credit = numerator = denominator = final_credit = expected_due = 0
        credit_rule = remediation_rule = {}
    add("trusted_environment_parse", environment_valid, "protected visible inputs must be internally consistent")

    top_fields = {
        "schema_version",
        "contract_id",
        "quarter",
        "region_id",
        "event_assessment",
        "credit",
        "remediation",
        "excluded_records",
        "ignored_sources",
    }
    shape_ok = exact_object(output, top_fields)
    if shape_ok:
        shape_ok = (
            exact_object(
                output["event_assessment"],
                {"eligible_event_ids", "eligible_minutes_by_event", "eligible_minutes_total", "p1_event_count"},
            )
            and exact_object(
                output["credit"],
                {
                    "rate_cny_per_minute",
                    "base_credit_cny",
                    "repeat_incident_threshold",
                    "eligible_event_count",
                    "multiplier_numerator",
                    "multiplier_denominator",
                    "final_credit_cny",
                    "triggered_rule_ids",
                    "evidence_ids",
                },
            )
            and exact_object(
                output["remediation"],
                {"level", "due_business_days", "triggered_rule_id", "evidence_ids"},
            )
        )
    add("output_shape", shape_ok, "output must exactly match the visible v2 field contract")

    def get(path: tuple[str, ...], default: Any = None) -> Any:
        value = output
        for key in path:
            if not isinstance(value, dict) or key not in value:
                return default
            value = value[key]
        return value

    add(
        "contract_identity",
        get(("schema_version",)) == "case14_sla_credit_assessment_v2"
        and get(("contract_id",)) == contract_id
        and get(("quarter",)) == quarter
        and get(("region_id",)) == region_id,
        "contract, quarter, region and schema must match fixed inputs",
    )
    add(
        "eligible_event_set",
        exact_unique_string_set(get(("event_assessment", "eligible_event_ids")), eligible_ids),
        "eligible event IDs must be an exact unordered set",
    )
    observed_details = object_list_map(
        get(("event_assessment", "eligible_minutes_by_event")),
        id_field="event_id",
        fields={"event_id", "severity", "duration_minutes", "grace_minutes", "eligible_minutes"},
    )
    detail_ok = observed_details is not None and set(observed_details) == set(eligible_details)
    if detail_ok:
        for event_id, expected in eligible_details.items():
            actual = observed_details[event_id]
            if not (
                actual["severity"] == expected["severity"]
                and all(
                    exact_int(actual[field], int(expected[field]))
                    for field in ("duration_minutes", "grace_minutes", "eligible_minutes")
                )
            ):
                detail_ok = False
    add("eligible_minutes_by_event", detail_ok, "per-event grace and eligible minutes must be exact")
    add(
        "eligible_aggregate",
        exact_int(get(("event_assessment", "eligible_minutes_total")), eligible_total)
        and exact_int(get(("event_assessment", "p1_event_count")), len(p1_ids)),
        "eligible-minute total and P1 count must be exact",
    )
    add(
        "credit_calculation",
        exact_int(get(("credit", "rate_cny_per_minute")), rate)
        and exact_int(get(("credit", "base_credit_cny")), base_credit)
        and exact_int(
            get(("credit", "repeat_incident_threshold")),
            int(credit_rule.get("repeat_incident_threshold", 0)),
        )
        and exact_int(get(("credit", "eligible_event_count")), len(eligible_ids))
        and exact_int(get(("credit", "multiplier_numerator")), numerator)
        and exact_int(get(("credit", "multiplier_denominator")), denominator)
        and exact_int(get(("credit", "final_credit_cny")), final_credit),
        "base credit and exact rational repeat multiplier must be correct",
    )
    add(
        "credit_rule_evidence",
        exact_unique_string_set(get(("credit", "triggered_rule_ids")), credit_rule_ids)
        and exact_unique_string_set(get(("credit", "evidence_ids")), eligible_ids),
        "credit rules and evidence must be exact unordered sets",
    )
    remediation_rule_id = str(remediation_rule.get("rule_id", ""))
    add(
        "remediation_rule",
        get(("remediation", "level")) == expected_level
        and exact_int(get(("remediation", "due_business_days")), expected_due)
        and get(("remediation", "triggered_rule_id")) == remediation_rule_id
        and exact_unique_string_set(
            get(("remediation", "evidence_ids")),
            p1_ids | {remediation_rule_id},
        ),
        "P1/eligible-minute trigger must determine level, deadline and evidence",
    )
    excluded_map = object_list_map(
        get(("excluded_records",)),
        id_field="event_id",
        fields={"event_id", "reason_code"},
    )
    add(
        "excluded_records_exact",
        excluded_map is not None
        and {key: value["reason_code"] for key, value in excluded_map.items()} == excluded_expected,
        "excluded event records and reason codes must match exactly with no extras or duplicates",
    )
    ignored_map = object_list_map(
        get(("ignored_sources",)),
        id_field="source_id",
        fields={"source_id", "reason_code"},
    )
    add(
        "ignored_sources_exact",
        ignored_map is not None
        and {key: value["reason_code"] for key, value in ignored_map.items()} == expected_ignored,
        "ignored non-contractual sources must match exactly with no extras or duplicates",
    )

    passed = all(check["passed"] for check in checks)
    result = {
        "schema_version": "case14_verifier_result_v2",
        "passed": passed,
        "checks": checks,
        "summary": {
            "total": len(checks),
            "passed": sum(check["passed"] for check in checks),
            "failed": sum(not check["passed"] for check in checks),
        },
    }
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
