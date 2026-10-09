#!/usr/bin/env python3
"""Build deterministic synthetic repository/artifact fixtures and reference state."""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import sqlite3
import subprocess
import tarfile
from pathlib import Path


TASK = Path(__file__).resolve().parents[2]
WORKSPACE = TASK / "workspace"
REFERENCE = TASK / "tests" / "reference"
SECRET = b"HB_SYNTH_SECRET_INC114_ALPHA_7Q9M2V6N_NOT_VALID"
PLACEHOLDER = "${RELEASE_PUBLISHER_TOKEN}"


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _commit_id(
    parent: str | None, when: str, subject: str, files: dict[str, bytes]
) -> str:
    digest = hashlib.sha256()
    digest.update((parent or "ROOT").encode())
    digest.update(when.encode())
    digest.update(subject.encode())
    for path, content in sorted(files.items()):
        digest.update(path.encode())
        digest.update(b"\0")
        digest.update(content)
    return "r" + digest.hexdigest()[:15]


def build_repository() -> None:
    path = WORKSPACE / "repository.db"
    path.unlink(missing_ok=True)
    db = sqlite3.connect(path)
    db.executescript(
        """
        PRAGMA journal_mode=DELETE;
        CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE commits(
          commit_id TEXT PRIMARY KEY,
          parent_id TEXT,
          authored_at TEXT NOT NULL,
          subject TEXT NOT NULL
        );
        CREATE TABLE refs(
          ref_name TEXT PRIMARY KEY,
          kind TEXT NOT NULL,
          commit_id TEXT NOT NULL
        );
        CREATE TABLE files(
          commit_id TEXT NOT NULL,
          path TEXT NOT NULL,
          mode TEXT NOT NULL,
          content BLOB NOT NULL,
          PRIMARY KEY(commit_id, path)
        );
        """
    )
    db.executemany(
        "INSERT INTO metadata VALUES (?,?)",
        [("format", "nimbus-repository-export-v1"), ("repository", "nimbus-release")],
    )
    history: list[tuple[str, str | None, str, str, dict[str, bytes]]] = []
    files0 = {
        "README.md": b"# Nimbus release service\nSynthetic offline fixture.\n",
        "deploy/release.env": b"RELEASE_REGION=global\nRELEASE_PUBLISHER_TOKEN=${RELEASE_PUBLISHER_TOKEN}\n",
    }
    c0 = _commit_id(None, "2026-08-10T08:00:00Z", "initialize release service", files0)
    history.append(
        (c0, None, "2026-08-10T08:00:00Z", "initialize release service", files0)
    )

    files1 = dict(files0)
    files1["deploy/release.env"] = (
        b"RELEASE_REGION=global\nRELEASE_PUBLISHER_TOKEN=" + SECRET + b"\n"
    )
    c1 = _commit_id(
        c0, "2026-08-12T09:15:00Z", "temporarily wire release publisher", files1
    )
    history.append(
        (c1, c0, "2026-08-12T09:15:00Z", "temporarily wire release publisher", files1)
    )

    files2 = dict(files1)
    files2["deploy/release.env"] = files0["deploy/release.env"]
    files2[".ci/cache/release.args"] = (
        b"--publisher-token=" + SECRET + b"\n--region=global\n"
    )
    c2 = _commit_id(
        c1,
        "2026-08-13T14:20:00Z",
        "redact deploy env but retain generated cache",
        files2,
    )
    history.append(
        (
            c2,
            c1,
            "2026-08-13T14:20:00Z",
            "redact deploy env but retain generated cache",
            files2,
        )
    )

    files3 = dict(files2)
    files3.pop(".ci/cache/release.args")
    files3["docs/release-runbook.md"] = (
        b"Release board approval is required before publication.\n"
    )
    c3 = _commit_id(
        c2, "2026-08-14T16:45:00Z", "remove generated cache and add runbook", files3
    )
    history.append(
        (
            c3,
            c2,
            "2026-08-14T16:45:00Z",
            "remove generated cache and add runbook",
            files3,
        )
    )

    clean_files = dict(files0)
    clean_files["docs/operations.md"] = b"Rotate synthetic fixtures every quarter.\n"
    cu = _commit_id(
        c0, "2026-08-11T10:00:00Z", "document operations cadence", clean_files
    )
    history.append(
        (cu, c0, "2026-08-11T10:00:00Z", "document operations cadence", clean_files)
    )

    for commit, parent, when, subject, files in history:
        db.execute(
            "INSERT INTO commits VALUES (?,?,?,?)", (commit, parent, when, subject)
        )
        db.executemany(
            "INSERT INTO files VALUES (?,?,?,?)",
            [
                (commit, name, "100644", content)
                for name, content in sorted(files.items())
            ],
        )
    db.executemany(
        "INSERT INTO refs VALUES (?,?,?)",
        [
            ("refs/heads/main", "branch", c3),
            ("refs/heads/release/2.7", "branch", c1),
            ("refs/heads/ops-docs", "branch", cu),
            ("refs/tags/build-2026.08.12", "tag", c1),
            ("refs/tags/baseline-clean", "tag", c0),
        ],
    )
    db.commit()
    db.execute("VACUUM")
    db.close()


