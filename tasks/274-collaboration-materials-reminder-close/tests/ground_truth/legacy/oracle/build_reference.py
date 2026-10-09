#!/usr/bin/env python3
"""Derive the hidden case_20 reference state from frozen fixtures and public rules."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


FIELDS = [
    "person_id",
    "name",
    "project_resume_status",
    "project_resume_file",
    "project_resume_source_attachment_id",
    "compliance_declaration_status",
    "compliance_declaration_file",
    "compliance_declaration_source_attachment_id",
    "overall_status",
    "reminder_status",
]
MATERIALS = [
    ("project_resume", "项目履历"),
    ("compliance_declaration", "合规声明"),
]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    case_root = Path(__file__).resolve().parents[1]
    seed = json.loads((case_root / "fixtures/service_seed.json").read_text(encoding="utf-8"))
    with (case_root / "fixtures/workspace_seed/inputs/person_roster.csv").open(
        "r", encoding="utf-8", newline=""
    ) as stream:
        roster = list(csv.DictReader(stream))
    template = (case_root / "fixtures/workspace_seed/inputs/reminder_template.txt").read_text(
        encoding="utf-8"
    ).rstrip("\n")
    cutoff = datetime.fromisoformat(seed["fixed_time"])
    messages = {item["message_id"]: item for item in seed["messages"]}
    roster_ids = {item["person_id"] for item in roster}

    eligible: dict[tuple[str, str], list[dict[str, Any]]] = {}
    attachment_ids = {item["attachment_id"] for item in seed["attachments"]}
    for item in seed["attachments"]:
        message = messages[item["message_id"]]
        if item["replaces_attachment_id"] is not None:
            if item["replaces_attachment_id"] not in attachment_ids:
                raise ValueError("replacement reference is unknown")
        if (
            item["owner_id"] in roster_ids
            and item["material_type"] in {name for name, _label in MATERIALS}
            and message["channel"] == seed["channel"]
            and datetime.fromisoformat(message["sent_at"]) <= cutoff
        ):
            eligible.setdefault((item["owner_id"], item["material_type"]), []).append(
                {**item, "sent_at": message["sent_at"]}
            )

    selected: dict[tuple[str, str], dict[str, Any]] = {}
    for key, candidates in eligible.items():
        selected[key] = max(candidates, key=lambda item: (item["sent_at"], item["attachment_id"]))

    archive_files: list[dict[str, str]] = []
    rows: list[dict[str, str]] = []
    reminders: list[dict[str, str]] = []
    for person in roster:
        person_id = person["person_id"]
        row = {"person_id": person_id, "name": person["name"]}
        missing_labels: list[str] = []
        for material_type, label in MATERIALS:
            item = selected.get((person_id, material_type))
            if item is None:
                row[f"{material_type}_status"] = "missing"
                row[f"{material_type}_file"] = ""
                row[f"{material_type}_source_attachment_id"] = ""
                missing_labels.append(label)
                continue
            relative = f"archive/{person_id}/{material_type}/{item['original_filename']}"
            fixture = case_root / "fixtures" / item["fixture_path"]
            row[f"{material_type}_status"] = "submitted"
            row[f"{material_type}_file"] = relative
            row[f"{material_type}_source_attachment_id"] = item["attachment_id"]
            archive_files.append(
                {
                    "attachment_id": item["attachment_id"],
                    "path": relative,
                    "sha256": sha256_file(fixture),
                }
            )
        complete = not missing_labels
        row["overall_status"] = "complete" if complete else "incomplete"
        row["reminder_status"] = "not_required" if complete else "sent"
        rows.append({field: row[field] for field in FIELDS})
        if not complete:
            reminders.append(
                {
                    "recipient_id": person_id,
                    "body": template.format(
                        name=person["name"],
                        person_id=person_id,
                        missing_materials="、".join(missing_labels),
                    ),
                }
            )

    payload = {
        "schema_version": "case20_reference_state_v2",
        "fixed_time": seed["fixed_time"],
        "archive_files": archive_files,
        "register_fields": FIELDS,
        "register_rows": rows,
        "reminders": reminders,
    }
    (case_root / "oracle/reference_state.json").write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
