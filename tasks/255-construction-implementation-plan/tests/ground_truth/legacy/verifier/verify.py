"""Deterministic final-state and collateral-damage verifier for case_01."""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import sys
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


OUTPUT_RELATIVE = "outputs/新桥市综合管廊监控升级项目_施工实施方案.docx"
REQUIRED_SECTIONS = [
    "1 项目理解",
    "2 施工部署与组织",
    "3 施工方法",
    "4 进度计划",
    "5 质量保证",
    "6 安全文明施工",
    "7 测试与验收",
    "8 质保与应急",
    "9 条款响应",
]
FACT_ANCHORS = [
    "新桥市综合管廊监控升级项目",
    "XQ-GGL-2026-017",
    "新桥市城市设施服务中心",
    "新桥市东港片区",
    "120日历天",
    "一次验收合格",
    "零较大及以上安全事故",
    "24个月",
    "48套",
    "12台",
    "36台",
    "6台",
    "林致远",
    "合成注册证 XQ-JZ-0418",
    "何沐言",
    "合成高级工程师证 XQ-GJ-1120",
    "周芮",
    "合成安全证 XQ-AQ-0731",
    "第1—10天",
    "第11—25天",
    "第26—55天",
    "第56—90天",
    "第91—110天",
    "第111—120天",
    "连续72小时",
    "关键设备安装不得分包",
]
CRITERIA_ANCHORS = ["技术响应", "25", "进度计划", "20", "质量保证", "15", "安全文明", "组织配置", "10", "测试验收", "质保服务", "5"]
FORBIDDEN_FABRICATION = ["海康威视", "华为", "鲁班奖", "国家级示范项目", "同类项目合同额"]
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

SECTION_ANCHORS = {
    "1 项目理解": ["新桥市综合管廊监控升级项目", "XQ-GGL-2026-017", "120日历天", "关键设备安装不得分包"],
    "2 施工部署与组织": ["林致远", "何沐言", "周芮", "3个安装班组"],
    "3 施工方法": ["现场复核", "点位连通", "告警联动"],
    "4 进度计划": ["第1—10天", "第11—25天", "第26—55天", "第56—90天", "第91—110天", "第111—120天"],
    "5 质量保证": ["一次验收合格", "连续72小时"],
    "6 安全文明施工": ["零较大及以上安全事故", "安全交底", "立即停工"],
    "7 测试与验收": ["设备数量", "点位连通性", "告警联动", "资料归档", "人员培训"],
    "8 质保与应急": ["24个月", "隔离影响范围", "保留日志"],
    "9 条款响应": ["技术响应", "进度计划", "质量保证", "安全文明", "组织配置", "测试验收", "质保服务"],
}

