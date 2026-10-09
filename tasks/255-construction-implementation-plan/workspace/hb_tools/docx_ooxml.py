"""Deterministic, dependency-free helpers for editable OOXML documents."""

from __future__ import annotations

import hashlib
import json
import zipfile
from html import escape
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
CP_NS = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
DC_NS = "http://purl.org/dc/elements/1.1/"
FIXED_ZIP_TIME = (2026, 1, 1, 0, 0, 0)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _zip_write(archive: zipfile.ZipFile, name: str, payload: bytes) -> None:
    info = zipfile.ZipInfo(name, FIXED_ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, payload, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def _run(text: str, *, bold: bool = False) -> str:
    properties = "<w:rPr><w:b/></w:rPr>" if bold else ""
    preserve = ' xml:space="preserve"' if text[:1].isspace() or text[-1:].isspace() else ""
    return f"<w:r>{properties}<w:t{preserve}>{escape(text)}</w:t></w:r>"


def paragraph(text: str, *, style: str | None = None, bold: bool = False, align: str | None = None) -> str:
    props: list[str] = []
    if style:
        props.append(f'<w:pStyle w:val="{escape(style)}"/>')
    if align:
        props.append(f'<w:jc w:val="{escape(align)}"/>')
    ppr = f"<w:pPr>{''.join(props)}</w:pPr>" if props else ""
    return f"<w:p>{ppr}{_run(text, bold=bold)}</w:p>"


def table(rows: list[list[str]], *, header: bool = True) -> str:
    if not rows or not rows[0]:
        raise ValueError("table must contain at least one cell")
    width = max(len(row) for row in rows)
    grid = "".join('<w:gridCol w:w="2400"/>' for _ in range(width))
    rendered_rows: list[str] = []
    for row_index, row in enumerate(rows):
        cells: list[str] = []
        for value in row + [""] * (width - len(row)):
            shading = '<w:shd w:fill="D9EAF7"/>' if header and row_index == 0 else ""
            cell_props = f'<w:tcPr><w:tcW w:w="2400" w:type="dxa"/>{shading}</w:tcPr>'
            cells.append(f"<w:tc>{cell_props}{paragraph(str(value), bold=header and row_index == 0)}</w:tc>")
        rendered_rows.append(f"<w:tr>{''.join(cells)}</w:tr>")
    return (
        '<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/>'
        '<w:tblW w:w="0" w:type="auto"/></w:tblPr>'
        f"<w:tblGrid>{grid}</w:tblGrid>{''.join(rendered_rows)}</w:tbl>"
    )


def document_xml(elements: Iterable[dict[str, Any]]) -> bytes:
    body: list[str] = []
    for item in elements:
        kind = item["type"]
        if kind == "paragraph":
            body.append(
                paragraph(
                    str(item["text"]),
                    style=item.get("style"),
                    bold=bool(item.get("bold", False)),
                    align=item.get("align"),
                )
            )
        elif kind == "table":
            body.append(table([[str(cell) for cell in row] for row in item["rows"]]))
        elif kind == "page_break":
            body.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
        else:
            raise ValueError(f"unsupported document element: {kind}")
    section = (
        '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" '
        'w:header="720" w:footer="720" w:gutter="0"/></w:sectPr>'
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{W_NS}"><w:body>{"".join(body)}{section}</w:body></w:document>'
    )
    return xml.encode("utf-8")


def _styles_xml() -> bytes:
    xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="{W_NS}">
  <w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Noto Sans CJK SC" w:eastAsia="Noto Sans CJK SC"/><w:sz w:val="21"/></w:rPr></w:rPrDefault></w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="正文"/></w:style>
  <w:style w:type="paragraph" w:styleId="Title"><w:name w:val="标题"/><w:basedOn w:val="Normal"/><w:qFormat/><w:pPr><w:jc w:val="center"/><w:spacing w:after="360"/></w:pPr><w:rPr><w:b/><w:sz w:val="36"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="标题 1"/><w:basedOn w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:spacing w:before="240" w:after="120"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:color w:val="1F4E78"/><w:sz w:val="28"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="标题 2"/><w:basedOn w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:spacing w:before="180" w:after="90"/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/><w:color w:val="2F75B5"/><w:sz w:val="24"/></w:rPr></w:style>
  <w:style w:type="table" w:styleId="TableGrid"><w:name w:val="表格网格"/><w:tblPr><w:tblBorders><w:top w:val="single" w:sz="4" w:color="808080"/><w:left w:val="single" w:sz="4" w:color="808080"/><w:bottom w:val="single" w:sz="4" w:color="808080"/><w:right w:val="single" w:sz="4" w:color="808080"/><w:insideH w:val="single" w:sz="4" w:color="BFBFBF"/><w:insideV w:val="single" w:sz="4" w:color="BFBFBF"/></w:tblBorders></w:tblPr></w:style>
</w:styles>'''
    return xml.encode("utf-8")


def create_template(path: Path) -> None:
    elements = [
        {"type": "paragraph", "text": "施工实施方案", "style": "Title", "align": "center"},
        {"type": "paragraph", "text": "项目名称：〔填写〕", "align": "center"},
        {"type": "paragraph", "text": "招标编号：〔填写〕", "align": "center"},
        {"type": "page_break"},
        {"type": "paragraph", "text": "1 项目理解", "style": "Heading1"},
        {"type": "paragraph", "text": "〔依据招标文件填写，不得虚构〕"},
        {"type": "paragraph", "text": "2 施工部署与组织", "style": "Heading1"},
        {"type": "paragraph", "text": "〔使用公司资质表填写〕"},
    ]
    entries = _base_entries(document_xml(elements), title="合成施工实施方案模板")
    _write_package(path, entries)


def _base_entries(document: bytes, *, title: str) -> dict[str, bytes]:
    content_types = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>'''
    rels = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>'''
    document_rels = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>'''
    core = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="{CP_NS}" xmlns:dc="{DC_NS}" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<dc:title>{escape(title)}</dc:title><dc:creator>agent_sft synthetic fixture</dc:creator><cp:lastModifiedBy>agent_sft synthetic fixture</cp:lastModifiedBy>
<dcterms:created xsi:type="dcterms:W3CDTF">2026-01-01T00:00:00Z</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">2026-01-01T00:00:00Z</dcterms:modified>
</cp:coreProperties>'''.encode("utf-8")
    app = b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>agent_sft deterministic OOXML writer</Application><AppVersion>1.0</AppVersion></Properties>'''
    return {
        "[Content_Types].xml": content_types,
        "_rels/.rels": rels,
        "docProps/app.xml": app,
        "docProps/core.xml": core,
        "word/_rels/document.xml.rels": document_rels,
        "word/document.xml": document,
        "word/styles.xml": _styles_xml(),
    }


def _write_package(path: Path, entries: dict[str, bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        for name in sorted(entries):
            _zip_write(archive, name, entries[name])


def render_from_template(template_path: Path, output_path: Path, elements: list[dict[str, Any]]) -> None:
    with zipfile.ZipFile(template_path, "r") as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    required = {"word/document.xml", "word/styles.xml", "[Content_Types].xml"}
    if not required.issubset(entries):
        raise ValueError("template lacks required editable OOXML parts")
    entries["word/document.xml"] = document_xml(elements)
    _write_package(output_path, entries)


def inspect_docx(path: Path) -> dict[str, Any]:
    required = {"[Content_Types].xml", "word/document.xml", "word/styles.xml"}
    with zipfile.ZipFile(path, "r") as archive:
        names = set(archive.namelist())
        bad_member = archive.testzip()
        if not required.issubset(names):
            raise ValueError("document lacks required OOXML parts")
        document = ET.fromstring(archive.read("word/document.xml"))
        styles_root = ET.fromstring(archive.read("word/styles.xml"))
        styles_hash = hashlib.sha256(archive.read("word/styles.xml")).hexdigest()
    ns = {"w": W_NS}
    paragraphs: list[dict[str, str]] = []
    for node in document.findall(".//w:body/w:p", ns):
        text = "".join(value.text or "" for value in node.findall(".//w:t", ns))
        style_node = node.find("./w:pPr/w:pStyle", ns)
        style = style_node.get(f"{{{W_NS}}}val", "Normal") if style_node is not None else "Normal"
        paragraphs.append({"text": text, "style": style})
    tables: list[list[list[str]]] = []
    for tbl in document.findall(".//w:body/w:tbl", ns):
        rows: list[list[str]] = []
        for tr in tbl.findall("./w:tr", ns):
            row = ["".join(t.text or "" for t in tc.findall(".//w:t", ns)) for tc in tr.findall("./w:tc", ns)]
            rows.append(row)
        tables.append(rows)
    style_ids = sorted(
        node.get(f"{{{W_NS}}}styleId", "")
        for node in styles_root.findall("./w:style", ns)
        if node.get(f"{{{W_NS}}}styleId")
    )
    return {
        "valid_zip": bad_member is None,
        "editable_ooxml": True,
        "paragraphs": paragraphs,
        "tables": tables,
        "text": "\n".join(item["text"] for item in paragraphs) + "\n" + "\n".join(" | ".join(row) for table_rows in tables for row in table_rows),
        "style_ids": style_ids,
        "styles_sha256": styles_hash,
        "part_names": sorted(names),
    }


def replace_document_text(source: Path, target: Path, old: str, new: str) -> None:
    with zipfile.ZipFile(source, "r") as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    before = entries["word/document.xml"]
    after = before.replace(old.encode("utf-8"), new.encode("utf-8"), 1)
    if after == before:
        raise ValueError("requested text was not found in document.xml")
    entries["word/document.xml"] = after
    _write_package(target, entries)


def dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
