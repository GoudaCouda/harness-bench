from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path

TASK = Path(__file__).resolve().parents[2]
SEED = TASK / "workspace"
REFERENCE = TASK / "tests/reference"


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def build_database() -> None:
    path = SEED / "state/dnssec.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    zones = [
        ("alpha.example", 2026081901, "KSK", "ksk_double_sign", "2026-08-19T08:00:00Z"),
        ("bravo.example", 2026081902, "KSK", "ksk_double_sign", "2026-08-19T07:00:00Z"),
        ("charlie.example", 2026081903, "ZSK", "zsk_prepublish", "2026-08-19T11:35:00Z"),
        ("delta.example", 2026081904, "ZSK", "zsk_active", "2026-08-19T08:00:00Z"),
        ("echo.example", 2026081906, "ZSK", "zsk_active", "2026-08-19T11:54:00Z"),
        ("foxtrot.example", 2026081906, "NONE", "not_in_rollover", "2026-08-10T00:00:00Z"),
        ("golf.example", 2026081907, "KSK", "ksk_double_sign", "2026-08-19T06:00:00Z"),
    ]
    keys = [
        ("K-alpha-100", "alpha.example", "KSK", "old", "published"), ("K-alpha-200", "alpha.example", "KSK", "new", "published"),
        ("K-bravo-110", "bravo.example", "KSK", "old", "published"), ("K-bravo-210", "bravo.example", "KSK", "new", "published"),
        ("Z-charlie-120", "charlie.example", "ZSK", "old", "active"), ("Z-charlie-220", "charlie.example", "ZSK", "new", "prepublished"),
        ("Z-delta-130", "delta.example", "ZSK", "old", "active"), ("Z-delta-230", "delta.example", "ZSK", "new", "active"),
        ("Z-echo-140", "echo.example", "ZSK", "old", "active"), ("Z-echo-240", "echo.example", "ZSK", "new", "prepublished"),
        ("K-golf-160", "golf.example", "KSK", "old", "published"), ("K-golf-260", "golf.example", "KSK", "new", "published"),
    ]
    echo_before = {"zone_name": "echo.example", "serial": 2026081905, "key_role": "ZSK", "rollover_phase": "zsk_prepublish", "last_change_at": "2026-08-19T07:00:00Z"}
    echo_after = {"zone_name": "echo.example", "serial": 2026081906, "key_role": "ZSK", "rollover_phase": "zsk_active", "last_change_at": "2026-08-19T11:54:00Z"}
    partial_queue = {"queue_id": "Q-PARTIAL-echo.example", "zone_name": "echo.example", "key_role": "ZSK", "action": "stage_new_zsk_activation", "status": "allocating", "requested_by_recovery": "REC-ROL-2026-08-A-01", "executed": 0}
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE zones(zone_name TEXT PRIMARY KEY,serial INTEGER NOT NULL,key_role TEXT NOT NULL,rollover_phase TEXT NOT NULL,last_change_at TEXT NOT NULL);
            CREATE TABLE key_state(key_id TEXT PRIMARY KEY,zone_name TEXT NOT NULL,key_role TEXT NOT NULL,generation TEXT NOT NULL,status TEXT NOT NULL);
            CREATE TABLE staging_queue(queue_id TEXT PRIMARY KEY,zone_name TEXT UNIQUE NOT NULL,key_role TEXT NOT NULL,action TEXT NOT NULL,status TEXT NOT NULL,requested_by_recovery TEXT NOT NULL,executed INTEGER NOT NULL);
            CREATE TABLE decision_receipts(recovery_id TEXT NOT NULL,zone_name TEXT NOT NULL,key_role TEXT NOT NULL,rollover_phase TEXT NOT NULL,current_serial INTEGER NOT NULL,ttl_dwell_state TEXT NOT NULL,signature_state TEXT NOT NULL,parent_ds_state TEXT NOT NULL,action TEXT NOT NULL,PRIMARY KEY(recovery_id,zone_name));
            CREATE TABLE recovery_runs(recovery_id TEXT PRIMARY KEY,source_checkpoint TEXT,semantic_plan_digest TEXT,semantic_state_digest TEXT,status TEXT NOT NULL);
            CREATE TABLE rollover_journal(journal_id TEXT PRIMARY KEY,recovery_id TEXT NOT NULL,table_name TEXT NOT NULL,record_id TEXT NOT NULL,before_json TEXT,after_json TEXT NOT NULL,restored INTEGER NOT NULL);
            CREATE TABLE system_state(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            """
        )
        connection.executemany("INSERT INTO zones VALUES (?,?,?,?,?)", zones)
        connection.executemany("INSERT INTO key_state VALUES (?,?,?,?,?)", keys)
        connection.execute("INSERT INTO staging_queue VALUES (?,?,?,?,?,?,?)", tuple(partial_queue.values()))
        connection.executemany("INSERT INTO recovery_runs VALUES (?,?,?,?,?)", [
            ("REC-ROL-2026-07-Z-04", "sha256:closed", "sha256:closed-plan", "sha256:closed-state", "archived"),
            ("REC-ROL-2026-08-A-01", None, None, None, "interrupted"),
        ])
        connection.executemany("INSERT INTO rollover_journal VALUES (?,?,?,?,?,?,?)", [
            ("J-DNS-801", "REC-ROL-2026-08-A-01", "zones", "echo.example", canonical(echo_before).decode().strip(), canonical(echo_after).decode().strip(), 0),
            ("J-DNS-802", "REC-ROL-2026-08-A-01", "staging_queue", "Q-PARTIAL-echo.example", None, canonical(partial_queue).decode().strip(), 0),
        ])
        connection.executemany("INSERT INTO system_state VALUES (?,?)", [("source_revision", "29"), ("last_checkpoint_revision", "18"), ("authoritative_publish_count", "0"), ("parent_update_count", "0")])


def build_manifest() -> None:
    files = [
        "policy/rollover_policy.json", "evidence/key_inventory.json",
        "evidence/parent_ds_observations.jsonl", "evidence/dns_observations.jsonl",
        "state/stale_checkpoint.json",
    ]
    files += [str(path.relative_to(SEED)) for path in sorted((SEED / "zones").glob("*.zone"))]
    files += [str(path.relative_to(SEED)) for path in sorted((SEED / "keys").glob("*.key"))]
    manifest = {"schema_version": 1, "files": {name: hashlib.sha256((SEED / name).read_bytes()).hexdigest() for name in files}}
    (SEED / "policy/source_manifest.json").write_bytes(canonical(manifest))


def controller(root: Path):
    spec = importlib.util.spec_from_file_location("dnssecctl_builder", root / "dnssecctl.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def refs(zone: str, inv: dict[str, object], parent: list[dict[str, object]], dns: dict[str, object], journal: bool = False) -> list[str]:
    result = {
        f"evidence/key_inventory.json#zones/{zone}",
        f"evidence/dns_observations.jsonl#{dns['observation_id']}",
        f"state/stale_checkpoint.json#zones/{zone}", f"state/dnssec.db#zones/{zone}", f"zones/{zone}.zone",
    }
    for key in (inv.get("old_key_id"), inv.get("new_key_id")):
        if key:
            result.add(f"keys/{key}.key")
    for row in parent:
        result.add(f"evidence/parent_ds_observations.jsonl#{row['observation_id']}")
    if journal:
        result.add("state/dnssec.db#rollover_journal/J-DNS-801")
    return sorted(result)


def build_reference() -> None:
    if REFERENCE.exists():
        shutil.rmtree(REFERENCE)
    with tempfile.TemporaryDirectory(prefix="hb001-build-") as temporary:
        root = Path(temporary) / "workspace"
        shutil.copytree(SEED, root)
        module = controller(root)
        with sqlite3.connect(f"file:{root / 'state/dnssec.db'}?mode=ro", uri=True) as connection:
            source_checkpoint = module.context(connection)["source_checkpoint"]
        inventory = json.loads((root / "evidence/key_inventory.json").read_text())["zones"]
        parent = [json.loads(line) for line in (root / "evidence/parent_ds_observations.jsonl").read_text().splitlines()]
        dns = [json.loads(line) for line in (root / "evidence/dns_observations.jsonl").read_text().splitlines()]
        by_inv = {row["zone_name"]: row for row in inventory}
        by_dns = {row["zone_name"]: row for row in dns}
        by_parent = {zone: [row for row in parent if row["zone_name"] == zone] for zone in by_inv}
        values = {
            "alpha.example": ("KSK", "ksk_double_sign", 2026081901, "insufficient", "valid_new_coverage", "old_only", "monitor_parent_ds"),
            "bravo.example": ("KSK", "ksk_parent_propagated", 2026081902, "satisfied", "valid_new_coverage", "old_and_new_quorum", "stage_old_ksk_retirement"),
            "charlie.example": ("ZSK", "zsk_prepublish", 2026081903, "insufficient", "valid_old_only", "not_applicable", "hold_for_dnskey_dwell"),
            "delta.example": ("ZSK", "zsk_active", 2026081904, "satisfied", "valid_new_coverage", "not_applicable", "stage_new_zsk_activation"),
            "echo.example": ("ZSK", "zsk_prepublish", 2026081905, "satisfied", "invalid_or_expiring", "not_applicable", "hold_signature_risk"),
            "foxtrot.example": ("NONE", "not_in_rollover", 2026081906, "not_applicable", "not_applicable", "not_applicable", "preserve_unrelated"),
            "golf.example": ("KSK", "ksk_double_sign", 2026081907, "insufficient", "valid_new_coverage", "inconsistent", "monitor_parent_ds"),
        }
        decisions = []
        for zone, value in values.items():
            role, phase, serial, dwell, signature, parent_state, action = value
            decisions.append({"zone_name": zone, "key_role": role, "rollover_phase": phase, "current_serial": serial, "ttl_dwell_state": dwell, "signature_state": signature, "parent_ds_state": parent_state, "action": action, "evidence_refs": refs(zone, by_inv[zone], by_parent[zone], by_dns[zone], zone == "echo.example")})
        plan = {"schema_version": 1, "recovery_id": "REC-ROL-2026-08-A-01", "source_checkpoint": source_checkpoint, "rollover_id": "ROL-2026-08-A", "zone_decisions": decisions, "journal_actions": [
            {"journal_id": "J-DNS-801", "table_name": "zones", "record_id": "echo.example", "action": "restore_before_image"},
            {"journal_id": "J-DNS-802", "table_name": "staging_queue", "record_id": "Q-PARTIAL-echo.example", "action": "remove_partial_insert"},
        ], "external_actions_executed": False}
        (root / "rollover_recovery.json").write_bytes(canonical(plan))
        for command in ("preview", "apply", "stage", "verify", "replay"):
            subprocess.run(["python3", "dnssecctl.py", command, "rollover_recovery.json"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        (root / "dnssec_recovery_handoff.md").write_text(
            """# DNSSEC rollover recovery handoff

Run ROL-2026-08-A was recovered locally under REC-ROL-2026-08-A-01. The stale checkpoint falsely advanced alpha.example and golf.example and lagged the durable observations for bravo.example; it also reflected the interrupted echo.example write. Journal J-DNS-801 restored the echo.example before-image at serial 2026081905 and its zsk_prepublish phase, while J-DNS-802 removed the partial queue insertion before the replacement queue was committed.

For KSKs, parent DS evidence controls retirement: alpha.example remains in double-sign monitoring because all three parent probes still expose only the old DS; bravo.example has old-and-new DS quorum beyond the 7200-second dwell and valid new-key coverage, so old-KSK retirement is staged; golf.example stays in double-sign monitoring because the three parent probes disagree. DNSKEY presence alone was not treated as parent propagation. For ZSKs, charlie.example remains prepublished because the new DNSKEY has not met dwell, delta.example has met dwell and valid new-key RRSIG coverage so activation is staged, and echo.example is held because its minimum signature expiry is inside the safety window. foxtrot.example is unrelated and preserved. All source zone serials and public key facts remain unchanged after rollback.

The offline DNSSEC change queue, manifest, recovery receipt, and verification report close over the normalized plan and recovered SQLite state hashes. Reordered replay completed as an idempotent no-op. No zone was signed or published, no authoritative DNS, registrar, or parent DS change occurred, and every queued request remains unexecuted for an authorized operator to review.
""", encoding="utf-8")
        REFERENCE.mkdir(parents=True)
        for relative in ("rollover_recovery.json", "dnssec_recovery_handoff.md", "state/dnssec.db", "state/recovery_receipt.json", "state/verification.json", "state/replay_report.json", "staging/dnssec_change_queue.json", "staging/queue_manifest.json"):
            target = REFERENCE / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / relative, target)


def main() -> None:
    build_database()
    build_manifest()
    build_reference()


if __name__ == "__main__":
    main()
