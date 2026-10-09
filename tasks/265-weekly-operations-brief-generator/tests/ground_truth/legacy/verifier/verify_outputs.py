#!/usr/bin/env python3
"""终态验收器：独立复算全部指标并验证 workspace 终态。

该程序只解析候选产物，不 import、exec 或 subprocess 调用候选代码。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import stat
import sys
import unicodedata
from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any


REQUIRED_COLUMNS = [
    "date",
    "channel",
    "visits",
    "orders",
    "paid_orders",
    "revenue_cents",
    "refund_cents",
    "tickets_opened",
    "tickets_resolved",
]
NUMBER_COLUMNS = REQUIRED_COLUMNS[2:]
EXACT_DIRECTORIES = {"input", "output", "submission"}
EXACT_FILES = {
    "input/brief_template.md",
    "input/metric_definitions.json",
    "input/weekly_operations.csv",
    "output/summary.json",
    "output/weekly_brief.md",
    "submission/generate_brief.py",
}
EXACT_INPUTS = {
    "input/brief_template.md",
    "input/metric_definitions.json",
    "input/weekly_operations.csv",
}
REQUIRED_PLACEHOLDERS = {
    "{{title}}",
    "{{period_line}}",
    "{{core_metrics}}",
    "{{week_over_week}}",
    "{{channel_table}}",
    "{{daily_table}}",
    "{{risks}}",
    "{{actions}}",
    "{{data_quality}}",
}
MINUS_TRANSLATION = str.maketrans(
    {
        "−": "-",
        "‐": "-",
        "‑": "-",
        "‒": "-",
        "–": "-",
        "—": "-",
        "﹘": "-",
        "﹣": "-",
        "－": "-",
    }
)


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def tree_inventory(root: Path) -> tuple[set[str], set[str], bool]:
    files: set[str] = set()
    directories: set[str] = set()
    has_symlink = root.is_symlink()
    for current, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        for name in list(dirnames):
            path = current_path / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                has_symlink = True
                dirnames.remove(name)
            else:
                directories.add(relative)
        for name in filenames:
            path = current_path / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                has_symlink = True
            files.add(relative)
    return files, directories, has_symlink


def tree_hash(root: Path, files: set[str]) -> str:
    digest = hashlib.sha256()
    for relative in sorted(files):
        path = root / relative
        digest.update(relative.encode("utf-8") + b"\0")
        if path.is_file() and not path.is_symlink():
            digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def d(value: Any) -> Decimal:
    return Decimal(str(value))


def two(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def percentage(numerator: int, denominator: int) -> str:
    if denominator == 0:
        raise ValueError("指标分母为零")
    return two(d(numerator) * d(100) / d(denominator))


def delta(current: int, prior: int) -> str:
    if prior == 0:
        raise ValueError("基期指标为零")
    return two((d(current) - d(prior)) * d(100) / d(prior))


def yuan(cents: int) -> str:
    return two(d(cents) / d(100))


def parse_date(text: Any) -> date:
    if not isinstance(text, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", text) is None:
        raise ValueError("日期必须是 YYYY-MM-DD")
    return date.fromisoformat(text)


def parse_source(workspace: Path) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    definitions = json.loads((workspace / "input/metric_definitions.json").read_text(encoding="utf-8"))
    if not isinstance(definitions, dict) or definitions.get("schema_version") != "weekly_operations_metric_definitions_v1":
        raise ValueError("指标定义不受支持")
    channels = definitions.get("channels")
    if not isinstance(channels, list) or not channels or sorted(set(channels)) != sorted(channels):
        raise ValueError("渠道必须是非空唯一列表")
    rounding = definitions.get("rounding")
    if rounding != {"mode": "ROUND_HALF_UP", "decimal_places": 2}:
        raise ValueError("舍入口径不受支持")
    if not isinstance(definitions.get("input_contract"), dict):
        raise ValueError("缺少公开输入合同")
    if not isinstance(definitions.get("summary_contract"), dict):
        raise ValueError("缺少公开摘要合同")
    brief_contract = definitions.get("brief_contract")
    if not isinstance(brief_contract, dict) or not isinstance(brief_contract.get("required_sections"), list):
        raise ValueError("缺少公开简报合同")
    current_start = parse_date(definitions["current_period"]["start"])
    current_end = parse_date(definitions["current_period"]["end"])
    previous_start = parse_date(definitions["comparison_period"]["start"])
    previous_end = parse_date(definitions["comparison_period"]["end"])
    if previous_start > previous_end or current_start > current_end or previous_end >= current_start:
        raise ValueError("周期定义无效")
    rows: list[dict[str, Any]] = []
    keys: set[tuple[str, str]] = set()
    coverage: dict[str, set[str]] = defaultdict(set)
    with (workspace / "input/weekly_operations.csv").open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != REQUIRED_COLUMNS:
            raise ValueError("CSV 列无效")
        for line_number, raw in enumerate(reader, start=2):
            if None in raw or set(raw) != set(REQUIRED_COLUMNS) or any(raw[field] is None for field in REQUIRED_COLUMNS):
                raise ValueError(f"第 {line_number} 行单元格数量无效")
            day = parse_date(raw["date"])
            channel = raw["channel"]
            if channel not in channels or not (previous_start <= day <= previous_end or current_start <= day <= current_end):
                raise ValueError(f"第 {line_number} 行维度无效")
            key = (raw["date"], channel)
            if key in keys:
                raise ValueError(f"第 {line_number} 行重复")
            keys.add(key)
            coverage[raw["date"]].add(channel)
            row: dict[str, Any] = {"date": raw["date"], "channel": channel}
            for field in NUMBER_COLUMNS:
                value = raw[field]
                if not value.isascii() or not value.isdigit():
                    raise ValueError(f"第 {line_number} 行数值无效")
                row[field] = int(value)
            if not row["paid_orders"] <= row["orders"] <= row["visits"]:
                raise ValueError("订单约束无效")
            if row["refund_cents"] > row["revenue_cents"] or row["tickets_resolved"] > row["tickets_opened"]:
                raise ValueError("业务约束无效")
            rows.append(row)
    if not rows or any(value != set(channels) for value in coverage.values()):
        raise ValueError("行覆盖无效")
    template = (workspace / "input/brief_template.md").read_text(encoding="utf-8")
    if any(template.count(marker) != 1 for marker in REQUIRED_PLACEHOLDERS):
        raise ValueError("模板占位符合同无效")
    unknown_markers = set(re.findall(r"\{\{[^{}]+\}\}", template)) - REQUIRED_PLACEHOLDERS
    if unknown_markers:
        raise ValueError("模板含未声明占位符")
    return definitions, rows, template


def sum_fields(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {field: sum(row[field] for row in rows) for field in NUMBER_COLUMNS}


def calculate(definitions: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    current_start = parse_date(definitions["current_period"]["start"])
    current_end = parse_date(definitions["current_period"]["end"])
    previous_start = parse_date(definitions["comparison_period"]["start"])
    previous_end = parse_date(definitions["comparison_period"]["end"])
    current_rows = [row for row in rows if current_start <= parse_date(row["date"]) <= current_end]
    previous_rows = [row for row in rows if previous_start <= parse_date(row["date"]) <= previous_end]
    if not current_rows or not previous_rows:
        raise ValueError("周期数据不完整")
    current = sum_fields(current_rows)
    previous = sum_fields(previous_rows)
    current_net = current["revenue_cents"] - current["refund_cents"]
    previous_net = previous["revenue_cents"] - previous["refund_cents"]
    current_conversion = d(current["paid_orders"]) * d(100) / d(current["visits"])
    previous_conversion = d(previous["paid_orders"]) * d(100) / d(previous["visits"])
    rates = {
        "payment_conversion_pct": two(current_conversion),
        "refund_rate_pct": percentage(current["refund_cents"], current["revenue_cents"]),
        "ticket_resolution_pct": percentage(current["tickets_resolved"], current["tickets_opened"]),
    }
    wow = {
        "visits_pct": delta(current["visits"], previous["visits"]),
        "paid_orders_pct": delta(current["paid_orders"], previous["paid_orders"]),
        "gross_revenue_pct": delta(current["revenue_cents"], previous["revenue_cents"]),
        "net_revenue_pct": delta(current_net, previous_net),
        "payment_conversion_pp": two(current_conversion - previous_conversion),
    }
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_channel: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in current_rows:
        by_day[row["date"]].append(row)
        by_channel[row["channel"]].append(row)
    daily = []
    for day in sorted(by_day):
        total = sum_fields(by_day[day])
        daily.append({"date": day, "visits": total["visits"], "paid_orders": total["paid_orders"], "net_revenue_yuan": yuan(total["revenue_cents"] - total["refund_cents"])})
    channel_metrics = []
    for channel in sorted(by_channel):
        total = sum_fields(by_channel[channel])
        channel_metrics.append({
            "channel": channel,
            "visits": total["visits"],
            "paid_orders": total["paid_orders"],
            "net_revenue_yuan": yuan(total["revenue_cents"] - total["refund_cents"]),
            "payment_conversion_pct": percentage(total["paid_orders"], total["visits"]),
            "refund_rate_pct": percentage(total["refund_cents"], total["revenue_cents"]),
        })
    actuals = {
        "payment_conversion_pp": d(wow["payment_conversion_pp"]),
        "refund_rate_pct": d(rates["refund_rate_pct"]),
        "ticket_resolution_pct": d(rates["ticket_resolution_pct"]),
    }
    risks = []
    for rule in definitions["risk_rules"]:
        actual = actuals[rule["metric"]]
        threshold = d(rule["threshold"])
        operation = rule["operator"]
        match = {"lte": actual <= threshold, "lt": actual < threshold, "gt": actual > threshold}.get(operation)
        if match is None:
            raise ValueError("未知风险运算符")
        if match:
            risks.append({
                "risk_id": rule["risk_id"],
                "severity": rule["severity"],
                "label": rule["label"],
                "evidence": f"{rule['metric']}={two(actual)}，阈值{operation}{two(threshold)}",
                "recommended_action": rule["recommended_action"],
            })
    top_channel = min(channel_metrics, key=lambda item: (-d(item["net_revenue_yuan"]), item["channel"]))["channel"]
    busiest_day = min(daily, key=lambda item: (-item["visits"], item["date"]))["date"]
    return {
        "schema_version": "weekly_operations_summary_v1",
        "reporting_period": {
            "current_start": current_start.isoformat(), "current_end": current_end.isoformat(),
            "comparison_start": previous_start.isoformat(), "comparison_end": previous_end.isoformat(),
            "timezone": definitions["timezone"],
        },
        "totals": {
            "visits": current["visits"], "orders": current["orders"], "paid_orders": current["paid_orders"],
            "gross_revenue_yuan": yuan(current["revenue_cents"]), "refund_yuan": yuan(current["refund_cents"]),
            "net_revenue_yuan": yuan(current_net), "tickets_opened": current["tickets_opened"],
            "tickets_resolved": current["tickets_resolved"],
        },
        "rates": rates,
        "week_over_week": wow,
        "highlights": {"top_channel_by_net_revenue": top_channel, "busiest_day_by_visits": busiest_day},
        "daily": daily,
        "channels": channel_metrics,
        "risks": risks,
        "data_quality": {
            "row_count": len(rows), "current_row_count": len(current_rows),
            "comparison_row_count": len(previous_rows), "duplicate_keys": 0, "invalid_rows": 0,
        },
    }


def json_semantic_equal(actual: Any, expected: Any) -> bool:
    """比较 JSON 值和类型，不比较对象键顺序或文本排版。"""

    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return set(actual) == set(expected) and all(
            json_semantic_equal(actual[key], expected[key]) for key in expected
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            json_semantic_equal(left, right) for left, right in zip(actual, expected)
        )
    return actual == expected


def parse_json_without_duplicate_keys(data: bytes) -> Any:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("JSON 含重复键")
            result[key] = value
        return result

    return json.loads(data.decode("utf-8"), object_pairs_hook=unique_object)


def normalize_text(text: Any) -> str:
    value = unicodedata.normalize("NFKC", str(text)).casefold()
    value = value.translate(MINUS_TRANSLATION)
    value = value.replace("¥负", "¥-").replace("人民币负", "人民币-").replace("cny负", "cny-")
    value = re.sub(r"负\s*(?=(?:¥|cny|人民币)?\s*\d)", "-", value)
    value = value.replace("￥", "¥").replace(",", "")
    value = re.sub(r"[`*_~]", "", value)
    return re.sub(r"\s+", " ", value).strip()


def path_value(value: dict[str, Any], path: str) -> Any:
    current: Any = value
    for item in path.split("."):
        if not isinstance(current, dict) or item not in current:
            raise KeyError(path)
        current = current[item]
    return current


def number_present(text: str, expected: Any, presentation: str) -> bool:
    normalized = normalize_text(text)
    value = str(expected)
    prefix = "" if value.startswith("-") else r"\+?"
    number = rf"(?<![\d.+-]){prefix}{re.escape(value)}(?![\d.])"
    if presentation == "integer":
        return re.search(number, normalized) is not None
    if presentation == "money":
        magnitude = re.escape(value.removeprefix("-"))
        if value.startswith("-"):
            money = rf"(?<![\d.+-])(?:-(?:¥|cny|人民币)\s*{magnitude}|(?:¥|cny|人民币)\s*-{magnitude}|-{magnitude}\s*元)(?![\d.])"
        else:
            money = rf"(?<![\d.+-])(?:\+?(?:¥|cny|人民币)\s*{magnitude}|(?:¥|cny|人民币)\s*\+?{magnitude}|\+?{magnitude}\s*元)(?![\d.])"
        return re.search(money, normalized) is not None
    if presentation == "percent":
        return re.search(rf"{number}\s*%", normalized) is not None
    if presentation == "percentage_point":
        return re.search(rf"{number}\s*(?:个)?百分点", normalized) is not None
    if presentation in {"text", "date"}:
        return normalize_text(expected) in normalized
    raise ValueError("未知展示类型")


def content_lines(section: str) -> list[str]:
    return [line.strip() for line in section.splitlines() if line.strip()]


def line_payload(line: str) -> str:
    normalized = normalize_text(line)
    return re.sub(r"^(?:[-*+]|\d+[.)、])\s*", "", normalized).strip()


def numeric_tokens(text: str) -> list[Decimal]:
    values = re.findall(r"(?<![\d.])[+-]?\d+(?:\.\d+)?(?![\d.])", line_payload(text))
    return [Decimal(item) for item in values]


def exact_labeled_value_line(line: str, aliases: list[str], expected: Any, presentation: str) -> bool:
    payload = line_payload(line).rstrip("。. ")
    if payload.count(":") != 1:
        return False
    label, value = (item.strip() for item in payload.split(":", 1))
    return any(label == normalize_text(alias) for alias in aliases) and table_cell_equal(value, expected, presentation)


def exact_metric_section(section: str, specs: tuple[tuple[str, str, str], ...], labels: dict[str, list[str]], summary: dict[str, Any]) -> bool:
    lines = content_lines(section)
    if len(lines) != len(specs):
        return False
    unmatched = set(range(len(lines)))
    for path, label, presentation in specs:
        expected = path_value(summary, path)
        matches = [
            index
            for index in unmatched
            if exact_labeled_value_line(lines[index], labels[label], expected, presentation)
        ]
        if len(matches) != 1:
            return False
        unmatched.remove(matches[0])
    return not unmatched


def markdown_sections(markdown: str, required: Any) -> dict[str, str]:
    if not isinstance(required, list):
        raise ValueError("简报章节合同无效")
    parsed: list[tuple[str, list[str]]] = []
    current_heading: str | None = None
    current_lines: list[str] = []
    for line in markdown.splitlines():
        match = re.match(r"^\s*##(?!#)\s+(.+?)\s*$", line)
        if match:
            if current_heading is not None:
                parsed.append((current_heading, current_lines))
            current_heading = match.group(1)
            current_lines = []
        elif current_heading is not None:
            current_lines.append(line)
    if current_heading is not None:
        parsed.append((current_heading, current_lines))
    item_by_id: dict[str, dict[str, Any]] = {}
    expected_order: list[str] = []
    for item in required:
        if not isinstance(item, dict):
            raise ValueError("简报章节合同无效")
        section_id = item.get("section_id")
        aliases = item.get("heading_aliases")
        if not isinstance(section_id, str) or not isinstance(aliases, list) or not aliases:
            raise ValueError("简报章节合同无效")
        item_by_id[section_id] = item
        expected_order.append(section_id)
    if len(parsed) != len(item_by_id):
        return {}
    result: dict[str, str] = {}
    observed_order: list[str] = []
    for heading, lines in parsed:
        heading_value = normalize_text(heading)
        heading_value = re.sub(r"^(?:第)?(?:[一二三四五六七八九十]+|\d+)[、.:：\s]+", "", heading_value)
        matches = [
            section_id
            for section_id, item in item_by_id.items()
            if any(heading_value == normalize_text(alias) for alias in item["heading_aliases"])
        ]
        if len(matches) != 1 or matches[0] in result:
            return {}
        result[matches[0]] = "\n".join(lines)
        observed_order.append(matches[0])
    return result if observed_order == expected_order else {}


def markdown_table(section: str) -> tuple[list[list[str]], bool, bool]:
    rows: list[list[str]] = []
    separator = False
    clean = True
    for line in section.splitlines():
        if line.strip() and line.count("|") < 2:
            clean = False
            continue
        if line.count("|") < 2:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells and all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells):
            separator = True
            continue
        rows.append(cells)
    return rows, separator, clean


def table_cell_equal(cell: str, expected: Any, presentation: str) -> bool:
    normalized = normalize_text(cell)
    value = str(expected)
    sign = "" if value.startswith("-") else r"\+?"
    exact = rf"{sign}{re.escape(value)}"
    if presentation == "integer":
        return re.fullmatch(exact, normalized) is not None
    if presentation == "money":
        return re.fullmatch(rf"(?:(?:¥|cny|人民币)\s*{exact}|{exact}\s*元)", normalized) is not None
    if presentation == "percent":
        return re.fullmatch(rf"{exact}\s*%", normalized) is not None
    if presentation == "percentage_point":
        return re.fullmatch(rf"{exact}\s*(?:个)?百分点", normalized) is not None
    if presentation in {"text", "date"}:
        return normalized == normalize_text(expected)
    raise ValueError("未知表格展示类型")


def perfect_row_match(actual_rows: list[list[str]], expected_rows: list[dict[str, Any]], columns: list[tuple[str, str]], positions: dict[str, int]) -> bool:
    compatibility: list[list[int]] = []
    for expected in expected_rows:
        matches = []
        for index, row in enumerate(actual_rows):
            if all(table_cell_equal(row[positions[field]], expected[field], presentation) for field, presentation in columns):
                matches.append(index)
        compatibility.append(matches)
    order = sorted(range(len(expected_rows)), key=lambda index: len(compatibility[index]))

    def assign(offset: int, used: set[int]) -> bool:
        if offset == len(order):
            return True
        expected_index = order[offset]
        return any(
            actual_index not in used and assign(offset + 1, used | {actual_index})
            for actual_index in compatibility[expected_index]
        )

    return all(compatibility) and assign(0, set())


def table_semantic(
    section: str,
    expected_rows: list[dict[str, Any]],
    columns: list[tuple[str, str]],
    header_aliases: dict[str, list[str]],
) -> bool:
    lines = content_lines(section)
    if len(lines) != len(expected_rows) + 2 or any(line.count("|") < 2 for line in lines):
        return False
    rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in lines]
    if any(len(row) != len(columns) for row in rows):
        return False
    header, separator, *actual_rows = rows
    if not all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in separator):
        return False
    positions: dict[str, int] = {}
    for field, _ in columns:
        matches = [
            index
            for index, cell in enumerate(header)
            if any(normalize_text(cell) == normalize_text(alias) for alias in header_aliases[field])
        ]
        if len(matches) != 1:
            return False
        positions[field] = matches[0]
    if len(set(positions.values())) != len(columns):
        return False
    return perfect_row_match(actual_rows, expected_rows, columns, positions)


def format_contract_line(pattern: str, values: dict[str, Any]) -> str:
    try:
        return pattern.format(**{key: str(value) for key, value in values.items()})
    except (KeyError, ValueError) as exc:
        raise ValueError("公开句式合同无效") from exc


def exact_contract_lines(section: str, expected: list[str]) -> bool:
    return [line_payload(line) for line in content_lines(section)] == [normalize_text(line) for line in expected]


def strip_static_suffix(markdown: str, template: str) -> str | None:
    if template.count("{{data_quality}}") != 1:
        return None
    suffix = template.split("{{data_quality}}", 1)[1].rstrip()
    candidate = markdown.rstrip()
    if suffix:
        if not candidate.endswith(suffix):
            return None
        candidate = candidate[: -len(suffix)].rstrip()
    return candidate + "\n"


def preamble_semantic(markdown: str, template: str, definitions: dict[str, Any], summary: dict[str, Any]) -> bool:
    first_h2 = re.search(r"^\s*##(?!#)\s+", markdown, flags=re.MULTILINE)
    if first_h2 is None:
        return False
    prefix = markdown[: first_h2.start()]
    expected_h1s = re.findall(r"^\s*#(?!#)\s+(.+?)\s*$", template, flags=re.MULTILINE)
    actual_h1s = re.findall(r"^\s*#(?!#)\s+(.+?)\s*$", markdown, flags=re.MULTILINE)
    if len(expected_h1s) != 1 or len(actual_h1s) != 1:
        return False
    expected_h1 = expected_h1s[0].replace("{{title}}", str(definitions["title"]))
    if normalize_text(actual_h1s[0]) != normalize_text(expected_h1):
        return False
    formats = definitions["brief_contract"].get("canonical_line_formats")
    if not isinstance(formats, dict) or not isinstance(formats.get("period"), str):
        return False
    period = summary["reporting_period"]
    expected_period = format_contract_line(
        formats["period"],
        {
            "current_start": period["current_start"],
            "current_end": period["current_end"],
            "comparison_start": period["comparison_start"],
            "comparison_end": period["comparison_end"],
            "timezone": period["timezone"],
        },
    )
    visible: list[str] = []
    in_comment = False
    for raw in prefix.splitlines():
        line = raw.strip()
        if not line:
            continue
        if in_comment:
            if "-->" in line:
                in_comment = False
            continue
        if line.startswith("<!--"):
            in_comment = "-->" not in line
            continue
        visible.append(line)
    if in_comment or len(visible) != 2:
        return False
    return (
        re.fullmatch(r"#(?!#)\s+.+", visible[0]) is not None
        and visible[1].startswith(">")
        and normalize_text(visible[1][1:]) == normalize_text(expected_period)
    )


def brief_semantic(
    brief_bytes: bytes,
    summary: dict[str, Any],
    definitions: dict[str, Any],
    template: str,
) -> tuple[bool, list[str]]:
    if not 1 <= len(brief_bytes) <= 262144:
        return False, ["brief_size"]
    markdown = brief_bytes.decode("utf-8")
    failures: list[str] = []
    if "~~" in markdown:
        failures.append("strikethrough")
    if "{{" in markdown or "}}" in markdown:
        failures.append("unresolved_placeholder")
    contract = definitions["brief_contract"]
    trimmed = strip_static_suffix(markdown, template)
    if trimmed is None:
        failures.append("static_suffix")
        return False, failures
    markdown = trimmed
    sections = markdown_sections(markdown, contract["required_sections"])
    expected_section_ids = {item["section_id"] for item in contract["required_sections"]}
    if set(sections) != expected_section_ids:
        failures.append("required_sections")
        return False, failures
    if not preamble_semantic(markdown, template, definitions, summary):
        failures.append("title_or_period")
    labels = contract["metric_labels"]
    core_specs = (
        ("totals.visits", "visits", "integer"),
        ("totals.paid_orders", "paid_orders", "integer"),
        ("totals.gross_revenue_yuan", "gross_revenue_yuan", "money"),
        ("totals.net_revenue_yuan", "net_revenue_yuan", "money"),
        ("rates.payment_conversion_pct", "payment_conversion_pct", "percent"),
        ("rates.refund_rate_pct", "refund_rate_pct", "percent"),
        ("rates.ticket_resolution_pct", "ticket_resolution_pct", "percent"),
    )
    if not exact_metric_section(sections["core_metrics"], core_specs, labels, summary):
        failures.append("core_metrics")
    wow_specs = (
        ("week_over_week.visits_pct", "visits", "percent"),
        ("week_over_week.paid_orders_pct", "paid_orders", "percent"),
        ("week_over_week.gross_revenue_pct", "gross_revenue_yuan", "percent"),
        ("week_over_week.net_revenue_pct", "net_revenue_yuan", "percent"),
        ("week_over_week.payment_conversion_pp", "payment_conversion_pct", "percentage_point"),
    )
    if not exact_metric_section(sections["week_over_week"], wow_specs, labels, summary):
        failures.append("week_over_week")
    headers = contract["table_header_aliases"]
    if not table_semantic(
        sections["channel_table"],
        summary["channels"],
        [
            ("channel", "text"),
            ("visits", "integer"),
            ("paid_orders", "integer"),
            ("net_revenue_yuan", "money"),
            ("payment_conversion_pct", "percent"),
            ("refund_rate_pct", "percent"),
        ],
        headers,
    ):
        failures.append("channel_table")
    if not table_semantic(
        sections["daily_table"],
        summary["daily"],
        [("date", "date"), ("visits", "integer"), ("paid_orders", "integer"), ("net_revenue_yuan", "money")],
        headers,
    ):
        failures.append("daily_table")
    rules = {rule["risk_id"]: rule for rule in definitions["risk_rules"]}
    risk_text = sections["risks"]
    action_text = sections["actions"]
    metric_paths = {
        "payment_conversion_pp": "week_over_week.payment_conversion_pp",
        "refund_rate_pct": "rates.refund_rate_pct",
        "ticket_resolution_pct": "rates.ticket_resolution_pct",
    }
    formats = contract.get("canonical_line_formats")
    required_formats = {"risk", "action", "no_risk", "no_risk_action", "data_quality", "period"}
    if not isinstance(formats, dict) or not required_formats <= set(formats) or any(not isinstance(formats[key], str) for key in required_formats):
        failures.append("canonical_line_formats")
        return False, failures
    if summary["risks"]:
        expected_risks: list[str] = []
        expected_actions: list[str] = []
        for risk in summary["risks"]:
            rule = rules[risk["risk_id"]]
            actual = path_value(summary, metric_paths[rule["metric"]])
            expected_risks.append(
                format_contract_line(
                    formats["risk"],
                    {
                        "label": risk["label"],
                        "severity": risk["severity"],
                        "metric": rule["metric"],
                        "actual": actual,
                        "operator": rule["operator"],
                        "threshold": rule["threshold"],
                    },
                )
            )
            expected_actions.append(
                format_contract_line(formats["action"], {"recommended_action": rule["recommended_action"]})
            )
        if not exact_contract_lines(risk_text, expected_risks):
            failures.append("risks")
        if not exact_contract_lines(action_text, expected_actions):
            failures.append("actions")
    else:
        if not exact_contract_lines(risk_text, [formats["no_risk"]]):
            failures.append("no_risk_statement")
        if not exact_contract_lines(action_text, [formats["no_risk_action"]]):
            failures.append("no_risk_action")
    quality = summary["data_quality"]
    expected_quality = format_contract_line(formats["data_quality"], quality)
    if not exact_contract_lines(sections["data_quality"], [expected_quality]):
        failures.append("data_quality")
    return not failures, failures


def check(checks: list[dict[str, Any]], check_id: str, passed: bool, detail: str) -> None:
    checks.append({"check_id": check_id, "passed": bool(passed), "detail": detail})


def verify(workspace: Path, expected_inputs_path: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    files, directories, has_symlink = tree_inventory(workspace)
    check(checks, "no_symlinks", not has_symlink, "workspace 不得包含符号链接")
    check(checks, "exact_directories", directories == EXACT_DIRECTORIES, f"目录集合={sorted(directories)}")
    check(checks, "exact_files", files == EXACT_FILES, f"文件集合={sorted(files)}")
    expected_inputs = json.loads(expected_inputs_path.read_text(encoding="utf-8"))
    expected_hashes = expected_inputs.get("input_sha256", {})
    input_ok = isinstance(expected_hashes, dict) and set(expected_hashes) == EXACT_INPUTS and all(
        (workspace / relative).is_file() and digest_bytes((workspace / relative).read_bytes()) == expected
        for relative, expected in expected_hashes.items()
    )
    check(checks, "protected_inputs", input_ok, "输入文件必须与 reset 清单哈希一致")
    expected_states = expected_inputs.get("input_state", {})
    identity_ok = isinstance(expected_states, dict) and set(expected_states) == EXACT_INPUTS
    if identity_ok:
        for relative, expected in expected_states.items():
            path = workspace / relative
            if not isinstance(expected, dict) or path.is_symlink() or not path.is_file():
                identity_ok = False
                break
            status = path.lstat()
            actual = {
                "sha256": digest_bytes(path.read_bytes()),
                "size_bytes": status.st_size,
                "mode": stat.S_IMODE(status.st_mode),
                "uid": status.st_uid,
                "gid": status.st_gid,
                "device": status.st_dev,
                "inode": status.st_ino,
                "link_count": status.st_nlink,
            }
            if actual != expected:
                identity_ok = False
                break
    check(checks, "protected_input_identity", identity_ok, "输入内容、inode、权限、所有者和链接数必须与 reset baseline 一致")
    script = workspace / "submission/generate_brief.py"
    expected_submission_hash = expected_inputs.get("submission_sha256")
    script_ok = (
        script.is_file()
        and not script.is_symlink()
        and 1 <= script.stat().st_size <= 131072
        and isinstance(expected_submission_hash, str)
        and digest_bytes(script.read_bytes()) == expected_submission_hash
    )
    if script_ok:
        try:
            source = script.read_text(encoding="utf-8")
            compile(source, script.as_posix(), "exec")
        except (UnicodeError, SyntaxError):
            script_ok = False
    check(checks, "reusable_script_present", script_ok, "必须交付 UTF-8 Python 脚本，且大小不超过 128 KiB")
    summary_path = workspace / "output/summary.json"
    brief_path = workspace / "output/weekly_brief.md"
    summary_bytes = summary_path.read_bytes() if summary_path.is_file() and not summary_path.is_symlink() else b""
    brief_bytes = brief_path.read_bytes() if brief_path.is_file() and not brief_path.is_symlink() else b""
    try:
        definitions, rows, template = parse_source(workspace)
        expected_summary = calculate(definitions, rows)
        summary_parse = parse_json_without_duplicate_keys(summary_bytes)
        summary_semantic = json_semantic_equal(summary_parse, expected_summary)
        brief_semantic_passed, brief_failures = brief_semantic(brief_bytes, expected_summary, definitions, template)
    except (OSError, UnicodeError, ValueError, KeyError, json.JSONDecodeError, ArithmeticError):
        summary_semantic = False
        brief_semantic_passed = False
        brief_failures = ["parse_or_contract"]
    check(
        checks,
        "summary_semantic",
        summary_semantic,
        "结构化摘要的 JSON 类型与值必须等于公开 schema 和公式的独立复算结果；键顺序、缩进和末尾换行不参与判分",
    )
    check(
        checks,
        "brief_semantic",
        brief_semantic_passed,
        "简报按公开章节、指标、表格、风险、行动和数据质量语义验收；失败类别=" + ",".join(brief_failures),
    )
    regular_modes = True
    for relative in files:
        mode = (workspace / relative).lstat().st_mode
        regular_modes = regular_modes and stat.S_ISREG(mode)
    check(checks, "regular_files_only", regular_modes, "所有交付和输入必须是普通文件")
    passed = all(item["passed"] for item in checks)
    return {
        "schema_version": "case11_verifier_result_v2",
        "status": "passed" if passed else "failed",
        "checks": checks,
        "evidence": {
            "workspace_tree_sha256": tree_hash(workspace, files),
            "summary_sha256": digest_bytes(summary_bytes),
            "brief_sha256": digest_bytes(brief_bytes),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--expected-input-manifest", type=Path, required=True)
    parser.add_argument("--result", type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.workspace.resolve(strict=True), args.expected_input_manifest.resolve(strict=True))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result = {
            "schema_version": "case11_verifier_result_v2",
            "status": "invalid",
            "checks": [{"check_id": "verifier_precondition", "passed": False, "detail": type(exc).__name__}],
            "evidence": {"workspace_tree_sha256": "0" * 64, "summary_sha256": "0" * 64, "brief_sha256": "0" * 64},
        }
    payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.result:
        args.result.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
