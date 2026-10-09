#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


TASK = Path(__file__).resolve().parents[2]
WORKSPACE = TASK / "workspace"
REFERENCE = TASK / "tests/reference"


def digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def integrity(name: str, version: str) -> str:
    return "sha256-" + digest(f"synthetic-registry:{name}@{version}")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def record(name: str, version: str, *, dependencies: dict[str, str] | None = None,
           peers: dict[str, str] | None = None, engine: str = ">=18.0.0 <21.0.0",
           native: dict[str, object] | None = None) -> dict[str, object]:
    value: dict[str, object] = {
        "version": version,
        "integrity": integrity(name, version),
        "engines": {"node": engine},
    }
    if dependencies:
        value["dependencies"] = dependencies
    if peers:
        value["peerDependencies"] = peers
    if native:
        value["native"] = native
    return value


def lock_for(manifest: dict[str, object], registry: dict[str, object]) -> dict[str, object]:
    direct = dict(manifest["dependencies"])
    selected: dict[str, str] = {}
    queue = list(direct.items())
    while queue:
        name, version = queue.pop(0)
        if name in selected:
            if selected[name] != version:
                raise ValueError((name, selected[name], version))
            continue
        selected[name] = version
        row = registry[name][version]
        queue.extend(row.get("dependencies", {}).items())
    packages: dict[str, object] = {
        "": {"name": manifest["name"], "version": manifest["version"], "dependencies": direct}
    }
    for name, version in sorted(selected.items()):
        source = registry[name][version]
        packages[f"node_modules/{name}"] = {
            key: source[key]
            for key in ("version", "integrity", "dependencies", "peerDependencies", "engines", "native")
            if key in source and source[key] not in ({}, None)
        }
    return {
        "name": manifest["name"],
        "version": manifest["version"],
        "lockfileVersion": 3,
        "requires": True,
        "packages": packages,
    }


