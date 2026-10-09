#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import tarfile
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path.cwd()
SOURCE_DB = "repository.db"
LINEAGE = "artifact_lineage.json"
DIST = "distribution_state.json"
REV = "revocation_registry.jsonl"
QEVENTS = "quarantine_events.jsonl"
PLACEHOLDER = "${RELEASE_PUBLISHER_TOKEN}"


def load_json(name: str) -> Any:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    rendered = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if path.is_file() and path.read_text(encoding="utf-8") == rendered:
        return
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(rendered, encoding="utf-8")
    temporary.replace(path)


def jsonl(name: str) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in (ROOT / name).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl(name: str, rows: list[dict[str, Any]]) -> None:
    rendered = "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows
    )
    path = ROOT / name
    if path.read_text(encoding="utf-8") == rendered:
        return
    path.write_text(rendered, encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def incident() -> dict[str, Any]:
    return load_json("incident.json")


def exact_matches(data: bytes) -> list[bytes]:
    inc = incident()
    pattern = re.compile(str(inc["pattern"]).encode())
    return [
        match.group(0)
        for match in pattern.finditer(data)
        if hashlib.sha256(match.group(0)).hexdigest() == inc["fingerprint_sha256"]
    ]


def db_snapshot(path: Path) -> dict[str, Any]:
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        metadata = dict(db.execute("SELECT key,value FROM metadata"))
        commits = {
            row[0]: {"parent_id": row[1], "authored_at": row[2], "subject": row[3]}
            for row in db.execute(
                "SELECT commit_id,parent_id,authored_at,subject FROM commits"
            )
        }
        refs = {
            row[0]: {"kind": row[1], "commit_id": row[2]}
            for row in db.execute("SELECT ref_name,kind,commit_id FROM refs")
        }
        files: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        for commit, name, mode, content in db.execute(
            "SELECT commit_id,path,mode,content FROM files"
        ):
            files[commit][name] = {"mode": mode, "content": bytes(content)}
    finally:
        db.close()
    return {
        "metadata": metadata,
        "commits": commits,
        "refs": refs,
        "files": dict(files),
    }


def ancestors(snapshot: dict[str, Any], commit: str) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    while commit:
        if commit in seen or commit not in snapshot["commits"]:
            raise ValueError("repository parent graph is cyclic or dangling")
        seen.add(commit)
        result.append(commit)
        commit = snapshot["commits"][commit]["parent_id"]
    return result


def repository_findings() -> tuple[list[dict[str, Any]], list[str]]:
    snapshot = db_snapshot(ROOT / SOURCE_DB)
    findings: list[dict[str, Any]] = []
    infected: set[str] = set()
    for commit, entries in snapshot["files"].items():
        for name, value in entries.items():
            matches = exact_matches(value["content"])
            if matches:
                infected.add(commit)
                findings.append(
                    {
                        "commit_id": commit,
                        "path": name,
                        "match_count": len(matches),
                        "fingerprint_sha256": incident()["fingerprint_sha256"],
                    }
                )
    impacted = sorted(
        ref
        for ref, value in snapshot["refs"].items()
        if infected.intersection(ancestors(snapshot, value["commit_id"]))
    )
    return sorted(findings, key=lambda row: (row["commit_id"], row["path"])), impacted


def node_bytes(path: Path) -> list[tuple[str, bytes]]:
    if path.suffix == ".tar":
        result: list[tuple[str, bytes]] = []
        try:
            with tarfile.open(path, "r") as archive:
                for member in archive.getmembers():
                    if member.isfile():
                        handle = archive.extractfile(member)
                        result.append((member.name, handle.read() if handle else b""))
            return result
        except (OSError, tarfile.TarError):
            return [(path.name, path.read_bytes())]
    return [(path.name, path.read_bytes())]


def lineage_findings() -> tuple[list[dict[str, Any]], set[str]]:
    lineage = load_json(LINEAGE)
    direct: list[dict[str, Any]] = []
    seeds: set[str] = set()
    for node in lineage["nodes"]:
        count = 0
        members: list[str] = []
        for member, data in node_bytes(ROOT / node["path"]):
            found = exact_matches(data)
            count += len(found)
            if found:
                members.append(member)
        if count:
            seeds.add(node["node_id"])
            direct.append(
                {
                    "node_id": node["node_id"],
                    "path": node["path"],
                    "members": members,
                    "match_count": count,
                }
            )
    impacted = set(seeds)
    changed = True
    while changed:
        changed = False
        for edge in lineage["edges"]:
            if (
                edge.get("payload_inherited") is True
                and edge["from"] in impacted
                and edge["to"] not in impacted
            ):
                impacted.add(edge["to"])
                changed = True
    return sorted(direct, key=lambda row: row["node_id"]), impacted


def expected() -> dict[str, Any]:
    findings, refs = repository_findings()
    nodes, impacted = lineage_findings()
    state = load_json("distribution_baseline.json")
    channels = sorted(
        row["channel_id"]
        for row in state["channels"]
        if row.get("artifact_id") in impacted
    )
    return {
        "repository_findings": findings,
        "impacted_refs": refs,
        "direct_nodes": nodes,
        "quarantine_nodes": sorted(impacted),
        "detach_channels": channels,
    }


def validate_plan(plan: dict[str, Any]) -> list[str]:
    exp = expected()
    inc = incident()
    problems: list[str] = []
    if plan.get("incident_id") != inc["incident_id"]:
        problems.append("incident_id does not match incident authority")
    if plan.get("credential_id") != inc["credential_id"]:
        problems.append("credential_id does not match incident authority")
    for field in ("impacted_refs", "quarantine_nodes", "detach_channels"):
        value = plan.get(field)
        if (
            not isinstance(value, list)
            or set(map(str, value)) != set(exp[field])
            or len(value) != len(set(map(str, value)))
        ):
            missing = sorted(set(exp[field]) - set(map(str, value or [])))
            extra = sorted(set(map(str, value or [])) - set(exp[field]))
            problems.append(
                f"{field} closure mismatch; missing={missing}, extra={extra}"
            )
    rewrite = plan.get("rewrite") if isinstance(plan.get("rewrite"), dict) else {}
    if rewrite != {
        "replacement_text": PLACEHOLDER,
        "preserve_ref_names": True,
        "preserve_unaffected_history": True,
    }:
        problems.append(
            "rewrite policy must use the environment reference and preserve refs/unaffected history"
        )
    replacement = (
        plan.get("replacement") if isinstance(plan.get("replacement"), dict) else {}
    )
    expected_replacement = {**inc["replacement"]}
    expected_replacement.pop("activation_authority", None)
    expected_replacement["activate"] = False
    if replacement != expected_replacement:
        problems.append(
            "replacement metadata differs from incident authority or requests activation"
        )
    evidence = plan.get("evidence")
    evidence = (
        evidence
        if isinstance(evidence, list)
        and all(isinstance(item, str) for item in evidence)
        else []
    )
    corpus = "\n".join(evidence)
    evidence_gaps: list[str] = []
    if not any(
        token in corpus
        for token in ("repository.db#", "exposure_scan.json#repository")
    ):
        evidence_gaps.append("repository history")
    for node_id in exp["quarantine_nodes"]:
        if node_id not in corpus:
            evidence_gaps.append(f"quarantine node {node_id}")
    for channel_id in exp["detach_channels"]:
        if channel_id not in corpus:
            evidence_gaps.append(f"distribution channel {channel_id}")
    if not any(
        token in corpus
        for token in ("incident.json#credential_id", "incident.json#revocation_authority")
    ):
        evidence_gaps.append("revocation authority")
    if "incident.json#replacement" not in corpus:
        evidence_gaps.append("replacement authority")
    if not evidence or evidence_gaps:
        problems.append(
            "evidence coverage gaps: " + ", ".join(evidence_gaps or ["evidence list"])
        )
    if any(exact_matches(item.encode()) for item in evidence):
        problems.append("evidence must not repeat credential material")
    return problems


def commit_id(
    parent: str | None, row: dict[str, Any], files: dict[str, dict[str, Any]]
) -> str:
    digest = hashlib.sha256()
    digest.update((parent or "ROOT").encode())
    digest.update(row["authored_at"].encode())
    digest.update(row["subject"].encode())
    for name, value in sorted(files.items()):
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update(value["mode"].encode())
        digest.update(value["content"])
    return "s" + digest.hexdigest()[:15]


def rewrite_repository(out: Path) -> None:
    source = db_snapshot(ROOT / SOURCE_DB)
    remaining = set(source["commits"])
    mapping: dict[str, str] = {}
    rewritten_files: dict[str, dict[str, dict[str, Any]]] = {}
    order: list[str] = []
    inc = incident()
    token_pattern = re.compile(str(inc["pattern"]).encode())
    while remaining:
        progress = False
        for old in sorted(remaining):
            parent = source["commits"][old]["parent_id"]
            if parent and parent not in mapping:
                continue
            entries = source["files"].get(old, {})
            clean: dict[str, dict[str, Any]] = {}
            changed = False
            for name, value in entries.items():

                def redact(match: re.Match[bytes]) -> bytes:
                    nonlocal changed
                    if (
                        hashlib.sha256(match.group(0)).hexdigest()
                        == inc["fingerprint_sha256"]
                    ):
                        changed = True
                        return PLACEHOLDER.encode()
                    return match.group(0)

                clean[name] = {
                    "mode": value["mode"],
                    "content": token_pattern.sub(redact, value["content"]),
                }
            mapped_parent = mapping.get(parent) if parent else None
            new = (
                old
                if not changed and mapped_parent == parent
                else commit_id(mapped_parent, source["commits"][old], clean)
            )
            mapping[old] = new
            rewritten_files[old] = clean
            order.append(old)
            remaining.remove(old)
            progress = True
        if not progress:
            raise ValueError("cannot topologically rewrite repository")
    out.unlink(missing_ok=True)
    db = sqlite3.connect(out)
    db.executescript("""
      PRAGMA journal_mode=DELETE;
      CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
      CREATE TABLE commits(commit_id TEXT PRIMARY KEY,original_commit_id TEXT UNIQUE NOT NULL,parent_id TEXT,authored_at TEXT NOT NULL,subject TEXT NOT NULL);
      CREATE TABLE refs(ref_name TEXT PRIMARY KEY,kind TEXT NOT NULL,commit_id TEXT NOT NULL);
      CREATE TABLE files(commit_id TEXT NOT NULL,path TEXT NOT NULL,mode TEXT NOT NULL,content BLOB NOT NULL,PRIMARY KEY(commit_id,path));
    """)
    db.executemany(
        "INSERT INTO metadata VALUES (?,?)",
        [
            ("format", "nimbus-sanitized-repository-v1"),
            ("source_sha256", sha(ROOT / SOURCE_DB)),
            ("incident_id", incident()["incident_id"]),
        ],
    )
    for old in order:
        row = source["commits"][old]
        new = mapping[old]
        db.execute(
            "INSERT INTO commits VALUES (?,?,?,?,?)",
            (
                new,
                old,
                mapping.get(row["parent_id"]) if row["parent_id"] else None,
                row["authored_at"],
                row["subject"],
            ),
        )
        db.executemany(
            "INSERT INTO files VALUES (?,?,?,?)",
            [
                (new, name, value["mode"], value["content"])
                for name, value in sorted(rewritten_files[old].items())
            ],
        )
    db.executemany(
        "INSERT INTO refs VALUES (?,?,?)",
        [
            (name, value["kind"], mapping[value["commit_id"]])
            for name, value in sorted(source["refs"].items())
        ],
    )
    db.commit()
    db.execute("VACUUM")
    db.close()


def validate_sanitized(path: Path) -> list[str]:
    problems: list[str] = []
    try:
        source = db_snapshot(ROOT / SOURCE_DB)
        db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        metadata = dict(db.execute("SELECT key,value FROM metadata"))
        commits = {
            row[1]: {
                "commit_id": row[0],
                "parent_id": row[2],
                "authored_at": row[3],
                "subject": row[4],
            }
            for row in db.execute(
                "SELECT commit_id,original_commit_id,parent_id,authored_at,subject FROM commits"
            )
        }
        refs = {
            row[0]: {"kind": row[1], "commit_id": row[2]}
            for row in db.execute("SELECT ref_name,kind,commit_id FROM refs")
        }
        files: dict[str, dict[str, tuple[str, bytes]]] = defaultdict(dict)
        for commit, name, mode, content in db.execute(
            "SELECT commit_id,path,mode,content FROM files"
        ):
            files[commit][name] = (mode, bytes(content))
        db.close()
    except (OSError, sqlite3.Error, KeyError, TypeError, ValueError) as exc:
        return [f"sanitized repository unreadable: {exc}"]
    if (
        metadata.get("source_sha256") != sha(ROOT / SOURCE_DB)
        or metadata.get("incident_id") != incident()["incident_id"]
    ):
        problems.append("sanitized repository source identity mismatch")
    if set(commits) != set(source["commits"]) or set(refs) != set(source["refs"]):
        problems.append("logical commits or refs were added/deleted")
        return problems
    mapped = {old: row["commit_id"] for old, row in commits.items()}
    token_pattern = re.compile(str(incident()["pattern"]).encode())
    for old, source_row in source["commits"].items():
        row = commits[old]
        expected_parent = (
            mapped.get(source_row["parent_id"]) if source_row["parent_id"] else None
        )
        if (
            row["parent_id"] != expected_parent
            or row["authored_at"] != source_row["authored_at"]
            or row["subject"] != source_row["subject"]
        ):
            problems.append(f"logical commit metadata changed for {old}")
        candidate_entries = files.get(row["commit_id"], {})
        if set(candidate_entries) != set(source["files"].get(old, {})):
            problems.append(f"file set changed for {old}")
            continue
        changed = False
        for name, value in source["files"].get(old, {}).items():
            expected_content = token_pattern.sub(
                lambda m: (
                    PLACEHOLDER.encode()
                    if hashlib.sha256(m.group(0)).hexdigest()
                    == incident()["fingerprint_sha256"]
                    else m.group(0)
                ),
                value["content"],
            )
            changed |= expected_content != value["content"]
            if candidate_entries[name] != (value["mode"], expected_content):
                problems.append(f"unexpected file rewrite in {old}:{name}")
            if exact_matches(candidate_entries[name][1]):
                problems.append(f"incident fingerprint remains in {old}:{name}")
        unchanged_lineage = not changed and expected_parent == source_row["parent_id"]
        if unchanged_lineage and row["commit_id"] != old:
            problems.append(f"unaffected commit ID changed for {old}")
        if not unchanged_lineage and row["commit_id"] == old:
            problems.append(f"affected descendant ID not recomputed for {old}")
    for name, source_ref in source["refs"].items():
        if refs[name] != {
            "kind": source_ref["kind"],
            "commit_id": mapped[source_ref["commit_id"]],
        }:
            problems.append(f"ref changed incorrectly: {name}")
    return problems


def final_distribution(exp: dict[str, Any]) -> dict[str, Any]:
    initial = load_json("distribution_baseline.json")
    # Normalize from the protected baseline so replay is independent of current state.
    channels = []
    for row in initial["channels"]:
        value = dict(row)
        if value["channel_id"] in exp["detach_channels"]:
            value["artifact_id"] = None
            value["status"] = "quarantined_pending_rebuild"
        channels.append(value)
    return {
        "revision": 13,
        "channels": channels,
        "quarantined_nodes": exp["quarantine_nodes"],
        "external_distribution_changed": False,
    }


def apply(plan_path: Path, repository: Path) -> None:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    problems = validate_plan(plan) + validate_sanitized(repository)
    if problems:
        raise ValueError("; ".join(problems))
    exp = expected()
    write_json(ROOT / DIST, final_distribution(exp))
    revisions = jsonl(REV)
    expected_rev = [
        {
            "event_id": "REV-002",
            "sequence": 2,
            "credential_id": incident()["credential_id"],
            "status": "revoked_local_containment",
            "recorded_at": "2026-08-18T20:00:00Z",
            "authority": incident()["revocation_authority"],
            "external_action": False,
        },
        {
            "event_id": "REV-003",
            "sequence": 3,
            "credential_id": incident()["credential_id"],
            "replacement_ref": incident()["replacement"]["secret_ref"],
            "status": "replacement_staged_not_activated",
            "recorded_at": "2026-08-18T20:01:00Z",
            "authority": incident()["replacement"]["owner"],
            "external_action": False,
        },
    ]
    if revisions == jsonl_seed(REV):
        revisions += expected_rev
    elif revisions != jsonl_seed(REV) + expected_rev:
        raise ValueError("revocation registry is not an append-only expected state")
    write_jsonl(REV, revisions)
    events = jsonl(QEVENTS)
    appended = [
        {
            "event_id": f"QEV-{index:03d}",
            "sequence": index,
            "incident_id": incident()["incident_id"],
            "event": "payload_quarantined",
            "subject": node,
            "recorded_at": f"2026-08-18T20:0{index}:00Z",
            "external_action": False,
        }
        for index, node in enumerate(exp["quarantine_nodes"], 2)
    ]
    if events == jsonl_seed(QEVENTS):
        events += appended
    elif events != jsonl_seed(QEVENTS) + appended:
        raise ValueError(
            "quarantine event registry is not an append-only expected state"
        )
    write_jsonl(QEVENTS, events)
    replacement = {
        "incident_id": incident()["incident_id"],
        "credential_id": incident()["credential_id"],
        "secret_ref": incident()["replacement"]["secret_ref"],
        "scope": incident()["replacement"]["scope"],
        "owner": incident()["replacement"]["owner"],
        "status": "staged_not_activated",
        "actual_value_present": False,
        "external_activation": False,
    }
    write_json(ROOT / "replacement_credential.json", replacement)
    state = {
        "schema_version": 1,
        "incident_id": incident()["incident_id"],
        "status": "contained_pending_external_coordination",
        "rewritten_refs": exp["impacted_refs"],
        "quarantined_nodes": exp["quarantine_nodes"],
        "detached_channels": exp["detach_channels"],
        "sanitized_repository_sha256": sha(repository),
        "distribution_revision": 13,
        "revocation_sequence": 3,
        "quarantine_sequence": 1 + len(exp["quarantine_nodes"]),
        "replacement_secret_ref": incident()["replacement"]["secret_ref"],
        "replacement_activated": False,
        "external_actions_executed": False,
    }
    write_json(ROOT / "containment_state.json", state)


def jsonl_seed(name: str) -> list[dict[str, Any]]:
    if name == REV:
        return [
            {
                "event_id": "REV-001",
                "sequence": 1,
                "credential_id": "SYN-CRED-REL-PUB-A",
                "status": "suspected_exposed",
                "recorded_at": "2026-08-18T19:40:00Z",
                "authority": "DET-REL-7",
                "external_action": False,
            }
        ]
    return [
        {
            "event_id": "QEV-001",
            "sequence": 1,
            "incident_id": "INC-114-2026-08",
            "event": "detector_alert_opened",
            "subject": "SYN-CRED-REL-PUB-A",
            "recorded_at": "2026-08-18T19:40:00Z",
            "external_action": False,
        }
    ]


def verify(plan_path: Path, repository: Path) -> None:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    problems = validate_plan(plan) + validate_sanitized(repository)
    exp = expected()
    if load_json(DIST) != final_distribution(exp):
        problems.append("distribution state is not closed")
    if (
        len(jsonl(REV)) != 3
        or jsonl(REV)[-1].get("status") != "replacement_staged_not_activated"
    ):
        problems.append("revocation/replacement registry is incomplete")
    if {row.get("subject") for row in jsonl(QEVENTS)[1:]} != set(
        exp["quarantine_nodes"]
    ):
        problems.append("quarantine ledger does not close the impacted node set")
    for required in (
        "containment_state.json",
        "replacement_credential.json",
        "incident_handoff.md",
    ):
        if not (ROOT / required).is_file():
            problems.append(f"missing final artifact: {required}")
    if problems:
        raise ValueError("; ".join(problems))
    sources = [
        "containment_policy.md",
        "incident.json",
        SOURCE_DB,
        LINEAGE,
        "distribution_baseline.json",
        "artifact_store/build-417.tar",
        "mirrors/build-417-copy.tar",
        "logs/build-418.log",
        "artifact_store/index-418.json",
        "artifact_store/build-419.tar",
        "artifact_store/build-420.tar",
        "artifact_store/detector-demo.tar",
    ]
    outputs = [
        "exposure_scan.json",
        "containment_plan.json",
        "sanitized_repository.db",
        DIST,
        REV,
        QEVENTS,
        "containment_state.json",
        "replacement_credential.json",
        "incident_handoff.md",
    ]
    source_hashes = {name: sha(ROOT / name) for name in sources}
    output_hashes = {name: sha(ROOT / name) for name in outputs}
    bundle = hashlib.sha256(
        json.dumps(
            {"source_hashes": source_hashes, "output_hashes": output_hashes},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    receipt = {
        "schema_version": 1,
        "incident_id": incident()["incident_id"],
        "result": "pass",
        "scan_clean": True,
        "distribution_closed": True,
        "append_only_ledgers": True,
        "unrelated_history_preserved": True,
        "replacement_staged_not_activated": True,
        "external_actions_executed": False,
        "source_hashes": source_hashes,
        "output_hashes": output_hashes,
        "bundle_sha256": bundle,
        "replay_stable": True,
    }
    write_json(ROOT / "recovery_receipt.json", receipt)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Offline synthetic secret-lineage containment controller"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    scan = sub.add_parser("scan")
    scan.add_argument("--out", type=Path, required=True)
    check = sub.add_parser("check-plan")
    check.add_argument("--plan", type=Path, required=True)
    rewrite = sub.add_parser("rewrite")
    rewrite.add_argument("--plan", type=Path, required=True)
    rewrite.add_argument("--out", type=Path, required=True)
    apply_parser = sub.add_parser("apply")
    apply_parser.add_argument("--plan", type=Path, required=True)
    apply_parser.add_argument("--repository", type=Path, required=True)
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("--plan", type=Path, required=True)
    verify_parser.add_argument("--repository", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "status":
            print(
                json.dumps(
                    {
                        "incident_id": incident()["incident_id"],
                        "credential_status": jsonl(REV)[-1]["status"],
                        "distribution_revision": load_json(DIST)["revision"],
                        "quarantine_event_count": len(jsonl(QEVENTS)),
                        "external_connectivity": False,
                    },
                    indent=2,
                )
            )
            return 0
        if args.command == "scan":
            repository, refs = repository_findings()
            nodes, _ = lineage_findings()
            value = {
                "schema_version": 1,
                "incident_id": incident()["incident_id"],
                "fingerprint_sha256": incident()["fingerprint_sha256"],
                "repository": {"direct_matches": repository, "impacted_refs": refs},
                "direct_payload_matches": nodes,
                "note": "direct matches only; compute inherited payload and distribution closure from artifact_lineage.json",
            }
            write_json(args.out, value)
            print(
                json.dumps(
                    {
                        "status": "pass",
                        "repository_matches": len(repository),
                        "direct_payload_nodes": len(nodes),
                    }
                )
            )
            return 0
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        problems = validate_plan(plan)
        if args.command == "check-plan":
            print(
                json.dumps(
                    {
                        "status": "pass" if not problems else "fail",
                        "problems": problems,
                    },
                    indent=2,
                )
            )
            return 0 if not problems else 2
        if problems:
            print(json.dumps({"status": "fail", "problems": problems}, indent=2))
            return 2
        if args.command == "rewrite":
            rewrite_repository(args.out)
            problems = validate_sanitized(args.out)
            print(
                json.dumps(
                    {
                        "status": "pass" if not problems else "fail",
                        "problems": problems,
                    },
                    indent=2,
                )
            )
            return 0 if not problems else 2
        if args.command == "apply":
            apply(args.plan, args.repository)
            print(
                json.dumps(
                    {
                        "status": "pass",
                        "state": "contained_pending_external_coordination",
                    }
                )
            )
            return 0
        verify(args.plan, args.repository)
        print(json.dumps({"status": "pass", "receipt": "recovery_receipt.json"}))
        return 0
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        json.JSONDecodeError,
        sqlite3.Error,
        tarfile.TarError,
    ) as exc:
        print(
            json.dumps(
                {"status": "fail", "problems": [f"{type(exc).__name__}: {exc}"]},
                indent=2,
            )
        )
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
