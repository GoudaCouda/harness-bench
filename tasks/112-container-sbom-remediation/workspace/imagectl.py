#!/usr/bin/env python3
"""Offline synthetic OCI image remediation controller."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
POLICY = ROOT / "policy/release_policy.json"
SOURCE_MANIFEST = ROOT / "policy/source_manifest.json"
REGISTRY = ROOT / "evidence/registry_snapshot.json"
ADVISORIES = ROOT / "evidence/advisories.json"
BASE = ROOT / "evidence/base_image.json"
COMPAT = ROOT / "evidence/compatibility_matrix.json"
PRIOR_PROVENANCE = ROOT / "evidence/prior_provenance.json"
PACKAGE = ROOT / "repo/package.json"
LOCK = ROOT / "repo/package-lock.json"
RECIPE = ROOT / "repo/Containerfile"
PLAN = ROOT / "remediation_plan.json"
DIST = ROOT / "dist"
BUILD_STATE = ROOT / ".image_build_state.json"
HANDOFF = ROOT / "release_handoff.md"
RELEASE = ROOT / "state/release.json"
RECEIPT = ROOT / "state/release_receipt.json"
GENERATED = (
    "image_manifest.json",
    "sbom.cdx.json",
    "vulnerability_scan.json",
    "abi_report.json",
    "provenance.json",
)


def fail(message: str) -> None:
    raise ValueError(message)


def load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        fail(f"cannot parse {path.relative_to(ROOT)}: {exc}")


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def pretty(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def version_tuple(value: str) -> tuple[int, int, int]:
    parts = value.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        fail(f"unsupported synthetic version: {value}")
    return tuple(int(part) for part in parts)  # type: ignore[return-value]


def satisfies(version: str, expression: str) -> bool:
    current = version_tuple(version)
    for term in expression.split():
        if term.startswith(">="):
            ok = current >= version_tuple(term[2:])
        elif term.startswith(">"):
            ok = current > version_tuple(term[1:])
        elif term.startswith("<="):
            ok = current <= version_tuple(term[2:])
        elif term.startswith("<"):
            ok = current < version_tuple(term[1:])
        elif term.startswith("^"):
            floor = version_tuple(term[1:])
            ok = current >= floor and current[0] == floor[0]
        else:
            ok = current == version_tuple(term)
        if not ok:
            return False
    return True


def registry() -> dict[str, Any]:
    value = load(REGISTRY)
    packages = value.get("packages") if isinstance(value, dict) else None
    if not isinstance(packages, dict):
        fail("registry packages must be an object")
    return packages


def package_record(packages: dict[str, Any], name: str, version: str) -> dict[str, Any]:
    values = packages.get(name)
    record = values.get(version) if isinstance(values, dict) else None
    if not isinstance(record, dict):
        fail(f"registry has no {name}@{version}")
    return record


def derive_graph(manifest: dict[str, Any]) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    packages = registry()
    direct = manifest.get("dependencies")
    if not isinstance(direct, dict) or not direct:
        fail("package.json dependencies must be a non-empty object")
    selected: dict[str, str] = {}
    records: dict[str, dict[str, Any]] = {}
    queue = [(str(name), str(version)) for name, version in direct.items()]
    while queue:
        name, version = queue.pop(0)
        previous = selected.get(name)
        if previous is not None:
            if previous != version:
                fail(f"dependency conflict for {name}: {previous} versus {version}")
            continue
        record = package_record(packages, name, version)
        selected[name] = version
        records[name] = record
        dependencies = record.get("dependencies", {})
        if not isinstance(dependencies, dict):
            fail(f"registry dependencies malformed for {name}@{version}")
        queue.extend((str(child), str(child_version)) for child, child_version in dependencies.items())
    return {str(k): str(v) for k, v in direct.items()}, records


def graph_errors(manifest: dict[str, Any], lock: dict[str, Any] | None = None) -> list[str]:
    policy = load(POLICY)
    direct, records = derive_graph(manifest)
    errors: list[str] = []
    runtime = policy["runtime"]
    for name, record in records.items():
        version = str(record["version"])
        engine = str(record.get("engines", {}).get("node", ">=0.0.0"))
        if not satisfies(str(runtime["node_version"]), engine):
            errors.append(f"{name}@{version}: Node {runtime['node_version']} violates {engine}")
        peers = record.get("peerDependencies", {})
        if isinstance(peers, dict):
            for peer, expression in peers.items():
                peer_version = direct.get(str(peer))
                if peer_version is None or not satisfies(peer_version, str(expression)):
                    errors.append(f"{name}@{version}: peer {peer} requires {expression}")
    if lock is not None:
        errors.extend(lock_errors(manifest, lock, records))
    return errors


def lock_errors(manifest: dict[str, Any], lock: dict[str, Any], records: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    if lock.get("lockfileVersion") != 3 or lock.get("name") != manifest.get("name") or lock.get("version") != manifest.get("version"):
        errors.append("lock root identity or lockfileVersion is inconsistent")
    locked = lock.get("packages")
    if not isinstance(locked, dict):
        return errors + ["lock packages must be an object"]
    root = locked.get("")
    if not isinstance(root, dict) or root.get("dependencies") != manifest.get("dependencies"):
        errors.append("lock root dependencies do not match package.json")
    expected_keys = {""} | {f"node_modules/{name}" for name in records}
    if set(locked) != expected_keys:
        errors.append(f"lock package keys differ: expected {sorted(expected_keys)}")
    for name, record in records.items():
        row = locked.get(f"node_modules/{name}")
        if not isinstance(row, dict):
            continue
        expected = {
            key: record[key]
            for key in ("version", "integrity", "dependencies", "peerDependencies", "engines", "native")
            if key in record and record[key] not in ({}, None)
        }
        if row != expected:
            errors.append(f"lock metadata differs from registry for {name}@{record['version']}")
    return errors


def findings(records: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    advisory_rows = load(ADVISORIES).get("advisories", [])
    for advisory in advisory_rows:
        name = str(advisory.get("package"))
        record = records.get(name)
        if record and satisfies(str(record["version"]), str(advisory["affected"])):
            result.append({
                "advisory_id": advisory["advisory_id"],
                "package": name,
                "version": record["version"],
                "severity": advisory["severity"],
            })
    return sorted(result, key=lambda row: (row["advisory_id"], row["package"]))


def abi_result(records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    policy = load(POLICY)
    matrix = load(COMPAT)
    runtime = policy["runtime"]
    native_rows: list[dict[str, Any]] = []
    all_pass = True
    for name, record in sorted(records.items()):
        native = record.get("native")
        if not isinstance(native, dict):
            continue
        checks = {
            "platform": native.get("platform") == runtime["platform"],
            "node_api": int(native.get("node_api", 999)) <= int(runtime["node_api"]),
            "glibc": version_tuple(str(native.get("glibc_min"))) <= version_tuple(str(runtime["glibc"])),
        }
        passed = all(checks.values())
        all_pass &= passed
        native_rows.append({
            "package": name,
            "version": record["version"],
            "requirements": native,
            "checks": checks,
            "status": "pass" if passed else "fail",
        })
    versions = {name: str(record["version"]) for name, record in records.items()}
    profiles: list[dict[str, Any]] = []
    for profile in matrix.get("profiles", []):
        required = profile.get("required_packages", {})
        constraints = profile.get("version_constraints", {})
        forbidden = profile.get("forbidden_packages", [])
        passed = (
            isinstance(required, dict)
            and all(versions.get(str(name)) == str(version) for name, version in required.items())
            and isinstance(constraints, dict)
            and all(name in versions and satisfies(versions[name], str(expr)) for name, expr in constraints.items())
            and not any(str(name) in versions for name in forbidden)
        )
        all_pass &= passed
        profiles.append({"profile_id": profile["profile_id"], "status": "pass" if passed else "fail"})
    return {
        "runtime": runtime,
        "native_components": native_rows,
        "profiles": profiles,
        "status": "pass" if all_pass else "fail",
    }


def viable_selection(manifest: dict[str, Any]) -> bool:
    try:
        _, records = derive_graph(manifest)
        return not graph_errors(manifest) and not findings(records) and abi_result(records)["status"] == "pass"
    except (KeyError, TypeError, ValueError):
        return False


def minimal_selection() -> dict[str, str]:
    policy = load(POLICY)
    initial = policy["initial_direct_dependencies"]
    packages = registry()
    targets = policy["remediation_direct_packages"]
    candidates: list[tuple[tuple[int, int, tuple[int, int, int], tuple[int, int, int]], dict[str, str]]] = []
    versions = [list(packages[name]) for name in targets]
    for choices in itertools.product(*versions):
        direct = dict(initial)
        direct.update(dict(zip(targets, choices, strict=True)))
        manifest = {"name": policy["application_name"], "version": policy["application_version"], "dependencies": direct}
        if not viable_selection(manifest):
            continue
        changed = sum(direct[name] != initial[name] for name in targets)
        distance = sum(
            list(packages[name]).index(direct[name]) - list(packages[name]).index(initial[name])
            for name in targets
        )
        candidates.append(((changed, distance, version_tuple(direct[targets[0]]), version_tuple(direct[targets[1]])), direct))
    if not candidates:
        fail("registry snapshot has no viable remediation")
    return min(candidates, key=lambda item: item[0])[1]


def source_errors() -> list[str]:
    manifest = load(SOURCE_MANIFEST)
    errors: list[str] = []
    for relative, expected in manifest.get("files", {}).items():
        path = ROOT / relative
        if not path.is_file() or sha(path) != expected:
            errors.append(f"protected source changed: {relative}")
    return errors


def source_bundle_sha() -> str:
    files = load(SOURCE_MANIFEST)["files"]
    return sha_bytes(canonical(files))


def validate_plan(plan: dict[str, Any], manifest: dict[str, Any]) -> list[str]:
    policy = load(POLICY)
    initial = policy["initial_direct_dependencies"]
    expected = minimal_selection()
    errors: list[str] = []
    if plan.get("schema_version") != 1 or plan.get("release_id") != policy["release_id"] or plan.get("strategy") != "least_change_coherent":
        errors.append("remediation plan identity or strategy is invalid")
    deltas = plan.get("applied_deltas")
    delta_map = {
        str(row.get("package")): (str(row.get("from")), str(row.get("to")))
        for row in deltas if isinstance(row, dict)
    } if isinstance(deltas, list) else {}
    expected_delta = {name: (initial[name], expected[name]) for name in policy["remediation_direct_packages"]}
    if delta_map != expected_delta:
        errors.append("remediation plan applied_deltas do not match the least-change pair")
    paths = plan.get("vulnerable_paths")
    normalized_paths = {tuple(str(part) for part in row) for row in paths if isinstance(row, list)} if isinstance(paths, list) else set()
    required_paths = {
        (policy["application_name"], "archive-stack", "zip-stream"),
        (policy["application_name"], "document-loader", "zip-stream"),
    }
    if normalized_paths != required_paths:
        errors.append("remediation plan must record both original vulnerable paths")
    rejected = plan.get("rejected_alternatives")
    reasons = {str(row.get("reason_code")) for row in rejected if isinstance(row, dict)} if isinstance(rejected, list) else set()
    if not {"node_engine_incompatible", "glibc_runtime_incompatible"}.issubset(reasons):
        errors.append("remediation plan omits required rejected-alternative reasons")
    if plan.get("external_push_executed") is not False:
        errors.append("remediation plan must remain no-push")
    if manifest.get("dependencies") != expected:
        errors.append("package.json is not the least-change viable direct selection")
    return errors


def build_payloads(manifest: dict[str, Any], lock: dict[str, Any]) -> tuple[dict[str, bytes], str]:
    policy = load(POLICY)
    base = load(BASE)
    prior = load(PRIOR_PROVENANCE)
    _, records = derive_graph(manifest)
    lock_hash = sha_bytes(pretty(lock))
    recipe_hash = sha(RECIPE)
    app_layer = {"mediaType": "application/vnd.oci.image.layer.v1.tar+gzip", "digest": f"sha256:{lock_hash}", "size": len(pretty(lock))}
    config = {
        "architecture": base["architecture"],
        "os": base["os"],
        "rootfs": {"type": "layers", "diff_ids": [row["digest"] for row in base["layers"]] + [app_layer["digest"]]},
        "config": {"Entrypoint": ["node", "server.js"], "Env": [f"NODE_VERSION={base['runtime']['node_version']}"]},
    }
    config_bytes = canonical(config)
    manifest_value = {
        "schemaVersion": 2,
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "config": {"mediaType": "application/vnd.oci.image.config.v1+json", "digest": f"sha256:{sha_bytes(config_bytes)}", "size": len(config_bytes)},
        "layers": base["layers"] + [app_layer],
        "annotations": {
            "org.opencontainers.image.base.digest": base["manifest_digest"],
            "org.opencontainers.image.revision": prior["source"]["digest"],
            "org.opencontainers.image.version": policy["candidate_tag"],
        },
    }
    manifest_bytes = pretty(manifest_value)
    image_digest = f"sha256:{sha_bytes(manifest_bytes)}"
    bom_refs = {name: f"pkg:npm/{name}@{record['version']}" for name, record in records.items()}
    components = [
        {
            "type": "library",
            "name": name,
            "version": record["version"],
            "bom-ref": bom_refs[name],
            "hashes": [{"alg": "SHA-256", "content": str(record["integrity"]).removeprefix("sha256-")}],
        }
        for name, record in sorted(records.items())
    ]
    dependencies = [
        {"ref": bom_refs[name], "dependsOn": sorted(bom_refs[child] for child in record.get("dependencies", {}))}
        for name, record in sorted(records.items())
    ]
    sbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{sha_bytes(manifest_bytes)[:32]}",
        "version": 1,
        "metadata": {"component": {"type": "container", "name": policy["application_name"], "version": policy["candidate_tag"], "bom-ref": image_digest}},
        "components": components,
        "dependencies": dependencies,
    }
    scan = {
        "subject_digest": image_digest,
        "advisory_snapshot_sha256": sha(ADVISORIES),
        "scanned_components": len(records),
        "findings": findings(records),
        "status": "clean" if not findings(records) else "blocked",
    }
    abi = abi_result(records)
    abi["subject_digest"] = image_digest
    materials = [
        {"uri": prior["source"]["uri"], "digest": {"sha256": prior["source"]["digest"].removeprefix("sha256:")}},
        {"uri": base["name"], "digest": {"sha256": base["manifest_digest"].removeprefix("sha256:")}},
        {"uri": "file:repo/Containerfile", "digest": {"sha256": recipe_hash}},
        {"uri": "file:repo/package-lock.json", "digest": {"sha256": lock_hash}},
    ]
    predicate = {
        "buildDefinition": {
            "buildType": prior["build_type"],
            "externalParameters": {"candidate_tag": policy["candidate_tag"], "network": "disabled"},
            "resolvedDependencies": materials,
        },
        "runDetails": {"builder": {"id": prior["builder_id"]}},
    }
    unsigned = {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [{"name": policy["application_name"], "digest": {"sha256": image_digest.removeprefix("sha256:")}}],
        "predicateType": "https://slsa.dev/provenance/v1",
        "predicate": predicate,
    }
    payload_hash = sha_bytes(canonical(unsigned))
    key_id = policy["attestation_key_id"]
    provenance = dict(unsigned)
    provenance["signature"] = {
        "key_id": key_id,
        "payload_sha256": payload_hash,
        "value": sha_bytes(f"{payload_hash}:{key_id}:{policy['attestation_verifier']}".encode()),
    }
    return {
        "image_manifest.json": manifest_bytes,
        "sbom.cdx.json": pretty(sbom),
        "vulnerability_scan.json": pretty(scan),
        "abi_report.json": pretty(abi),
        "provenance.json": pretty(provenance),
    }, image_digest


def expected_build_state(payloads: dict[str, bytes], image_digest: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "release_id": load(POLICY)["release_id"],
        "phase": "built_verified_offline",
        "image_digest": image_digest,
        "source_bundle_sha256": source_bundle_sha(),
        "package_json_sha256": sha(PACKAGE),
        "package_lock_sha256": sha(LOCK),
        "remediation_plan_sha256": sha(PLAN),
        "generated_sha256": {name: sha_bytes(value) for name, value in sorted(payloads.items())},
        "external_push_executed": False,
    }


def build_errors() -> tuple[list[str], dict[str, bytes] | None, str | None]:
    errors = source_errors()
    try:
        manifest = load(PACKAGE)
        lock = load(LOCK)
        plan = load(PLAN)
        errors.extend(graph_errors(manifest, lock))
        _, records = derive_graph(manifest)
        current_findings = findings(records)
        if current_findings:
            errors.append(f"applicable vulnerabilities remain: {current_findings}")
        abi = abi_result(records)
        if abi["status"] != "pass":
            errors.append("runtime/native ABI or compatibility profile failed")
        errors.extend(validate_plan(plan, manifest))
        if errors:
            return errors, None, None
        payloads, image_digest = build_payloads(manifest, lock)
        return [], payloads, image_digest
    except (KeyError, TypeError, ValueError) as exc:
        return errors + [str(exc)], None, None


def command_status() -> int:
    release = load(RELEASE)
    value = {
        "release": release,
        "build_state_present": BUILD_STATE.is_file(),
        "receipt_present": RECEIPT.is_file(),
        "protected_source_errors": source_errors(),
    }
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


def command_graph() -> int:
    manifest = load(PACKAGE)
    direct, records = derive_graph(manifest)
    edges = []
    for name, record in sorted(records.items()):
        edges.extend({"from": name, "to": child, "version": version} for child, version in sorted(record.get("dependencies", {}).items()))
    vulnerable_names = {row["package"] for row in findings(records)}
    paths = []
    for root_name in direct:
        stack = [(root_name, [load(POLICY)["application_name"], root_name])]
        while stack:
            name, path = stack.pop()
            if name in vulnerable_names:
                paths.append(path)
            for child in records[name].get("dependencies", {}):
                stack.append((child, path + [child]))
    print(json.dumps({"direct": direct, "components": {name: row["version"] for name, row in sorted(records.items())}, "edges": edges, "vulnerable_paths": paths}, indent=2, sort_keys=True))
    return 0


def command_scan() -> int:
    manifest = load(PACKAGE)
    _, records = derive_graph(manifest)
    result = findings(records)
    print(json.dumps({"findings": result, "status": "clean" if not result else "blocked"}, indent=2, sort_keys=True))
    return 0 if not result else 1


def command_abi() -> int:
    manifest = load(PACKAGE)
    _, records = derive_graph(manifest)
    value = abi_result(records)
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0 if value["status"] == "pass" else 1


def command_build() -> int:
    errors, payloads, image_digest = build_errors()
    if errors or payloads is None or image_digest is None:
        print(json.dumps({"built": False, "errors": errors}, indent=2, sort_keys=True))
        return 1
    temporary = Path(tempfile.mkdtemp(prefix=".image-build-", dir=ROOT))
    try:
        for name, value in payloads.items():
            (temporary / name).write_bytes(value)
        if DIST.exists():
            shutil.rmtree(DIST)
        os.replace(temporary, DIST)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    BUILD_STATE.write_bytes(pretty(expected_build_state(payloads, image_digest)))
    print(json.dumps({"built": True, "image_digest": image_digest, "generated": sorted(payloads)}, indent=2, sort_keys=True))
    return 0


def validation_errors(require_handoff: bool = True) -> list[str]:
    errors, payloads, image_digest = build_errors()
    if errors or payloads is None or image_digest is None:
        return errors
    for name, expected in payloads.items():
        path = DIST / name
        if not path.is_file() or path.read_bytes() != expected:
            errors.append(f"generated artifact is missing or stale: dist/{name}")
    expected_state = expected_build_state(payloads, image_digest)
    if not BUILD_STATE.is_file() or load(BUILD_STATE) != expected_state:
        errors.append(".image_build_state.json is missing or stale")
    if require_handoff:
        try:
            text = HANDOFF.read_text(encoding="utf-8").lower()
        except (OSError, UnicodeError):
            text = ""
        topic_groups = {
            "both vulnerable paths": ("archive-stack", "document-loader", "zip-stream"),
            "Node-major rejection": ("node 22", "engine"),
            "glibc rejection": ("glibc 2.38", "glibc_2.38"),
            "scan closure": ("clean", "zero applicable", "no applicable"),
            "ABI closure": ("abi", "node-api"),
            "provenance": ("provenance", "builder"),
            "pending approval": ("pending release approval", "staged pending"),
            "no push": ("no push", "not pushed", "external_push_executed"),
        }
        for label, variants in topic_groups.items():
            if label == "both vulnerable paths":
                if not all(value in text for value in variants):
                    errors.append(f"release_handoff.md omits {label}")
            elif not any(value in text for value in variants):
                errors.append(f"release_handoff.md omits {label}")
    return errors


def command_validate() -> int:
    errors = validation_errors()
    print(json.dumps({"valid": not errors, "errors": errors}, indent=2, sort_keys=True))
    return 0 if not errors else 1


def expected_stage() -> tuple[dict[str, Any], dict[str, Any]]:
    policy = load(POLICY)
    build_state = load(BUILD_STATE)
    release = load(RELEASE)
    base_revision = 1 if release.get("revision") in (1, 2) else int(release.get("revision", 0))
    state = {
        "schema_version": 1,
        "release_id": policy["release_id"],
        "revision": base_revision + 1,
        "candidate_tag": policy["candidate_tag"],
        "phase": "staged_pending_release_approval",
        "prior_image_digest": policy["prior_image_digest"],
        "staged_image_digest": build_state["image_digest"],
        "applicable_vulnerabilities": [],
        "abi_status": "pass",
        "provenance_status": "verified",
        "approval_status": "pending",
        "external_push_executed": False,
        "build_state_sha256": sha(BUILD_STATE),
    }
    unsigned = dict(state)
    token = sha_bytes(canonical(unsigned))
    state["stage_token"] = token
    receipt = {
        "receipt_type": "local_container_remediation_stage",
        "release_id": policy["release_id"],
        "revision": state["revision"],
        "phase": state["phase"],
        "image_digest": state["staged_image_digest"],
        "build_state_sha256": state["build_state_sha256"],
        "provenance_sha256": sha(DIST / "provenance.json"),
        "sbom_sha256": sha(DIST / "sbom.cdx.json"),
        "stage_token": token,
        "external_push_executed": False,
    }
    return state, receipt


def command_stage() -> int:
    errors = validation_errors()
    if errors:
        print(json.dumps({"staged": False, "errors": errors}, indent=2, sort_keys=True))
        return 1
    release = load(RELEASE)
    if release.get("phase") == "staged_pending_release_approval" and RECEIPT.is_file():
        current_state, current_receipt = expected_stage()
        current_state["revision"] = release.get("revision")
        current_receipt["revision"] = release.get("revision")
        if release == current_state and load(RECEIPT) == current_receipt:
            print(json.dumps({"staged": True, "replayed": True, "stage_token": release["stage_token"]}, indent=2, sort_keys=True))
            return 0
    state, receipt = expected_stage()
    RELEASE.write_bytes(pretty(state))
    RECEIPT.write_bytes(pretty(receipt))
    print(json.dumps({"staged": True, "replayed": False, "stage_token": state["stage_token"]}, indent=2, sort_keys=True))
    return 0


def command_verify_stage() -> int:
    errors = validation_errors()
    if not RELEASE.is_file() or not RECEIPT.is_file():
        errors.append("release state or receipt is missing")
    else:
        release = load(RELEASE)
        receipt = load(RECEIPT)
        expected_state, expected_receipt = expected_stage()
        expected_state["revision"] = release.get("revision")
        expected_receipt["revision"] = release.get("revision")
        if release != expected_state:
            errors.append("release state does not match the current build")
        if receipt != expected_receipt:
            errors.append("release receipt does not match the current build")
    print(json.dumps({"stage_valid": not errors, "errors": errors}, indent=2, sort_keys=True))
    return 0 if not errors else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("status", "graph", "scan", "abi", "build", "validate", "stage", "verify-stage"))
    args = parser.parse_args()
    try:
        return globals()[f"command_{args.command.replace('-', '_')}"]()
    except (KeyError, TypeError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, indent=2, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
