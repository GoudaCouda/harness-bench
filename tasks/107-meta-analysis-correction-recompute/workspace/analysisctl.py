#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
SOURCE_HASHES = {
    "policy.md": "8e0fdef82956f0fc1f05ec48e799f54e0ecef8fcedf4e147d7ed791c822d88d6",
    "protocol.json": "7186e018c22c9a2dd88c83e1796e65649860832ef894b6af61095071656fa8f1",
    "extraction_catalog.json": "14fdd61b60ad2521b5255b36f9e46c91ddc1807fb9141d6393ba3018afc14016",
    "correction_notices.json": "e9a00bae464e6733806da433dfb3d05a4d02c46f6bdd50b35282ef361b1962fc",
    "prior_analysis.json": "11255f467ed917bc922899265f513b40d1523a4813ed19f5a12a135f3c3eb215",
    "publication_claims.json": "b72b1e2508ea454ed1c030ec82be5dadada8caf1dcce72c894d727678d2560a7",
}
GENERATED = (
    "analysis_manifest.json",
    "meta_analysis.json",
    "sensitivity.csv",
    "forest_plot.svg",
    "claim_updates.json",
    "update_handoff.md",
)
BUILD_OUTPUTS = GENERATED[:4]
EVIDENCE_RE = re.compile(r"^[A-Za-z0-9_.-]+#[A-Za-z0-9_.:-]+$")
Z95 = 1.959963984540054


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def load_json(name: str) -> Any:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def source_errors() -> list[str]:
    errors = []
    for name, expected in SOURCE_HASHES.items():
        path = ROOT / name
        if not path.is_file() or sha256(path) != expected:
            errors.append(f"protected source changed: {name}")
    return errors


