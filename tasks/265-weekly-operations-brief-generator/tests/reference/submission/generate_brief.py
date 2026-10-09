#!/usr/bin/env python3
"""参考求解：把运营 CSV 转换为结构化摘要和中文周简报。

该实现只供环境测试使用，不会挂载给候选 Agent。
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, NoReturn


FIELDS = (
    "date",
    "channel",
    "visits",
    "orders",
    "paid_orders",
    "revenue_cents",
    "refund_cents",
    "tickets_opened",
    "tickets_resolved",
)
NUMERIC_FIELDS = FIELDS[2:]
CENT = Decimal("0.01")


def fail(message: str) -> NoReturn:
    raise ValueError(message)


def parse_day(value: str, field: str) -> date:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None:
        raise ValueError(f"{field} 必须是 YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} 必须是 YYYY-MM-DD") from exc


def load_definitions(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != "weekly_operations_metric_definitions_v1":
        fail("指标口径版本不受支持")
    if value.get("rounding") != {"mode": "ROUND_HALF_UP", "decimal_places": 2}:
        fail("舍入口径不受支持")
    channels = value.get("channels")
    if not isinstance(channels, list) or not channels or any(not isinstance(item, str) or not item for item in channels):
        fail("渠道列表无效")
    if len(set(channels)) != len(channels):
        fail("渠道列表重复")
    current = value.get("current_period")
    comparison = value.get("comparison_period")
    if not isinstance(current, dict) or not isinstance(comparison, dict):
        fail("周期定义缺失")
    current_start = parse_day(str(current.get("start", "")), "current_period.start")
    current_end = parse_day(str(current.get("end", "")), "current_period.end")
    comparison_start = parse_day(str(comparison.get("start", "")), "comparison_period.start")
    comparison_end = parse_day(str(comparison.get("end", "")), "comparison_period.end")
    if current_start > current_end or comparison_start > comparison_end or comparison_end >= current_start:
        fail("周期顺序无效")
    rules = value.get("risk_rules")
    if not isinstance(rules, list) or not rules:
        fail("风险规则缺失")
    return value


def load_rows(path: Path, definitions: dict[str, Any]) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != FIELDS:
            fail("CSV 列必须与口径完全一致")
        raw_rows = list(reader)
    if not raw_rows:
        fail("CSV 不得为空")
    channels = set(definitions["channels"])
    current_start = parse_day(definitions["current_period"]["start"], "current_period.start")
    current_end = parse_day(definitions["current_period"]["end"], "current_period.end")
    comparison_start = parse_day(definitions["comparison_period"]["start"], "comparison_period.start")
    comparison_end = parse_day(definitions["comparison_period"]["end"], "comparison_period.end")
    rows: list[dict[str, Any]] = []
    keys: set[tuple[str, str]] = set()
    coverage: dict[str, set[str]] = defaultdict(set)
    for index, raw in enumerate(raw_rows, start=2):
        if None in raw or set(raw) != set(FIELDS) or any(raw[field] is None for field in FIELDS):
            fail(f"第 {index} 行单元格数量必须与表头完全一致")
        day = parse_day(raw["date"], f"第 {index} 行 date")
        if not (comparison_start <= day <= comparison_end or current_start <= day <= current_end):
            fail(f"第 {index} 行日期不在两个周期内")
        channel = raw["channel"]
        if channel not in channels:
            fail(f"第 {index} 行渠道不在口径中")
        key = (raw["date"], channel)
        if key in keys:
            fail(f"第 {index} 行日期与渠道重复")
        keys.add(key)
        coverage[raw["date"]].add(channel)
        parsed: dict[str, Any] = {"date": raw["date"], "channel": channel}
        for field in NUMERIC_FIELDS:
            text = raw[field]
            if not text.isascii() or not text.isdigit():
                fail(f"第 {index} 行 {field} 必须是非负整数")
            parsed[field] = int(text)
        if not parsed["paid_orders"] <= parsed["orders"] <= parsed["visits"]:
            fail(f"第 {index} 行订单逻辑无效")
        if parsed["refund_cents"] > parsed["revenue_cents"]:
            fail(f"第 {index} 行退款超过收入")
        if parsed["tickets_resolved"] > parsed["tickets_opened"]:
            fail(f"第 {index} 行解决工单超过新增工单")
        rows.append(parsed)
    expected_channels = set(definitions["channels"])
    if any(value != expected_channels for value in coverage.values()):
        fail("每个有数据的日期必须覆盖全部渠道且各一行")
    if not any(current_start <= parse_day(row["date"], "date") <= current_end for row in rows):
        fail("当期无数据")
    if not any(comparison_start <= parse_day(row["date"], "date") <= comparison_end for row in rows):
        fail("对比期无数据")
    return rows


def add_rows(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {field: sum(int(row[field]) for row in rows) for field in NUMERIC_FIELDS}


def q2(value: Decimal) -> str:
    return str(value.quantize(CENT, rounding=ROUND_HALF_UP))


def pct(numerator: int, denominator: int) -> str:
    if denominator == 0:
        fail("百分比分母不得为零")
    return q2(Decimal(numerator) * Decimal(100) / Decimal(denominator))


def change_pct(current: int, previous: int) -> str:
    if previous == 0:
        fail("环比基期不得为零")
    return q2((Decimal(current) - Decimal(previous)) * Decimal(100) / Decimal(previous))


def money(cents: int) -> str:
    return q2(Decimal(cents) / Decimal(100))


def period_rows(rows: list[dict[str, Any]], start: date, end: date) -> list[dict[str, Any]]:
    return [row for row in rows if start <= parse_day(row["date"], "date") <= end]


def make_summary(rows: list[dict[str, Any]], definitions: dict[str, Any]) -> dict[str, Any]:
    current_start = parse_day(definitions["current_period"]["start"], "current_period.start")
    current_end = parse_day(definitions["current_period"]["end"], "current_period.end")
    previous_start = parse_day(definitions["comparison_period"]["start"], "comparison_period.start")
    previous_end = parse_day(definitions["comparison_period"]["end"], "comparison_period.end")
    current_rows = period_rows(rows, current_start, current_end)
    previous_rows = period_rows(rows, previous_start, previous_end)
    current = add_rows(current_rows)
    previous = add_rows(previous_rows)
    current_net = current["revenue_cents"] - current["refund_cents"]
    previous_net = previous["revenue_cents"] - previous["refund_cents"]
    current_conversion = Decimal(current["paid_orders"]) * Decimal(100) / Decimal(current["visits"])
    previous_conversion = Decimal(previous["paid_orders"]) * Decimal(100) / Decimal(previous["visits"])
    rates = {
        "payment_conversion_pct": q2(current_conversion),
        "refund_rate_pct": pct(current["refund_cents"], current["revenue_cents"]),
        "ticket_resolution_pct": pct(current["tickets_resolved"], current["tickets_opened"]),
    }
    wow = {
        "visits_pct": change_pct(current["visits"], previous["visits"]),
        "paid_orders_pct": change_pct(current["paid_orders"], previous["paid_orders"]),
        "gross_revenue_pct": change_pct(current["revenue_cents"], previous["revenue_cents"]),
        "net_revenue_pct": change_pct(current_net, previous_net),
        "payment_conversion_pp": q2(current_conversion - previous_conversion),
    }
    daily: list[dict[str, Any]] = []
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in current_rows:
        by_day[row["date"]].append(row)
    for day in sorted(by_day):
        total = add_rows(by_day[day])
        daily.append(
            {
                "date": day,
                "visits": total["visits"],
                "paid_orders": total["paid_orders"],
                "net_revenue_yuan": money(total["revenue_cents"] - total["refund_cents"]),
            }
        )
    channels: list[dict[str, Any]] = []
    by_channel: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in current_rows:
        by_channel[row["channel"]].append(row)
    for channel in sorted(by_channel):
        total = add_rows(by_channel[channel])
        channels.append(
            {
                "channel": channel,
                "visits": total["visits"],
                "paid_orders": total["paid_orders"],
                "net_revenue_yuan": money(total["revenue_cents"] - total["refund_cents"]),
                "payment_conversion_pct": pct(total["paid_orders"], total["visits"]),
                "refund_rate_pct": pct(total["refund_cents"], total["revenue_cents"]),
            }
        )
    metric_values = {
        "payment_conversion_pp": Decimal(wow["payment_conversion_pp"]),
        "refund_rate_pct": Decimal(rates["refund_rate_pct"]),
        "ticket_resolution_pct": Decimal(rates["ticket_resolution_pct"]),
    }
    risks: list[dict[str, str]] = []
    for rule in definitions["risk_rules"]:
        metric = str(rule["metric"])
        actual = metric_values[metric]
        threshold = Decimal(str(rule["threshold"]))
        operator = rule["operator"]
        triggered = (operator == "lte" and actual <= threshold) or (operator == "lt" and actual < threshold) or (operator == "gt" and actual > threshold)
        if operator not in {"lte", "lt", "gt"}:
            fail("风险运算符不受支持")
        if triggered:
            risks.append(
                {
                    "risk_id": str(rule["risk_id"]),
                    "severity": str(rule["severity"]),
                    "label": str(rule["label"]),
                    "evidence": f"{metric}={q2(actual)}，阈值{operator}{q2(threshold)}",
                    "recommended_action": str(rule["recommended_action"]),
                }
            )
    top_channel = sorted(channels, key=lambda item: (-Decimal(item["net_revenue_yuan"]), item["channel"]))[0]["channel"]
    busiest_day = sorted(daily, key=lambda item: (-item["visits"], item["date"]))[0]["date"]
    return {
        "schema_version": "weekly_operations_summary_v1",
        "reporting_period": {
            "current_start": current_start.isoformat(),
            "current_end": current_end.isoformat(),
            "comparison_start": previous_start.isoformat(),
            "comparison_end": previous_end.isoformat(),
            "timezone": definitions["timezone"],
        },
        "totals": {
            "visits": current["visits"],
            "orders": current["orders"],
            "paid_orders": current["paid_orders"],
            "gross_revenue_yuan": money(current["revenue_cents"]),
            "refund_yuan": money(current["refund_cents"]),
            "net_revenue_yuan": money(current_net),
            "tickets_opened": current["tickets_opened"],
            "tickets_resolved": current["tickets_resolved"],
        },
        "rates": rates,
        "week_over_week": wow,
        "highlights": {
            "top_channel_by_net_revenue": top_channel,
            "busiest_day_by_visits": busiest_day,
        },
        "daily": daily,
        "channels": channels,
        "risks": risks,
        "data_quality": {
            "row_count": len(rows),
            "current_row_count": len(current_rows),
            "comparison_row_count": len(previous_rows),
            "duplicate_keys": 0,
            "invalid_rows": 0,
        },
    }


def signed(value: str, suffix: str) -> str:
    number = Decimal(value)
    prefix = "+" if number > 0 else ""
    return f"{prefix}{value}{suffix}"


def render_brief(summary: dict[str, Any], definitions: dict[str, Any], template: str) -> str:
    totals = summary["totals"]
    rates = summary["rates"]
    wow = summary["week_over_week"]
    core_metrics = "\n".join(
        [
            f"- 访问量：{totals['visits']}",
            f"- 支付订单：{totals['paid_orders']}",
            f"- 总收入：¥{totals['gross_revenue_yuan']}",
            f"- 净收入：¥{totals['net_revenue_yuan']}",
            f"- 支付转化率：{rates['payment_conversion_pct']}%",
            f"- 退款率：{rates['refund_rate_pct']}%",
            f"- 工单解决率：{rates['ticket_resolution_pct']}%",
        ]
    )
    week_over_week = "\n".join(
        [
            f"- 访问量：{signed(wow['visits_pct'], '%')}",
            f"- 支付订单：{signed(wow['paid_orders_pct'], '%')}",
            f"- 总收入：{signed(wow['gross_revenue_pct'], '%')}",
            f"- 净收入：{signed(wow['net_revenue_pct'], '%')}",
            f"- 支付转化率：{signed(wow['payment_conversion_pp'], ' 个百分点')}",
        ]
    )
    channel_lines = ["| 渠道 | 访问量 | 支付订单 | 净收入 | 转化率 | 退款率 |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for item in summary["channels"]:
        channel_lines.append(f"| {item['channel']} | {item['visits']} | {item['paid_orders']} | ¥{item['net_revenue_yuan']} | {item['payment_conversion_pct']}% | {item['refund_rate_pct']}% |")
    daily_lines = ["| 日期 | 访问量 | 支付订单 | 净收入 |", "| --- | ---: | ---: | ---: |"]
    for item in summary["daily"]:
        daily_lines.append(f"| {item['date']} | {item['visits']} | {item['paid_orders']} | ¥{item['net_revenue_yuan']} |")
    if summary["risks"]:
        risk_lines = [f"{index}. **{item['label']}**（{item['severity']}）：{item['evidence']}。" for index, item in enumerate(summary["risks"], start=1)]
        action_lines = [f"{index}. {item['recommended_action']}" for index, item in enumerate(summary["risks"], start=1)]
    else:
        risk_lines = ["本周未触发预设风险规则。"]
        action_lines = ["继续按现有口径跟踪核心指标。"]
    quality = summary["data_quality"]
    replacements = {
        "{{title}}": definitions["title"],
        "{{period_line}}": f"本期 {summary['reporting_period']['current_start']} 至 {summary['reporting_period']['current_end']}；对比 {summary['reporting_period']['comparison_start']} 至 {summary['reporting_period']['comparison_end']}；时区 {summary['reporting_period']['timezone']}。",
        "{{core_metrics}}": core_metrics,
        "{{week_over_week}}": week_over_week,
        "{{channel_table}}": "\n".join(channel_lines),
        "{{daily_table}}": "\n".join(daily_lines),
        "{{risks}}": "\n".join(risk_lines),
        "{{actions}}": "\n".join(action_lines),
        "{{data_quality}}": f"已校验 {quality['row_count']} 行；当期 {quality['current_row_count']} 行，对比期 {quality['comparison_row_count']} 行；重复键 {quality['duplicate_keys']} 个，无效行 {quality['invalid_rows']} 行。",
    }
    result = template
    for marker, value in replacements.items():
        if marker not in result:
            fail(f"模板缺少占位符 {marker}")
        result = result.replace(marker, value)
    if "{{" in result or "}}" in result:
        fail("模板仍有未解析占位符")
    return result.rstrip() + "\n"


def atomic_outputs(output_dir: Path, summary_bytes: bytes, brief_bytes: bytes) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    if output_dir.is_symlink() or not output_dir.is_dir():
        fail("输出目录无效")
    staged = [output_dir / ".summary.json.next", output_dir / ".weekly_brief.md.next"]
    final = [output_dir / "summary.json", output_dir / "weekly_brief.md"]
    for path in staged:
        if path.exists() or path.is_symlink():
            fail("存在未处理的上次临时产物")
    try:
        staged[0].write_bytes(summary_bytes)
        staged[1].write_bytes(brief_bytes)
        os.replace(staged[0], final[0])
        os.replace(staged[1], final[1])
    finally:
        for path in staged:
            path.unlink(missing_ok=True)


def run(args: argparse.Namespace) -> None:
    definitions = load_definitions(args.definitions)
    rows = load_rows(args.input_csv, definitions)
    template = args.template.read_text(encoding="utf-8")
    summary = make_summary(rows, definitions)
    brief = render_brief(summary, definitions, template)
    summary_bytes = (json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    atomic_outputs(args.output_dir, summary_bytes, brief.encode("utf-8"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-csv", type=Path, required=True)
    parser.add_argument("--definitions", type=Path, required=True)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    try:
        run(parse_args())
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        print(f"生成失败：{exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
