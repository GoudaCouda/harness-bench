#!/usr/bin/env python3
"""Build and stage a consent-safe synthetic DMS repository package."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
PROJECT_PATH = ROOT / "project.json"
REPOSITORIES_PATH = ROOT / "repositories.json"
PLAN_PATH = ROOT / "deposit_plan.json"
STAGING = ROOT / "staging"
MANIFEST = ROOT / "package_manifest.csv"
BUILD_STATE = ROOT / ".dms_build_state.json"
HANDOFF = ROOT / "revised_plan.md"
STAGE_STATE = ROOT / ".dms_stage_state.json"
RECEIPT = ROOT / "dms_stage_receipt.json"
SOURCE_HASHES = {
    "policy_2026-01.md": "e3fa1a863e717b4f23f386f5714dc00bac2e546c503cb3a8516136cad2bebcd0",
    "project.json": "c6047a3345c094e67cbd8a2462e8163d9f1db4e2b097f02d7e13fe9ff292b863",
    "repositories.json": "3c163433642b9346228122a559eb4f517a0659ae2c4d1499c76117c958d4f496",
    "prior_build_checkpoint.json": "e2c28610278826d3a6e177e40f0b86bb556b44042a68c5b9d8d7664562f480de",
    "assets/analysis_code.py": "14425851f7cfcc160cc1cf0a869839be3b90d5c088f05878f4a313b22a1e7044",
    "assets/analysis_environment.txt": "9cbdcad55c1a892cdb569f27cfc1e8039c2f02d242d209373742dc7568399f59",
    "assets/audio_metadata.csv": "f1cb1092c31505375fed3ecf0f6d3820938fdfae543b4442f7381aa8c8db9ce3",
    "assets/audio_raw.bin": "e7f3c8eb1aa3e7579930d58b3005b8e26d82afef7cc7e99f0e9e66d6966ea2cd",
    "assets/audio_transcript_deid.txt": "e14e45d0258539d333c78ccabfa0aa624c7de0557d44e4ef93c9307d8d04cfd8",
    "assets/model_outputs.csv": "0a397feba992033f29bf8e9c6e622af515102ca159d1f2725c81dbf80e3e58d4",
    "assets/survey_dictionary.csv": "1483fb86dd1319e36f4db9b37b11e7a48553eb14c29ee30ad1e2bc86be804ba4",
    "assets/survey_raw.csv": "0ea0b5e765fd0dfa34485792af9ba3afb9ae2bc63d253107f708b6cba949b793",
}
PLAN_KEYS = {
    "schema_version",
    "plan_id",
    "policy_effective",
    "plan_revision",
    "publication_release_date",
    "assets",
    "approval_gates",
    "repository_split_required",
    "external_deposit_executed",
}
ASSET_KEYS = {"asset_id", "disposition", "repository", "access", "evidence_refs"}
DISPOSITIONS = {
    "controlled_file",
    "public_file",
    "metadata_only_record",
    "code_file",
    "excluded_external_file",
}
MANIFEST_HEADER = (
    "asset_id",
    "source_path",
    "source_sha256",
    "disposition",
    "repository",
    "staged_path",
    "staged_sha256",
    "bytes",
    "evidence_refs",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _bundle_hash() -> str:
    raw = json.dumps(SOURCE_HASHES, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _source_errors() -> list[str]:
    errors: list[str] = []
    for name, expected in SOURCE_HASHES.items():
        path = ROOT / name
        if not path.is_file() or path.is_symlink():
            errors.append(f"protected source missing or symlinked: {name}")
        elif _sha256(path) != expected:
            errors.append(f"protected source changed: {name}")
    return errors


def _project() -> dict[str, Any]:
    return _read_json(PROJECT_PATH)


def _repository_map() -> dict[str, dict[str, Any]]:
    payload = _read_json(REPOSITORIES_PATH)
    return {str(row["name"]): row for row in payload.get("repositories", [])}


def _asset_map() -> dict[str, dict[str, Any]]:
    return {str(row["asset_id"]): row for row in _project().get("assets", [])}


def _plan_errors(plan: Any) -> list[str]:
    project = _project()
    assets = _asset_map()
    repositories = _repository_map()
    errors = _source_errors()
    if not isinstance(plan, dict):
        return errors + ["deposit_plan.json must be one JSON object"]
    if set(plan) != PLAN_KEYS:
        errors.append("deposit plan top-level keys are noncanonical")
    if plan.get("schema_version") != 1 or plan.get("plan_id") != project.get("project_id"):
        errors.append("schema_version or plan_id does not match the project")
    if plan.get("policy_effective") != project.get("policy_snapshot"):
        errors.append("the controlling policy snapshot is not selected")
    revision = plan.get("plan_revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision <= 1:
        errors.append("plan_revision must be an integer greater than interrupted revision 1")
    if plan.get("publication_release_date") != project.get("planned_publication_date"):
        errors.append("participant-data release date must close at publication")
    if plan.get("repository_split_required") is not True:
        errors.append("repository_split_required must be true")
    if plan.get("external_deposit_executed") is not False:
        errors.append("external_deposit_executed must remain false")
    if plan.get("approval_gates") != {
        "plan_revision": "pending",
        "privacy_review": "pending",
        "institutional_review": "pending",
    }:
        errors.append("all three approval gates must remain pending")
    rows = plan.get("assets")
    if not isinstance(rows, list):
        return errors + ["assets must be an array"]
    by_id = {
        str(row.get("asset_id", "")): row for row in rows if isinstance(row, dict)
    }
    if len(rows) != len(by_id) or set(by_id) != set(assets):
        errors.append("assets must contain each project asset exactly once")
    for asset_id, row in by_id.items():
        if set(row) != ASSET_KEYS:
            errors.append(f"{asset_id}: asset row keys are noncanonical")
            continue
        disposition = row.get("disposition")
        repository_name = str(row.get("repository", ""))
        access = row.get("access")
        refs = row.get("evidence_refs")
        if disposition not in DISPOSITIONS:
            errors.append(f"{asset_id}: unknown disposition")
        if not isinstance(refs, list) or not refs or not all(
            isinstance(ref, str)
            and "#" in ref
            and not ref.startswith(("http://", "https://", "/", "../", "file://"))
            for ref in refs
        ):
            errors.append(f"{asset_id}: evidence_refs must be nonempty local basename#id values")
        asset = assets.get(asset_id, {})
        kind = asset.get("kind")
        if asset_id in {"audio_raw", "audio_transcript_deid"}:
            if (
                disposition != "excluded_external_file"
                or repository_name != "internal_only"
                or access != "no_external_sharing"
            ):
                errors.append(f"{asset_id}: C2 file must remain excluded and internal-only")
            continue
        repository = repositories.get(repository_name)
        if not repository or repository.get("external") is not True:
            errors.append(f"{asset_id}: repository must be a visible external repository")
            continue
        if asset_id == "survey_raw":
            if not (
                disposition == "controlled_file"
                and access == "controlled_reuse"
                and repository.get("accepts_controlled_files") is True
                and repository.get("supports_dua_workflow") is True
                and repository.get("supports_access_committee") is True
            ):
                errors.append("survey_raw: controlled consent/capability route failed")
        elif asset_id == "audio_metadata":
            if not (
                disposition == "metadata_only_record"
                and access == "public_metadata"
                and repository.get("supports_metadata_only_record") is True
            ):
                errors.append("audio_metadata: metadata-only route failed")
        elif kind in {"code", "code_environment"}:
            if not (
                disposition == "code_file"
                and access == "public"
                and repository.get("accepts_code") is True
            ):
                errors.append(f"{asset_id}: code-capable public route failed")
        elif kind in {"documentation", "aggregate_output"}:
            if not (
                disposition == "public_file"
                and access == "public"
                and repository.get("accepts_public_files") is True
            ):
                errors.append(f"{asset_id}: public-file route failed")
    if by_id:
        code_repos = {
            by_id.get(asset_id, {}).get("repository")
            for asset_id in ("analysis_code", "analysis_environment")
        }
        if len(code_repos) != 1:
            errors.append("analysis code and environment inventory must travel together")
        external_repos = {
            str(row.get("repository"))
            for row in by_id.values()
            if row.get("repository") != "internal_only"
        }
        if len(external_repos) < 2:
            errors.append("the final package must use a real repository split")
    return errors


def _load_plan() -> tuple[dict[str, Any], list[str]]:
    try:
        plan = _read_json(PLAN_PATH)
    except (OSError, json.JSONDecodeError) as exc:
        return {}, [f"cannot read deposit_plan.json: {exc}"]
    return plan, _plan_errors(plan)


def _destination(row: dict[str, Any], asset: dict[str, Any]) -> str:
    if row["disposition"] == "excluded_external_file":
        return ""
    source = Path(str(asset["path"]))
    return (
        Path("staging")
        / str(row["repository"])
        / str(row["disposition"])
        / source.name
    ).as_posix()


def _expected_manifest(plan: dict[str, Any], staging_root: Path) -> list[dict[str, str]]:
    assets = _asset_map()
    by_id = {str(row["asset_id"]): row for row in plan["assets"]}
    rows: list[dict[str, str]] = []
    for asset_id, asset in assets.items():
        plan_row = by_id[asset_id]
        source_path = ROOT / str(asset["path"])
        relative = _destination(plan_row, asset)
        staged_path = staging_root / Path(relative).relative_to("staging") if relative else None
        rows.append(
            {
                "asset_id": asset_id,
                "source_path": str(asset["path"]),
                "source_sha256": _sha256(source_path),
                "disposition": str(plan_row["disposition"]),
                "repository": str(plan_row["repository"]),
                "staged_path": relative,
                "staged_sha256": _sha256(staged_path) if staged_path and staged_path.is_file() else "",
                "bytes": str(source_path.stat().st_size),
                "evidence_refs": ";".join(str(ref) for ref in plan_row["evidence_refs"]),
            }
        )
    return rows


def _write_manifest(rows: list[dict[str, str]]) -> None:
    temporary = MANIFEST.with_suffix(".csv.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_HEADER, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(MANIFEST)


def _read_manifest() -> list[dict[str, str]]:
    try:
        with MANIFEST.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            return list(reader) if tuple(reader.fieldnames or ()) == MANIFEST_HEADER else []
    except OSError:
        return []


def _build_state(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "checkpoint_id": "DMS-NEURO-042-build-reconciled",
        "phase": "package_built_pending_review",
        "plan_revision": plan["plan_revision"],
        "source_bundle_sha256": _bundle_hash(),
        "plan_sha256": _sha256(PLAN_PATH),
        "manifest_sha256": _sha256(MANIFEST),
        "staged_assets": [
            row["asset_id"] for row in _read_manifest() if row["staged_path"]
        ],
        "excluded_external_assets": [
            row["asset_id"] for row in _read_manifest() if not row["staged_path"]
        ],
        "external_deposit_executed": False,
    }


def _build_errors(plan: dict[str, Any]) -> list[str]:
    errors = _plan_errors(plan)
    if errors:
        return errors
    expected = _expected_manifest(plan, STAGING)
    actual = _read_manifest()
    if actual != expected:
        errors.append("package_manifest.csv is absent, stale, or inconsistent with source bytes")
    staged_files = {
        path.relative_to(ROOT).as_posix()
        for path in STAGING.rglob("*")
        if path.is_file() and not path.is_symlink()
    } if STAGING.is_dir() else set()
    expected_files = {row["staged_path"] for row in expected if row["staged_path"]}
    if staged_files != expected_files:
        errors.append("staging tree has missing, extra, stale, or excluded files")
    if any(
        row["staged_path"] and row["source_sha256"] != row["staged_sha256"]
        for row in expected
    ):
        errors.append("one or more staged files differ from their protected source bytes")
    state = _read_json(BUILD_STATE) if BUILD_STATE.is_file() else {}
    if state != _build_state(plan):
        errors.append(".dms_build_state.json is absent, stale, or noncanonical")
    return errors


def _stage_objects(plan: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    token = hashlib.sha256(
        "\n".join(
            (
                "dms-local-stage-v1",
                _bundle_hash(),
                _sha256(PLAN_PATH),
                _sha256(MANIFEST),
                _sha256(HANDOFF),
                str(plan["plan_revision"]),
            )
        ).encode()
    ).hexdigest()
    state = {
        "schema_version": 1,
        "stage_id": "DMS-NEURO-042-local-review",
        "phase": "staged_pending_institutional_review",
        "plan_revision": plan["plan_revision"],
        "source_bundle_sha256": _bundle_hash(),
        "plan_sha256": _sha256(PLAN_PATH),
        "manifest_sha256": _sha256(MANIFEST),
        "handoff_sha256": _sha256(HANDOFF),
        "stage_token": token,
        "external_deposit_executed": False,
    }
    receipt = {
        "receipt_type": "local_dms_package_stage",
        "stage_id": state["stage_id"],
        "phase": state["phase"],
        "plan_revision": state["plan_revision"],
        "source_bundle_sha256": state["source_bundle_sha256"],
        "plan_sha256": state["plan_sha256"],
        "manifest_sha256": state["manifest_sha256"],
        "handoff_sha256": state["handoff_sha256"],
        "stage_token": token,
        "external_deposit_executed": False,
    }
    return state, receipt


def command_status(_: argparse.Namespace) -> int:
    state = _read_json(BUILD_STATE) if BUILD_STATE.is_file() else {}
    print(json.dumps({"build_state": state, "stage_present": STAGE_STATE.is_file()}, indent=2, sort_keys=True))
    return 0


def command_scan(_: argparse.Namespace) -> int:
    inventory = []
    for asset_id, asset in _asset_map().items():
        path = ROOT / str(asset["path"])
        inventory.append(
            {
                "asset_id": asset_id,
                "path": asset["path"],
                "kind": asset["kind"],
                "participant_level": asset["participant_level"],
                "consent_group": asset["consent_group"],
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    print(json.dumps({"assets": inventory, "source_errors": _source_errors()}, indent=2, sort_keys=True))
    return 0 if not _source_errors() else 1


def command_build(_: argparse.Namespace) -> int:
    plan, errors = _load_plan()
    if errors:
        print(json.dumps({"built": False, "errors": errors}, indent=2), file=sys.stderr)
        return 1
    assets = _asset_map()
    by_id = {str(row["asset_id"]): row for row in plan["assets"]}
    with tempfile.TemporaryDirectory(prefix=".dms-build-", dir=ROOT) as temporary:
        next_staging = Path(temporary) / "staging"
        for asset_id, asset in assets.items():
            row = by_id[asset_id]
            relative = _destination(row, asset)
            if not relative:
                continue
            destination = next_staging / Path(relative).relative_to("staging")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / str(asset["path"]), destination)
        if STAGING.exists():
            shutil.rmtree(STAGING)
        shutil.copytree(next_staging, STAGING)
    _write_manifest(_expected_manifest(plan, STAGING))
    _write_json(BUILD_STATE, _build_state(plan))
    print(
        json.dumps(
            {
                "built": True,
                "staged_assets": _build_state(plan)["staged_assets"],
                "excluded_external_assets": _build_state(plan)["excluded_external_assets"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _handoff_errors() -> list[str]:
    if not HANDOFF.is_file() or HANDOFF.is_symlink() or HANDOFF.stat().st_size < 800:
        return ["revised_plan.md must be a reviewable file of at least 800 bytes"]
    low = HANDOFF.read_text(encoding="utf-8", errors="replace").casefold()
    required = (
        "surve",
        "controlled",
        "audio",
        "transcript",
        "metadata",
        "code",
        "publication",
        "privacy review",
        "institutional review",
        "pending",
        "interrupted",
        "offline",
        "no deposit",
    )
    return [f"revised_plan.md omits required topic: {term}" for term in required if term not in low]


def command_validate(_: argparse.Namespace) -> int:
    plan, errors = _load_plan()
    if not errors:
        errors.extend(_build_errors(plan))
    errors.extend(_handoff_errors())
    print(json.dumps({"valid": not errors, "errors": errors}, indent=2, sort_keys=True))
    return 0 if not errors else 1


def command_stage(args: argparse.Namespace) -> int:
    if command_validate(args):
        return 1
    plan = _read_json(PLAN_PATH)
    state, receipt = _stage_objects(plan)
    _write_json(STAGE_STATE, state)
    _write_json(RECEIPT, receipt)
    print(json.dumps({"staged": True, "stage_token": state["stage_token"]}, indent=2))
    return 0


def command_verify_stage(_: argparse.Namespace) -> int:
    plan, errors = _load_plan()
    if not errors:
        errors.extend(_build_errors(plan))
        errors.extend(_handoff_errors())
    if not errors:
        expected_state, expected_receipt = _stage_objects(plan)
        try:
            state = _read_json(STAGE_STATE)
            receipt = _read_json(RECEIPT)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"stage state or receipt unreadable: {exc}")
        else:
            if state != expected_state:
                errors.append("stage state is stale or noncanonical")
            if receipt != expected_receipt:
                errors.append("stage receipt is stale or noncanonical")
    print(json.dumps({"stage_valid": not errors, "errors": errors}, indent=2, sort_keys=True))
    return 0 if not errors else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status", help="show interrupted build and local stage state").set_defaults(func=command_status)
    subparsers.add_parser("scan", help="hash and inventory protected source assets").set_defaults(func=command_scan)
    subparsers.add_parser("build", help="reconcile plan and atomically rebuild staging").set_defaults(func=command_build)
    subparsers.add_parser("validate", help="validate plan, package bytes, manifest, and handoff").set_defaults(func=command_validate)
    subparsers.add_parser("stage", help="create a local hash-bound review receipt").set_defaults(func=command_stage)
    subparsers.add_parser("verify-stage", help="verify exact stage state and receipt").set_defaults(func=command_verify_stage)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