def generate_inputs() -> None:
    for name in ("policy", "evidence", "repo", "state", "dist"):
        path = WORKSPACE / name
        if path.exists() and name == "dist":
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)
    registry = {
        "archive-stack": {
            "4.8.0": record("archive-stack", "4.8.0", dependencies={"zip-stream": "1.4.2"}, peers={"document-loader": ">=2.2.0 <3.0.0"}),
            "4.8.1": record("archive-stack", "4.8.1", dependencies={"zip-stream": "1.4.3"}, peers={"document-loader": ">=2.2.0 <3.0.0"}),
            "4.9.0": record("archive-stack", "4.9.0", dependencies={"zip-stream": "1.5.1"}, peers={"document-loader": ">=2.3.0 <3.0.0"}),
            "5.0.0": record("archive-stack", "5.0.0", dependencies={"zip-stream": "2.0.0"}, peers={"document-loader": ">=3.0.0 <4.0.0"}, engine=">=22.0.0 <23.0.0"),
        },
        "document-loader": {
            "2.2.0": record("document-loader", "2.2.0", dependencies={"zip-stream": "1.4.2"}, peers={"archive-stack": ">=4.8.0 <5.0.0"}),
            "2.2.1": record("document-loader", "2.2.1", dependencies={"zip-stream": "1.4.3"}, peers={"archive-stack": ">=4.8.0 <5.0.0"}),
            "2.3.0": record("document-loader", "2.3.0", dependencies={"zip-stream": "1.5.1"}, peers={"archive-stack": ">=4.9.0 <5.0.0"}),
            "2.4.0": record("document-loader", "2.4.0", dependencies={"zip-stream": "1.5.1", "fast-crc-native": "4.0.0"}, peers={"archive-stack": ">=4.9.0 <5.0.0"}),
        },
        "zip-stream": {
            version: record("zip-stream", version)
            for version in ("1.4.2", "1.4.3", "1.5.1", "2.0.0")
        },
        "fast-crc-native": {
            "4.0.0": record("fast-crc-native", "4.0.0", native={"platform": "linux/amd64", "node_api": 9, "glibc_min": "2.38.0"})
        },
        "render-native": {
            "3.1.0": record("render-native", "3.1.0", dependencies={"pixel-abi": "2.6.0"})
        },
        "pixel-abi": {
            "2.6.0": record("pixel-abi", "2.6.0", native={"platform": "linux/amd64", "node_api": 8, "glibc_min": "2.28.0"})
        },
        "telemetry-core": {
            "2.5.0": record("telemetry-core", "2.5.0", dependencies={"log-helper": "1.1.0"})
        },
        "log-helper": {"1.1.0": record("log-helper", "1.1.0")},
        "shell-helper": {"7.0.0": record("shell-helper", "7.0.0")},
    }
    initial_direct = {
        "archive-stack": "4.8.0",
        "document-loader": "2.2.0",
        "render-native": "3.1.0",
        "telemetry-core": "2.5.0",
    }
    policy = {
        "schema_version": 1,
        "release_id": "REL-REPORT-2026-08",
        "candidate_tag": "report-worker:2026.08-rc2",
        "application_name": "report-worker",
        "application_version": "2026.8.0",
        "prior_image_digest": "sha256:" + digest("prior-report-worker-image"),
        "runtime": {"node_version": "20.16.0", "node_api": 9, "glibc": "2.36.0", "platform": "linux/amd64"},
        "initial_direct_dependencies": initial_direct,
        "remediation_direct_packages": ["archive-stack", "document-loader"],
        "selection_policy": "fewest_changed_direct_packages_then_lowest_registry_steps",
        "allowed_builder_id": "urn:synthetic:builder:hermetic-image-v3",
        "allowed_build_type": "https://example.invalid/buildtypes/oci-offline/v1",
        "attestation_key_id": "synthetic-release-attestor-2026",
        "attestation_verifier": "offline-demo-verifier-v1",
        "stage_boundary": "local_only_pending_release_approval",
    }
    base_digest = "sha256:" + digest("synthetic-node20-base-manifest")
    base = {
        "name": "synthetic.registry/runtime/node20",
        "manifest_digest": base_digest,
        "architecture": "amd64",
        "os": "linux",
        "runtime": policy["runtime"],
        "config": {"digest": "sha256:" + digest("synthetic-node20-base-config"), "size": 612},
        "layers": [
            {"mediaType": "application/vnd.oci.image.layer.v1.tar+gzip", "digest": "sha256:" + digest("synthetic-base-layer-1"), "size": 48211},
            {"mediaType": "application/vnd.oci.image.layer.v1.tar+gzip", "digest": "sha256:" + digest("synthetic-base-layer-2"), "size": 12907},
        ],
    }
    advisories = {
        "snapshot_id": "SYN-ADV-2026-08-17",
        "advisories": [
            {"advisory_id": "CVE-SYN-2026-1042", "package": "zip-stream", "affected": ">=1.0.0 <1.5.0", "severity": "critical", "summary": "crafted archive boundary bypass"},
            {"advisory_id": "CVE-SYN-2025-7331", "package": "render-native", "affected": ">=1.0.0 <3.0.0", "severity": "high", "summary": "legacy renderer memory fault"},
            {"advisory_id": "CVE-SYN-2026-8800", "package": "shell-helper", "affected": ">=6.0.0 <7.1.0", "severity": "critical", "summary": "absent-package command injection lure"},
        ],
    }
    compatibility = {
        "matrix_id": "REPORT-RUNTIME-20-A",
        "profiles": [
            {"profile_id": "archive-import-and-stream", "required_packages": {"zip-stream": "1.5.1"}, "version_constraints": {"archive-stack": ">=4.9.0 <5.0.0", "document-loader": ">=2.3.0 <2.4.0"}, "forbidden_packages": []},
            {"profile_id": "native-report-render", "required_packages": {"render-native": "3.1.0", "pixel-abi": "2.6.0"}, "version_constraints": {}, "forbidden_packages": ["fast-crc-native"]},
            {"profile_id": "telemetry-regression", "required_packages": {"telemetry-core": "2.5.0", "log-helper": "1.1.0"}, "version_constraints": {}, "forbidden_packages": []},
        ],
    }
    prior = {
        "statement_id": "PROV-REPORT-RC1",
        "verified": True,
        "builder_id": policy["allowed_builder_id"],
        "build_type": policy["allowed_build_type"],
        "source": {"uri": "git+https://example.invalid/synthetic/report-worker", "digest": "sha256:" + digest("report-worker-source-revision-88a1")},
        "base": {"uri": base["name"], "digest": base_digest},
        "subject": {"name": "report-worker", "digest": policy["prior_image_digest"]},
    }
    write_json(WORKSPACE / "policy/release_policy.json", policy)
    write_json(WORKSPACE / "evidence/registry_snapshot.json", {"snapshot_id": "SYN-NPM-2026-08-17", "packages": registry})
    write_json(WORKSPACE / "evidence/advisories.json", advisories)
    write_json(WORKSPACE / "evidence/base_image.json", base)
    write_json(WORKSPACE / "evidence/compatibility_matrix.json", compatibility)
    write_json(WORKSPACE / "evidence/prior_provenance.json", prior)
    manifest = {"name": "report-worker", "version": "2026.8.0", "private": True, "dependencies": initial_direct}
    write_json(WORKSPACE / "repo/package.json", manifest)
    write_json(WORKSPACE / "repo/package-lock.json", lock_for(manifest, registry))
    (WORKSPACE / "repo/Containerfile").write_text(
        f"FROM synthetic.registry/runtime/node20@{base_digest}\nWORKDIR /srv/report-worker\nCOPY package.json package-lock.json ./\nRUN synthetic-npm-ci --offline --ignore-scripts=false\nCOPY server.js ./server.js\nENTRYPOINT [\"node\", \"server.js\"]\n",
        encoding="utf-8",
    )
    release = {
        "schema_version": 1,
        "release_id": policy["release_id"],
        "revision": 1,
        "candidate_tag": "report-worker:2026.08-rc1",
        "phase": "blocked_vulnerability",
        "prior_image_digest": policy["prior_image_digest"],
        "staged_image_digest": None,
        "applicable_vulnerabilities": ["CVE-SYN-2026-1042"],
        "abi_status": "pass",
        "provenance_status": "verified",
        "approval_status": "pending",
        "external_push_executed": False,
    }
    write_json(WORKSPACE / "state/release.json", release)
    static_names = [
        "policy/release_policy.json",
        "evidence/registry_snapshot.json",
        "evidence/advisories.json",
        "evidence/base_image.json",
        "evidence/compatibility_matrix.json",
        "evidence/prior_provenance.json",
        "repo/Containerfile",
        "imagectl.py",
    ]
    source_hashes = {name: hashlib.sha256((WORKSPACE / name).read_bytes()).hexdigest() for name in static_names}
    write_json(WORKSPACE / "policy/source_manifest.json", {"schema_version": 1, "files": source_hashes})