def source_bundle_sha256() -> str:
    payload = json.dumps(
        SOURCE_HASHES, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def evidence_ok(
    values: Any, required: set[str], *, allow_generated: bool = False
) -> bool:
    if not isinstance(values, list) or not values:
        return False
    normalized = {str(value) for value in values}
    if not required.issubset(normalized):
        return False
    return all(
        EVIDENCE_RE.fullmatch(value)
        and (allow_generated or value.split("#", 1)[0] not in GENERATED)
        for value in normalized
    )


def validate_manifest(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    errors = source_errors()
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, [*errors, f"manifest is not valid JSON: {exc}"]
    protocol = load_json("protocol.json")
    catalog = load_json("extraction_catalog.json")
    corrections = load_json("correction_notices.json")
    by_id = {row["record_id"]: row for row in catalog}
    if manifest.get("analysis_id") != protocol["analysis_id"]:
        errors.append("analysis_id does not match protocol")
    if str(manifest.get("protocol_version")) != str(protocol["protocol_version"]):
        errors.append("protocol_version does not match")
    included = manifest.get("included_records")
    excluded = manifest.get("excluded_records")
    chain = manifest.get("correction_chain")
    if not isinstance(included, list):
        included = []
        errors.append("included_records must be a list")
    if not isinstance(excluded, list):
        excluded = []
        errors.append("excluded_records must be a list")
    if not isinstance(chain, list):
        chain = []
        errors.append("correction_chain must be a list")

    included_ids: list[str] = []
    included_studies: list[str] = []
    for index, item in enumerate(included):
        if not isinstance(item, dict):
            errors.append(f"included_records[{index}] must be an object")
            continue
        record_id = str(item.get("record_id", ""))
        row = by_id.get(record_id)
        if row is None:
            errors.append(f"unknown included record: {record_id}")
            continue
        included_ids.append(record_id)
        included_studies.append(str(item.get("study_id", "")))
        if item.get("study_id") != row["study_id"]:
            errors.append(f"study_id mismatch for {record_id}")
        if row["status"] != "eligible_primary":
            errors.append(f"record is not eligible_primary: {record_id}")
        for field in ("population", "outcome", "timepoint_months"):
            target = protocol[field]
            if row[field] != target:
                errors.append(f"protocol {field} mismatch for {record_id}")
        if not evidence_ok(item.get("evidence"), {row["evidence_ref"]}):
            errors.append(f"missing local extraction evidence for {record_id}")
    if len(included_ids) != len(set(included_ids)):
        errors.append("included record IDs must be unique")
    if len(included_studies) != len(set(included_studies)):
        errors.append("included study IDs must be unique")
    expected_included = {
        row["record_id"]
        for row in catalog
        if row["status"] == "eligible_primary"
        and row["population"] == protocol["population"]
        and row["outcome"] == protocol["outcome"]
        and row["timepoint_months"] == protocol["timepoint_months"]
    }
    if set(included_ids) != expected_included:
        missing = sorted(expected_included - set(included_ids))
        extra = sorted(set(included_ids) - expected_included)
        errors.append(f"eligible inclusion set mismatch; missing={missing} extra={extra}")

    excluded_ids: list[str] = []
    for index, item in enumerate(excluded):
        if not isinstance(item, dict):
            errors.append(f"excluded_records[{index}] must be an object")
            continue
        record_id = str(item.get("record_id", ""))
        row = by_id.get(record_id)
        if row is None:
            errors.append(f"unknown excluded record: {record_id}")
            continue
        excluded_ids.append(record_id)
        if not str(item.get("reason", "")).strip():
            errors.append(f"missing exclusion reason for {record_id}")
        if not evidence_ok(item.get("evidence"), {row["evidence_ref"]}):
            errors.append(f"missing local exclusion evidence for {record_id}")
    if len(excluded_ids) != len(set(excluded_ids)):
        errors.append("excluded record IDs must be unique")
    expected_excluded = set(by_id) - expected_included
    if set(excluded_ids) != expected_excluded:
        missing = sorted(expected_excluded - set(excluded_ids))
        extra = sorted(set(excluded_ids) - expected_excluded)
        errors.append(f"catalog exclusion set mismatch; missing={missing} extra={extra}")
    if set(included_ids) & set(excluded_ids):
        errors.append("a record cannot be included and excluded")

    relevant = next(
        row for row in corrections if row["correction_id"] == "CORR-BOREALIS-2026-02"
    )
    if len(chain) != 1 or not isinstance(chain[0], dict):
        errors.append("correction_chain must contain exactly the scoped primary correction")
    else:
        item = chain[0]
        required_values = {
            relevant["evidence_ref"],
            by_id[relevant["applies_to"]]["evidence_ref"],
            by_id[relevant["replacement"]]["evidence_ref"],
        }
        expected = {
            "correction_id": relevant["correction_id"],
            "superseded_record_id": relevant["applies_to"],
            "replacement_record_id": relevant["replacement"],
        }
        for key, value in expected.items():
            if item.get(key) != value:
                errors.append(f"correction_chain {key} mismatch")
        if not evidence_ok(item.get("evidence"), required_values):
            errors.append("correction_chain evidence is incomplete")
    return manifest, errors


def study_effect(row: dict[str, Any]) -> tuple[float, float]:
    intervention = row["intervention"]
    control = row["control"]
    a = float(intervention["events"])
    n1 = float(intervention["total"])
    c = float(control["events"])
    n0 = float(control["total"])
    if a == 0 or c == 0:
        a += 0.5
        c += 0.5
        n1 += 1.0
        n0 += 1.0
    log_rr = math.log((a / n1) / (c / n0))
    variance = 1.0 / a - 1.0 / n1 + 1.0 / c - 1.0 / n0
    return log_rr, variance


def pool(rows: list[dict[str, Any]]) -> dict[str, float]:
    effects = [study_effect(row) for row in rows]
    fixed_weights = [1.0 / variance for _, variance in effects]
    fixed_mean = sum(
        weight * effect[0] for weight, effect in zip(fixed_weights, effects, strict=True)
    ) / sum(fixed_weights)
    q_value = sum(
        weight * (effect[0] - fixed_mean) ** 2
        for weight, effect in zip(fixed_weights, effects, strict=True)
    )
    degrees = len(rows) - 1
    denominator = sum(fixed_weights) - sum(
        weight**2 for weight in fixed_weights
    ) / sum(fixed_weights)
    tau_squared = max(0.0, (q_value - degrees) / denominator) if denominator else 0.0
    random_weights = [1.0 / (variance + tau_squared) for _, variance in effects]
    random_mean = sum(
        weight * effect[0] for weight, effect in zip(random_weights, effects, strict=True)
    ) / sum(random_weights)
    standard_error = math.sqrt(1.0 / sum(random_weights))
    i_squared = max(0.0, (q_value - degrees) / q_value * 100.0) if q_value else 0.0
    return {
        "log_risk_ratio": random_mean,
        "risk_ratio": math.exp(random_mean),
        "ci_low": math.exp(random_mean - Z95 * standard_error),
        "ci_high": math.exp(random_mean + Z95 * standard_error),
        "standard_error": standard_error,
        "q": q_value,
        "degrees_of_freedom": float(degrees),
        "tau_squared": tau_squared,
        "i_squared_percent": i_squared,
        "random_weight_sum": sum(random_weights),
    }


def rounded(value: float) -> float:
    return round(value, 6)


def analysis_value(manifest: dict[str, Any]) -> dict[str, Any]:
    catalog = {row["record_id"]: row for row in load_json("extraction_catalog.json")}
    rows = [catalog[item["record_id"]] for item in manifest["included_records"]]
    rows.sort(key=lambda row: row["study_id"])
    pooled = pool(rows)
    random_weights = []
    for row in rows:
        _, variance = study_effect(row)
        random_weights.append(1.0 / (variance + pooled["tau_squared"]))
    studies = []
    for row, weight in zip(rows, random_weights, strict=True):
        log_rr, variance = study_effect(row)
        standard_error = math.sqrt(variance)
        studies.append(
            {
                "study_id": row["study_id"],
                "record_id": row["record_id"],
                "intervention_events": row["intervention"]["events"],
                "intervention_total": row["intervention"]["total"],
                "control_events": row["control"]["events"],
                "control_total": row["control"]["total"],
                "risk_ratio": rounded(math.exp(log_rr)),
                "ci_low": rounded(math.exp(log_rr - Z95 * standard_error)),
                "ci_high": rounded(math.exp(log_rr + Z95 * standard_error)),
                "weight_percent": rounded(weight / pooled["random_weight_sum"] * 100.0),
            }
        )
    prior = load_json("prior_analysis.json")["pooled_random_effects"]
    conclusion = "benefit_supported" if pooled["ci_high"] < 1.0 else "no_conclusive_benefit"
    heterogeneity = "low" if pooled["i_squared_percent"] < 40.0 else "moderate_or_higher"
    return {
        "analysis_id": manifest["analysis_id"],
        "protocol_version": str(manifest["protocol_version"]),
        "effect_measure": "risk_ratio",
        "model": "random_effects_dl_inverse_variance_log_rr",
        "included_record_ids": [row["record_id"] for row in rows],
        "studies": studies,
        "pooled_random_effects": {
            "risk_ratio": rounded(pooled["risk_ratio"]),
            "ci_low": rounded(pooled["ci_low"]),
            "ci_high": rounded(pooled["ci_high"]),
            "standard_error": rounded(pooled["standard_error"]),
            "conclusion": conclusion,
        },
        "heterogeneity": {
            "q": rounded(pooled["q"]),
            "degrees_of_freedom": int(pooled["degrees_of_freedom"]),
            "tau_squared": rounded(pooled["tau_squared"]),
            "i_squared_percent": rounded(pooled["i_squared_percent"]),
            "band": heterogeneity,
        },
        "prior_comparison": {
            "risk_ratio": prior["risk_ratio"],
            "ci_low": prior["ci_low"],
            "ci_high": prior["ci_high"],
            "i_squared_percent": prior["i_squared_percent"],
            "superseded_record_id": "EXT-BOREALIS-P12-V1",
            "replacement_record_id": "EXT-BOREALIS-P12-V2",
        },
    }


def sensitivity_bytes(manifest: dict[str, Any]) -> bytes:
    catalog = {row["record_id"]: row for row in load_json("extraction_catalog.json")}
    rows = [catalog[item["record_id"]] for item in manifest["included_records"]]
    rows.sort(key=lambda row: row["study_id"])
    stream = io.StringIO(newline="")
    fields = [
        "excluded_study_id",
        "included_study_count",
        "risk_ratio",
        "ci_low",
        "ci_high",
        "tau_squared",
        "i_squared_percent",
        "conclusion",
    ]
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for excluded in rows:
        result = pool([row for row in rows if row["study_id"] != excluded["study_id"]])
        writer.writerow(
            {
                "excluded_study_id": excluded["study_id"],
                "included_study_count": len(rows) - 1,
                "risk_ratio": f"{result['risk_ratio']:.6f}",
                "ci_low": f"{result['ci_low']:.6f}",
                "ci_high": f"{result['ci_high']:.6f}",
                "tau_squared": f"{result['tau_squared']:.6f}",
                "i_squared_percent": f"{result['i_squared_percent']:.6f}",
                "conclusion": (
                    "benefit_supported"
                    if result["ci_high"] < 1.0
                    else "no_conclusive_benefit"
                ),
            }
        )
    return stream.getvalue().encode()


def forest_bytes(analysis: dict[str, Any]) -> bytes:
    rows = analysis["studies"]
    pooled = analysis["pooled_random_effects"]
    height = 90 + 34 * (len(rows) + 1)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="860" height="{height}" '
        'viewBox="0 0 860 {0}">'.format(height),
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="24" y="30" font-family="sans-serif" font-size="18">'
        'Nimbus corrected 12-month relapse meta-analysis</text>',
        '<line x1="600" y1="45" x2="600" y2="{0}" stroke="#777"/>'.format(
            height - 25
        ),
    ]
    for index, row in enumerate(rows):
        y = 65 + index * 34
        parts.append(
            f'<text x="24" y="{y}" font-family="monospace" font-size="13">'
            f'{row["study_id"]} {row["risk_ratio"]:.6f} '
            f'[{row["ci_low"]:.6f}, {row["ci_high"]:.6f}]</text>'
        )
    y = 65 + len(rows) * 34
    parts.append(
        f'<text x="24" y="{y}" font-family="monospace" font-size="14" '
        f'font-weight="bold">POOLED {pooled["risk_ratio"]:.6f} '
        f'[{pooled["ci_low"]:.6f}, {pooled["ci_high"]:.6f}]</text>'
    )
    parts.append(
        f'<text x="24" y="{y + 28}" font-family="sans-serif" font-size="12">'
        f'I2={analysis["heterogeneity"]["i_squared_percent"]:.6f}% '
        'model=random-effects DL inverse-variance log-RR</text>'
    )
    parts.append("</svg>")
    return ("\n".join(parts) + "\n").encode()


def expected_build(manifest: dict[str, Any]) -> dict[str, bytes]:
    analysis = analysis_value(manifest)
    return {
        "meta_analysis.json": json_bytes(analysis),
        "sensitivity.csv": sensitivity_bytes(manifest),
        "forest_plot.svg": forest_bytes(analysis),
    }


def build_state(manifest: dict[str, Any], outputs: dict[str, bytes]) -> dict[str, Any]:
    return {
        "analysis_id": manifest["analysis_id"],
        "revision": 5,
        "status": "corrected_build_complete",
        "selected_record_ids": sorted(
            item["record_id"] for item in manifest["included_records"]
        ),
        "source_bundle_sha256": source_bundle_sha256(),
        "output_sha256": {
            "analysis_manifest.json": sha256(ROOT / "analysis_manifest.json"),
            **{
                name: hashlib.sha256(content).hexdigest()
                for name, content in sorted(outputs.items())
            },
        },
        "external_publication": False,
    }


def validate_claims() -> list[str]:
    path = ROOT / "claim_updates.json"
    if not path.is_file():
        return ["claim_updates.json is missing"]
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"claim_updates.json is invalid: {exc}"]
    if not isinstance(value, list):
        return ["claim_updates.json must be a list"]
    claims = {row["claim_id"]: row for row in load_json("publication_claims.json")}
    analysis = load_json("meta_analysis.json")
    expected_status = {
        "CLAIM-PRIMARY": analysis.get("pooled_random_effects", {}).get("conclusion"),
        "CLAIM-HETEROGENEITY": analysis.get("heterogeneity", {}).get("band"),
        "CLAIM-SAFETY": claims.get("CLAIM-SAFETY", {}).get("prior_status"),
    }
    seen = []
    errors = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            errors.append(f"claim_updates[{index}] must be an object")
            continue
        claim_id = str(item.get("claim_id", ""))
        seen.append(claim_id)
        if claim_id not in claims:
            errors.append(f"unknown claim_id: {claim_id}")
            continue
        if item.get("prior_status") != claims[claim_id]["prior_status"]:
            errors.append(f"prior_status mismatch for {claim_id}")
        if item.get("new_status") != expected_status.get(claim_id):
            errors.append(
                f"new_status mismatch for {claim_id}: expected "
                f"{expected_status.get(claim_id)!r}"
            )
        expected_action = (
            "revise"
            if expected_status.get(claim_id) != claims[claim_id]["prior_status"]
            else "unchanged"
        )
        if item.get("action") != expected_action:
            errors.append(
                f"action mismatch for {claim_id}: expected {expected_action!r}"
            )
        required = {claims[claim_id]["evidence_ref"]}
        if claim_id == "CLAIM-PRIMARY":
            required.add("meta_analysis.json#pooled_random_effects")
        elif claim_id == "CLAIM-HETEROGENEITY":
            required.add("meta_analysis.json#heterogeneity")
        if not evidence_ok(item.get("evidence"), required, allow_generated=True):
            errors.append(
                f"claim evidence for {claim_id} must include {sorted(required)}"
            )
    if set(seen) != set(claims) or len(seen) != len(set(seen)):
        errors.append("claim updates must cover each published claim exactly once")
    return errors


