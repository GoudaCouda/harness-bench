#!/usr/bin/env python3
"""Deterministic, dependency-free writer for a small editable DOCX subset."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CP_NS = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
DC_NS = "http://purl.org/dc/elements/1.1/"
DCTERMS_NS = "http://purl.org/dc/terms/"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
ET.register_namespace("w", W_NS)
ET.register_namespace("r", R_NS)
ET.register_namespace("cp", CP_NS)
ET.register_namespace("dc", DC_NS)
ET.register_namespace("dcterms", DCTERMS_NS)
ET.register_namespace("xsi", XSI_NS)


def q(namespace: str, tag: str) -> str:
    return f"{{{namespace}}}{tag}"


def _xml_bytes(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _run(paragraph: ET.Element, text: str, *, bold: bool = False) -> None:
    run = ET.SubElement(paragraph, q(W_NS, "r"))
    if bold:
        properties = ET.SubElement(run, q(W_NS, "rPr"))
        ET.SubElement(properties, q(W_NS, "b"))
    node = ET.SubElement(run, q(W_NS, "t"))
    if text.startswith(" ") or text.endswith(" "):
        node.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    node.text = text


def _paragraph(parent: ET.Element, text: str, style: str = "Normal") -> ET.Element:
    paragraph = ET.SubElement(parent, q(W_NS, "p"))
    properties = ET.SubElement(paragraph, q(W_NS, "pPr"))
    ET.SubElement(properties, q(W_NS, "pStyle"), {q(W_NS, "val"): style})
    _run(paragraph, text)
    return paragraph


def _table(parent: ET.Element, headers: list[str], rows: list[list[str]]) -> None:
    if not headers or any(len(row) != len(headers) for row in rows):
        raise ValueError("table rows must match a non-empty header")
    table = ET.SubElement(parent, q(W_NS, "tbl"))
    properties = ET.SubElement(table, q(W_NS, "tblPr"))
    ET.SubElement(properties, q(W_NS, "tblStyle"), {q(W_NS, "val"): "TableGrid"})
    width = ET.SubElement(properties, q(W_NS, "tblW"))
    width.set(q(W_NS, "w"), "0")
    width.set(q(W_NS, "type"), "auto")
    borders = ET.SubElement(properties, q(W_NS, "tblBorders"))
    for name in ("top", "left", "bottom", "right", "insideH", "insideV"):
        ET.SubElement(
            borders,
            q(W_NS, name),
            {
                q(W_NS, "val"): "single",
                q(W_NS, "sz"): "4",
                q(W_NS, "space"): "0",
                q(W_NS, "color"): "B7C4D6",
            },
        )
    for row_index, values in enumerate([headers, *rows]):
        row = ET.SubElement(table, q(W_NS, "tr"))
        for value in values:
            cell = ET.SubElement(row, q(W_NS, "tc"))
            cell_properties = ET.SubElement(cell, q(W_NS, "tcPr"))
            ET.SubElement(
                cell_properties,
                q(W_NS, "tcW"),
                {q(W_NS, "w"): "0", q(W_NS, "type"): "auto"},
            )
            paragraph = ET.SubElement(cell, q(W_NS, "p"))
            _run(paragraph, str(value), bold=row_index == 0)


def _document_xml(plan: dict[str, Any]) -> bytes:
    title = plan.get("title")
    blocks = plan.get("blocks")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("plan.title must be a non-empty string")
    if not isinstance(blocks, list):
        raise ValueError("plan.blocks must be a list")
    document = ET.Element(q(W_NS, "document"))
    body = ET.SubElement(document, q(W_NS, "body"))
    _paragraph(body, title.strip(), "Title")
    for block in blocks:
        if not isinstance(block, dict):
            raise ValueError("each block must be an object")
        kind = block.get("type")
        if kind == "heading":
            level = block.get("level", 1)
            text = block.get("text")
            if level != 1 or not isinstance(text, str) or not text.strip():
                raise ValueError("only non-empty level-1 headings are supported")
            _paragraph(body, text.strip(), "Heading1")
        elif kind == "paragraph":
            text = block.get("text")
            if not isinstance(text, str) or not text.strip():
                raise ValueError("paragraph text must be non-empty")
            _paragraph(body, text.strip(), "Normal")
        elif kind == "table":
            headers = block.get("headers")
            rows = block.get("rows")
            if not isinstance(headers, list) or not all(
                isinstance(value, str) for value in headers
            ):
                raise ValueError("table headers must be strings")
            if not isinstance(rows, list) or not all(
                isinstance(row, list) and all(isinstance(value, str) for value in row)
                for row in rows
            ):
                raise ValueError("table rows must be arrays of strings")
            _table(body, headers, rows)
        else:
            raise ValueError("unsupported block type")
    section = ET.SubElement(body, q(W_NS, "sectPr"))
    ET.SubElement(
        section,
        q(W_NS, "pgSz"),
        {q(W_NS, "w"): "11906", q(W_NS, "h"): "16838"},
    )
    ET.SubElement(
        section,
        q(W_NS, "pgMar"),
        {
            q(W_NS, "top"): "1134",
            q(W_NS, "right"): "1134",
            q(W_NS, "bottom"): "1134",
            q(W_NS, "left"): "1134",
            q(W_NS, "header"): "720",
            q(W_NS, "footer"): "720",
            q(W_NS, "gutter"): "0",
        },
    )
    return _xml_bytes(document)


def _styles_xml() -> bytes:
    styles = ET.Element(q(W_NS, "styles"))
    defaults = ET.SubElement(styles, q(W_NS, "docDefaults"))
    run_defaults = ET.SubElement(defaults, q(W_NS, "rPrDefault"))
    run_props = ET.SubElement(run_defaults, q(W_NS, "rPr"))
    ET.SubElement(
        run_props,
        q(W_NS, "rFonts"),
        {
            q(W_NS, "ascii"): "Noto Sans CJK SC",
            q(W_NS, "hAnsi"): "Noto Sans CJK SC",
            q(W_NS, "eastAsia"): "Noto Sans CJK SC",
        },
    )
    for style_id, name, size, bold in (
        ("Normal", "Normal", "21", False),
        ("Title", "Title", "36", True),
        ("Heading1", "heading 1", "28", True),
    ):
        style = ET.SubElement(
            styles,
            q(W_NS, "style"),
            {q(W_NS, "type"): "paragraph", q(W_NS, "styleId"): style_id},
        )
        ET.SubElement(style, q(W_NS, "name"), {q(W_NS, "val"): name})
        properties = ET.SubElement(style, q(W_NS, "rPr"))
        ET.SubElement(properties, q(W_NS, "sz"), {q(W_NS, "val"): size})
        ET.SubElement(properties, q(W_NS, "szCs"), {q(W_NS, "val"): size})
        if bold:
            ET.SubElement(properties, q(W_NS, "b"))
    table_style = ET.SubElement(
        styles,
        q(W_NS, "style"),
        {q(W_NS, "type"): "table", q(W_NS, "styleId"): "TableGrid"},
    )
    ET.SubElement(table_style, q(W_NS, "name"), {q(W_NS, "val"): "Table Grid"})
    return _xml_bytes(styles)


def _core_xml() -> bytes:
    root = ET.Element(q(CP_NS, "coreProperties"))
    ET.SubElement(root, q(DC_NS, "title")).text = "Editable incident postmortem"
    ET.SubElement(root, q(DC_NS, "creator")).text = "agent_sft synthetic environment"
    created = ET.SubElement(root, q(DCTERMS_NS, "created"))
    created.set(q(XSI_NS, "type"), "dcterms:W3CDTF")
    created.text = "2026-07-12T03:00:00Z"
    modified = ET.SubElement(root, q(DCTERMS_NS, "modified"))
    modified.set(q(XSI_NS, "type"), "dcterms:W3CDTF")
    modified.text = "2026-07-12T03:00:00Z"
    return _xml_bytes(root)


def _write_member(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=(2026, 7, 12, 3, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, data)


def write_docx(plan: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    content_types = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>'''
    root_rels = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>'''
    document_rels = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>'''
    app_xml = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>agent_sft deterministic writer</Application></Properties>'''
    with zipfile.ZipFile(output_path, "w") as archive:
        for name, data in (
            ("[Content_Types].xml", content_types),
            ("_rels/.rels", root_rels),
            ("docProps/core.xml", _core_xml()),
            ("docProps/app.xml", app_xml),
            ("word/document.xml", _document_xml(plan)),
            ("word/styles.xml", _styles_xml()),
            ("word/_rels/document.xml.rels", document_rels),
        ):
            _write_member(archive, name, data)


def _resolve_output(workspace: Path, logical_output: str) -> Path:
    workspace = workspace.resolve()
    output_root = (workspace / "output").resolve()
    candidate = (workspace / logical_output).resolve()
    if candidate.parent != output_root or candidate.suffix.lower() != ".docx":
        raise ValueError("output must be one DOCX directly under workspace/output")
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    if not isinstance(plan, dict):
        raise ValueError("plan must be a JSON object")
    write_docx(plan, _resolve_output(args.workspace, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
