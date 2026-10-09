#!/usr/bin/env python3
"""Deterministic, answer-agnostic OOXML spreadsheet writer for case_07."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import zipfile
from datetime import date
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape, quoteattr


FIXED_ZIP_TIME = (2026, 7, 1, 0, 0, 0)
CELL_REF_RE = re.compile(r"^[A-Z]{1,3}[1-9][0-9]*$")
RANGE_REF_RE = re.compile(r"^[A-Z]{1,3}[1-9][0-9]*(?::[A-Z]{1,3}[1-9][0-9]*)?$")
SHEET_NAME_RE = re.compile(r"^[^\\/*?:\[\]]{1,31}$")
FORMULA_REF_RE = re.compile(r"^'[^']+'!\$[A-Z]{1,3}\$[1-9][0-9]*(?::\$[A-Z]{1,3}\$[1-9][0-9]*)?$")
STYLE_IDS = {
    "normal": 0,
    "date": 1,
    "header": 2,
    "money": 3,
    "percent": 4,
    "title": 5,
    "integer": 6,
    "kpi_label": 7,
}


class SpecError(ValueError):
    """Raised when the caller provides an invalid workbook specification."""


def _column_name(index: int) -> str:
    if index < 1:
        raise SpecError("column index must be positive")
    result = ""
    while index:
        index, rem = divmod(index - 1, 26)
        result = chr(65 + rem) + result
    return result


def _excel_serial(value: str) -> int:
    parsed = date.fromisoformat(value)
    epoch = date(1899, 12, 30)
    return (parsed - epoch).days


def _style_id(cell: dict[str, Any]) -> int:
    style = cell.get("style", "normal")
    if style not in STYLE_IDS:
        raise SpecError(f"unsupported cell style: {style}")
    return STYLE_IDS[style]


def _finite_number(value: Any) -> float | int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SpecError("numeric cell value must be an integer or float")
    if not math.isfinite(float(value)):
        raise SpecError("numeric cell value must be finite")
    return value


def _cell_xml(row_number: int, column_number: int, cell: Any) -> str:
    ref = f"{_column_name(column_number)}{row_number}"
    if not isinstance(cell, dict):
        raise SpecError(f"cell {ref} must be an object")
    cell_type = cell.get("type")
    style_id = _style_id(cell)
    style_attr = f' s="{style_id}"' if style_id else ""
    if cell_type == "string":
        value = cell.get("value")
        if not isinstance(value, str):
            raise SpecError(f"string cell {ref} requires a string value")
        preserve = ' xml:space="preserve"' if value != value.strip() else ""
        return f'<c r="{ref}" t="inlineStr"{style_attr}><is><t{preserve}>{escape(value)}</t></is></c>'
    if cell_type == "number":
        value = _finite_number(cell.get("value"))
        return f'<c r="{ref}"{style_attr}><v>{value}</v></c>'
    if cell_type == "date":
        value = cell.get("value")
        if not isinstance(value, str):
            raise SpecError(f"date cell {ref} requires an ISO date string")
        serial = _excel_serial(value)
        date_style = STYLE_IDS["date"]
        return f'<c r="{ref}" s="{date_style}"><v>{serial}</v></c>'
    if cell_type == "formula":
        formula = cell.get("formula")
        if not isinstance(formula, str) or not formula.startswith("=") or len(formula) > 1000:
            raise SpecError(f"formula cell {ref} requires a bounded formula beginning with =")
        if "[" in formula or "]" in formula or "http:" in formula.lower() or "https:" in formula.lower():
            raise SpecError(f"formula cell {ref} contains an external or unsafe reference")
        value = _finite_number(cell.get("value"))
        return f'<c r="{ref}"{style_attr}><f>{escape(formula[1:])}</f><v>{value}</v></c>'
    raise SpecError(f"unsupported cell type at {ref}: {cell_type}")


def _worksheet_xml(sheet: dict[str, Any], drawing_id: int | None) -> str:
    rows = sheet.get("rows")
    if not isinstance(rows, list) or not rows or len(rows) > 10000:
        raise SpecError("each worksheet requires 1..10000 rows")
    max_columns = 0
    row_xml: list[str] = []
    for row_number, row in enumerate(rows, start=1):
        if not isinstance(row, list) or not row or len(row) > 1000:
            raise SpecError(f"worksheet row {row_number} must contain 1..1000 cells")
        max_columns = max(max_columns, len(row))
        cells = "".join(
            _cell_xml(row_number, column_number, cell)
            for column_number, cell in enumerate(row, start=1)
        )
        row_xml.append(f'<row r="{row_number}">{cells}</row>')
    dimension = f"A1:{_column_name(max_columns)}{len(rows)}"
    widths = sheet.get("column_widths", [])
    cols_xml = ""
    if widths:
        if not isinstance(widths, list) or len(widths) > max_columns:
            raise SpecError("column_widths must be a bounded list")
        definitions = []
        for index, width in enumerate(widths, start=1):
            width = _finite_number(width)
            if not 1 <= float(width) <= 100:
                raise SpecError("column width must be between 1 and 100")
            definitions.append(f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>')
        cols_xml = f"<cols>{''.join(definitions)}</cols>"
    pane_xml = ""
    freeze = sheet.get("freeze_panes")
    if freeze is not None:
        if not isinstance(freeze, str) or not CELL_REF_RE.fullmatch(freeze):
            raise SpecError("freeze_panes must be a cell reference")
        row_match = re.search(r"[0-9]+$", freeze)
        col_match = re.match(r"[A-Z]+", freeze)
        assert row_match and col_match
        y_split = int(row_match.group()) - 1
        x_split = 0
        for char in col_match.group():
            x_split = x_split * 26 + ord(char) - 64
        x_split -= 1
        pane_xml = (
            f'<pane xSplit="{x_split}" ySplit="{y_split}" topLeftCell="{freeze}" '
            'activePane="bottomRight" state="frozen"/>'
        )
    filter_xml = ""
    auto_filter = sheet.get("auto_filter")
    if auto_filter is not None:
        if not isinstance(auto_filter, str) or not RANGE_REF_RE.fullmatch(auto_filter):
            raise SpecError("auto_filter must be a local worksheet range")
        filter_xml = f'<autoFilter ref="{auto_filter}"/>'
    drawing_xml = f'<drawing r:id="rId{drawing_id}"/>' if drawing_id is not None else ""
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<dimension ref="{dimension}"/><sheetViews><sheetView workbookViewId="0">{pane_xml}</sheetView></sheetViews>'
        f'<sheetFormatPr defaultRowHeight="15"/>{cols_xml}<sheetData>{"".join(row_xml)}</sheetData>'
        f'{filter_xml}{drawing_xml}</worksheet>'
    )


def _styles_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <numFmts count="3"><numFmt numFmtId="164" formatCode="yyyy-mm-dd"/><numFmt numFmtId="165" formatCode="¥#,##0.00"/><numFmt numFmtId="166" formatCode="0.00%"/></numFmts>
  <fonts count="3"><font><sz val="11"/><name val="Noto Sans CJK SC"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Noto Sans CJK SC"/></font><font><b/><sz val="16"/><name val="Noto Sans CJK SC"/></font></fonts>
  <fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF1F4E78"/><bgColor indexed="64"/></patternFill></fill></fills>
  <borders count="2"><border><left/><right/><top/><bottom/><diagonal/></border><border><left style="thin"/><right style="thin"/><top style="thin"/><bottom style="thin"/><diagonal/></border></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="8">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"/>
    <xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
    <xf numFmtId="166" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
    <xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1"/>
    <xf numFmtId="1" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>
  </cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>"""


