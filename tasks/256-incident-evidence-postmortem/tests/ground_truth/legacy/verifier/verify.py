#!/usr/bin/env python3
"""Deterministic structural and fact verifier for the case_02 DOCX deliverable."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
EVIDENCE_PATTERN = re.compile(r"[A-Z]+(?:-[A-Z0-9]+){2,}")


def q(namespace: str, tag: str) -> str:
    return f"{{{namespace}}}{tag}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def text_of(node: ET.Element) -> str:
    return normalize("".join(part.text or "" for part in node.iter(q(W_NS, "t"))))


@dataclass(frozen=True)
class Paragraph:
    text: str
    style: str


@dataclass(frozen=True)
class Table:
    rows: tuple[tuple[str, ...], ...]


def parse_docx(path: Path) -> list[Paragraph | Table]:
    if not path.is_file() or path.is_symlink():
        raise ValueError("deliverable is missing or unsafe")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("DOCX exceeds the 2 MiB case limit")
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if len(infos) > 64:
            raise ValueError("DOCX contains too many package parts")
        total_uncompressed = 0
        for info in infos:
            pure = Path(info.filename)
            if pure.is_absolute() or ".." in pure.parts:
                raise ValueError("DOCX contains an unsafe package path")
            total_uncompressed += info.file_size
            if info.file_size > 5 * 1024 * 1024:
                raise ValueError("DOCX package part is too large")
            if info.compress_size and info.file_size / info.compress_size > 100:
                raise ValueError("DOCX package part has an unsafe compression ratio")
        if total_uncompressed > 10 * 1024 * 1024:
            raise ValueError("DOCX expanded size exceeds the case limit")
        required = {"[Content_Types].xml", "_rels/.rels", "word/document.xml"}
        listed_names = archive.namelist()
        names = set(listed_names)
        if len(names) != len(listed_names):
            raise ValueError("DOCX contains duplicate package paths")
        if not required.issubset(names):
            raise ValueError("DOCX is missing required OPC parts")
        if any(
            name.endswith("vbaProject.bin")
            or "/embeddings/" in name
            or name.startswith("word/media/")
            or name.startswith("customXml/")
            or name.startswith("_xmlsignatures/")
            for name in names
        ):
            raise ValueError("DOCX contains executable or embedded content")
        for name in names:
            if name.endswith(".rels"):
                root = ET.fromstring(archive.read(name))
                for relationship in root.findall(q(PKG_REL_NS, "Relationship")):
                    if relationship.get("TargetMode") == "External":
                        raise ValueError("DOCX contains an external relationship")
        root = ET.fromstring(archive.read("word/document.xml"))
        forbidden_nodes = (
            "altChunk",
            "documentProtection",
            "drawing",
            "object",
            "pict",
            "subDoc",
        )
        if any(root.find(f".//{q(W_NS, name)}") is not None for name in forbidden_nodes):
            raise ValueError("DOCX contains a non-editable or unsafe document element")
        if "word/settings.xml" in names:
            settings = ET.fromstring(archive.read("word/settings.xml"))
            if settings.find(f".//{q(W_NS, 'documentProtection')}") is not None:
                raise ValueError("DOCX editing is protected")
    body = root.find(q(W_NS, "body"))
    if body is None:
        raise ValueError("DOCX lacks a document body")
    if any(child.tag not in {q(W_NS, "p"), q(W_NS, "tbl"), q(W_NS, "sectPr")} for child in body):
        raise ValueError("DOCX body contains an unsupported top-level element")
    blocks: list[Paragraph | Table] = []
    for child in body:
        if child.tag == q(W_NS, "p"):
            style_node = child.find(f"{q(W_NS, 'pPr')}/{q(W_NS, 'pStyle')}")
            style = style_node.get(q(W_NS, "val"), "Normal") if style_node is not None else "Normal"
            value = text_of(child)
            if value:
                blocks.append(Paragraph(value, style))
        elif child.tag == q(W_NS, "tbl"):
            rows: list[tuple[str, ...]] = []
            for row in child.findall(q(W_NS, "tr")):
                rows.append(tuple(text_of(cell) for cell in row.findall(q(W_NS, "tc"))))
            if rows:
                blocks.append(Table(tuple(rows)))
    if not blocks:
        raise ValueError("DOCX has no readable content")
    return blocks


def table_map(blocks: list[Paragraph | Table]) -> dict[tuple[str, ...], Table]:
    result: dict[tuple[str, ...], Table] = {}
    for block in blocks:
        if not isinstance(block, Table) or not block.rows:
            continue
        header = block.rows[0]
        if header in result:
            raise ValueError("DOCX repeats a required table header")
        result[header] = block
    return result


def section_text(blocks: list[Paragraph | Table], heading: str) -> str:
    active = False
    values: list[str] = []
    for block in blocks:
        if isinstance(block, Paragraph) and block.style == "Heading1":
            if active:
                break
            active = block.text == heading
            continue
        if active:
            if isinstance(block, Paragraph):
                values.append(block.text)
            else:
                values.extend(cell for row in block.rows for cell in row)
    return " ".join(values)


def evidence_set(value: str) -> set[str]:
    return set(EVIDENCE_PATTERN.findall(value))


def check_structured_rows(
    table: Table | None,
    *,
    key_index: int,
    content_index: int,
    evidence_index: int | None,
    expected: list[dict[str, Any]],
    key_name: str,
) -> tuple[bool, str]:
    if table is None:
        return False, "required table is missing"
    rows = table.rows[1:]
    if len(rows) != len(expected):
        return False, f"expected {len(expected)} rows, observed {len(rows)}"
    by_key: dict[str, tuple[str, ...]] = {}
    for row in rows:
        if max(key_index, content_index, evidence_index or 0) >= len(row):
            return False, "table row has the wrong number of cells"
        if row[key_index] in by_key:
            return False, "table contains duplicate keys"
        by_key[row[key_index]] = row
    for item in expected:
        key = item[key_name]
        row = by_key.get(key)
        if row is None:
            return False, f"missing required row {key}"
        content = row[content_index]
        if len(content) > 500 or not all(term in content for term in item["required_terms"]):
            return False, f"row {key} lacks its bounded required facts"
        if evidence_index is not None and evidence_set(row[evidence_index]) != set(item["evidence"]):
            return False, f"row {key} has missing, extra, or misplaced evidence"
    return True, "all rows contain the required fact and exact evidence set"


def workspace_integrity(workspace: Path, manifest: dict[str, Any]) -> tuple[bool, str]:
    expected: dict[str, str] = {
        item["workspace_path"]: item["sha256"] for item in manifest["fixture_files"]
    }
    expected["output/incident_postmortem.docx"] = "dynamic"
    observed: list[str] = []
    expected_directories = {
        parent.as_posix()
        for relative in expected
        for parent in Path(relative).parents
        if parent.as_posix() not in {"", "."}
    }
    observed_directories: set[str] = set()
    for path in sorted(workspace.rglob("*")):
        if path.is_symlink():
            return False, "workspace contains a symbolic link"
        relative = path.relative_to(workspace).as_posix()
        if path.is_dir():
            observed_directories.add(relative)
        elif path.is_file():
            observed.append(relative)
            if relative not in expected:
                return False, "workspace contains an undeclared file"
            if expected[relative] != "dynamic" and sha256_file(path) != expected[relative]:
                return False, "an immutable input file was modified"
    if set(observed) != set(expected):
        return False, "workspace is missing an input or the required output"
    if observed_directories != expected_directories:
        return False, "workspace contains an undeclared or missing directory"
    return True, "inputs are unchanged and the DOCX is the only new file"


def source_evidence(workspace: Path) -> set[str]:
    result: set[str] = set()
    with (workspace / "input/service_events.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            item = json.loads(line)
            result.add(item["event_id"])
    for name in ("change_ticket.json", "impact_summary.json"):
        item = json.loads((workspace / f"input/{name}").read_text(encoding="utf-8"))
        result.add(item["evidence_id"])
    alerts = json.loads((workspace / "input/alerts.json").read_text(encoding="utf-8"))
    result.update(item["evidence_id"] for item in alerts["alerts"])
    return result


def verify(case_root: Path, workspace: Path) -> dict[str, Any]:
    facts = json.loads((case_root / "verifier/oracle_facts.json").read_text(encoding="utf-8"))
    manifest = json.loads((case_root / "environment/workspace_manifest.json").read_text(encoding="utf-8"))
    runtime = json.loads((case_root / "environment/runtime_contract.json").read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []

    def add(check_id: str, passed: bool, detail: str) -> None:
        checks.append({"check_id": check_id, "passed": passed, "detail": detail})

    integrity_ok, integrity_detail = workspace_integrity(workspace, manifest)
    add("workspace_integrity", integrity_ok, integrity_detail)
    runtime_ok = (
        runtime.get("image_digest")
        == "sha256:ba7e2064c4e1ab67d2af2cd761183b4af961cbc21f47020ef785b738472b01ac"
        and runtime.get("network_mode") == "none"
        and runtime.get("published_ports") == []
        and runtime.get("user") == "2050:4007"
        and runtime.get("read_only_rootfs") is True
        and runtime.get("cap_drop") == ["ALL"]
        and runtime.get("no_new_privileges") is True
    )
    add(
        "runtime_contract",
        runtime_ok,
        "frozen runtime contract is offline, unprivileged, and port-free"
        if runtime_ok
        else "frozen runtime contract does not satisfy the isolation gate",
    )
    available_evidence = source_evidence(workspace)
    evidence_ok = set(facts["known_evidence_ids"]).issubset(available_evidence)
    add("source_evidence_closed", evidence_ok, "trusted expected evidence is present in immutable inputs" if evidence_ok else "trusted expected evidence is absent from inputs")
    try:
        blocks = parse_docx(workspace / "output/incident_postmortem.docx")
    except (OSError, ValueError, zipfile.BadZipFile, ET.ParseError) as exc:
        add("docx_structure", False, f"DOCX structural check failed: {type(exc).__name__}")
        return {
            "schema_version": "nami_work_case02_verifier_result_v1",
            "task_id": "case_02",
            "verdict": "reject",
            "score": 0.0,
            "checks": checks,
        }
    add("docx_structure", True, "OPC package and OOXML body parsed without external or embedded content")
    paragraphs = [block for block in blocks if isinstance(block, Paragraph)]
    titles = [item.text for item in paragraphs if item.style == "Title"]
    add("title", titles == [facts["title"]], "exactly one required title is present" if titles == [facts["title"]] else "title is missing, duplicated, or changed")
    headings = [item.text for item in paragraphs if item.style == "Heading1"]
    add("heading_order", headings == facts["headings"], "all required sections appear once and in order" if headings == facts["headings"] else "required section order or heading styles are incorrect")
    style_counts = {
        style: sum(item.style == style for item in paragraphs)
        for style in {item.style for item in paragraphs}
    }
    paragraph_structure_ok = style_counts == {"Title": 1, "Heading1": 7, "Normal": 1}
    add(
        "paragraph_structure",
        paragraph_structure_ok,
        "the title, seven headings, and one bounded summary are the only paragraphs"
        if paragraph_structure_ok
        else "the document contains a missing, extra, or mis-styled paragraph",
    )
    try:
        tables = table_map(blocks)
    except ValueError:
        tables = {}
        add("table_uniqueness", False, "a required table header is duplicated")
    else:
        add("table_uniqueness", True, "required table headers are unique")

    metadata_table = tables.get(("字段", "内容"))
    metadata_ok = False
    if metadata_table is not None:
        rows = metadata_table.rows[1:]
        metadata_ok = len(rows) == len(facts["metadata"]) and {
            row[0]: row[1] for row in rows if len(row) == 2
        } == facts["metadata"]
    add("incident_metadata", metadata_ok, "incident identity and time window match the inputs" if metadata_ok else "incident metadata is incomplete or inconsistent")

    impact_ok, impact_detail = check_structured_rows(
        tables.get(("指标", "结果", "证据")),
        key_index=0,
        content_index=1,
        evidence_index=2,
        expected=facts["impact"],
        key_name="metric",
    )
    add("quantified_impact", impact_ok, impact_detail)
    timeline_ok, timeline_detail = check_structured_rows(
        tables.get(("时间", "事件", "证据")),
        key_index=0,
        content_index=1,
        evidence_index=2,
        expected=facts["timeline"],
        key_name="time",
    )
    add("evidenced_timeline", timeline_ok, timeline_detail)
    root_ok, root_detail = check_structured_rows(
        tables.get(("链路环节", "事实", "证据")),
        key_index=0,
        content_index=1,
        evidence_index=2,
        expected=facts["root_cause"],
        key_name="step",
    )
    root_text = section_text(blocks, "4. 根因分析与证据链")
    no_distractor_root = all(item not in root_text for item in facts["distractor_ids"])
    add("root_cause_chain", root_ok and no_distractor_root, root_detail if no_distractor_root else "a distractor alert appears inside the root-cause section")
    recovery_ok, recovery_detail = check_structured_rows(
        tables.get(("时间", "处置", "证据")),
        key_index=0,
        content_index=1,
        evidence_index=2,
        expected=facts["recovery"],
        key_name="time",
    )
    add("recovery_process", recovery_ok, recovery_detail)
    distractor_ok, distractor_detail = check_structured_rows(
        tables.get(("告警", "判断与理由", "证据")),
        key_index=0,
        content_index=1,
        evidence_index=2,
        expected=facts["distractors"],
        key_name="alert",
    )
    add("distractor_exclusion", distractor_ok, distractor_detail)

    action_table = tables.get(("行动项", "负责人", "完成期限", "验收标准"))
    actions_ok = False
    if action_table is not None and len(action_table.rows[1:]) == len(facts["actions"]):
        action_rows = {row[0]: row for row in action_table.rows[1:] if len(row) == 4}
        actions_ok = all(
            item["action"] in action_rows
            and action_rows[item["action"]][1] == item["owner"]
            and action_rows[item["action"]][2] == item["deadline"]
            and len(action_rows[item["action"]][3]) <= 300
            and all(term in action_rows[item["action"]][3] for term in item["required_terms"])
            for item in facts["actions"]
        )
    add("action_ownership", actions_ok, "all actions have an exact owner, deadline, and measurable acceptance standard" if actions_ok else "an action lacks its required owner, deadline, or measurable acceptance standard")

    summary_text = section_text(blocks, "1. 事故摘要")
    summary_terms = ["CHG-2026-0712-041", "db.pool.max", "120", "12", "21分钟", "1,260", "10:24", "无订单丢失"]
    summary_ok = 80 <= len(summary_text) <= 800 and all(term in summary_text for term in summary_terms)
    add("bounded_summary", summary_ok, "summary states the cause, impact, recovery, and data-integrity conclusion" if summary_ok else "summary is missing a required conclusion or is unbounded")

    full_text = " ".join(
        [item.text for item in paragraphs]
        + [cell for table in tables.values() for row in table.rows for cell in row]
    )
    evidence_counts = {item: full_text.count(item) for item in facts["known_evidence_ids"]}
    expected_use_counts = {item: 0 for item in facts["known_evidence_ids"]}
    for section_name in ("timeline", "impact", "root_cause", "recovery", "distractors"):
        for row in facts[section_name]:
            for evidence_id in row["evidence"]:
                expected_use_counts[evidence_id] += 1
    evidence_repetition_ok = all(
        evidence_counts[evidence_id] <= expected_use_counts[evidence_id] + 1
        for evidence_id in evidence_counts
    )
    forbidden_assertions = {
        "数据库发生永久损坏",
        "订单丢失42笔",
        "ALT-CPU-112是根因",
        "ALT-SSL-209是根因",
    }
    copy_safe = (
        1200 <= len(full_text) <= 16000
        and "{\"event_id\"" not in full_text
        and "\"timestamp\"" not in full_text
        and evidence_repetition_ok
        and not any(assertion in full_text for assertion in forbidden_assertions)
    )
    add("anti_keyword_dump", copy_safe, "document is bounded and does not copy raw logs or repeat evidence indiscriminately" if copy_safe else "document resembles a raw-log or keyword dump, or contains a contradictory cause claim")

    passed = sum(item["passed"] for item in checks)
    verdict = "accept" if passed == len(checks) else "reject"
    return {
        "schema_version": "nami_work_case02_verifier_result_v1",
        "task_id": "case_02",
        "verdict": verdict,
        "score": round(passed / len(checks), 6),
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = verify(args.case_root, args.workspace)
    except Exception as exc:  # fail closed without exposing payload content
        result = {
            "schema_version": "nami_work_case02_verifier_result_v1",
            "task_id": "case_02",
            "verdict": "invalid",
            "score": 0.0,
            "checks": [
                {
                    "check_id": "verifier_runtime",
                    "passed": False,
                    "detail": f"trusted verifier failed: {type(exc).__name__}",
                }
            ],
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return {"accept": 0, "reject": 1, "invalid": 2}[result["verdict"]]


if __name__ == "__main__":
    raise SystemExit(main())