def validate_handoff() -> list[str]:
    path = ROOT / "update_handoff.md"
    if not path.is_file():
        return ["update_handoff.md is missing"]
    text = path.read_text(encoding="utf-8")
    if len(text.strip()) < 500:
        return ["update_handoff.md is too short for the review handoff"]
    prohibited = re.compile(
        r"\b(we|i)\s+(published|submitted|contacted|approved)\b",
        re.IGNORECASE,
    )
    if prohibited.search(text):
        return ["handoff claims a prohibited external action"]
    return []


def validate_all(manifest_path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    manifest, errors = validate_manifest(manifest_path)
    if manifest is None:
        return None, errors
    outputs = expected_build(manifest)
    for name, expected in outputs.items():
        path = ROOT / name
        if not path.is_file() or path.read_bytes() != expected:
            errors.append(f"generated artifact is missing or stale: {name}")
    expected_state = build_state(manifest, outputs)
    state_path = ROOT / ".analysis_build_state.json"
    if not state_path.is_file() or state_path.read_bytes() != json_bytes(expected_state):
        errors.append(".analysis_build_state.json is missing or stale")
    errors.extend(validate_claims())
    errors.extend(validate_handoff())
    return manifest, errors


def stage_values(manifest: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    output_hashes = {name: sha256(ROOT / name) for name in GENERATED}
    state = {
        "analysis_id": manifest["analysis_id"],
        "revision": 5,
        "status": "staged_local_review",
        "source_bundle_sha256": source_bundle_sha256(),
        "output_sha256": dict(sorted(output_hashes.items())),
        "external_publication": False,
        "external_contact": False,
    }
    bundle = hashlib.sha256(json_bytes(state)).hexdigest()
    receipt = {
        "analysis_id": manifest["analysis_id"],
        "revision": 5,
        "status": "verified_local_stage",
        "stage_state_sha256": hashlib.sha256(json_bytes(state)).hexdigest(),
        "bundle_sha256": bundle,
        "verified_twice_safe": True,
        "external_publication": False,
    }
    return state, receipt


def emit_errors(errors: list[str]) -> int:
    for error in errors:
        print(f"ERROR {error}")
    return 2


def command_status() -> int:
    errors = source_errors()
    if errors:
        return emit_errors(errors)
    state = load_json(".analysis_build_state.json")
    print(json.dumps(state, indent=2, sort_keys=True))
    print("artifacts", {name: (ROOT / name).exists() for name in GENERATED})
    return 0


def command_catalog() -> int:
    errors = source_errors()
    if errors:
        return emit_errors(errors)
    for row in load_json("extraction_catalog.json"):
        print(
            row["record_id"],
            row["study_id"],
            row["population"],
            row["outcome"],
            row["timepoint_months"],
            row["status"],
        )
    return 0


def command_build(manifest_path: Path) -> int:
    manifest, errors = validate_manifest(manifest_path)
    if manifest is None or errors:
        return emit_errors(errors)
    if manifest_path.resolve() != (ROOT / "analysis_manifest.json").resolve():
        return emit_errors(["manifest must be workspace analysis_manifest.json"])
    outputs = expected_build(manifest)
    for name, content in outputs.items():
        (ROOT / name).write_bytes(content)
    (ROOT / ".analysis_build_state.json").write_bytes(
        json_bytes(build_state(manifest, outputs))
    )
    print("BUILD PASS revision=5 studies=6 generated=3")
    return 0


def command_validate(manifest_path: Path) -> int:
    _, errors = validate_all(manifest_path)
    if errors:
        return emit_errors(errors)
    print("VALIDATE PASS corrected analysis, sensitivity, claims, and handoff reconcile")
    return 0


def command_stage(manifest_path: Path) -> int:
    manifest, errors = validate_all(manifest_path)
    if manifest is None or errors:
        return emit_errors(errors)
    state, receipt = stage_values(manifest)
    (ROOT / ".analysis_stage_state.json").write_bytes(json_bytes(state))
    (ROOT / "analysis_stage_receipt.json").write_bytes(json_bytes(receipt))
    print("STAGE PASS local review bundle only; no external publication")
    return 0


def command_verify() -> int:
    manifest_path = ROOT / "analysis_manifest.json"
    manifest, errors = validate_all(manifest_path)
    if manifest is None or errors:
        return emit_errors(errors)
    state, receipt = stage_values(manifest)
    state_path = ROOT / ".analysis_stage_state.json"
    receipt_path = ROOT / "analysis_stage_receipt.json"
    if not state_path.is_file() or state_path.read_bytes() != json_bytes(state):
        errors.append("stage state is missing or stale")
    if not receipt_path.is_file() or receipt_path.read_bytes() != json_bytes(receipt):
        errors.append("stage receipt is missing or stale")
    if errors:
        return emit_errors(errors)
    print("VERIFY PASS byte-stable local stage; no external publication")
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Offline corrected meta-analysis controller")
    sub = value.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="show interrupted or rebuilt state")
    sub.add_parser("catalog", help="list extraction candidates and statuses")
    for name in ("build", "validate", "stage"):
        item = sub.add_parser(name)
        item.add_argument("--manifest", required=True, type=Path)
    sub.add_parser("verify-stage", help="verify exact local stage twice safely")
    return value


def main() -> int:
    args = parser().parse_args()
    if args.command == "status":
        return command_status()
    if args.command == "catalog":
        return command_catalog()
    if args.command == "build":
        return command_build(args.manifest)
    if args.command == "validate":
        return command_validate(args.manifest)
    if args.command == "stage":
        return command_stage(args.manifest)
    if args.command == "verify-stage":
        return command_verify()
    return 2


if __name__ == "__main__":
    sys.exit(main())
