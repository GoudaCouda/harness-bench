#!/usr/bin/env python3
"""Deterministically verify case_03 by parsing DOCX OOXML and workspace state."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
W = f"{{{W_NS}}}"
PLACEHOLDER = "____________________"
EXPECTED_ROOT_DIRS = {"input", "output", "task", "tools"}
EXPECTED_PROTECTED_FILES = {
    "input/hospital_header.json",
    "input/equipment_registry.json",
    "input/inspection_standard.json",
    "task/instruction.md",
    "tools/docx_writer.py",
    "tools/tool_contract.json",
}
EXPECTED_OUTPUT = "output/monitoring_equipment_inspection_form.docx"
EXPECTED_PACKAGE_PARTS = {
    "[Content_Types].xml",
    "_rels/.rels",
    "docProps/app.xml",
    "docProps/core.xml",
    "word/_rels/document.xml.rels",
    "word/document.xml",
    "word/settings.xml",
    "word/styles.xml",
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def workspace_digest(workspace: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(workspace.rglob("*")):
        relative = path.relative_to(workspace).as_posix()
        if path.is_symlink():
            digest.update(f"L\0{relative}\n".encode())
        elif path.is_dir():
            digest.update(f"D\0{relative}\0{path.stat().st_mode & 0o777:o}\n".encode())
        elif path.is_file():
            digest.update(f"F\0{relative}\0{path.stat().st_mode & 0o777:o}\0{file_sha256(path)}\n".encode())
        else:
            digest.update(f"X\0{relative}\n".encode())
    return digest.hexdigest()


def all_workspace_entries(workspace: Path) -> tuple[set[str], set[str], set[str]]:
    directories: set[str] = set()
    files: set[str] = set()
    links: set[str] = set()
    for path in workspace.rglob("*"):
        relative = path.relative_to(workspace).as_posix()
        if path.is_symlink():
            links.add(relative)
        elif path.is_dir():
            directories.add(relative)
        elif path.is_file():
            files.add(relative)
        else:
            links.add(relative)
    return directories, files, links


def cell_signature(cell: ET.Element) -> tuple[str, int]:
    text = "".join(node.text or "" for node in cell.iter(f"{W}t"))
    span_node = cell.find(f"{W}tcPr/{W}gridSpan")
    span = int(span_node.attrib.get(f"{W}val", "1")) if span_node is not None else 1
    return text, span


def table_signature(table: ET.Element) -> list[list[tuple[str, int]]]:
    return [
        [cell_signature(cell) for cell in row.findall(f"{W}tc")]
        for row in table.findall(f"{W}tr")
    ]


def expected_table(hospital: dict, device: dict, common: list[str], typed: dict[str, list[str]]) -> list[list[tuple[str, int]]]:
    items = common + typed[device["device_type"]]
    rows: list[list[tuple[str, int]]] = [
        [(hospital["hospital_name"], 4)],
        [(hospital["form_title"], 4)],
        [("文档编号", 1), (hospital["document_code"], 1), ("负责部门", 1), (hospital["department"], 1)],
        [("设备编号", 1), (device["asset_id"], 1), ("设备名称", 1), (device["device_name"], 1)],
        [("设备类型", 1), (device["device_type"], 1), ("设备型号", 1), (device["model"], 1)],
        [("安装位置", 1), (device["location"], 1), ("责任班组", 1), (device["responsible_team"], 1)],
        [("巡检周期", 1), (device["inspection_cycle"], 1), ("巡检日期", 1), (PLACEHOLDER, 1)],
        [("序号", 1), ("巡检项目", 1), ("状态（正常/异常）", 1), ("问题及处理记录", 1)],
    ]
    for index, item in enumerate(items, 1):
        rows.append([(str(index), 1), (item, 1), (PLACEHOLDER, 1), (PLACEHOLDER, 1)])
    rows.extend([
        [("处理结果/复核意见", 1), (PLACEHOLDER + PLACEHOLDER, 3)],
        [("巡检人签字", 1), (PLACEHOLDER, 1), ("复核人签字", 1), (PLACEHOLDER, 1)],
        [("巡检日期", 1), (PLACEHOLDER, 1), ("复核日期", 1), (PLACEHOLDER, 1)],
        [(hospital["privacy_notice"], 4)],
    ])
    return rows


def safe_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON fixture must be an object")
    return value


def verify(workspace: Path, case_root: Path) -> dict:
    workspace = workspace.resolve()
    before = workspace_digest(workspace)
    checks: list[dict] = []

    def record(check_id: str, passed: bool, evidence: str) -> None:
        checks.append({"check_id": check_id, "passed": bool(passed), "evidence": evidence[:1000]})

    directories, files, links = all_workspace_entries(workspace)
    root_dirs = {item for item in directories if "/" not in item}
    expected_files = EXPECTED_PROTECTED_FILES | {EXPECTED_OUTPUT}
    shape_ok = not links and root_dirs == EXPECTED_ROOT_DIRS and files == expected_files and directories == EXPECTED_ROOT_DIRS
    record("workspace_shape", shape_ok, f"root_dirs={sorted(root_dirs)} files={len(files)} links={sorted(links)}")

    manifest = safe_json(case_root / "environment/workspace_manifest.json")
    protected_ok = True
    protected_bad: list[str] = []
    for relative, expected_hash in manifest["protected_file_sha256"].items():
        path = workspace / relative
        if not path.is_file() or path.is_symlink() or file_sha256(path) != expected_hash:
            protected_ok = False
            protected_bad.append(relative)
    record("protected_inputs", protected_ok, "unchanged" if protected_ok else "changed=" + ",".join(protected_bad))

    output_path = workspace / EXPECTED_OUTPUT
    output_ok = output_path.is_file() and not output_path.is_symlink() and 1000 <= output_path.stat().st_size <= 2_000_000
    record("output_contract", output_ok, f"exists={output_path.is_file()} size={output_path.stat().st_size if output_path.is_file() else 0}")

    document_root: ET.Element | None = None
    package_ok = False
    editable_ok = False
    package_evidence = "output missing"
    if output_ok:
        try:
            with zipfile.ZipFile(output_path) as archive:
                names = archive.namelist()
                safe_names = all(name and not name.startswith("/") and ".." not in Path(name).parts for name in names)
                unique_names = len(names) == len(set(names))
                bounded = all(info.file_size <= 5_000_000 for info in archive.infolist()) and sum(info.file_size for info in archive.infolist()) <= 10_000_000
                package_ok = safe_names and unique_names and bounded and set(names) == EXPECTED_PACKAGE_PARTS
                package_evidence = f"parts={len(names)} safe={safe_names} unique={unique_names} bounded={bounded}"
                if package_ok:
                    document_root = ET.fromstring(archive.read("word/document.xml"))
                    settings_root = ET.fromstring(archive.read("word/settings.xml"))
                    rel_roots = [ET.fromstring(archive.read("_rels/.rels")), ET.fromstring(archive.read("word/_rels/document.xml.rels"))]
                    external = any(
                        node.attrib.get("TargetMode") == "External"
                        for root in rel_roots
                        for node in root.iter(f"{{{R_NS}}}Relationship")
                    )
                    forbidden_nodes = ["documentProtection", "drawing", "pict", "object", "altChunk", "subDoc"]
                    forbidden_present = any(document_root.find(f".//{W}{name}") is not None for name in forbidden_nodes)
                    protected = settings_root.find(f".//{W}documentProtection") is not None
                    editable_ok = not external and not forbidden_present and not protected
        except (OSError, ValueError, KeyError, ET.ParseError, zipfile.BadZipFile) as exc:
            package_evidence = f"parse_error={type(exc).__name__}"
    record("docx_package", package_ok, package_evidence)
    record("editable_ooxml", editable_ok, "plain OOXML tables without protection, media, external relationships, macros or embedded objects")

    layout_ok = False
    mapping_ok = False
    inspection_ok = False
    fillable_ok = False
    privacy_ok = False
    if document_root is not None:
        hospital = safe_json(workspace / "input/hospital_header.json")
        registry = safe_json(workspace / "input/equipment_registry.json")
        standard = safe_json(workspace / "input/inspection_standard.json")
        body = document_root.find(f"{W}body")
        if body is not None:
            children = list(body)
            tags = [node.tag.rsplit("}", 1)[-1] for node in children]
            expected_tags = ["tbl", "p", "tbl", "p", "tbl", "p", "tbl", "sectPr"]
            breaks = document_root.findall(f".//{W}br")
            break_paragraphs = [node for node in children if node.tag == f"{W}p"]
            clean_break_paragraphs = all(
                not paragraph.findall(f".//{W}t")
                and len(paragraph.findall(f".//{W}br")) == 1
                and paragraph.findall(f".//{W}br")[0].attrib.get(f"{W}type")
                == "page"
                for paragraph in break_paragraphs
            )
            section = body.find(f"{W}sectPr")
            page_size = section.find(f"{W}pgSz") if section is not None else None
            page_margin = section.find(f"{W}pgMar") if section is not None else None
            layout_ok = (
                tags == expected_tags
                and len(breaks) == 3
                and len(break_paragraphs) == 3
                and clean_break_paragraphs
                and all(item.attrib.get(f"{W}type") == "page" for item in breaks)
                and page_size is not None
                and page_size.attrib.get(f"{W}w") == "11906"
                and page_size.attrib.get(f"{W}h") == "16838"
                and page_size.attrib.get(f"{W}orient") == "portrait"
                and page_margin is not None
                and {key: page_margin.attrib.get(f"{W}{key}") for key in ("top", "right", "bottom", "left")}
                == {"top": "1134", "right": "1276", "bottom": "1134", "left": "1276"}
            )
        tables = document_root.findall(f".//{W}tbl")
        actual = [table_signature(table) for table in tables]
        expected = [
            expected_table(hospital, device, standard["common_items"], standard["device_type_items"])
            for device in registry["devices"]
        ]
        mapping_ok = len(actual) == len(expected) == 4 and all(
            len(a) == len(e) == 17
            and a[:8] == e[:8]
            and a[13:] == e[13:]
            for a, e in zip(actual, expected)
        )
        inspection_ok = len(actual) == 4 and all(a[8:13] == e[8:13] for a, e in zip(actual, expected))
        fillable_ok = len(actual) == 4 and all(
            len(table) == 17
            and all(
                len(row) == 4
                and row[2][0] == PLACEHOLDER
                and row[3][0] == PLACEHOLDER
                for row in table[8:13]
            )
            and table[13] == expected[index][13]
            and table[14] == expected[index][14]
            and table[15] == expected[index][15]
            for index, table in enumerate(actual)
        )
        all_text = "\n".join(node.text or "" for node in document_root.iter(f"{W}t"))
        sensitive_pattern = re.compile(r"(?:1[3-9]\d{9}|[\w.+-]+@[\w.-]+\.\w+|\b\d{17}[\dXx]\b)")
        privacy_ok = (
            len(actual) == 4
            and all(
                len(table) == 17
                and table[0] == expected[index][0]
                and table[16] == expected[index][16]
                for index, table in enumerate(actual)
            )
            and sensitive_pattern.search(all_text) is None
            and "真实医院" not in all_text
        )
    record("page_layout", layout_ok, "four A4 portrait pages with three explicit page breaks and fixed margins")
    record("device_mapping", mapping_ok, "four device tables with exact unique source-field mapping")
    record("inspection_rows", inspection_ok, "each table contains three common and two type-specific checks in source order")
    record("fillable_areas", fillable_ok, "status, issue/action, review, signature and date cells are plain editable placeholders")
    record("privacy_boundary", privacy_ok, "fixed synthetic heading and notice; no phone, email, identity number or real-hospital substitution")

    after = workspace_digest(workspace)
    nonmutation_ok = before == after
    record("verifier_nonmutation", nonmutation_ok, f"before={before} after={after}")
    passed_count = sum(1 for item in checks if item["passed"])
    verdict = "accept" if passed_count == len(checks) else "reject"
    return {
        "schema_version": "case03_verifier_result_v1",
        "verdict": verdict,
        "score": passed_count / len(checks),
        "checks": checks,
        "workspace_state_sha256": after,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--case-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.workspace, args.case_root.resolve())
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if result["verdict"] == "accept" else 1


if __name__ == "__main__":
    raise SystemExit(main())