def _tar(path: Path, members: dict[str, bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, "w", format=tarfile.USTAR_FORMAT) as archive:
        for name, content in sorted(members.items()):
            info = tarfile.TarInfo(name)
            info.size = len(content)
            info.mode = 0o644
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            archive.addfile(info, io.BytesIO(content))


def build_artifacts() -> None:
    _tar(
        WORKSPACE / "artifact_store" / "build-417.tar",
        {
            "app/release.env": b"PUBLISHER_TOKEN=" + SECRET + b"\n",
            "meta/provenance.json": b'{"build":"417","commit":"exposed"}\n',
        },
    )
    (WORKSPACE / "mirrors" / "build-417-copy.tar").write_bytes(
        b"NIMBUS_OPAQUE_MIRROR\nsource=ART-417\npayload_inherited=true\n"
    )
    _tar(
        WORKSPACE / "artifact_store" / "build-419.tar",
        {
            "app/release.env": b"PUBLISHER_TOKEN=HB_SYNTH_SECRET_[REDACTED]_NOT_VALID\n",
            "meta/provenance.json": b'{"build":"419","commit":"partially-redacted"}\n',
        },
    )
    _tar(
        WORKSPACE / "artifact_store" / "build-420.tar",
        {
            "app/release.env": f"PUBLISHER_TOKEN={PLACEHOLDER}\n".encode(),
            "meta/provenance.json": b'{"build":"420","credential_ref":"vault://synthetic/nimbus/release-publisher@v3"}\n',
        },
    )
    _tar(
        WORKSPACE / "artifact_store" / "detector-demo.tar",
        {"training/example.txt": b"HB_SYNTH_SECRET_DEMO_NOT_VALID\n"},
    )
    log = WORKSPACE / "logs" / "build-418.log"
    log.write_text(
        log.read_text(encoding="utf-8").replace(
            "PLACEHOLDER_GENERATED", SECRET.decode()
        ),
        encoding="utf-8",
    )
    incident = json.loads((WORKSPACE / "incident.json").read_text(encoding="utf-8"))
    incident["fingerprint_sha256"] = hashlib.sha256(SECRET).hexdigest()
    (WORKSPACE / "incident.json").write_text(
        json.dumps(incident, indent=2) + "\n", encoding="utf-8"
    )


def build_reference() -> None:
    if REFERENCE.exists():
        shutil.rmtree(REFERENCE)
    REFERENCE.mkdir(parents=True)
    with subprocess.Popen(
        ["python3", "tools/containmentctl.py", "scan", "--out", "exposure_scan.json"],
        cwd=WORKSPACE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    ) as completed:
        output, _ = completed.communicate()
        if completed.returncode:
            raise RuntimeError(output)
    scan = json.loads((WORKSPACE / "exposure_scan.json").read_text())
    plan = {
        "incident_id": "INC-114-2026-08",
        "credential_id": "SYN-CRED-REL-PUB-A",
        "impacted_refs": scan["repository"]["impacted_refs"],
        "quarantine_nodes": ["ART-417", "LOG-418", "MIR-417-A"],
        "detach_channels": ["release-production", "rollback-west"],
        "rewrite": {
            "replacement_text": PLACEHOLDER,
            "preserve_ref_names": True,
            "preserve_unaffected_history": True,
        },
        "replacement": {
            "secret_ref": "vault://synthetic/nimbus/release-publisher@v3",
            "scope": ["release:publish:nimbus"],
            "owner": "release-automation",
            "activate": False,
        },
        "evidence": [
            "repository.db#refs/heads/main",
            "repository.db#refs/heads/release/2.7",
            "repository.db#refs/tags/build-2026.08.12",
            "artifact_lineage.json#ART-417",
            "artifact_lineage.json#LOG-418",
            "artifact_lineage.json#MIR-417-A",
            "distribution_state.json#release-production",
            "distribution_state.json#rollback-west",
            "incident.json#credential_id",
            "incident.json#replacement",
        ],
    }
    (WORKSPACE / "containment_plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    for args in (
        ["check-plan", "--plan", "containment_plan.json"],
        [
            "rewrite",
            "--plan",
            "containment_plan.json",
            "--out",
            "sanitized_repository.db",
        ],
        [
            "apply",
            "--plan",
            "containment_plan.json",
            "--repository",
            "sanitized_repository.db",
        ],
    ):
        subprocess.run(
            ["python3", "tools/containmentctl.py", *args], cwd=WORKSPACE, check=True
        )
    handoff = """# INC-114 local containment handoff

Detector DET-REL-7 and `incident.json` bind this response to synthetic credential SYN-CRED-REL-PUB-A. Direct matches occurred in repository commits reachable from main, release/2.7, and build-2026.08.12, in ART-417, and in LOG-418. Payload lineage also carries ART-417 into opaque mirror MIR-417-A; IDX-418 is metadata-only. ART-419 is partially redacted but has no matching fingerprint, ART-420 is clean, and ART-DEMO is a different training fingerprint.

The affected refs were rewritten into `sanitized_repository.db`; exact matches became the environment reference while ref names, logical commits, files, parents, subjects, and the unrelated ops-docs history were preserved. Production and rollback-west were detached and ART-417, LOG-418, and MIR-417-A were quarantined. Nightly, QA, training, IDX-418, ART-419, ART-420, and ART-DEMO were left unchanged.

The append-only local registry now records the old credential as revoked for containment. The replacement is only staged at `vault://synthetic/nimbus/release-publisher@v3`, scoped to `release:publish:nimbus`, owned by release-automation, and not activated. No plaintext replacement was created.

The controller rescan found no incident fingerprint in reachable rewritten history or any distributable payload. It verified preserved history, exact channel closure, append-only events, hashes, and replay stability. Existing developer clones and remote caches remain a coordination risk after a history rewrite; owners must re-clone or clean them before any later authorized publication. This exercise performed no provider revocation, force-push, remote deletion, credential activation, publication, or contact.
"""
    (WORKSPACE / "incident_handoff.md").write_text(handoff, encoding="utf-8")
    subprocess.run(
        [
            "python3",
            "tools/containmentctl.py",
            "verify",
            "--plan",
            "containment_plan.json",
            "--repository",
            "sanitized_repository.db",
        ],
        cwd=WORKSPACE,
        check=True,
    )
    subprocess.run(
        [
            "python3",
            "tools/containmentctl.py",
            "verify",
            "--plan",
            "containment_plan.json",
            "--repository",
            "sanitized_repository.db",
        ],
        cwd=WORKSPACE,
        check=True,
    )
    generated = [
        "exposure_scan.json",
        "containment_plan.json",
        "sanitized_repository.db",
        "distribution_state.json",
        "revocation_registry.jsonl",
        "quarantine_events.jsonl",
        "containment_state.json",
        "replacement_credential.json",
        "recovery_receipt.json",
        "incident_handoff.md",
    ]
    for name in generated:
        shutil.copy2(WORKSPACE / name, REFERENCE / name)


def restore_seed() -> None:
    seed_distribution = {
        "revision": 12,
        "channels": [
            {
                "channel_id": "release-production",
                "artifact_id": "ART-417",
                "status": "active",
                "region": "global",
            },
            {
                "channel_id": "rollback-west",
                "artifact_id": "MIR-417-A",
                "status": "active",
                "region": "us-west",
            },
            {
                "channel_id": "nightly-candidate",
                "artifact_id": "ART-419",
                "status": "held",
                "region": "internal",
            },
            {
                "channel_id": "qa-clean",
                "artifact_id": "ART-420",
                "status": "qa_only",
                "region": "internal",
            },
            {
                "channel_id": "training-demo",
                "artifact_id": "ART-DEMO",
                "status": "isolated",
                "region": "training",
            },
        ],
        "quarantined_nodes": [],
        "external_distribution_changed": False,
    }
    (WORKSPACE / "distribution_state.json").write_text(
        json.dumps(seed_distribution, indent=2) + "\n"
    )
    (WORKSPACE / "revocation_registry.jsonl").write_text(
        '{"event_id":"REV-001","sequence":1,"credential_id":"SYN-CRED-REL-PUB-A","status":"suspected_exposed","recorded_at":"2026-08-18T19:40:00Z","authority":"DET-REL-7","external_action":false}\n'
    )
    (WORKSPACE / "quarantine_events.jsonl").write_text(
        '{"event_id":"QEV-001","sequence":1,"incident_id":"INC-114-2026-08","event":"detector_alert_opened","subject":"SYN-CRED-REL-PUB-A","recorded_at":"2026-08-18T19:40:00Z","external_action":false}\n'
    )
    for name in (
        "exposure_scan.json",
        "containment_plan.json",
        "sanitized_repository.db",
        "containment_state.json",
        "replacement_credential.json",
        "recovery_receipt.json",
        "incident_handoff.md",
    ):
        (WORKSPACE / name).unlink(missing_ok=True)


def main() -> None:
    build_repository()
    build_artifacts()
    build_reference()
    restore_seed()
    for path in TASK.rglob("*"):
        if path.is_file():
            os.chmod(
                path,
                0o755
                if path.suffix == ".py"
                and ("tools" in path.parts or path.name.startswith("build_"))
                else 0o644,
            )


if __name__ == "__main__":
    main()
