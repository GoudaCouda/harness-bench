#!/usr/bin/env python3
"""Deterministic, dependency-free DOCX form writer for case_03."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape


FIXED_TIMESTAMP = (2026, 1, 1, 0, 0, 0)
PLACEHOLDER = "____________________"


def text_run(text: str, *, bold: bool = False, size: int = 20) -> str:
    props = [f'<w:sz w:val="{size}"/>', f'<w:szCs w:val="{size}"/>']
    if bold:
        props.append("<w:b/>")
    value = escape(str(text))
    return (
        "<w:r><w:rPr>"
        + "".join(props)
        + '</w:rPr><w:t xml:space="preserve">'
        + value
        + "</w:t></w:r>"
    )


def paragraph(text: str, *, bold: bool = False, align: str = "left", size: int = 20) -> str:
    return (
        f'<w:p><w:pPr><w:jc w:val="{align}"/><w:spacing w:after="80"/></w:pPr>'
        + text_run(text, bold=bold, size=size)
        + "</w:p>"
    )


def cell(text: str, *, width: int = 2300, bold: bool = False, span: int = 1, fill: str | None = None) -> str:
    tc_pr = [f'<w:tcW w:w="{width}" w:type="dxa"/>', '<w:vAlign w:val="center"/>']
    if span > 1:
        tc_pr.append(f'<w:gridSpan w:val="{span}"/>')
    if fill:
        tc_pr.append(f'<w:shd w:val="clear" w:fill="{fill}"/>')
    return (
        "<w:tc><w:tcPr>"
        + "".join(tc_pr)
        + "</w:tcPr>"
        + paragraph(text, bold=bold, align="center" if bold else "left", size=18)
        + "</w:tc>"
    )


def row(cells: list[str], *, height: int = 420) -> str:
    return (
        f'<w:tr><w:trPr><w:trHeight w:val="{height}" w:hRule="atLeast"/></w:trPr>'
        + "".join(cells)
        + "</w:tr>"
    )


def device_table(hospital: dict, device: dict) -> str:
    required = [
        "asset_id", "device_name", "device_type", "model", "location",
        "responsible_team", "inspection_cycle", "inspection_items",
    ]
    for key in required:
        if key not in device:
            raise ValueError(f"device missing required field: {key}")
    items = device["inspection_items"]
    if not isinstance(items, list) or len(items) != 5 or any(not isinstance(x, str) or not x for x in items):
        raise ValueError("each device must contain exactly five non-empty inspection_items")
    rows = [
        row([cell(hospital["hospital_name"], width=9200, bold=True, span=4, fill="D9EAF7")], height=520),
        row([cell(hospital["form_title"], width=9200, bold=True, span=4, fill="EAF2F8")], height=520),
        row([cell("文档编号", bold=True), cell(hospital["document_code"]), cell("负责部门", bold=True), cell(hospital["department"])]),
        row([cell("设备编号", bold=True), cell(device["asset_id"]), cell("设备名称", bold=True), cell(device["device_name"])]),
        row([cell("设备类型", bold=True), cell(device["device_type"]), cell("设备型号", bold=True), cell(device["model"])]),
        row([cell("安装位置", bold=True), cell(device["location"]), cell("责任班组", bold=True), cell(device["responsible_team"])]),
        row([cell("巡检周期", bold=True), cell(device["inspection_cycle"]), cell("巡检日期", bold=True), cell(PLACEHOLDER)]),
        row([cell("序号", width=700, bold=True, fill="EAF2F8"), cell("巡检项目", width=3900, bold=True, fill="EAF2F8"), cell("状态（正常/异常）", width=1900, bold=True, fill="EAF2F8"), cell("问题及处理记录", width=2700, bold=True, fill="EAF2F8")], height=520),
    ]
    for index, item in enumerate(items, 1):
        rows.append(row([cell(str(index), width=700), cell(item, width=3900), cell(PLACEHOLDER, width=1900), cell(PLACEHOLDER, width=2700)], height=620))
    rows.extend([
        row([cell("处理结果/复核意见", width=2300, bold=True), cell(PLACEHOLDER + PLACEHOLDER, width=6900, span=3)], height=720),
        row([cell("巡检人签字", bold=True), cell(PLACEHOLDER), cell("复核人签字", bold=True), cell(PLACEHOLDER)], height=560),
        row([cell("巡检日期", bold=True), cell(PLACEHOLDER), cell("复核日期", bold=True), cell(PLACEHOLDER)], height=560),
        row([cell(hospital["privacy_notice"], width=9200, span=4, fill="FFF2CC")], height=560),
    ])
    return (
        '<w:tbl><w:tblPr><w:tblW w:w="9200" w:type="dxa"/>'
        '<w:tblLayout w:type="fixed"/><w:tblBorders>'
        '<w:top w:val="single" w:sz="8"/><w:left w:val="single" w:sz="8"/>'
        '<w:bottom w:val="single" w:sz="8"/><w:right w:val="single" w:sz="8"/>'
        '<w:insideH w:val="single" w:sz="4"/><w:insideV w:val="single" w:sz="4"/>'
        '</w:tblBorders></w:tblPr><w:tblGrid>'
        '<w:gridCol w:w="2300"/><w:gridCol w:w="2300"/><w:gridCol w:w="2300"/><w:gridCol w:w="2300"/>'
        '</w:tblGrid>' + "".join(rows) + "</w:tbl>"
    )


def document_xml(spec: dict) -> str:
    hospital = spec.get("hospital")
    devices = spec.get("devices")
    if not isinstance(hospital, dict) or not isinstance(devices, list):
        raise ValueError("spec must contain hospital object and devices array")
    hospital_fields = ["document_code", "hospital_name", "department", "form_title", "privacy_notice"]
    for key in hospital_fields:
        if not isinstance(hospital.get(key), str) or not hospital[key]:
            raise ValueError(f"hospital missing required field: {key}")
    if len(devices) != 4:
        raise ValueError("spec must contain exactly four devices")
    body: list[str] = []
    for index, device in enumerate(devices):
        body.append(device_table(hospital, device))
        if index != len(devices) - 1:
            body.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
    body.append(
        '<w:sectPr><w:pgSz w:w="11906" w:h="16838" w:orient="portrait"/>'
        '<w:pgMar w:top="1134" w:right="1276" w:bottom="1134" w:left="1276" '
        'w:header="0" w:footer="0" w:gutter="0"/></w:sectPr>'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body>' + "".join(body) + "</w:body></w:document>"
    )


STATIC_PARTS = {
    "[Content_Types].xml": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>''',
    "_rels/.rels": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>''',
    "word/_rels/document.xml.rels": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>''',
    "word/styles.xml": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Noto Sans CJK SC" w:eastAsia="Noto Sans CJK SC"/></w:rPr></w:rPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
</w:styles>''',
    "word/settings.xml": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:zoom w:percent="100"/></w:settings>''',
    "docProps/core.xml": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<dc:title>监控系统设备巡检记录表</dc:title><dc:creator>agent_sft synthetic fixture</dc:creator><cp:lastModifiedBy>agent_sft synthetic fixture</cp:lastModifiedBy>
<dcterms:created xsi:type="dcterms:W3CDTF">2026-01-01T00:00:00Z</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">2026-01-01T00:00:00Z</dcterms:modified>
</cp:coreProperties>''',
    "docProps/app.xml": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>agent_sft deterministic docx writer</Application><AppVersion>1.0</AppVersion></Properties>''',
}


def build_docx(spec: dict, output_path: Path) -> None:
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.suffix.lower() != ".docx":
        raise ValueError("output must use .docx extension")
    parts = dict(STATIC_PARTS)
    parts["word/document.xml"] = document_xml(spec)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(parts):
            info = zipfile.ZipInfo(name, FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, parts[name].encode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    build_docx(spec, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