def generate_reference() -> None:
    with tempfile.TemporaryDirectory(prefix="hb112-reference-") as temporary:
        workspace = Path(temporary) / "workspace"
        shutil.copytree(WORKSPACE, workspace)
        registry = json.loads((workspace / "evidence/registry_snapshot.json").read_text())["packages"]
        manifest = json.loads((workspace / "repo/package.json").read_text())
        manifest["dependencies"]["archive-stack"] = "4.9.0"
        manifest["dependencies"]["document-loader"] = "2.3.0"
        write_json(workspace / "repo/package.json", manifest)
        write_json(workspace / "repo/package-lock.json", lock_for(manifest, registry))
        plan = {
            "schema_version": 1,
            "release_id": "REL-REPORT-2026-08",
            "strategy": "least_change_coherent",
            "applied_deltas": [
                {"package": "archive-stack", "from": "4.8.0", "to": "4.9.0", "reason": "moves its archive path to zip-stream 1.5.1"},
                {"package": "document-loader", "from": "2.2.0", "to": "2.3.0", "reason": "moves the second archive path and satisfies reciprocal peers"},
            ],
            "vulnerable_paths": [
                ["report-worker", "archive-stack", "zip-stream"],
                ["report-worker", "document-loader", "zip-stream"],
            ],
            "rejected_alternatives": [
                {"selection": {"archive-stack": "5.0.0"}, "reason_code": "node_engine_incompatible", "reason": "requires Node 22 on the pinned Node 20 base"},
                {"selection": {"document-loader": "2.4.0"}, "reason_code": "glibc_runtime_incompatible", "reason": "introduces fast-crc-native requiring glibc 2.38 on glibc 2.36"},
            ],
            "external_push_executed": False,
        }
        write_json(workspace / "remediation_plan.json", plan)
        handoff = """# Report-worker container remediation handoff

Both original paths, report-worker -> archive-stack -> zip-stream and
report-worker -> document-loader -> zip-stream, retained vulnerable
zip-stream 1.4.2. The least-change repair advances archive-stack from 4.8.0 to
4.9.0 and document-loader from 2.2.0 to 2.3.0, yielding the shared secure
zip-stream 1.5.1 while preserving render-native, pixel-abi, telemetry-core, and
log-helper.

Archive-stack 5.0.0 was rejected because its Node 22 engine exceeds the pinned
Node 20.16 base. Document-loader 2.4.0 was rejected because fast-crc-native
requires glibc 2.38 while the image provides glibc 2.36. The rebuilt SBOM and
independent frozen-advisory scan report zero applicable findings. The native
ABI report confirms platform, Node-API, glibc, and all three smoke profiles.

The new provenance preserves the trusted hermetic-image-v3 builder, offline
build type, source revision, and pinned base material while adding the exact
Containerfile and new package-lock digest and binding the rebuilt image. The
local state is staged pending release approval. No push, deployment, approval,
publication, or external notification occurred.
"""
        (workspace / "release_handoff.md").write_text(handoff, encoding="utf-8")
        command = ["python3", "imagectl.py"]
        for args in (("build",), ("validate",), ("stage",), ("verify-stage",), ("verify-stage",)):
            subprocess.run([*command, *args], cwd=workspace, check=True)
        if REFERENCE.exists():
            shutil.rmtree(REFERENCE)
        REFERENCE.mkdir(parents=True)
        names = [
            "repo/package.json", "repo/package-lock.json", "remediation_plan.json",
            "dist/image_manifest.json", "dist/sbom.cdx.json", "dist/vulnerability_scan.json",
            "dist/abi_report.json", "dist/provenance.json", ".image_build_state.json",
            "release_handoff.md", "state/release.json", "state/release_receipt.json",
        ]
        for name in names:
            target = REFERENCE / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(workspace / name, target)


def main() -> None:
    generate_inputs()
    generate_reference()


if __name__ == "__main__":
    main()