def _validated_chart_title(chart: dict[str, Any]) -> str:
    title = chart.get("title")
    if (
        not isinstance(title, str)
        or not title
        or title != title.strip()
        or len(title) > 128
        or any(ord(char) < 0x20 and char not in "\t\n\r" for char in title)
    ):
        raise SpecError("chart title must be a safe non-empty XML text value")
    return title


def _chart_xml(chart: dict[str, Any]) -> str:
    if chart.get("type") != "column":
        raise SpecError("only native column charts are supported")
    title = _validated_chart_title(chart)
    refs = [chart.get("series_name_ref"), chart.get("category_ref"), chart.get("value_ref")]
    if not all(isinstance(value, str) and FORMULA_REF_RE.fullmatch(value) for value in refs):
        raise SpecError("chart references must be absolute in-workbook ranges")
    series_name_ref, category_ref, value_ref = [escape(str(value)) for value in refs]
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <c:chart><c:title><c:tx><c:rich><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="zh-CN"/><a:t>{escape(title)}</a:t></a:r></a:p></c:rich></c:tx><c:layout/></c:title><c:autoTitleDeleted val="0"/><c:plotArea><c:layout/>
    <c:barChart><c:barDir val="col"/><c:grouping val="clustered"/><c:varyColors val="0"/><c:ser><c:idx val="0"/><c:order val="0"/><c:tx><c:strRef><c:f>{series_name_ref}</c:f></c:strRef></c:tx><c:cat><c:strRef><c:f>{category_ref}</c:f></c:strRef></c:cat><c:val><c:numRef><c:f>{value_ref}</c:f></c:numRef></c:val></c:ser><c:axId val="48650112"/><c:axId val="48672768"/></c:barChart>
    <c:catAx><c:axId val="48650112"/><c:scaling><c:orientation val="minMax"/></c:scaling><c:delete val="0"/><c:axPos val="b"/><c:tickLblPos val="nextTo"/><c:crossAx val="48672768"/><c:crosses val="autoZero"/><c:auto val="1"/><c:lblAlgn val="ctr"/><c:lblOffset val="100"/></c:catAx>
    <c:valAx><c:axId val="48672768"/><c:scaling><c:orientation val="minMax"/></c:scaling><c:delete val="0"/><c:axPos val="l"/><c:numFmt formatCode="¥#,##0.00" sourceLinked="0"/><c:tickLblPos val="nextTo"/><c:crossAx val="48650112"/><c:crosses val="autoZero"/><c:crossBetween val="between"/></c:valAx>
  </c:plotArea><c:legend><c:legendPos val="r"/><c:layout/></c:legend><c:plotVisOnly val="1"/><c:dispBlanksAs val="gap"/></c:chart></c:chartSpace>'''


def _drawing_xml(chart: dict[str, Any]) -> str:
    drawing_name = quoteattr(f"{_validated_chart_title(chart)}图表")
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
  <xdr:twoCellAnchor><xdr:from><xdr:col>1</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>6</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:from><xdr:to><xdr:col>9</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>22</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:to><xdr:graphicFrame macro=""><xdr:nvGraphicFramePr><xdr:cNvPr id="2" name={drawing_name}/><xdr:cNvGraphicFramePr/></xdr:nvGraphicFramePr><xdr:xfrm/><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/chart"><c:chart xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" r:id="rId1"/></a:graphicData></a:graphic></xdr:graphicFrame><xdr:clientData/></xdr:twoCellAnchor>
</xdr:wsDr>'''


