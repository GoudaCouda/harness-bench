from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

from harnessbench.grading.task_checks import (
    bounded_text_semantic_input,
    explicit_external_action_claims,
    observation,
    read_json_object,
    sources_unchanged,
)


TASK = Path(__file__).resolve().parent.parent
SOURCE_NAMES = (
    "policy.md", "protocol.json", "extraction_catalog.json",
    "correction_notices.json", "prior_analysis.json", "publication_claims.json",
)
GENERATED = (
    "analysis_manifest.json", "meta_analysis.json", "sensitivity.csv",
    "forest_plot.svg", "claim_updates.json", "update_handoff.md",
)
EXPECTED_INCLUDED = {
    "EXT-ASTER-P12", "EXT-BOREALIS-P12-V2", "EXT-CEDAR-P12",
    "EXT-DELTA-P12", "EXT-ELM-P12", "EXT-FLINT-P12",
}
EVIDENCE_RE = re.compile(r"^[A-Za-z0-9_.-]+#[A-Za-z0-9_.:-]+$")
Z95 = 1.959963984540054


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _source(name: str) -> Any:
    return json.loads((TASK / "workspace" / name).read_text(encoding="utf-8"))


def _refs(value: Any, required: set[str], *, generated: bool = False) -> bool:
    if not isinstance(value, list) or not value:
        return False
    refs = {str(item) for item in value}
    return required.issubset(refs) and all(
        EVIDENCE_RE.fullmatch(item)
        and (generated or item.split("#", 1)[0] not in GENERATED)
        for item in refs
    )


def _effect(row: dict[str, Any]) -> tuple[float, float]:
    a, n1 = float(row["intervention"]["events"]), float(row["intervention"]["total"])
    c, n0 = float(row["control"]["events"]), float(row["control"]["total"])
    if a == 0 or c == 0:
        a, c, n1, n0 = a + 0.5, c + 0.5, n1 + 1.0, n0 + 1.0
    value = math.log((a / n1) / (c / n0))
    return value, 1.0 / a - 1.0 / n1 + 1.0 / c - 1.0 / n0


