#!/usr/bin/env python3
"""Deterministically verify case_07 from source CSV and OOXML semantics."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import posixpath
import re
import stat
import zipfile
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


VERSION = "1.0.0"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main", "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships", "pr": "http://schemas.openxmlformats.org/package/2006/relationships", "c": "http://schemas.openxmlformats.org/drawingml/2006/chart", "xdr": "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"}
EXPECTED_SHEETS = ["清洗明细", "区域汇总", "品类汇总", "异常清单", "仪表盘"]
DETAIL_HEADERS = ["订单号", "销售日期", "区域", "渠道", "销售人员", "产品", "品类", "数量", "单价", "折扣率", "状态", "有效性", "异常原因", "净销售额"]
REGIONS = ["华北", "华东", "华南", "西部"]
CATEGORIES = ["办公配件", "数码配件", "数码设备"]
CHANNELS = {"直营网", "电商", "渠道"}
FORBIDDEN_PART_FRAGMENTS = ("vbaproject", "xl/externallinks/", "xl/connections", "xl/querytables/", "xl/embeddings/", "xl/activex/", "xl/ctrlprops/", "xl/media/")
CELL_REF_RE = re.compile(r"^([A-Z]{1,3})([1-9][0-9]*)$")


@dataclass(frozen=True)
class Cell:
    value: str | float | None
    formula: str | None
    cell_type: str | None
    style_id: int


class WorkbookError(ValueError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _finite_float(value: str | float | None) -> float:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise WorkbookError("expected numeric cached value") from exc
    if not math.isfinite(number):
        raise WorkbookError("cached value is not finite")
    return number


def _formula_key(value: str | None) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", "", value).upper()


def _excel_serial(value: str) -> int:
    return (date.fromisoformat(value) - date(1899, 12, 30)).days


def _is_valid_date(value: str) -> bool:
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return False
    return date(2026, 4, 1) <= parsed <= date(2026, 6, 30)


def _safe_decimal(value: str) -> Decimal | None:
    try:
        number = Decimal(value)
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def _classify(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    for line_number, row in enumerate(rows, start=2):
        order_id = row["order_id"]
        if order_id in seen:
            reason = "重复订单号"
        elif not _is_valid_date(row["sale_date"]):
            reason = "无效日期"
        elif not row["salesperson"].strip():
            reason = "销售人员缺失"
        else:
            try:
                quantity = int(row["quantity"])
                quantity_valid = str(quantity) == row["quantity"].strip() and quantity > 0
            except ValueError:
                quantity_valid = False
            discount = _safe_decimal(row["discount_pct"])
            price = _safe_decimal(row["unit_price"])
            if not quantity_valid:
                reason = "数量无效"
            elif discount is None or not Decimal("0") <= discount <= Decimal("0.30"):
                reason = "折扣率无效"
            elif row["status"] != "已完成":
                reason = "状态非已完成"
            elif row["region"] not in REGIONS:
                reason = "区域无效"
            elif row["channel"] not in CHANNELS:
                reason = "渠道无效"
            elif not row["product"].strip() or row["category"] not in CATEGORIES:
                reason = "产品或品类无效"
            elif price is None or price <= 0:
                reason = "单价无效"
            else:
                reason = ""
        seen.add(order_id)
        if reason:
            net = Decimal("0.00")
        else:
            net = (Decimal(row["quantity"]) * Decimal(row["unit_price"]) * (Decimal(1) - Decimal(row["discount_pct"]))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        results.append({"line": line_number, "row": row, "reason": reason, "net": net})
    return results


def _check_workspace(workspace: Path, expected_input_hashes: dict[str, str]) -> tuple[bool, dict[str, Any]]:
    expected = {"task.md", "input", "output"}
    actual: set[str] = set()
    violations: list[str] = []
    if workspace.is_symlink() or not workspace.is_dir():
        return False, {"violation_codes": ["workspace_not_directory"]}
    for path in workspace.rglob("*"):
        relative = path.relative_to(workspace).as_posix()
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            violations.append(f"symlink:{relative}")
        elif not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            violations.append(f"special:{relative}")
    actual = {path.name for path in workspace.iterdir()}
    if actual != expected:
        violations.append("root_entries")
    input_dir = workspace / "input"
    output_dir = workspace / "output"
    if not input_dir.is_dir() or input_dir.is_symlink():
        violations.append("input_directory")
    elif {path.name for path in input_dir.iterdir()} != set(expected_input_hashes):
        violations.append("input_entries")
    if not output_dir.is_dir() or output_dir.is_symlink():
        violations.append("output_directory")
    elif {path.name for path in output_dir.iterdir()} != {"sales_analysis.xlsx"}:
        violations.append("output_entries")
    task = workspace / "task.md"
    if not task.is_file() or task.is_symlink():
        violations.append("task_file")
    return not violations, {"violation_codes": sorted(violations), "root_entries": sorted(actual)}


def _read_xml(archive: zipfile.ZipFile, name: str) -> ET.Element:
    try:
        data = archive.read(name)
    except KeyError as exc:
        raise WorkbookError(f"required OOXML part missing: {name}") from exc
    if len(data) > 5_000_000 or b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise WorkbookError("unsafe or oversized XML part")
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        raise WorkbookError("malformed OOXML XML") from exc


def _relationship_target(base_part: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join(posixpath.dirname(base_part), target))


class Workbook:
    def __init__(self, path: Path):
        if path.stat().st_size > 5_000_000:
            raise WorkbookError("workbook exceeds size limit")
        self.archive = zipfile.ZipFile(path)
        names = self.archive.namelist()
        if len(names) != len(set(names)) or len(names) > 500:
            raise WorkbookError("duplicate or excessive OOXML parts")
        total_uncompressed = 0
        for info in self.archive.infolist():
            normalized = posixpath.normpath(info.filename)
            lowered = normalized.lower()
            if normalized.startswith("../") or normalized.startswith("/") or "\\" in info.filename:
                raise WorkbookError("unsafe OOXML part path")
            if any(fragment in lowered for fragment in FORBIDDEN_PART_FRAGMENTS):
                raise WorkbookError("forbidden macro, external, embedded, or media part")
            total_uncompressed += info.file_size
        if total_uncompressed > 20_000_000:
            raise WorkbookError("OOXML expansion exceeds limit")
        for name in names:
            if name.endswith(".rels"):
                root = _read_xml(self.archive, name)
                for rel in root.findall("pr:Relationship", NS):
                    target = rel.attrib.get("Target", "")
                    if rel.attrib.get("TargetMode") == "External" or re.match(r"^(?:https?|file):", target, re.I):
                        raise WorkbookError("external relationship is forbidden")
            if name.startswith("xl/drawings/") and name.endswith(".xml"):
                drawing_root = _read_xml(self.archive, name)
                if drawing_root.find(".//xdr:pic", NS) is not None:
                    raise WorkbookError("pictures cannot substitute for native charts")
        self.shared_strings = self._load_shared_strings()
        self.date_styles = self._load_date_styles()
        self.sheet_parts = self._load_sheet_parts()

    def close(self) -> None:
        self.archive.close()

    def _load_shared_strings(self) -> list[str]:
        if "xl/sharedStrings.xml" not in self.archive.namelist():
            return []
        root = _read_xml(self.archive, "xl/sharedStrings.xml")
        return ["".join(node.text or "" for node in item.findall(".//m:t", NS)) for item in root.findall("m:si", NS)]

    def _load_date_styles(self) -> set[int]:
        root = _read_xml(self.archive, "xl/styles.xml")
        custom: dict[int, str] = {}
        for fmt in root.findall("m:numFmts/m:numFmt", NS):
            custom[int(fmt.attrib["numFmtId"])] = fmt.attrib.get("formatCode", "")
        date_styles: set[int] = set()
        for index, xf in enumerate(root.findall("m:cellXfs/m:xf", NS)):
            num_fmt = int(xf.attrib.get("numFmtId", "0"))
            code = custom.get(num_fmt, "").lower()
            if 14 <= num_fmt <= 22 or ("y" in code and ("m" in code or "d" in code)):
                date_styles.add(index)
        return date_styles

    def _load_sheet_parts(self) -> dict[str, str]:
        workbook = _read_xml(self.archive, "xl/workbook.xml")
        rels = _read_xml(self.archive, "xl/_rels/workbook.xml.rels")
        targets = {rel.attrib["Id"]: _relationship_target("xl/workbook.xml", rel.attrib["Target"]) for rel in rels.findall("pr:Relationship", NS) if rel.attrib.get("Type", "").endswith("/worksheet")}
        result: dict[str, str] = {}
        for sheet in workbook.findall("m:sheets/m:sheet", NS):
            name = sheet.attrib.get("name", "")
            if sheet.attrib.get("state", "visible") != "visible":
                raise WorkbookError("hidden worksheets are forbidden")
            relation_id = sheet.attrib.get(f"{{{NS['r']}}}id", "")
            if relation_id not in targets:
                raise WorkbookError("worksheet relationship is missing")
            result[name] = targets[relation_id]
        return result

    def cells(self, sheet_name: str) -> dict[str, Cell]:
        if sheet_name not in self.sheet_parts:
            raise WorkbookError("worksheet missing")
        root = _read_xml(self.archive, self.sheet_parts[sheet_name])
        cells: dict[str, Cell] = {}
        for node in root.findall(".//m:sheetData/m:row/m:c", NS):
            ref = node.attrib.get("r", "")
            if not CELL_REF_RE.fullmatch(ref) or ref in cells:
                raise WorkbookError("invalid or duplicate cell reference")
            formula_node = node.find("m:f", NS)
            formula = formula_node.text if formula_node is not None else None
            cell_type = node.attrib.get("t")
            style_id = int(node.attrib.get("s", "0"))
            if cell_type == "inlineStr":
                value: str | float | None = "".join(part.text or "" for part in node.findall(".//m:t", NS))
            else:
                value_node = node.find("m:v", NS)
                raw = value_node.text if value_node is not None else None
                if cell_type == "s":
                    try:
                        value = self.shared_strings[int(raw or "")]
                    except (ValueError, IndexError) as exc:
                        raise WorkbookError("invalid shared string index") from exc
                elif cell_type in {"str", "e", "b"}:
                    value = raw
                elif raw is None or raw == "":
                    value = None
                else:
                    value = _finite_float(raw)
            cells[ref] = Cell(value=value, formula=formula, cell_type=cell_type, style_id=style_id)
        return cells

    def sheet_root(self, sheet_name: str) -> ET.Element:
        return _read_xml(self.archive, self.sheet_parts[sheet_name])


def _text(cell: Cell | None) -> str:
    if cell is None or not isinstance(cell.value, str):
        raise WorkbookError("expected string cell")
    return cell.value


def _number(cell: Cell | None) -> float:
    if cell is None or cell.cell_type in {"inlineStr", "s", "str", "e", "b"}:
        raise WorkbookError("expected numeric cell")
    return _finite_float(cell.value)


def _formula(cell: Cell | None, expected: str, expected_value: Decimal | int) -> bool:
    if cell is None or _formula_key(cell.formula) != _formula_key(expected):
        return False
    actual = _finite_float(cell.value)
    return math.isclose(actual, float(expected_value), rel_tol=0, abs_tol=1e-6)


def _summary_expected(classified: list[dict[str, Any]], key: str, labels: list[str]) -> dict[str, tuple[int, int, Decimal]]:
    output: dict[str, tuple[int, int, Decimal]] = {}
    for label in labels:
        selected = [item for item in classified if not item["reason"] and item["row"][key] == label]
        output[label] = (len(selected), sum(int(item["row"]["quantity"]) for item in selected), sum((item["net"] for item in selected), Decimal(0)))
    return output


def verify(workspace: Path, fixture_root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    def add(check_id: str, passed: bool, **evidence: Any) -> None:
        checks.append({"check_id": check_id, "passed": bool(passed), "evidence": evidence})

    expected_hashes = {name: _sha256(fixture_root / "workspace_seed" / "input" / name) for name in ("sales_records.csv", "metric_rules.md")}
    expected_task_hash = _sha256(fixture_root / "workspace_seed" / "task.md")
    workspace_ok, workspace_evidence = _check_workspace(workspace, expected_hashes)
    add("workspace_scope", workspace_ok, **workspace_evidence)
    input_ok = False
    if workspace_ok:
        observed_hashes = {f"input/{name}": _sha256(workspace / "input" / name) for name in expected_hashes}
        observed_hashes["task.md"] = _sha256(workspace / "task.md")
        required_hashes = {f"input/{name}": value for name, value in expected_hashes.items()}
        required_hashes["task.md"] = expected_task_hash
        input_ok = observed_hashes == required_hashes
        add("input_integrity", input_ok, observed_sha256=observed_hashes)
    else:
        add("input_integrity", False, violation_codes=["workspace_scope_failed"])
    workbook_path = workspace / "output" / "sales_analysis.xlsx"
    workbook_hash = _sha256(workbook_path) if workbook_path.is_file() and not workbook_path.is_symlink() else None
    if not (workspace_ok and input_ok and workbook_hash):
        return _result(checks, workbook_hash)
    try:
        with (workspace / "input" / "sales_records.csv").open(encoding="utf-8", newline="") as handle:
            source_rows = list(csv.DictReader(handle))
        if len(source_rows) != 20:
            raise WorkbookError("source row count is not fixed")
        classified = _classify(source_rows)
        workbook = Workbook(workbook_path)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        add("ooxml_security", False, error_code=type(exc).__name__)
        return _result(checks, workbook_hash)
    try:
        add("ooxml_security", True, part_count=len(workbook.archive.namelist()), macro_external_media_absent=True)
        structure_ok = list(workbook.sheet_parts) == EXPECTED_SHEETS
        try:
            cells = {name: workbook.cells(name) for name in EXPECTED_SHEETS}
        except WorkbookError:
            structure_ok = False
            cells = {}
        add("workbook_structure", structure_ok, observed_sheets=list(workbook.sheet_parts), expected_sheets=EXPECTED_SHEETS)
        if not structure_ok:
            return _result(checks, workbook_hash)

        detail = cells["清洗明细"]
        detail_clean = True
        detail_formula = True
        if [_text(detail.get(f"{chr(65 + index)}1")) for index in range(14)] != DETAIL_HEADERS:
            detail_clean = False
        expected_refs = {f"{chr(65 + column)}{row}" for row in range(1, 22) for column in range(14)}
        if set(detail) != expected_refs:
            detail_clean = False
        for excel_row, item in enumerate(classified, start=2):
            row = item["row"]
            reason = item["reason"]
            expected_strings = {"A": row["order_id"], "C": row["region"], "D": row["channel"], "E": row["salesperson"], "F": row["product"], "G": row["category"], "K": row["status"], "L": "异常" if reason else "有效", "M": reason}
            for column, expected in expected_strings.items():
                try:
                    if _text(detail.get(f"{column}{excel_row}")) != expected:
                        detail_clean = False
                except WorkbookError:
                    detail_clean = False
            try:
                if _number(detail.get(f"H{excel_row}")) != int(row["quantity"]):
                    detail_clean = False
                if not math.isclose(_number(detail.get(f"I{excel_row}")), float(Decimal(row["unit_price"])), abs_tol=1e-9):
                    detail_clean = False
                if not math.isclose(_number(detail.get(f"J{excel_row}")), float(Decimal(row["discount_pct"])), abs_tol=1e-9):
                    detail_clean = False
                date_cell = detail.get(f"B{excel_row}")
                if _is_valid_date(row["sale_date"]):
                    if _number(date_cell) != _excel_serial(row["sale_date"]) or date_cell is None or date_cell.style_id not in workbook.date_styles:
                        detail_clean = False
                elif _text(date_cell) != row["sale_date"]:
                    detail_clean = False
            except (WorkbookError, InvalidOperation, ValueError):
                detail_clean = False
            expected_formula = f'IF(L{excel_row}="有效",ROUND(H{excel_row}*I{excel_row}*(1-J{excel_row}),2),0)'
            try:
                if not _formula(detail.get(f"N{excel_row}"), expected_formula, item["net"]):
                    detail_formula = False
            except WorkbookError:
                detail_formula = False
        add("detail_cleaning", detail_clean, source_rows=len(classified), expected_anomalies=sum(bool(item["reason"]) for item in classified))
        add("detail_formulas", detail_formula, required_formula_count=20, formula_column="N2:N21")

        def verify_summary(sheet: str, labels: list[str], source_key: str, field_column: str) -> tuple[bool, dict[str, Any]]:
            data = cells[sheet]
            expected = _summary_expected(classified, source_key, labels)
            header = "区域" if source_key == "region" else "品类"
            ok = all(_text(data.get(f"{column}1")) == value for column, value in zip("ABCD", [header, "有效订单数", "销售数量", "净销售额"]))
            for row_number, label in enumerate(labels, start=2):
                orders, quantity, net = expected[label]
                ok = ok and _text(data.get(f"A{row_number}")) == label
                formulas = [
                    (f"COUNTIFS('清洗明细'!${field_column}$2:${field_column}$21,A{row_number},'清洗明细'!$L$2:$L$21,\"有效\")", orders),
                    (f"SUMIFS('清洗明细'!$H$2:$H$21,'清洗明细'!${field_column}$2:${field_column}$21,A{row_number},'清洗明细'!$L$2:$L$21,\"有效\")", quantity),
                    (f"SUMIFS('清洗明细'!$N$2:$N$21,'清洗明细'!${field_column}$2:${field_column}$21,A{row_number},'清洗明细'!$L$2:$L$21,\"有效\")", net),
                ]
                for column, (formula, value) in zip("BCD", formulas):
                    try:
                        ok = ok and _formula(data.get(f"{column}{row_number}"), formula, value)
                    except WorkbookError:
                        ok = False
            total_row = len(labels) + 2
            last_row = total_row - 1
            totals = (sum(value[0] for value in expected.values()), sum(value[1] for value in expected.values()), sum((value[2] for value in expected.values()), Decimal(0)))
            ok = ok and _text(data.get(f"A{total_row}")) == "合计"
            for column, value in zip("BCD", totals):
                try:
                    ok = ok and _formula(data.get(f"{column}{total_row}"), f"SUM({column}2:{column}{last_row})", value)
                except WorkbookError:
                    ok = False
            expected_cell_count = 4 * (len(labels) + 2)
            ok = ok and len(data) == expected_cell_count
            return ok, {"labels": labels, "total_orders": totals[0], "total_quantity": totals[1], "total_net_sales": float(totals[2])}

        region_ok, region_evidence = verify_summary("区域汇总", REGIONS, "region", "C")
        add("region_summary", region_ok, **region_evidence)
        category_ok, category_evidence = verify_summary("品类汇总", CATEGORIES, "category", "G")
        add("category_summary", category_ok, **category_evidence)

        anomaly = cells["异常清单"]
        expected_anomalies = [item for item in classified if item["reason"]]
        anomaly_ok = len(anomaly) == 3 * (len(expected_anomalies) + 1)
        try:
            anomaly_ok = anomaly_ok and [_text(anomaly.get(f"{column}1")) for column in "ABC"] == ["源行号", "订单号", "异常原因"]
            for row_number, item in enumerate(expected_anomalies, start=2):
                anomaly_ok = anomaly_ok and _number(anomaly.get(f"A{row_number}")) == item["line"] and _text(anomaly.get(f"B{row_number}")) == item["row"]["order_id"] and _text(anomaly.get(f"C{row_number}")) == item["reason"]
        except WorkbookError:
            anomaly_ok = False
        add("anomaly_list", anomaly_ok, expected_count=len(expected_anomalies), expected_source_lines=[item["line"] for item in expected_anomalies])

        dashboard = cells["仪表盘"]
        region_totals = region_evidence
        dashboard_ok = len(dashboard) == 9
        try:
            dashboard_ok = dashboard_ok and _text(dashboard.get("A1")) == "2026 年第二季度销售仪表盘"
            dashboard_ok = dashboard_ok and [_text(dashboard.get(f"A{row}")) for row in range(3, 6)] == ["有效订单数", "销售数量", "净销售额"]
            dashboard_ok = dashboard_ok and _formula(dashboard.get("B3"), "'区域汇总'!B6", int(region_totals["total_orders"]))
            dashboard_ok = dashboard_ok and _formula(dashboard.get("B4"), "'区域汇总'!C6", int(region_totals["total_quantity"]))
            dashboard_ok = dashboard_ok and _formula(dashboard.get("B5"), "'区域汇总'!D6", Decimal(str(region_totals["total_net_sales"])))
        except WorkbookError:
            dashboard_ok = False
        add("dashboard_kpis", dashboard_ok, formula_cells=["B3", "B4", "B5"])

        chart_parts = sorted(name for name in workbook.archive.namelist() if re.fullmatch(r"xl/charts/chart[0-9]+\.xml", name))
        chart_ok = len(chart_parts) == 1
        chart_refs: list[str] = []
        chart_title = ""
        if chart_ok:
            chart_root = _read_xml(workbook.archive, chart_parts[0])
            chart_title = "".join(node.text or "" for node in chart_root.findall(".//a:t", {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}))
            chart_refs = [node.text or "" for node in chart_root.findall(".//c:f", NS)]
            expected_refs = ["'区域汇总'!$D$1", "'区域汇总'!$A$2:$A$5", "'区域汇总'!$D$2:$D$5"]
            chart_ok = chart_title == "区域净销售额" and chart_refs == expected_refs and chart_root.find(".//c:barChart/c:barDir[@val='col']", NS) is not None
            dashboard_root = workbook.sheet_root("仪表盘")
            chart_ok = chart_ok and dashboard_root.find("m:drawing", NS) is not None
        add("chart_binding", chart_ok, chart_title=chart_title, chart_refs=chart_refs, native_chart_parts=chart_parts)
    except (WorkbookError, OSError, ValueError, InvalidOperation) as exc:
        add("verifier_execution", False, error_code=type(exc).__name__)
    finally:
        workbook.close()
    return _result(checks, workbook_hash)


def _result(checks: list[dict[str, Any]], workbook_hash: str | None) -> dict[str, Any]:
    failed = sum(not item["passed"] for item in checks)
    return {"schema_version": "case07_verifier_result_v1", "verifier_version": VERSION, "verdict": "accept" if failed == 0 else "reject", "checks": checks, "summary": {"passed": len(checks) - failed, "failed": failed, "workbook_sha256": workbook_hash}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--fixtures", type=Path, default=Path("/case/fixtures"))
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.workspace.resolve(strict=True), args.fixtures.resolve(strict=True))
    args.result.parent.mkdir(parents=True, exist_ok=True)
    next_path = args.result.with_suffix(args.result.suffix + ".next")
    next_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_path.replace(args.result)
    print(json.dumps({"verdict": result["verdict"], "failed": result["summary"]["failed"]}, sort_keys=True))
    return 0 if result["verdict"] == "accept" else 1


if __name__ == "__main__":
    raise SystemExit(main())
