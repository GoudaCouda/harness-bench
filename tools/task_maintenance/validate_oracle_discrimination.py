#!/usr/bin/env python3
"""Check that task oracles distinguish valid-looking wrong work from reference work.

The baseline quality audit proves that empty, untouched, malformed, and reference
workspaces behave correctly.  This companion audit starts from the complete
reference workspace and applies one parseable semantic mutation at a time.  It
detects declared artifacts that are present but effectively ungraded, missing
workspace-mutation gates, and legacy all-or-nothing scoring that prevents useful
failure analysis.  Formal outcome-case tasks instead provide boolean case-level
diagnostics and may correctly gate a structurally corrupted artifact to zero.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import yaml

from common import iter_task_yamls, load_task_metadata, score_task_workspace
from harnessbench.grading.oracle_contract import (
    normalize_required_artifacts,
    workspace_manifest,
    workspace_mutation_report,
)
from validate_oracle_quality import make_workspace


ROOT = Path(__file__).resolve().parents[2]
CLOSED_WORKSPACE_CONFIGS = {
    "bridge.json": ("protected_files", "outputs"),
    "native.json": ("protected_files", "required_artifacts"),
}


def oracle_enforces_closed_workspace(task_dir: Path) -> bool:
    """True when the hidden oracle rejects files outside a declared allowlist."""
    for name, keys in CLOSED_WORKSPACE_CONFIGS.items():
        path = task_dir / "tests" / "ground_truth" / name
        if path.is_file():
            config = json.loads(path.read_text(encoding="utf-8"))
            if all(key in config for key in keys):
                return True
    return False


def _wrong_scalar(value: Any) -> Any:
    if isinstance(value, bool):
        return not value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value + 997
    if value is None:
        return "__WRONG__"
    if isinstance(value, str):
        return "__WRONG__" if value != "__WRONG__" else "__OTHER_WRONG__"
    return value


def _wrong_tree(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _wrong_tree(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_wrong_tree(child) for child in value]
    return _wrong_scalar(value)


def _mutate_office_package(path: Path) -> None:
    """Keep an Office package valid while replacing its user-visible content."""
    suffix = path.suffix.lower()
    part_prefixes = {
        ".docx": ("word/document.xml",),
        ".pptx": ("ppt/slides/slide",),
        ".xlsx": ("xl/sharedStrings.xml", "xl/worksheets/sheet"),
    }
    prefixes = part_prefixes[suffix]
    output = io.BytesIO()
    changed_nodes = 0
    with (
        zipfile.ZipFile(path, "r") as source,
        zipfile.ZipFile(
            output,
            "w",
        ) as destination,
    ):
        for info in source.infolist():
            payload = source.read(info.filename)
            if info.filename.endswith(".xml") and any(
                info.filename.startswith(prefix) for prefix in prefixes
            ):
                root = ET.fromstring(payload)
                for node in root.iter():
                    local_name = node.tag.rsplit("}", 1)[-1]
                    if local_name in {"t", "v"} and (node.text or "").strip():
                        node.text = "__WRONG__"
                        changed_nodes += 1
                payload = ET.tostring(
                    root,
                    encoding="utf-8",
                    xml_declaration=True,
                )
            destination.writestr(info, payload)
    if changed_nodes == 0:
        raise ValueError(f"no mutable Office content found in {path}")
    path.write_bytes(output.getvalue())


def mutate_file(path: Path) -> None:
    """Keep common serialization formats parseable while changing their meaning."""
    suffix = path.suffix.lower()
    if suffix in {".docx", ".pptx", ".xlsx"}:
        _mutate_office_package(path)
        return
    if suffix == ".json":
        value = json.loads(path.read_text(encoding="utf-8"))
        path.write_text(
            json.dumps(_wrong_tree(value), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return
    if suffix == ".csv":
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = list(reader.fieldnames or [])
            rows = list(reader)
        if not fieldnames:
            path.write_text("wrong\n__WRONG__\n", encoding="utf-8")
            return
        # Preserve likely key columns so keyed oracles can still align rows and
        # award diagnostic partial credit for unaffected work items/artifacts.
        mutable = [
            name
            for name in fieldnames
            if name.casefold()
            not in {"id", "item_id", "record_id", "case_id", "task_id"}
        ] or fieldnames[-1:]
        for row in rows:
            for name in mutable:
                row[name] = "__WRONG__"
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=fieldnames,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
        path.write_text(output.getvalue(), encoding="utf-8")
        return
    if suffix in {".yaml", ".yml"}:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        path.write_text(
            yaml.safe_dump(_wrong_tree(value), sort_keys=False),
            encoding="utf-8",
        )
        return
    try:
        path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        payload = bytearray(path.read_bytes())
        if payload:
            payload[0] ^= 0x01
        else:
            payload.extend(b"wrong")
        path.write_bytes(bytes(payload))
    else:
        path.write_text(
            "# Incorrect synthetic candidate\n\n"
            "No required decision or evidence was verified.\n",
            encoding="utf-8",
        )


def mutate_artifact(workspace: Path, artifact: str) -> bool:
    path = workspace / artifact.rstrip("/")
    if path.is_file():
        mutate_file(path)
        return True
    if path.is_dir():
        files = sorted(child for child in path.rglob("*") if child.is_file())
        if not files:
            (path / "incorrect.txt").write_text("__WRONG__\n", encoding="utf-8")
        else:
            for child in files:
                mutate_file(child)
        return True
    return False


def score_result(
    task_dir: Path, metadata: dict[str, Any], workspace: Path
) -> dict[str, Any]:
    result = score_task_workspace(task_dir, metadata, workspace)
    raw = result.get("outcome_score")
    return {
        "score": float(raw) if isinstance(raw, (int, float)) else None,
        "oracle_contract_failure": bool(result.get("oracle_contract_failure")),
        "oracle_infrastructure_failure": bool(
            result.get("oracle_infrastructure_failure")
        ),
    }


def audit_task(
    task_dir: Path,
    metadata: dict[str, Any],
    *,
    require_partial_credit: bool,
) -> dict[str, Any]:
    reference, cleanup = make_workspace(task_dir, metadata, "reference")
    try:
        baseline_result = score_result(task_dir, metadata, reference)
        baseline = baseline_result["score"]
        artifacts = normalize_required_artifacts(
            [
                str(value).strip().replace("\\", "/")
                for value in metadata.get("required_artifacts", [])
            ]
        )
        artifact_cases: list[dict[str, Any]] = []
        for artifact in artifacts:
            candidate, candidate_cleanup = make_workspace(
                task_dir,
                metadata,
                "reference",
            )
            try:
                mutated = mutate_artifact(candidate, artifact)
                first_result = score_result(task_dir, metadata, candidate)
                second_result = score_result(task_dir, metadata, candidate)
                first = first_result["score"]
            finally:
                for root in candidate_cleanup:
                    shutil.rmtree(root, ignore_errors=True)
            artifact_cases.append(
                {
                    "artifact": artifact,
                    "mutated": mutated,
                    "score": first,
                    "deterministic": first_result == second_result,
                    "oracle_contract_failure": first_result["oracle_contract_failure"],
                    "oracle_infrastructure_failure": first_result[
                        "oracle_infrastructure_failure"
                    ],
                    "discriminated": (
                        mutated
                        and isinstance(first, float)
                        and isinstance(baseline, float)
                        and first < baseline
                    ),
                    "partial_credit": isinstance(first, float) and 0 < first < 1,
                }
            )

        tampered, tampered_cleanup = make_workspace(
            task_dir,
            metadata,
            "reference",
        )
        try:
            before_tamper = workspace_manifest(tampered)
            marker = tampered / "_oracle_mutation_probe.txt"
            marker.write_text("unexpected workspace mutation\n", encoding="utf-8")
            mutation = workspace_mutation_report(
                before_tamper,
                workspace_manifest(tampered),
                contract=metadata.get("mutation_contract"),
            )
            mutation_result = score_task_workspace(
                task_dir,
                metadata,
                tampered,
                workspace_mutation=mutation,
            )
            raw_mutation_score = mutation_result.get("outcome_score")
            workspace_mutation_score = (
                float(raw_mutation_score)
                if isinstance(raw_mutation_score, (int, float))
                else None
            )
            mutation_contract_failure = bool(
                mutation_result.get("oracle_contract_failure")
            )
            mutation_infrastructure_failure = bool(
                mutation_result.get("oracle_infrastructure_failure")
            )
        finally:
            for root in tampered_cleanup:
                shutil.rmtree(root, ignore_errors=True)

        blocked = bool(
            baseline_result["oracle_infrastructure_failure"]
            or mutation_infrastructure_failure
            or any(case["oracle_infrastructure_failure"] for case in artifact_cases)
        )
        failures: list[str] = []
        if blocked:
            failures.append("trusted_dependency_unavailable")
        else:
            if baseline_result["oracle_contract_failure"]:
                failures.append("reference_oracle_contract_failure")
            if baseline != 1.0:
                failures.append(f"reference_score={baseline}")
            for case in artifact_cases:
                if case["oracle_contract_failure"]:
                    failures.append(f"oracle_contract_failure={case['artifact']}")
                elif not case["mutated"]:
                    failures.append(f"missing_reference_artifact={case['artifact']}")
                elif not case["deterministic"]:
                    failures.append(f"nondeterministic={case['artifact']}")
                elif not case["discriminated"]:
                    failures.append(f"ungraded_artifact={case['artifact']}")
            formal_outcome = bool(str(metadata.get("outcome_test") or "").strip())
            expected_mutation_score = (
                baseline
                if formal_outcome and not oracle_enforces_closed_workspace(task_dir)
                else 0.0
            )
            if mutation_contract_failure:
                failures.append("workspace_mutation_oracle_contract_failure")
            elif workspace_mutation_score != expected_mutation_score:
                failures.append(
                    "workspace_mutation_score="
                    f"{workspace_mutation_score} expected={expected_mutation_score}"
                )
            if (
                require_partial_credit
                and artifact_cases
                and not any(case["partial_credit"] for case in artifact_cases)
            ):
                failures.append("no_parseable_partial_credit_case")
        return {
            "task_id": metadata["task_id"],
            "reference_score": baseline,
            "artifact_cases": artifact_cases,
            "workspace_mutation_score": workspace_mutation_score,
            "failures": failures,
            "blocked": blocked,
            "pass": not failures,
        }
    finally:
        for root in cleanup:
            shutil.rmtree(root, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--min-task-number",
        type=int,
        default=1,
        help="audit tasks at or above this numeric ID (default: the full suite)",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=(ROOT / "artifacts" / "audits" / "oracle-discrimination.json"),
    )
    args = parser.parse_args()

    rows: list[dict[str, Any]] = []
    for task_yaml in iter_task_yamls():
        number = int(task_yaml.parent.name.split("-", 1)[0])
        if number < args.min_task_number:
            continue
        metadata = load_task_metadata(task_yaml)
        # Formal outcome-case tasks already expose case-level diagnostics, and
        # each artifact is owned by one or more coherent business blocks.
        # Corrupting an entire artifact may therefore lose several blocks and
        # naturally reach zero; this audit must not impose an artificial
        # positive floor. Legacy scalar oracles still need the old probe because
        # their individual checks are the only diagnostic surface available.
        partial_credit_required = not bool(
            str(metadata.get("outcome_test") or "").strip()
        )
        row = audit_task(
            task_yaml.parent,
            metadata,
            require_partial_credit=partial_credit_required,
        )
        row["partial_credit_required"] = partial_credit_required
        rows.append(row)
        details = ", ".join(
            f"{case['artifact']}={case['score']}" for case in row["artifact_cases"]
        )
        state = "PASS" if row["pass"] else ("BLOCKED" if row["blocked"] else "FAIL")
        suffix = "" if row["pass"] else " [" + ", ".join(row["failures"]) + "]"
        print(
            f"{state} {row['task_id']}: reference={row['reference_score']}, "
            f"workspace_mutation={row['workspace_mutation_score']}, "
            f"{details}{suffix}"
        )

    payload = {
        "schema_version": 1,
        "min_task_number": args.min_task_number,
        "task_count": len(rows),
        "passed": sum(row["pass"] for row in rows),
        "blocked": sum(row["blocked"] for row in rows),
        "failed": sum(not row["pass"] for row in rows),
        "tasks": rows,
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"tasks={payload['task_count']} passed={payload['passed']} "
        f"failed={payload['failed']}"
    )
    print(f"report={args.json_out}")
    if payload["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
