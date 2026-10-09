#!/usr/bin/env python3
"""不启动容器的语义验收器回归，覆盖已知误收攻击。"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from types import ModuleType


CASE_ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expect_value_error(callable_object, value: str) -> None:
    try:
        callable_object(value)
    except ValueError:
        return
    raise AssertionError(f"应拒绝日期：{value}")


def main() -> int:
    verifier = load_module("case11_semantic_verifier", CASE_ROOT / "verifier/verify_outputs.py")
    oracle = load_module("case11_reference_generator", CASE_ROOT / "oracle/reference_generator.py")

    primary_definitions = oracle.load_definitions(CASE_ROOT / "fixtures/metric_definitions.json")
    primary_rows = oracle.load_rows(CASE_ROOT / "fixtures/weekly_operations.csv", primary_definitions)
    primary_summary = oracle.make_summary(primary_rows, primary_definitions)
    primary_template = (CASE_ROOT / "fixtures/brief_template.md").read_text(encoding="utf-8")
    primary_brief = oracle.render_brief(primary_summary, primary_definitions, primary_template)
    assert verifier.brief_semantic(primary_brief.encode("utf-8"), primary_summary, primary_definitions, primary_template)[0]
    for visible in (
        "线上运营周简报",
        "本期 2026-07-06 至 2026-07-12；对比 2026-06-29 至 2026-07-05；时区 Asia/Shanghai。",
        "访问量：12580",
        "支付转化率显著下降",
        "分渠道复盘流量质量和下单路径，优先排查转化降幅最大的渠道。",
        "已校验 28 行；当期 14 行，对比期 14 行；重复键 0 个，无效行 0 行。",
    ):
        struck = primary_brief.replace(visible, f"~~{visible}~~", 1)
        assert not verifier.brief_semantic(struck.encode("utf-8"), primary_summary, primary_definitions, primary_template)[0]

    reordered = {key: primary_summary[key] for key in reversed(primary_summary)}
    assert verifier.json_semantic_equal(reordered, primary_summary)
    wrong_summary = json.loads(json.dumps(primary_summary, ensure_ascii=False))
    wrong_summary["totals"]["visits"] += 1
    assert not verifier.json_semantic_equal(wrong_summary, primary_summary)

    assert not verifier.number_present("访问量：-10.45%", "10.45", "percent")
    assert not verifier.number_present("总收入：-¥24950.00", "24950.00", "money")
    for negative in ("−10.45%", "负10.45%"):
        assert not verifier.number_present(f"访问量：{negative}", "10.45", "percent")
    for negative in ("−12580", "负12580"):
        assert not verifier.number_present(f"访问量：{negative}", "12580", "integer")
    for negative in ("−¥24950.00", "负¥24950.00", "¥负24950.00"):
        assert not verifier.number_present(f"总收入：{negative}", "24950.00", "money")

    table_columns = [
        ("channel", "text"),
        ("visits", "integer"),
        ("paid_orders", "integer"),
        ("net_revenue_yuan", "money"),
        ("payment_conversion_pct", "percent"),
        ("refund_rate_pct", "percent"),
    ]
    collapsed_table = "\n".join(
        [
            "| 渠道 | 访问量 | 支付订单 | 净收入 | 转化率 | 退款率 |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
            "| 合作渠道 直营网 | 4890 7690 | 309 515 | ¥33402.90 ¥50830.50 | 6.32% 6.70% | 6.00% |",
        ]
    )
    assert not verifier.table_semantic(
        collapsed_table,
        primary_summary["channels"],
        table_columns,
        primary_definitions["brief_contract"]["table_header_aliases"],
    )
    channel_table = primary_brief.split("## 三、渠道表现", 1)[1].split("## 四、每日趋势", 1)[0].strip()
    channel_lines = channel_table.splitlines()
    assert verifier.table_semantic(
        channel_table,
        primary_summary["channels"],
        table_columns,
        primary_definitions["brief_contract"]["table_header_aliases"],
    )
    malformed_tables = [
        "\n".join([channel_lines[0], "| --- |", *channel_lines[2:]]),
        "\n".join([channel_lines[0], channel_lines[1], channel_lines[1], *channel_lines[2:]]),
        "\n".join([channel_lines[0], *channel_lines[2:], channel_lines[1]]),
        "\n".join([channel_lines[2], channel_lines[1], channel_lines[0], *channel_lines[3:]]),
    ]
    for malformed in malformed_tables:
        assert not verifier.table_semantic(
            malformed,
            primary_summary["channels"],
            table_columns,
            primary_definitions["brief_contract"]["table_header_aliases"],
        )
    missing_currency = primary_brief.replace("总收入：¥", "总收入：", 1)
    assert not verifier.brief_semantic(missing_currency.encode("utf-8"), primary_summary, primary_definitions, primary_template)[0]
    sections = re.split(r"(?=^##(?!#)\s+)", primary_brief, flags=re.MULTILINE)
    reversed_sections = sections[0] + "".join(reversed(sections[1:]))
    assert not verifier.brief_semantic(reversed_sections.encode("utf-8"), primary_summary, primary_definitions, primary_template)[0]

    negated_primary = primary_brief.replace("支付转化率显著下降", "并非支付转化率显著下降", 1).replace(
        "分渠道复盘流量质量和下单路径", "不要分渠道复盘流量质量和下单路径", 1
    )
    assert not verifier.brief_semantic(negated_primary.encode("utf-8"), primary_summary, primary_definitions, primary_template)[0]
    alternate_negation = primary_brief.replace("支付转化率显著下降", "未发现支付转化率显著下降", 1).replace(
        "分渠道复盘流量质量和下单路径", "不能分渠道复盘流量质量和下单路径", 1
    )
    assert not verifier.brief_semantic(alternate_negation.encode("utf-8"), primary_summary, primary_definitions, primary_template)[0]
    appended_contradiction = primary_brief.replace(
        "支付转化率显著下降**（high）", "支付转化率显著下降**（high），其实没有这种风险", 1
    ).replace(
        "优先排查转化降幅最大的渠道。", "优先排查转化降幅最大的渠道，但不能执行。", 1
    )
    assert not verifier.brief_semantic(appended_contradiction.encode("utf-8"), primary_summary, primary_definitions, primary_template)[0]
    first_risk = primary_summary["risks"][0]
    first_rule = next(item for item in primary_definitions["risk_rules"] if item["risk_id"] == first_risk["risk_id"])
    actual = primary_summary["week_over_week"][first_rule["metric"]]
    swapped_roles = primary_brief.replace(
        f"{first_rule['metric']}={actual}，阈值{first_rule['operator']}{first_rule['threshold']}",
        f"阈值={actual}，实际值={first_rule['threshold']}",
        1,
    )
    assert not verifier.brief_semantic(swapped_roles.encode("utf-8"), primary_summary, primary_definitions, primary_template)[0]
    negated_title = primary_brief.replace("# 线上运营周简报", "# 这不是线上运营周简报", 1)
    assert not verifier.brief_semantic(negated_title.encode("utf-8"), primary_summary, primary_definitions, primary_template)[0]
    metric_contradiction = primary_brief.replace("- 访问量：12580", "- 访问量：12580，但该数值错误", 1)
    assert not verifier.brief_semantic(metric_contradiction.encode("utf-8"), primary_summary, primary_definitions, primary_template)[0]
    extra_heading = primary_brief + "\n## 八、真实结论\n以上数据均错误。\n"
    assert not verifier.brief_semantic(extra_heading.encode("utf-8"), primary_summary, primary_definitions, primary_template)[0]
    extra_h3 = primary_brief + "\n### 补充\n以上数据均错误。\n"
    assert not verifier.brief_semantic(extra_h3.encode("utf-8"), primary_summary, primary_definitions, primary_template)[0]

    alternate_definitions = oracle.load_definitions(CASE_ROOT / "tests/hidden/alternate_metric_definitions.json")
    alternate_rows = oracle.load_rows(CASE_ROOT / "tests/hidden/alternate_weekly_operations.csv", alternate_definitions)
    alternate_summary = oracle.make_summary(alternate_rows, alternate_definitions)
    alternate_template = (CASE_ROOT / "tests/hidden/alternate_brief_template.md").read_text(encoding="utf-8")
    alternate_brief = oracle.render_brief(alternate_summary, alternate_definitions, alternate_template)
    assert not alternate_summary["risks"]
    assert verifier.brief_semantic(alternate_brief.encode("utf-8"), alternate_summary, alternate_definitions, alternate_template)[0]
    contradicted_no_risk = alternate_brief.replace(
        "本周未触发预设风险规则。", "本周未触发预设风险规则。\n实际存在重大风险。", 1
    ).replace(
        "继续按现有口径跟踪核心指标。", "继续按现有口径跟踪核心指标。\n不应继续监控。", 1
    )
    assert not verifier.brief_semantic(contradicted_no_risk.encode("utf-8"), alternate_summary, alternate_definitions, alternate_template)[0]
    uncertain_no_risk = alternate_brief.replace(
        "本周未触发预设风险规则。", "本周未必没有触发预设风险规则。", 1
    ).replace(
        "继续按现有口径跟踪核心指标。", "不可继续按现有口径跟踪核心指标。", 1
    )
    assert not verifier.brief_semantic(uncertain_no_risk.encode("utf-8"), alternate_summary, alternate_definitions, alternate_template)[0]
    appended_no_risk = alternate_brief.replace(
        "本周未触发预设风险规则。", "本周未触发预设风险规则，但实际存在重大风险。", 1
    ).replace(
        "继续按现有口径跟踪核心指标。", "继续按现有口径跟踪核心指标，但不能执行。", 1
    )
    assert not verifier.brief_semantic(appended_no_risk.encode("utf-8"), alternate_summary, alternate_definitions, alternate_template)[0]

    expect_value_error(verifier.parse_date, "20260801")
    expect_value_error(verifier.parse_date, "2026-W28-1")
    expect_value_error(lambda value: oracle.parse_day(value, "date"), "20260801")
    invalid_extra = CASE_ROOT / "tests/hidden/invalid_extra_cell_weekly_operations.csv"
    try:
        oracle.load_rows(invalid_extra, alternate_definitions)
    except ValueError:
        pass
    else:
        raise AssertionError("行尾额外单元格必须被拒绝")
    print(json.dumps({"status": "passed", "checks": 42}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