TABLE_CONTRACTS = [
    {
        "name": "project_facts",
        "header": ["字段", "材料事实"],
        "minimum_rows": 9,
        "required_rows": [["项目名称", "新桥市综合管廊监控升级项目"], ["计划工期", "120日历天"], ["质保期", "24个月"]],
    },
    {
        "name": "equipment",
        "header": ["设备", "数量", "工作范围"],
        "minimum_rows": 5,
        "required_rows": [["环境传感器", "48套"], ["边缘采集柜", "12台"], ["高清摄像机", "36台"], ["通信网关", "6台"]],
    },
    {
        "name": "team",
        "header": ["岗位", "姓名", "合成资格信息", "年限"],
        "minimum_rows": 4,
        "required_rows": [["项目经理", "林致远", "合成注册证 XQ-JZ-0418"], ["技术负责人", "何沐言"], ["安全负责人", "周芮"]],
    },
    {
        "name": "milestones",
        "header": ["阶段", "时间", "交付检查点"],
        "minimum_rows": 7,
        "required_rows": [["进场准备", "第1—10天"], ["联合调试", "第91—110天"], ["试运行与验收", "第111—120天"]],
    },
    {
        "name": "acceptance",
        "header": ["验收项", "通过条件"],
        "minimum_rows": 7,
        "required_rows": [["设备数量"], ["点位连通性"], ["告警联动"], ["连续试运行", "连续72小时"], ["资料归档"], ["人员培训"]],
    },
    {
        "name": "evaluation_response",
        "header": ["评审项", "分值", "方案响应"],
        "minimum_rows": 8,
        "required_rows": [["技术响应", "25"], ["进度计划", "20"], ["质量保证", "15"], ["安全文明", "15"], ["组织配置", "10"], ["测试验收", "10"], ["质保服务", "5"]],
    },
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check(check_id: str, passed: bool, **evidence: Any) -> dict[str, Any]:
    return {"check_id": check_id, "passed": bool(passed), "evidence": evidence}


def parse_section_blocks(path: Path) -> tuple[list[str], dict[str, dict[str, Any]]]:
    with zipfile.ZipFile(path, "r") as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    ns = {"w": W_NS}
    body = root.find("./w:body", ns)
    if body is None:
        raise ValueError("document body is missing")
    order: list[str] = []
    sections: dict[str, dict[str, Any]] = {}
    current: str | None = None
    for node in list(body):
        local = node.tag.rsplit("}", 1)[-1]
        if local == "p":
            text = "".join(item.text or "" for item in node.findall(".//w:t", ns))
            style_node = node.find("./w:pPr/w:pStyle", ns)
            style = style_node.get(f"{{{W_NS}}}val", "Normal") if style_node is not None else "Normal"
            if style == "Heading1":
                current = text
                order.append(text)
                sections.setdefault(text, {"paragraphs": [], "tables": []})
            elif current and text.strip():
                sections[current]["paragraphs"].append(text)
        elif local == "tbl" and current:
            rows: list[list[str]] = []
            for row in node.findall("./w:tr", ns):
                rows.append(["".join(item.text or "" for item in cell.findall(".//w:t", ns)) for cell in row.findall("./w:tc", ns)])
            sections[current]["tables"].append(rows)
    return order, sections


def section_contract_failures(path: Path) -> list[dict[str, Any]]:
    order, sections = parse_section_blocks(path)
    failures: list[dict[str, Any]] = []
    if order != REQUIRED_SECTIONS:
        failures.append({"type": "heading_order_or_cardinality", "observed": order})
    for heading in REQUIRED_SECTIONS:
        block = sections.get(heading, {"paragraphs": [], "tables": []})
        text = "\n".join(block["paragraphs"]) + "\n" + "\n".join(
            " | ".join(row) for table_rows in block["tables"] for row in table_rows
        )
        missing = [anchor for anchor in SECTION_ANCHORS[heading] if anchor not in text]
        if len(text.replace(" ", "").strip()) < 30 or missing:
            failures.append({
                "type": "section_content",
                "heading": heading,
                "effective_characters": len(text.replace(" ", "").strip()),
                "missing_anchor_count": len(missing),
                "missing": missing,
            })
    return failures


def table_contract_failures(tables: list[list[list[str]]]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for contract in TABLE_CONTRACTS:
        matches = [rows for rows in tables if rows and rows[0] == contract["header"]]
        if len(matches) != 1:
            failures.append({"name": contract["name"], "type": "header_cardinality", "count": len(matches)})
            continue
        rows = matches[0]
        missing_rows = []
        for expected in contract["required_rows"]:
            if not any(
                all(any(value in cell for cell in row) for value in expected)
                for row in rows[1:]
            ):
                missing_rows.append(expected)
        if len(rows) < contract["minimum_rows"] or missing_rows:
            failures.append({
                "name": contract["name"],
                "type": "row_structure",
                "row_count": len(rows),
                "minimum_rows": contract["minimum_rows"],
                "missing_rows": missing_rows,
            })
    return failures


def verify(case_root: Path, workspace: Path) -> dict[str, Any]:
    sys.path.insert(0, str(case_root / "environment"))
    from docx_ooxml import inspect_docx

    manifest = json.loads((case_root / "environment/workspace_manifest.json").read_text(encoding="utf-8"))
    output = workspace / OUTPUT_RELATIVE
    checks: list[dict[str, Any]] = []
    checks.append(check("check_output_exists", output.is_file(), logical_path=OUTPUT_RELATIVE))

    inspection: dict[str, Any] | None = None
    try:
        if output.is_file():
            inspection = inspect_docx(output)
        checks.append(
            check(
                "check_ooxml_valid",
                bool(inspection and inspection["valid_zip"] and inspection["editable_ooxml"]),
                required_parts_present=bool(inspection),
                valid_zip=bool(inspection and inspection["valid_zip"]),
            )
        )
    except Exception as exc:
        checks.append(check("check_ooxml_valid", False, error_type=type(exc).__name__))

    text = inspection["text"] if inspection else ""
    paragraphs = inspection["paragraphs"] if inspection else []
    tables = inspection["tables"] if inspection else []
    section_failures = section_contract_failures(output) if inspection else [{"type": "document_unavailable"}]
    checks.append(check("check_required_sections", not section_failures, failures=section_failures))

    missing_facts = [item for item in FACT_ANCHORS + CRITERIA_ANCHORS if item not in text]
    checks.append(check("check_fact_anchors", not missing_facts, missing=missing_facts, anchor_count=len(FACT_ANCHORS + CRITERIA_ANCHORS)))

    template_styles = None
    output_styles = inspection["styles_sha256"] if inspection else None
    try:
        template_styles = inspect_docx(workspace / "inputs/05_实施方案模板.docx")["styles_sha256"]
    except Exception:
        pass
    title_ok = any(item["style"] == "Title" and "施工实施方案" in item["text"] for item in paragraphs)
    heading2_count = sum(item["style"] == "Heading2" for item in paragraphs)
    style_ids = set(inspection["style_ids"] if inspection else [])
    table_failures = table_contract_failures(tables)
    structural_ok = (
        len(tables) == 6
        and title_ok
        and heading2_count >= 4
        and {"Title", "Heading1", "Heading2", "TableGrid"}.issubset(style_ids)
        and template_styles is not None
        and template_styles == output_styles
        and not table_failures
    )
    checks.append(
        check(
            "check_tables_and_styles",
            structural_ok,
            table_count=len(tables),
            heading2_count=heading2_count,
            title_style=title_ok,
            template_style_preserved=template_styles == output_styles if template_styles else False,
            table_contract_failures=table_failures,
        )
    )

    fabricated = [item for item in FORBIDDEN_FABRICATION if item in text]
    checks.append(check("check_no_fabrication", not fabricated, forbidden_hits=fabricated))

    changed_inputs: list[str] = []
    missing_inputs: list[str] = []
    for expected in manifest["expected_initial_files"]:
        relative = expected["logical_path"]
        if relative == ".case_id":
            continue
        path = workspace / relative
        if not path.is_file():
            missing_inputs.append(relative)
        elif sha256_file(path) != expected["sha256"]:
            changed_inputs.append(relative)
    checks.append(check("check_inputs_unchanged", not changed_inputs and not missing_inputs, changed=changed_inputs, missing=missing_inputs))

    actual_files = sorted(path.relative_to(workspace).as_posix() for path in workspace.rglob("*") if path.is_file())
    allowed_files = sorted(manifest["allowed_final_files"])
    unexpected = sorted(set(actual_files) - set(allowed_files))
    missing_allowed_inputs = sorted(set(item["logical_path"] for item in manifest["expected_initial_files"]) - set(actual_files))
    checks.append(
        check(
            "check_allowed_file_scope",
            not unexpected and not missing_allowed_inputs,
            unexpected=unexpected,
            missing_initial=missing_allowed_inputs,
        )
    )

    interfaces = sorted(name for _, name in socket.if_nameindex())
    checks.append(
        check(
            "check_runtime_network_none",
            set(interfaces).issubset({"lo"}),
            interfaces=interfaces,
            required_mode="docker_network_none",
        )
    )

    passed_count = sum(item["passed"] for item in checks)
    verdict = "accept" if passed_count == len(checks) else "reject"
    return {
        "schema_version": "case01_verifier_result_v1",
        "case_id": "case_01",
        "verdict": verdict,
        "score": passed_count / len(checks),
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = verify(args.case_root.resolve(), args.workspace.resolve())
        exit_code = 0 if result["verdict"] == "accept" else 1
    except Exception as exc:
        result = {
            "schema_version": "case01_verifier_result_v1",
            "case_id": "case_01",
            "verdict": "invalid",
            "score": 0,
            "checks": [check("check_verifier_runtime", False, error_type=type(exc).__name__)],
        }
        exit_code = 2
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": result["verdict"], "score": result["score"]}, ensure_ascii=False, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