def _content_types(sheet_count: int, has_chart: bool) -> str:
    overrides = [
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>',
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>',
    ]
    overrides.extend(
        f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for index in range(1, sheet_count + 1)
    )
    if has_chart:
        overrides.extend([
            '<Override PartName="/xl/drawings/drawing1.xml" ContentType="application/vnd.openxmlformats-officedocument.drawing+xml"/>',
            '<Override PartName="/xl/charts/chart1.xml" ContentType="application/vnd.openxmlformats-officedocument.drawingml.chart+xml"/>',
        ])
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        + "".join(overrides)
        + '</Types>'
    )


def _build_parts(spec: dict[str, Any]) -> dict[str, str]:
    sheets = spec.get("sheets")
    charts = spec.get("charts")
    if not isinstance(sheets, list) or not 1 <= len(sheets) <= 20:
        raise SpecError("sheets must contain 1..20 worksheets")
    if not isinstance(charts, list) or len(charts) > 1:
        raise SpecError("charts must be an array containing at most one chart")
    names: list[str] = []
    for sheet in sheets:
        if not isinstance(sheet, dict):
            raise SpecError("each sheet must be an object")
        name = sheet.get("name")
        if not isinstance(name, str) or not SHEET_NAME_RE.fullmatch(name) or name in names:
            raise SpecError("worksheet names must be unique and valid")
        names.append(name)
    chart_sheet_index: int | None = None
    if charts:
        chart_sheet = charts[0].get("sheet")
        if chart_sheet not in names:
            raise SpecError("chart target worksheet does not exist")
        chart_sheet_index = names.index(str(chart_sheet)) + 1

    workbook_sheets = "".join(
        f'<sheet name={quoteattr(name)} sheetId="{index}" r:id="rId{index}"/>'
        for index, name in enumerate(names, start=1)
    )
    parts: dict[str, str] = {
        "[Content_Types].xml": _content_types(len(sheets), bool(charts)),
        "_rels/.rels": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/></Relationships>''',
        "docProps/core.xml": '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:creator>Agent SFT Spreadsheet Writer</dc:creator><cp:lastModifiedBy>Agent SFT Spreadsheet Writer</cp:lastModifiedBy><dcterms:created xsi:type="dcterms:W3CDTF">2026-07-01T00:00:00Z</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">2026-07-01T00:00:00Z</dcterms:modified></cp:coreProperties>''',
        "docProps/app.xml": f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>Agent SFT Spreadsheet Writer</Application><DocSecurity>0</DocSecurity><ScaleCrop>false</ScaleCrop><HeadingPairs><vt:vector size="2" baseType="variant"><vt:variant><vt:lpstr>Worksheets</vt:lpstr></vt:variant><vt:variant><vt:i4>{len(sheets)}</vt:i4></vt:variant></vt:vector></HeadingPairs><TitlesOfParts><vt:vector size="{len(sheets)}" baseType="lpstr">{''.join(f'<vt:lpstr>{escape(name)}</vt:lpstr>' for name in names)}</vt:vector></TitlesOfParts><Company>Agent SFT</Company><LinksUpToDate>false</LinksUpToDate><SharedDoc>false</SharedDoc><HyperlinksChanged>false</HyperlinksChanged><AppVersion>1.0</AppVersion></Properties>''',
        "xl/workbook.xml": f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><fileVersion appName="xl"/><workbookPr date1904="0"/><bookViews><workbookView xWindow="0" yWindow="0" windowWidth="24000" windowHeight="12000"/></bookViews><sheets>{workbook_sheets}</sheets><calcPr calcId="191029" calcMode="auto" fullCalcOnLoad="1" forceFullCalc="1"/></workbook>''',
        "xl/styles.xml": _styles_xml(),
    }
    relationships = []
    for index in range(1, len(sheets) + 1):
        relationships.append(f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>')
    relationships.append(f'<Relationship Id="rId{len(sheets) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>')
    parts["xl/_rels/workbook.xml.rels"] = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + "".join(relationships) + '</Relationships>'
    for index, sheet in enumerate(sheets, start=1):
        drawing_id = 1 if chart_sheet_index == index else None
        parts[f"xl/worksheets/sheet{index}.xml"] = _worksheet_xml(sheet, drawing_id)
        if drawing_id is not None:
            parts[f"xl/worksheets/_rels/sheet{index}.xml.rels"] = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing" Target="../drawings/drawing1.xml"/></Relationships>'''
    if charts:
        parts["xl/drawings/drawing1.xml"] = _drawing_xml(charts[0])
        parts["xl/drawings/_rels/drawing1.xml.rels"] = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart" Target="../charts/chart1.xml"/></Relationships>'''
        parts["xl/charts/chart1.xml"] = _chart_xml(charts[0])
    return parts


def write_workbook(spec: dict[str, Any], output: Path) -> None:
    parts = _build_parts(spec)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() or output.is_symlink():
        raise SpecError("output_exists")
    staging = output.with_suffix(output.suffix + ".next")
    if staging.exists() or staging.is_symlink():
        raise SpecError("staging output already exists")
    try:
        with zipfile.ZipFile(staging, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name in sorted(parts):
                info = zipfile.ZipInfo(name, date_time=FIXED_ZIP_TIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, parts[name].encode("utf-8"))
        staging.replace(output)
    except Exception:
        if staging.exists():
            staging.unlink()
        raise


def _inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path("/workspace"))
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        workspace = args.workspace.resolve(strict=True)
        spec_path = args.spec.resolve(strict=True)
        output = args.output.resolve(strict=False)
        if not workspace.is_dir() or not _inside(workspace, spec_path) or not _inside(workspace / "output", output):
            raise SpecError("path_outside_workspace")
        if spec_path.is_symlink() or output.is_symlink():
            raise SpecError("symbolic links are not allowed")
        payload = json.loads(spec_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise SpecError("workbook spec must be an object")
        write_workbook(payload, output)
        result = {"status": "ok", "output": str(output), "size_bytes": output.stat().st_size}
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, ValueError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        print(json.dumps({"status": "error", "error": type(exc).__name__}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
