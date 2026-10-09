from __future__ import annotations

import shutil
import sqlite3
import hashlib
import json
from pathlib import Path


TASK = Path(__file__).resolve().parents[2]
WORKSPACE = TASK / "workspace"
REFERENCE = TASK / "tests" / "reference"


def build_seed(path: Path) -> None:
    if path.exists():
        path.unlink()
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE records(record_id TEXT PRIMARY KEY, doi TEXT UNIQUE NOT NULL, kind TEXT NOT NULL, state TEXT NOT NULL, publication_date TEXT, cohort TEXT);
        CREATE TABLE edges(edge_id TEXT PRIMARY KEY NOT NULL, from_doi TEXT NOT NULL, relation TEXT NOT NULL, to_doi TEXT NOT NULL, status TEXT NOT NULL, evidence_refs TEXT NOT NULL, source_kind TEXT NOT NULL);
        CREATE UNIQUE INDEX edge_identity ON edges(from_doi, relation, to_doi, edge_id);
        CREATE TABLE change_log(change_id TEXT PRIMARY KEY NOT NULL, action TEXT NOT NULL, source_ref TEXT NOT NULL, before_value TEXT NOT NULL, after_value TEXT NOT NULL);
        """
    )
    records = [
        ("REC-CONCEPT", "10.data/cohort", "concept", "findable", None, "Longitudinal Cohort Dataset"),
        ("REC-V1", "10.data/cohort.v1", "version", "findable", "2023-01-15", "baseline"),
        ("REC-V2", "10.data/cohort.v2", "version", "findable", "2024-02-20", "baseline plus follow-up"),
        ("REC-V3", "10.data/cohort.v3", "version", "findable", "2025-03-10", "2025 refresh"),
        ("REC-DRAFT", "10.data/cohort.v3-draft", "version", "draft", None, "internal pre-release"),
    ]
    connection.executemany("INSERT INTO records VALUES(?,?,?,?,?,?)", records)
    relation_rows = [
        ("R1","10.data/cohort","HasVersion","10.data/cohort.v1"),
        ("R2","10.data/cohort.v1","IsVersionOf","10.data/cohort"),
        ("R3","10.data/cohort.v2","HasVersion","10.data/cohort"),
        ("R4","10.data/cohort","HasVersion","10.data/cohort.v3"),
        ("R5","10.data/cohort","HasVersion","10.data/cohort.v3"),
        ("R6","10.data/cohort.v3","IsVersionOf","10.data/cohort"),
        ("R7","10.data/cohort.v3","IsNewVersionOf","10.data/cohort.v2"),
        ("R8","10.data/cohort.v2","IsPreviousVersionOf","10.data/cohort.v3"),
        ("R9","10.data/cohort.v3","IsNewVersionOf","10.data/cohort.v3"),
        ("R10","10.data/cohort.v3-draft","IsVersionOf","10.data/cohort"),
    ]
    connection.executemany("INSERT INTO edges VALUES(?,?,?,?,?,?,?)", [(edge_id, source, relation, target, "raw", f"relations.json#{edge_id}", "relation") for edge_id, source, relation, target in relation_rows])
    citation_rows = [
        ("C1","10.paper/alpha","10.data/cohort.v2"),
        ("C1-DUP","10.paper/alpha","10.data/cohort.v2"),
        ("C2","10.paper/beta","10.data/cohort.v3"),
        ("C3","10.paper/gamma","10.data/cohort"),
    ]
    connection.executemany("INSERT INTO edges VALUES(?,?,?,?,?,?,?)", [(edge_id, source, "Cites", target, "raw", f"citations.json#{edge_id}", "citation") for edge_id, source, target in citation_rows])
    connection.commit()
    connection.execute("VACUUM")
    connection.close()


def main() -> None:
    seed = WORKSPACE / "repository_seed.db"
    build_seed(seed)
    shutil.copy2(seed, WORKSPACE / "repository.db")
    source_names = [
        "change.json",
        "citations.json",
        "policy.md",
        "prior_graph_state.json",
        "records.json",
        "relations.json",
        "repository_seed.db",
    ]
    source_hashes = {
        name: hashlib.sha256((WORKSPACE / name).read_bytes()).hexdigest()
        for name in source_names
    }
    bundle = hashlib.sha256(
        json.dumps(source_hashes, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    seed_sha = hashlib.sha256(seed.read_bytes()).hexdigest()
    initial_state = {
        "schema_version": 1,
        "checkpoint_id": "datacite-v4-repair",
        "phase": "draft",
        "revision": 0,
        "input_bundle_sha256": bundle,
        "repository_sha256": seed_sha,
        "migration_sha256": None,
        "validation_sha256": None,
        "decision_sha256": None,
        "stage_token": None,
        "external_actions_executed": False,
    }
    (WORKSPACE / ".repository_stage_state.json").write_text(
        json.dumps(initial_state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    reference_db = REFERENCE / "repository.db"
    shutil.copy2(seed, reference_db)
    connection = sqlite3.connect(reference_db)
    connection.executescript(
        "BEGIN IMMEDIATE;\n"
        + (REFERENCE / "migration.sql").read_text(encoding="utf-8")
        + "\nCOMMIT;"
    )
    connection.close()
    repository = hashlib.sha256(reference_db.read_bytes()).hexdigest()
    migration = hashlib.sha256((REFERENCE / "migration.sql").read_bytes()).hexdigest()
    validation = hashlib.sha256((REFERENCE / "graph_validation.json").read_bytes()).hexdigest()
    decision = hashlib.sha256((REFERENCE / "version_decision.md").read_bytes()).hexdigest()
    token = hashlib.sha256(
        f"datacite-v4-repair\n{bundle}\n{repository}\n{migration}\n{validation}\n{decision}\nlocal-only\n".encode()
    ).hexdigest()
    state = {
        "schema_version": 1,
        "checkpoint_id": "datacite-v4-repair",
        "phase": "staged_for_metadata_review",
        "revision": 2,
        "input_bundle_sha256": bundle,
        "repository_sha256": repository,
        "migration_sha256": migration,
        "validation_sha256": validation,
        "decision_sha256": decision,
        "stage_token": token,
        "external_actions_executed": False,
    }
    receipt = {
        "receipt_type": "local_repository_stage",
        "checkpoint_id": "datacite-v4-repair",
        "state_revision": 2,
        "phase": "staged_for_metadata_review",
        "input_bundle_sha256": bundle,
        "repository_sha256": repository,
        "migration_sha256": migration,
        "validation_sha256": validation,
        "decision_sha256": decision,
        "stage_token": token,
        "external_actions_executed": False,
    }
    (REFERENCE / ".repository_stage_state.json").write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (REFERENCE / "repository_stage_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
