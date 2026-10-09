#!/usr/bin/env python3
"""Build one correct reference workbook without exposing it to the Agent."""

from __future__ import annotations

import argparse
import csv
import importlib.util
from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any


REGIONS = ["华北", "华东", "华南", "西部"]
CATEGORIES = ["办公配件", "数码配件", "数码设备"]
CHANNELS = {"直营网", "电商", "渠道"}
HEADERS = ["订单号", "销售日期", "区域", "渠道", "销售人员", "产品", "品类", "数量", "单价", "折扣率", "状态", "有效性", "异常原因", "净销售额"]


def _load_writer():
    path = Path(__file__).resolve().parents[1] / "environment" / "spreadsheet_writer.py"
    spec = importlib.util.spec_from_file_location("case07_spreadsheet_writer", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load spreadsheet writer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _valid_date(value: str) -> bool:
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return False
    return date(2026, 4, 1) <= parsed <= date(2026, 6, 30)


def _classify(row: dict[str, str], seen: set[str]) -> str:
    order_id = row["order_id"]
    duplicate = order_id in seen
    seen.add(order_id)
    if duplicate:
        return "重复订单号"
    if not _valid_date(row["sale_date"]):
        return "无效日期"
    if not row["salesperson"].strip():
        return "销售人员缺失"
    try:
        quantity = int(row["quantity"])
        if str(quantity) != row["quantity"].strip() or quantity <= 0:
            return "数量无效"
    except ValueError:
        return "数量无效"
    try:
        discount = Decimal(row["discount_pct"])
        if not Decimal("0") <= discount <= Decimal("0.30"):
            return "折扣率无效"
    except Exception:
        return "折扣率无效"
    if row["status"] != "已完成":
        return "状态非已完成"
    if row["region"] not in REGIONS:
        return "区域无效"
    if row["channel"] not in CHANNELS:
        return "渠道无效"
    if not row["product"].strip() or row["category"] not in CATEGORIES:
        return "产品或品类无效"
    try:
        if Decimal(row["unit_price"]) <= 0:
            return "单价无效"
    except Exception:
        return "单价无效"
    return ""


def _string(value: str, style: str = "normal") -> dict[str, Any]:
    return {"type": "string", "value": value, "style": style}


def _number(value: int | float, style: str = "normal") -> dict[str, Any]:
    return {"type": "number", "value": value, "style": style}


def _formula(formula: str, value: int | float, style: str = "normal") -> dict[str, Any]:
    return {"type": "formula", "formula": formula, "value": value, "style": style}


def _money(row: dict[str, str]) -> Decimal:
    return (
        Decimal(row["quantity"])
        * Decimal(row["unit_price"])
        * (Decimal("1") - Decimal(row["discount_pct"]))
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def build_spec(workspace: Path) -> dict[str, Any]:
    with (workspace / "input" / "sales_records.csv").open(encoding="utf-8", newline="") as handle:
        records = list(csv.DictReader(handle))
    if len(records) != 20:
        raise ValueError("reference source row count changed")
    seen: set[str] = set()
    classified: list[tuple[int, dict[str, str], str, Decimal]] = []
    for source_line, row in enumerate(records, start=2):
        reason = _classify(row, seen)
        net = Decimal("0.00") if reason else _money(row)
        classified.append((source_line, row, reason, net))

    detail_rows: list[list[dict[str, Any]]] = [[_string(value, "header") for value in HEADERS]]
    region_totals: dict[str, list[Decimal]] = defaultdict(lambda: [Decimal(0), Decimal(0), Decimal(0)])
    category_totals: dict[str, list[Decimal]] = defaultdict(lambda: [Decimal(0), Decimal(0), Decimal(0)])
    anomaly_rows: list[list[dict[str, Any]]] = [[_string(value, "header") for value in ["源行号", "订单号", "异常原因"]]]
    for excel_row, (source_line, row, reason, net) in enumerate(classified, start=2):
        valid = not reason
        if valid:
            for key in (row["region"], row["category"]):
                target = region_totals[key] if key in REGIONS else category_totals[key]
                target[0] += 1
                target[1] += Decimal(row["quantity"])
                target[2] += net
        else:
            anomaly_rows.append([_number(source_line, "integer"), _string(row["order_id"]), _string(reason)])
        date_cell = (
            {"type": "date", "value": row["sale_date"], "style": "date"}
            if _valid_date(row["sale_date"])
            else _string(row["sale_date"])
        )
        detail_rows.append([
            _string(row["order_id"]),
            date_cell,
            _string(row["region"]),
            _string(row["channel"]),
            _string(row["salesperson"]),
            _string(row["product"]),
            _string(row["category"]),
            _number(int(row["quantity"]), "integer"),
            _number(float(Decimal(row["unit_price"])), "money"),
            _number(float(Decimal(row["discount_pct"])), "percent"),
            _string(row["status"]),
            _string("有效" if valid else "异常"),
            _string(reason),
            _formula(f'=IF(L{excel_row}="有效",ROUND(H{excel_row}*I{excel_row}*(1-J{excel_row}),2),0)', float(net), "money"),
        ])

    def summary_rows(labels: list[str], totals: dict[str, list[Decimal]], field_column: str) -> list[list[dict[str, Any]]]:
        rows: list[list[dict[str, Any]]] = [[_string("区域" if field_column == "C" else "品类", "header"), _string("有效订单数", "header"), _string("销售数量", "header"), _string("净销售额", "header")]]
        for row_number, label in enumerate(labels, start=2):
            values = totals[label]
            rows.append([
                _string(label),
                _formula(f'=COUNTIFS(\'清洗明细\'!${field_column}$2:${field_column}$21,A{row_number},\'清洗明细\'!$L$2:$L$21,"有效")', int(values[0]), "integer"),
                _formula(f'=SUMIFS(\'清洗明细\'!$H$2:$H$21,\'清洗明细\'!${field_column}$2:${field_column}$21,A{row_number},\'清洗明细\'!$L$2:$L$21,"有效")', int(values[1]), "integer"),
                _formula(f'=SUMIFS(\'清洗明细\'!$N$2:$N$21,\'清洗明细\'!${field_column}$2:${field_column}$21,A{row_number},\'清洗明细\'!$L$2:$L$21,"有效")', float(values[2]), "money"),
            ])
        total_row = len(labels) + 2
        last_data_row = total_row - 1
        rows.append([
            _string("合计", "header"),
            _formula(f"=SUM(B2:B{last_data_row})", sum(int(totals[label][0]) for label in labels), "integer"),
            _formula(f"=SUM(C2:C{last_data_row})", sum(int(totals[label][1]) for label in labels), "integer"),
            _formula(f"=SUM(D2:D{last_data_row})", float(sum((totals[label][2] for label in labels), Decimal(0))), "money"),
        ])
        return rows

    region_rows = summary_rows(REGIONS, region_totals, "C")
    category_rows = summary_rows(CATEGORIES, category_totals, "G")
    total_orders = int(region_rows[-1][1]["value"])
    total_quantity = int(region_rows[-1][2]["value"])
    total_net = float(region_rows[-1][3]["value"])
    dashboard_rows = [
        [_string("2026 年第二季度销售仪表盘", "title")],
        [_string("指标", "header"), _string("数值", "header")],
        [_string("有效订单数", "kpi_label"), _formula("='区域汇总'!B6", total_orders, "integer")],
        [_string("销售数量", "kpi_label"), _formula("='区域汇总'!C6", total_quantity, "integer")],
        [_string("净销售额", "kpi_label"), _formula("='区域汇总'!D6", total_net, "money")],
    ]
    return {
        "sheets": [
            {"name": "清洗明细", "rows": detail_rows, "freeze_panes": "A2", "auto_filter": "A1:N21", "column_widths": [14, 13, 10, 10, 12, 16, 12, 10, 12, 12, 12, 10, 18, 14]},
            {"name": "区域汇总", "rows": region_rows, "freeze_panes": "A2", "auto_filter": "A1:D6", "column_widths": [14, 14, 14, 16]},
            {"name": "品类汇总", "rows": category_rows, "freeze_panes": "A2", "auto_filter": "A1:D5", "column_widths": [14, 14, 14, 16]},
            {"name": "异常清单", "rows": anomaly_rows, "freeze_panes": "A2", "auto_filter": f"A1:C{len(anomaly_rows)}", "column_widths": [12, 14, 22]},
            {"name": "仪表盘", "rows": dashboard_rows, "column_widths": [18, 18]},
        ],
        "charts": [{
            "sheet": "仪表盘",
            "type": "column",
            "title": "区域净销售额",
            "series_name_ref": "'区域汇总'!$D$1",
            "category_ref": "'区域汇总'!$A$2:$A$5",
            "value_ref": "'区域汇总'!$D$2:$D$5",
        }],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    workspace = args.workspace.resolve(strict=True)
    output = args.output.resolve(strict=False) if args.output else workspace / "output" / "sales_analysis.xlsx"
    output.parent.mkdir(parents=True, exist_ok=True)
    writer = _load_writer()
    writer.write_workbook(build_spec(workspace), output)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
