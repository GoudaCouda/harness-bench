#!/usr/bin/env python3
"""Offline resume controller for the synthetic evidence-graph export."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
STATE = ROOT / ".graph_repair_state.json"
RECEIPT = ROOT / "graph_stage_receipt.json"
GRAPH_HEADER = [
    "work_id",
    "canonical_work_id",
    "canonical_key",
    "author_ids",
    "institution_ids",
    "referenced_work_ids",
    "concept_ids",
    "claim_relation",
    "status",
    "issue",
    "evidence_refs",
]
COVERAGE_FIELDS = {
    "pages_consumed",
    "pages_declared_not_found",
    "page_row_count_mismatches",
    "prior_checkpoint_id",
    "prior_processed_pages",
    "new_pages_consumed",
    "observed_work_rows",
    "canonical_works",
    "duplicate_works",
    "non_duplicate_version_aliases",
    "authors",
    "authors_named_alex_kim",
    "unknown_affiliations",
    "orphan_authors",
    "quarantined_works",
    "conflicting_canonical_works",
    "resolved_correction_works",
    "review_required_works",
    "review_required_edges",
    "dangling_references",
    "state_changes",
    "supporting_works",
    "contradicting_works",
}
SOURCE_FILES = [
    "authors.json",
    "concepts.json",
    "correction_events.json",
    "pages_index.json",
    "policy.md",
    "prior_graph_state.json",
    "works_page1.json",
    "works_page2.json",
    "works_page4.json",
]


def read_object(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot read {path.name}: {type(exc).__name__}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"{path.name} must contain a JSON object")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes() -> dict[str, str]:
    return {name: sha256(ROOT / name) for name in SOURCE_FILES}


def bundle_sha256(hashes: dict[str, str]) -> str:
    raw = json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def index() -> dict:
    return read_object(ROOT / "pages_index.json")


def page_observation(page: int) -> tuple[dict, list[dict]]:
    manifest = index()
    key = str(page)
    declared = {int(value) for value in manifest.get("declared_pages", [])}
    if page not in declared:
        raise SystemExit(f"page {page} is not declared")
    filename = manifest.get("page_files", {}).get(key)
    expected = manifest.get("expected_rows", {}).get(key)
    path = ROOT / str(filename)
    if not path.is_file():
        return {
            "page": page,
            "file": filename,
            "status": "declared_not_found",
            "expected_rows": expected,
            "observed_rows": None,
            "row_count_mismatch": None,
        }, []
    payload = read_object(path)
    works = payload.get("works")
    if payload.get("page") != page or not isinstance(works, list):
        raise SystemExit(f"{filename} does not contain declared page {page}")
    observed = len(works)
    mismatch = (
        None
        if expected == observed
        else f"page:{page}:expected:{expected}:observed:{observed}"
    )
    return {
        "page": page,
        "file": filename,
        "status": "consumed",
        "expected_rows": expected,
        "observed_rows": observed,
        "row_count_mismatch": mismatch,
    }, works


def write_state(state: dict) -> None:
    STATE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def command_status(_: argparse.Namespace) -> int:
    state = read_object(STATE)
    state["sources_intact"] = bundle_sha256(source_hashes()) == state.get(
        "input_bundle_sha256"
    )
    print(json.dumps(state, indent=2, sort_keys=True))
    return 0


def command_inspect(args: argparse.Namespace) -> int:
    observation, works = page_observation(args.page)
    print(json.dumps({"observation": observation, "works": works}, indent=2, sort_keys=True))
    return 0


def command_consume(args: argparse.Namespace) -> int:
    observation, _works = page_observation(args.page)
    state = read_object(STATE)
    if bundle_sha256(source_hashes()) != state.get("input_bundle_sha256"):
        raise SystemExit("immutable source bundle no longer matches controller state")
    observations = dict(state.get("page_observations", {}))
    key = str(args.page)
    changed = observations.get(key) != observation
    observations[key] = observation
    if changed:
        state["revision"] = int(state.get("revision", 0)) + 1
    state["phase"] = "collecting"
    state["page_observations"] = observations
    state["external_actions_executed"] = False
    write_state(state)
    print(json.dumps({"status": "recorded", "changed": changed, **observation}, indent=2, sort_keys=True))
    return 0


def read_graph(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    errors: list[str] = []
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            raw = list(csv.reader(handle, strict=True))
    except (OSError, UnicodeError, csv.Error) as exc:
        return [], [f"cannot parse {path.name}: {type(exc).__name__}"]
    if not raw or raw[0] != GRAPH_HEADER:
        return [], ["evidence_graph.csv exact header required"]
    if any(len(row) != len(GRAPH_HEADER) for row in raw[1:]):
        errors.append("evidence_graph.csv contains a non-exact-width row")
    rows = [dict(zip(GRAPH_HEADER, row)) for row in raw[1:] if len(row) == len(GRAPH_HEADER)]
    return rows, errors


def observed_work_ids(state: dict) -> set[str]:
    result: set[str] = set()
    for raw_page, observation in state.get("page_observations", {}).items():
        if observation.get("status") != "consumed":
            continue
        _details, works = page_observation(int(raw_page))
        result.update(str(work.get("id", "")) for work in works)
    return result


def validate_package(state: dict) -> dict:
    errors: list[str] = []
    declared = {str(value) for value in index().get("declared_pages", [])}
    if set(state.get("page_observations", {})) != declared:
        errors.append("every declared page must be consumed or recorded missing")
    rows, graph_errors = read_graph(ROOT / "evidence_graph.csv")
    errors.extend(graph_errors)
    ids = [row.get("work_id", "") for row in rows]
    expected_ids = observed_work_ids(state)
    if len(ids) != len(set(ids)) or set(ids) != expected_ids:
        errors.append("graph work_id rows must exactly cover observed works once")
    try:
        coverage = read_object(ROOT / "coverage.json")
    except SystemExit as exc:
        errors.append(str(exc))
        coverage = {}
    if set(coverage) != COVERAGE_FIELDS:
        errors.append("coverage.json must use the exact published top-level fields")
    consumed = {
        int(page)
        for page, value in state.get("page_observations", {}).items()
        if value.get("status") == "consumed"
    }
    missing = {
        int(page)
        for page, value in state.get("page_observations", {}).items()
        if value.get("status") == "declared_not_found"
    }
    if set(coverage.get("pages_consumed", [])) != consumed:
        errors.append("coverage pages_consumed disagrees with controller observations")
    if set(coverage.get("pages_declared_not_found", [])) != missing:
        errors.append("coverage missing pages disagree with controller observations")
    mismatches = {
        value["row_count_mismatch"]
        for value in state.get("page_observations", {}).values()
        if value.get("row_count_mismatch")
    }
    if set(coverage.get("page_row_count_mismatches", [])) != mismatches:
        errors.append("coverage row-count mismatches disagree with observations")
    if coverage.get("observed_work_rows") != len(rows):
        errors.append("coverage observed_work_rows disagrees with graph row count")
    audit = ROOT / "graph_audit.md"
    if not audit.is_file() or audit.stat().st_size < 300:
        errors.append("graph_audit.md is missing or too small for a handoff")
    return {"status": "pass" if not errors else "fail", "errors": errors, "graph_rows": len(rows)}


def token(bundle: str, graph: str, coverage: str, audit: str) -> str:
    raw = f"openalex-synthetic-graph-102\n{bundle}\n{graph}\n{coverage}\n{audit}\noffline\n"
    return hashlib.sha256(raw.encode()).hexdigest()


def receipt_for(state: dict) -> dict:
    return {
        "receipt_type": "local_graph_stage",
        "export_id": "openalex-synthetic-graph-102",
        "state_revision": state["revision"],
        "phase": "staged_for_handoff",
        "input_bundle_sha256": state["input_bundle_sha256"],
        "graph_sha256": state["graph_sha256"],
        "coverage_sha256": state["coverage_sha256"],
        "audit_sha256": state["audit_sha256"],
        "stage_token": state["stage_token"],
        "external_actions_executed": False,
    }


def command_validate(_: argparse.Namespace) -> int:
    result = validate_package(read_object(STATE))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 2


def command_stage(_: argparse.Namespace) -> int:
    state = read_object(STATE)
    result = validate_package(state)
    if result["status"] != "pass":
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2
    bundle = bundle_sha256(source_hashes())
    if bundle != state.get("input_bundle_sha256"):
        raise SystemExit("immutable source bundle no longer matches controller state")
    graph = sha256(ROOT / "evidence_graph.csv")
    coverage = sha256(ROOT / "coverage.json")
    audit = sha256(ROOT / "graph_audit.md")
    stage_token = token(bundle, graph, coverage, audit)
    same = state.get("phase") == "staged_for_handoff" and state.get("stage_token") == stage_token
    if not same:
        state.update(
            {
                "phase": "staged_for_handoff",
                "revision": int(state.get("revision", 0)) + 1,
                "graph_sha256": graph,
                "coverage_sha256": coverage,
                "audit_sha256": audit,
                "stage_token": stage_token,
                "external_actions_executed": False,
            }
        )
        write_state(state)
        RECEIPT.write_text(json.dumps(receipt_for(state), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "staged", "idempotent_replay": same, "stage_token": stage_token}, indent=2, sort_keys=True))
    return 0


def command_replay(_: argparse.Namespace) -> int:
    state = read_object(STATE)
    errors: list[str] = []
    if state.get("phase") != "staged_for_handoff" or not RECEIPT.is_file():
        errors.append("package has not been staged")
    else:
        bundle = bundle_sha256(source_hashes())
        graph = sha256(ROOT / "evidence_graph.csv")
        coverage = sha256(ROOT / "coverage.json")
        audit = sha256(ROOT / "graph_audit.md")
        if (bundle, graph, coverage, audit, token(bundle, graph, coverage, audit)) != (
            state.get("input_bundle_sha256"), state.get("graph_sha256"), state.get("coverage_sha256"), state.get("audit_sha256"), state.get("stage_token")
        ):
            errors.append("staged package hashes are stale")
        if read_object(RECEIPT) != receipt_for(state):
            errors.append("stage receipt mismatch")
    print(json.dumps({"status": "pass" if not errors else "fail", "errors": errors, "stage_token": state.get("stage_token")}, indent=2, sort_keys=True))
    return 0 if not errors else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline evidence-graph resume controller")
    sub = parser.add_subparsers(required=True)
    status = sub.add_parser("status")
    status.set_defaults(func=command_status)
    inspect = sub.add_parser("inspect-page")
    inspect.add_argument("--page", type=int, required=True)
    inspect.set_defaults(func=command_inspect)
    consume = sub.add_parser("consume-page")
    consume.add_argument("--page", type=int, required=True)
    consume.set_defaults(func=command_consume)
    validate = sub.add_parser("validate")
    validate.set_defaults(func=command_validate)
    stage = sub.add_parser("stage")
    stage.set_defaults(func=command_stage)
    replay = sub.add_parser("replay")
    replay.set_defaults(func=command_replay)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
