from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import subprocess
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


TASK = Path(__file__).resolve().parents[2]
WORKSPACE = TASK / "workspace"
REFERENCE = TASK / "tests" / "reference"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CP_NS = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
DC_NS = "http://purl.org/dc/elements/1.1/"
DCTERMS_NS = "http://purl.org/dc/terms/"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
W = f"{{{W_NS}}}"
R = f"{{{R_NS}}}"

for prefix, uri in (
    ("w", W_NS),
    ("r", R_NS),
    ("cp", CP_NS),
    ("dc", DC_NS),
    ("dcterms", DCTERMS_NS),
    ("xsi", XSI_NS),
):
    ET.register_namespace(prefix, uri)


PREFIXES = {
    "CH-01": "Eligibility notice: customers receive notice within ",
    "CH-02": "Effective date: ",
    "CH-03": "Coverage: this process applies to ",
    "CH-04": "Coverage footnote: ",
    "CH-05": "Contact: write to ",
    "CH-06": "Records: ",
    "CH-07": "Records FAQ: ",
    "CH-08": "Revision: ",
    "CH-09": "Accessibility: ",
    "CH-10": "Publication footer: ",
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def text_run(text: str, *, bold: bool = False) -> ET.Element:
    run = ET.Element(f"{W}r")
    if bold:
        properties = ET.SubElement(run, f"{W}rPr")
        ET.SubElement(properties, f"{W}b")
    node = ET.SubElement(run, f"{W}t")
    if text.startswith(" ") or text.endswith(" "):
        node.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    node.text = text
    return run


def revision_run(tag: str, revision_id: str, text: str) -> ET.Element:
    wrapper = ET.Element(f"{W}{tag}")
    wrapper.set(f"{W}id", revision_id)
    wrapper.set(f"{W}author", "Northstar Review Workflow")
    wrapper.set(f"{W}date", "2026-08-19T08:00:00Z")
    run = ET.SubElement(wrapper, f"{W}r")
    properties = ET.SubElement(run, f"{W}rPr")
    ET.SubElement(properties, f"{W}color", {f"{W}val": "1F4E79"})
    node = ET.SubElement(run, f"{W}delText" if tag == "del" else f"{W}t")
    node.text = text
    return wrapper


def xml_bytes(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def current_events() -> dict[str, dict]:
    manifest = json.loads((WORKSPACE / "revision_manifest.json").read_text())
    grouped: dict[str, list[dict]] = {}
    for event in manifest["events"]:
        if event["basis_status"] == "current":
            grouped.setdefault(event["change_id"], []).append(event)
    return {
        change_id: max(rows, key=lambda row: int(row["event_seq"]))
        for change_id, rows in grouped.items()
    }


def build_document() -> None:
    events = current_events()
    document = ET.Element(f"{W}document")
    body = ET.SubElement(document, f"{W}body")

    title = ET.SubElement(body, f"{W}p")
    title_props = ET.SubElement(title, f"{W}pPr")
    ET.SubElement(title_props, f"{W}pStyle", {f"{W}val": "Title"})
    title.append(text_run("Northstar Service Bulletin", bold=True))

    stable = ET.SubElement(body, f"{W}p")
    stable.append(text_run("Document control note: internal review copy; preserve styles, bookmarks, comments, header, and footer."))

    for index, change_id in enumerate(sorted(events), start=1):
        event = events[change_id]
        paragraph = ET.SubElement(body, f"{W}p")
        properties = ET.SubElement(paragraph, f"{W}pPr")
        ET.SubElement(properties, f"{W}pStyle", {f"{W}val": "BodyText"})
        ET.SubElement(
            paragraph,
            f"{W}bookmarkStart",
            {f"{W}id": str(index), f"{W}name": f"HB_{change_id.replace('-', '_')}"},
        )
        paragraph.append(text_run(PREFIXES[change_id], bold=change_id in {"CH-01", "CH-10"}))
        paragraph.append(
            revision_run("del", str(event["ooxml_revision_id"]), event["old_text"])
        )
        paragraph.append(
            revision_run("ins", str(event["ooxml_revision_id"]), event["new_text"])
        )
        paragraph.append(text_run("."))
        ET.SubElement(paragraph, f"{W}bookmarkEnd", {f"{W}id": str(index)})

    section = ET.SubElement(body, f"{W}sectPr")
    ET.SubElement(section, f"{W}headerReference", {f"{W}type": "default", f"{R}id": "rId2"})
    ET.SubElement(section, f"{W}footerReference", {f"{W}type": "default", f"{R}id": "rId3"})
    ET.SubElement(section, f"{W}pgSz", {f"{W}w": "12240", f"{W}h": "15840"})

    styles = ET.Element(f"{W}styles")
    for style_id, name in (("Normal", "Normal"), ("Title", "Title"), ("BodyText", "Body Text")):
        style = ET.SubElement(
            styles,
            f"{W}style",
            {f"{W}type": "paragraph", f"{W}styleId": style_id},
        )
        ET.SubElement(style, f"{W}name", {f"{W}val": name})

    settings = ET.Element(f"{W}settings")
    ET.SubElement(settings, f"{W}trackRevisions")
    ET.SubElement(settings, f"{W}doNotTrackMoves")

    comments = ET.Element(f"{W}comments")
    comment = ET.SubElement(
        comments,
        f"{W}comment",
        {f"{W}id": "0", f"{W}author": "Records", f"{W}date": "2026-08-18T12:00:00Z"},
    )
    comment_p = ET.SubElement(comment, f"{W}p")
    comment_p.append(text_run("Preserve the seven-year retention control."))

    header = ET.Element(f"{W}hdr")
    header_p = ET.SubElement(header, f"{W}p")
    header_p.append(text_run("NORTHSTAR / INTERNAL"))
    footer = ET.Element(f"{W}ftr")
    footer_p = ET.SubElement(footer, f"{W}p")
    footer_p.append(text_run("Confidential — internal approval workflow"))

    content_types = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
  <Override PartName="/word/comments.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"/>
  <Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>
  <Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>
'''
    root_rels = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
'''
    document_rels = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header1.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>
  <Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments" Target="comments.xml"/>
  <Relationship Id="rId5" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>
</Relationships>
'''
    core = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>Northstar Service Bulletin</dc:title><dc:creator>Northstar Publishing</dc:creator>
  <dcterms:created xsi:type="dcterms:W3CDTF">2026-08-18T12:00:00Z</dcterms:created>
</cp:coreProperties>
'''
    app = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>HarnessBench OOXML Fixture</Application></Properties>
'''
    entries = {
        "[Content_Types].xml": content_types,
        "_rels/.rels": root_rels,
        "docProps/core.xml": core,
        "docProps/app.xml": app,
        "word/document.xml": xml_bytes(document),
        "word/styles.xml": xml_bytes(styles),
        "word/settings.xml": xml_bytes(settings),
        "word/comments.xml": xml_bytes(comments),
        "word/header1.xml": xml_bytes(header),
        "word/footer1.xml": xml_bytes(footer),
        "word/_rels/document.xml.rels": document_rels,
    }
    target = WORKSPACE / "bulletin_working.docx"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, payload in entries.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 8, 18, 12, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, payload, compresslevel=9)


def build_database() -> None:
    target = WORKSPACE / "review_state.db"
    target.unlink(missing_ok=True)
    source_sha = sha256_bytes((WORKSPACE / "bulletin_working.docx").read_bytes())
    event = current_events()["CH-05"]
    proposal_sha = sha256_bytes(event["new_text"].encode())
    prior_plan_sha = sha256_bytes(b"TX-04 durable contact decision")
    connection = sqlite3.connect(target)
    connection.executescript(
        """
        PRAGMA journal_mode=DELETE;
        PRAGMA foreign_keys=ON;
        CREATE TABLE workflow_state (
          workflow_id TEXT PRIMARY KEY,
          phase TEXT NOT NULL,
          source_revision INTEGER NOT NULL,
          target_revision INTEGER NOT NULL,
          checkpoint_status TEXT NOT NULL,
          base_docx_sha256 TEXT NOT NULL,
          active_plan_sha256 TEXT NOT NULL,
          staged_docx_sha256 TEXT NOT NULL,
          external_published INTEGER NOT NULL CHECK (external_published IN (0,1)),
          updated_at TEXT NOT NULL
        );
        CREATE TABLE revision_journal (
          sequence INTEGER PRIMARY KEY,
          transaction_id TEXT NOT NULL,
          change_id TEXT NOT NULL UNIQUE,
          event_id TEXT NOT NULL,
          disposition TEXT NOT NULL CHECK (disposition IN ('accept','reject','invalidate_dependency')),
          proposal_sha256 TEXT NOT NULL,
          recorded_at TEXT NOT NULL
        );
        CREATE TABLE transactions (
          transaction_id TEXT PRIMARY KEY,
          plan_sha256 TEXT NOT NULL UNIQUE,
          source_docx_sha256 TEXT NOT NULL,
          output_docx_sha256 TEXT NOT NULL,
          action_count INTEGER NOT NULL,
          appended_count INTEGER NOT NULL,
          reconciled_count INTEGER NOT NULL,
          accepted_count INTEGER NOT NULL,
          rejected_count INTEGER NOT NULL,
          invalidated_count INTEGER NOT NULL,
          committed_at TEXT NOT NULL
        );
        """
    )
    connection.execute(
        "INSERT INTO workflow_state VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "NORTHSTAR-BULLETIN-REV5",
            "interrupted_after_journal_commit",
            4,
            5,
            "document_checkpoint_missing",
            source_sha,
            "",
            "",
            0,
            "2026-08-18T16:42:00Z",
        ),
    )
    connection.execute(
        "INSERT INTO revision_journal VALUES (?, ?, ?, ?, ?, ?, ?)",
        (1, "TX-04", "CH-05", "EV-508", "accept", proposal_sha, "2026-08-18T16:42:00Z"),
    )
    connection.execute(
        "INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "TX-04",
            prior_plan_sha,
            source_sha,
            "",
            1,
            1,
            0,
            1,
            0,
            0,
            "2026-08-18T16:42:00Z",
        ),
    )
    connection.commit()
    connection.execute("VACUUM")
    connection.close()


def reference_plan() -> dict:
    events = current_events()
    dispositions = {
        "CH-01": "accept",
        "CH-02": "accept",
        "CH-03": "reject",
        "CH-04": "invalidate_dependency",
        "CH-05": "accept",
        "CH-06": "reject",
        "CH-07": "invalidate_dependency",
        "CH-08": "accept",
        "CH-09": "accept",
        "CH-10": "reject",
    }
    dependencies = {
        "CH-02", "CH-04", "CH-07", "CH-08", "CH-10"
    }
    actions = []
    for change_id in sorted(events):
        event = events[change_id]
        evidence = [
            f"revision_manifest.json#{event['event_id']}",
            f"authority_policy.md#{event['policy_rule']}",
        ]
        if event.get("credential_id"):
            evidence.append(f"signature_registry.json#{event['credential_id']}")
        if change_id in dependencies:
            evidence.append(f"revision_dependencies.csv#{change_id}")
        if change_id == "CH-05":
            evidence.append("review_state.db#TX-04")
        actions.append(
            {
                "change_id": change_id,
                "selected_event_id": event["event_id"],
                "disposition": dispositions[change_id],
                "evidence": evidence,
            }
        )
    return {
        "workflow_id": "NORTHSTAR-BULLETIN-REV5",
        "source_document": "bulletin_working.docx",
        "adjudication_order": sorted(events),
        "approval_boundary": "staged_for_internal_approval",
        "actions": actions,
    }


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_reference() -> None:
    with tempfile.TemporaryDirectory(prefix="hb110-reference-") as temporary:
        workspace = Path(temporary) / "workspace"
        shutil.copytree(WORKSPACE, workspace)
        write_json(workspace / "adjudication_plan.json", reference_plan())
        for command in (
            ["inspect"],
            ["preview", "--plan", "adjudication_plan.json"],
            ["apply", "--plan", "adjudication_plan.json"],
        ):
            subprocess.run(
                ["python3", "bulletinctl.py", *command],
                cwd=workspace,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        (workspace / "editorial_handoff.md").write_text(
            """# Northstar revision recovery handoff

The package used the highest current event for every change. EV-114 is the
later verified signed legal correction for CH-01 and supersedes EV-107; it was
accepted with CH-02, CH-05, CH-08, and CH-09. CH-03, CH-06, and CH-10 were
rejected because campaign scope, controlled-retention deletion, and public
portal publication lack governing authority. CH-04 and CH-07 were dependency-
invalidated after their prerequisites failed, rather than being applied on
their own.

TX-04 had already durably recorded CH-05/EV-508 before the document checkpoint
was lost. Recovery reconciled that contact decision into the DOCX without a
second journal row. TX-05 appended the other nine outcomes in deterministic
topological order and closed one recovery transaction.

The controller resolved the actual OOXML w:ins/w:del pairs in
approved_bulletin.docx. The title, unaffected control note, paragraph order,
bookmarks, styles, comments, header, footer, relationships, and all other
non-document package parts were preserved. The clean document has no remaining
tracked insertion or deletion markup.

Preview, apply, and hash-bound verification passed. Reapplying the normalized
plan and verifying again were idempotent: document bytes, journal rows,
transaction count, database logical state, and verification receipt remained
stable. The package is staged only for internal approval. No publication,
portal export, message send, notification, external approval, or other
external action occurred.
""",
            encoding="utf-8",
        )
        for command in (
            ["verify", "--plan", "adjudication_plan.json"],
            ["verify", "--plan", "adjudication_plan.json"],
            ["apply", "--plan", "adjudication_plan.json"],
        ):
            subprocess.run(
                ["python3", "bulletinctl.py", *command],
                cwd=workspace,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        if REFERENCE.exists():
            shutil.rmtree(REFERENCE)
        REFERENCE.mkdir(parents=True)
        for name in (
            "approved_bulletin.docx",
            "review_state.db",
            "adjudication_plan.json",
            "verification_receipt.json",
            "editorial_handoff.md",
        ):
            shutil.copy2(workspace / name, REFERENCE / name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources-only", action="store_true")
    args = parser.parse_args()
    build_document()
    build_database()
    if not args.sources_only:
        build_reference()


if __name__ == "__main__":
    main()