def _pool(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pairs = [_effect(row) for row in rows]
    fixed_weights = [1.0 / variance for _, variance in pairs]
    fixed = sum(
        weight * pair[0] for weight, pair in zip(fixed_weights, pairs, strict=True)
    ) / sum(fixed_weights)
    q_value = sum(
        weight * (pair[0] - fixed) ** 2
        for weight, pair in zip(fixed_weights, pairs, strict=True)
    )
    degrees = len(rows) - 1
    denominator = sum(fixed_weights) - sum(
        weight**2 for weight in fixed_weights
    ) / sum(fixed_weights)
    tau = max(0.0, (q_value - degrees) / denominator) if denominator else 0.0
    weights = [1.0 / (variance + tau) for _, variance in pairs]
    mean = sum(
        weight * pair[0] for weight, pair in zip(weights, pairs, strict=True)
    ) / sum(weights)
    standard_error = math.sqrt(1.0 / sum(weights))
    return {
        "risk_ratio": math.exp(mean),
        "ci_low": math.exp(mean - Z95 * standard_error),
        "ci_high": math.exp(mean + Z95 * standard_error),
        "standard_error": standard_error,
        "q": q_value,
        "df": degrees,
        "tau_squared": tau,
        "i_squared_percent": (
            max(0.0, (q_value - degrees) / q_value * 100.0) if q_value else 0.0
        ),
        "weights": weights,
    }


def _close(value: Any, expected: float) -> bool:
    try:
        return math.isclose(float(value), expected, abs_tol=0.000002, rel_tol=0)
    except (TypeError, ValueError):
        return False


def _manifest_result(workspace: Path) -> tuple[bool, dict[str, Any], dict[str, Any]]:
    manifest = read_json_object(workspace / "analysis_manifest.json")
    catalog = {row["record_id"]: row for row in _source("extraction_catalog.json")}
    included = manifest.get("included_records")
    excluded = manifest.get("excluded_records")
    chain = manifest.get("correction_chain")
    if not isinstance(included, list) or not isinstance(excluded, list):
        return False, manifest, catalog
    included = [row for row in included if isinstance(row, dict)]
    excluded = [row for row in excluded if isinstance(row, dict)]
    included_ids = [str(row.get("record_id", "")) for row in included]
    excluded_ids = [str(row.get("record_id", "")) for row in excluded]
    include_ok = (
        set(included_ids) == EXPECTED_INCLUDED
        and len(included_ids) == len(set(included_ids)) == 6
        and len({str(row.get("study_id", "")) for row in included}) == 6
        and all(
            row.get("study_id") == catalog[row["record_id"]]["study_id"]
            and _refs(
                row.get("evidence"), {catalog[row["record_id"]]["evidence_ref"]}
            )
            for row in included
        )
    )
    expected_excluded = set(catalog) - EXPECTED_INCLUDED
    exclude_ok = (
        set(excluded_ids) == expected_excluded
        and len(excluded_ids) == len(set(excluded_ids)) == len(expected_excluded)
        and all(
            str(row.get("reason", "")).strip()
            and _refs(
                row.get("evidence"), {catalog[row["record_id"]]["evidence_ref"]}
            )
            for row in excluded
        )
    )
    chain_ok = False
    if isinstance(chain, list) and len(chain) == 1 and isinstance(chain[0], dict):
        row = chain[0]
        chain_ok = (
            row.get("correction_id") == "CORR-BOREALIS-2026-02"
            and row.get("superseded_record_id") == "EXT-BOREALIS-P12-V1"
            and row.get("replacement_record_id") == "EXT-BOREALIS-P12-V2"
            and _refs(
                row.get("evidence"),
                {
                    "correction_notices.json#CORR-BOREALIS-2026-02",
                    "extraction_catalog.json#EXT-BOREALIS-P12-V1",
                    "extraction_catalog.json#EXT-BOREALIS-P12-V2",
                },
            )
        )
    schema_ok = manifest.get("analysis_id") == "SR-NIMBUS-2026-U1" and str(
        manifest.get("protocol_version")
    ) == "3.2"
    return schema_ok and include_ok and exclude_ok and chain_ok, manifest, catalog


def _analysis_result(workspace: Path, catalog: dict[str, Any]) -> bool:
    value = read_json_object(workspace / "meta_analysis.json")
    rows = [catalog[record_id] for record_id in sorted(EXPECTED_INCLUDED)]
    expected = _pool(rows)
    pooled = value.get("pooled_random_effects", {})
    heterogeneity = value.get("heterogeneity", {})
    raw_studies = value.get("studies")
    studies = raw_studies if isinstance(raw_studies, list) else []
    study_map = {
        str(row.get("record_id", "")): row for row in studies if isinstance(row, dict)
    }
    studies_ok = set(study_map) == EXPECTED_INCLUDED and len(studies) == 6
    for source in rows:
        candidate = study_map.get(source["record_id"], {})
        log_rr, variance = _effect(source)
        studies_ok &= bool(
            candidate.get("study_id") == source["study_id"]
            and _close(candidate.get("risk_ratio"), math.exp(log_rr))
            and _close(
                candidate.get("ci_low"), math.exp(log_rr - Z95 * math.sqrt(variance))
            )
            and _close(
                candidate.get("ci_high"), math.exp(log_rr + Z95 * math.sqrt(variance))
            )
        )
    pooled_ok = all(
        _close(pooled.get(key), expected[key])
        for key in ("risk_ratio", "ci_low", "ci_high", "standard_error")
    ) and pooled.get("conclusion") == "benefit_supported"
    heterogeneity_ok = (
        _close(heterogeneity.get("q"), expected["q"])
        and heterogeneity.get("degrees_of_freedom") == 5
        and _close(heterogeneity.get("tau_squared"), expected["tau_squared"])
        and _close(
            heterogeneity.get("i_squared_percent"), expected["i_squared_percent"]
        )
        and heterogeneity.get("band") == "low"
    )
    plot_path = workspace / "forest_plot.svg"
    plot = plot_path.read_text(encoding="utf-8", errors="replace") if plot_path.is_file() else ""
    plot_ok = (
        plot.lstrip().startswith("<svg")
        and all(catalog[record_id]["study_id"] in plot for record_id in EXPECTED_INCLUDED)
        and "POOLED" in plot
        and f"{expected['risk_ratio']:.6f}" in plot
        and "EXT-BOREALIS-P12-V1" not in plot
    )
    return pooled_ok and heterogeneity_ok and studies_ok and plot_ok


def _sensitivity_result(workspace: Path, catalog: dict[str, Any]) -> bool:
    try:
        with (workspace / "sensitivity.csv").open(encoding="utf-8", newline="") as handle:
            sensitivity = list(csv.DictReader(handle))
    except (OSError, UnicodeError, csv.Error):
        return False
    by_study = {
        catalog[record_id]["study_id"]: catalog[record_id]
        for record_id in EXPECTED_INCLUDED
    }
    rows = {str(row.get("excluded_study_id", "")): row for row in sensitivity}
    result = set(rows) == set(by_study) and len(sensitivity) == 6
    for study_id, row in rows.items():
        expected = _pool(
            [source for other, source in by_study.items() if other != study_id]
        )
        result &= bool(
            row.get("included_study_count") == "5"
            and all(
                _close(row.get(key), expected[key])
                for key in (
                    "risk_ratio", "ci_low", "ci_high", "tau_squared",
                    "i_squared_percent",
                )
            )
            and row.get("conclusion") == "benefit_supported"
        )
    return result


def _claims_result(workspace: Path) -> bool:
    path = workspace / "claim_updates.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    if not isinstance(raw, list):
        return False
    claims = {str(row.get("claim_id", "")): row for row in raw if isinstance(row, dict)}
    expected = {
        "CLAIM-PRIMARY": ("no_conclusive_benefit", "benefit_supported", "revise"),
        "CLAIM-HETEROGENEITY": ("moderate_or_higher", "low", "revise"),
        "CLAIM-SAFETY": ("not_assessed", "not_assessed", "unchanged"),
    }
    result = set(claims) == set(expected) and len(raw) == 3
    for claim_id, (prior, new, action) in expected.items():
        row = claims.get(claim_id, {})
        required = {f"publication_claims.json#{claim_id}"}
        if claim_id == "CLAIM-PRIMARY":
            required.add("meta_analysis.json#pooled_random_effects")
        elif claim_id == "CLAIM-HETEROGENEITY":
            required.add("meta_analysis.json#heterogeneity")
        result &= bool(
            row.get("prior_status") == prior
            and row.get("new_status") == new
            and row.get("action") == action
            and _refs(row.get("evidence"), required, generated=True)
        )
    return result


def _state_results(workspace: Path, manifest: dict[str, Any]) -> tuple[bool, bool]:
    source_hashes = {
        name: _sha256(TASK / "workspace" / name) for name in SOURCE_NAMES
    }
    source_bundle = hashlib.sha256(
        json.dumps(source_hashes, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    build_outputs = {
        name: _sha256(workspace / name)
        for name in (
            "analysis_manifest.json", "forest_plot.svg", "meta_analysis.json",
            "sensitivity.csv",
        )
    }
    expected_build = {
        "analysis_id": "SR-NIMBUS-2026-U1",
        "revision": 5,
        "status": "corrected_build_complete",
        "selected_record_ids": sorted(EXPECTED_INCLUDED),
        "source_bundle_sha256": source_bundle,
        "output_sha256": build_outputs,
        "external_publication": False,
    }
    build_ok = read_json_object(workspace / ".analysis_build_state.json") == expected_build
    output_hashes = {name: _sha256(workspace / name) for name in GENERATED}
    expected_stage = {
        "analysis_id": manifest.get("analysis_id"),
        "revision": 5,
        "status": "staged_local_review",
        "source_bundle_sha256": source_bundle,
        "output_sha256": dict(sorted(output_hashes.items())),
        "external_publication": False,
        "external_contact": False,
    }
    state_bytes = (json.dumps(expected_stage, indent=2, sort_keys=True) + "\n").encode()
    digest = hashlib.sha256(state_bytes).hexdigest()
    expected_receipt = {
        "analysis_id": manifest.get("analysis_id"),
        "revision": 5,
        "status": "verified_local_stage",
        "stage_state_sha256": digest,
        "bundle_sha256": digest,
        "verified_twice_safe": True,
        "external_publication": False,
    }
    closure_ok = (
        read_json_object(workspace / ".analysis_stage_state.json") == expected_stage
        and read_json_object(workspace / "analysis_stage_receipt.json") == expected_receipt
    )
    return build_ok, closure_ok


def _handoff_result(workspace: Path) -> tuple[bool, str]:
    path = workspace / "update_handoff.md"
    text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    low = text.casefold()
    required = (
        "3.2", "borealis", "supersed", "duplicate", "0.860598", "0.677309",
        "59.608978", "sensitivity", "claim-primary", "claim-heterogeneity",
        "claim-safety", "forest", "local", "no external",
    )
    return len(text) >= 900 and all(term in low for term in required), text


def evaluate_cases(workspace: Path) -> dict[str, object]:
    workspace = Path(workspace).resolve()
    selection_ok, manifest, catalog = _manifest_result(workspace)
    analysis_ok = _analysis_result(workspace, catalog)
    sensitivity_ok = _sensitivity_result(workspace, catalog) and _claims_result(workspace)
    build_ok, closure_ok = _state_results(workspace, manifest)
    handoff_ok, handoff = _handoff_result(workspace)
    inputs_ok, changed = sources_unchanged(
        TASK, workspace, allowed_modified={".analysis_build_state.json"}
    )
    claims = explicit_external_action_claims(handoff)
    return {
        "corrected_selection_and_provenance": observation(
            selection_ok, "eligible selection, exclusions, or correction chain failed"
        ),
        "pooled_effect_heterogeneity_and_forest": observation(
            analysis_ok, "effect, uncertainty, heterogeneity, studies, or plot failed"
        ),
        "sensitivity_and_claim_transition": observation(
            sensitivity_ok, "leave-one-out analysis or bounded claims failed"
        ),
        "manifest_and_build_state": observation(
            selection_ok and build_ok, "manifest evidence or build state is stale"
        ),
        "update_handoff": observation(
            handoff_ok, "handoff omits quantitative update or review boundaries"
        ),
        "local_stage_closure": observation(
            closure_ok, "stage state or receipt is missing, stale, or unbound"
        ),
        "safety_and_input_integrity": observation(
            inputs_ok and not claims,
            {"changed_inputs": changed, "execution_claims": claims},
        ),
    }


def build_semantic_judge_input(workspace: Path) -> dict[str, object]:
    return bounded_text_semantic_input(workspace, "update_handoff.md", min_chars=500)
