"""Hidden deterministic reference solver for case_01."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path


def load_inputs(workspace: Path) -> tuple[dict[str, str], dict, list[list[str]]]:
    tender_text = (workspace / "inputs/01_招标要求.md").read_text(encoding="utf-8")
    qualifications = json.loads((workspace / "inputs/02_公司资质.json").read_text(encoding="utf-8"))
    with (workspace / "inputs/03_评审标准.csv").open(encoding="utf-8", newline="") as stream:
        criteria = list(csv.reader(stream))
    keys = {
        "project": r"项目名称：([^\n]+)",
        "tender_id": r"招标编号：([^\n]+)",
        "owner": r"招标人：([^\n]+)",
        "location": r"实施地点：([^\n]+)",
        "duration": r"计划工期：([^\n]+)",
        "quality": r"质量目标：([^\n]+)",
        "safety": r"安全目标：([^\n]+)",
        "warranty": r"质保期：([^\n]+)",
    }
    facts: dict[str, str] = {}
    for name, pattern in keys.items():
        match = re.search(pattern, tender_text)
        if not match:
            raise ValueError(f"missing synthetic tender fact: {name}")
        facts[name] = match.group(1).strip()
    if sum(int(row[1]) for row in criteria[1:]) != 100:
        raise ValueError("synthetic evaluation scores must total 100")
    return facts, qualifications, criteria


def build_elements(facts: dict[str, str], qualifications: dict, criteria: list[list[str]]) -> list[dict]:
    team_rows = [["岗位", "姓名", "合成资格信息", "年限"]]
    team_rows.extend([[item["role"], item["name"], item["credential"], str(item["years"])] for item in qualifications["team"]])
    criteria_rows = [["评审项", "分值", "方案响应"]]
    criteria_rows.extend([[row[0], row[1], row[2]] for row in criteria[1:]])
    return [
        {"type": "paragraph", "text": f"{facts['project']}施工实施方案", "style": "Title", "align": "center"},
        {"type": "paragraph", "text": f"招标编号：{facts['tender_id']}", "align": "center"},
        {"type": "paragraph", "text": f"投标人：{qualifications['bidder']}", "align": "center"},
        {"type": "page_break"},
        {"type": "paragraph", "text": "1 项目理解", "style": "Heading1"},
        {"type": "paragraph", "text": "1.1 项目事实", "style": "Heading2"},
        {"type": "table", "rows": [
            ["字段", "材料事实"],
            ["项目名称", facts["project"]],
            ["招标编号", facts["tender_id"]],
            ["招标人", facts["owner"]],
            ["实施地点", facts["location"]],
            ["计划工期", facts["duration"]],
            ["质量目标", facts["quality"]],
            ["安全目标", facts["safety"]],
            ["质保期", facts["warranty"]],
        ]},
        {"type": "paragraph", "text": "本方案覆盖供货、安装、联调、试运行、验收、资料归档和培训，关键设备安装不得分包。"},
        {"type": "paragraph", "text": "1.2 设备范围", "style": "Heading2"},
        {"type": "table", "rows": [
            ["设备", "数量", "工作范围"],
            ["环境传感器", "48套", "供货、安装、联调"],
            ["边缘采集柜", "12台", "供货、安装、联调"],
            ["高清摄像机", "36台", "供货、安装、联调"],
            ["通信网关", "6台", "供货、安装、联调"],
        ]},
        {"type": "paragraph", "text": "2 施工部署与组织", "style": "Heading1"},
        {"type": "paragraph", "text": "采用项目经理负责制，技术、质量和安全职责相互校核；公司可投入3个安装班组、4名调试工程师和6套测试仪器。"},
        {"type": "table", "rows": team_rows},
        {"type": "paragraph", "text": "3 施工方法", "style": "Heading1"},
        {"type": "paragraph", "text": "3.1 现场复核与深化设计", "style": "Heading2"},
        {"type": "paragraph", "text": "逐点核对位置、供电、网络和安装条件，形成点位确认记录后再实施。"},
        {"type": "paragraph", "text": "3.2 安装与联调", "style": "Heading2"},
        {"type": "paragraph", "text": "设备进场先核验数量和外观；安装后分别完成单机测试、点位连通测试和告警联动测试。"},
        {"type": "paragraph", "text": "4 进度计划", "style": "Heading1"},
        {"type": "table", "rows": [
            ["阶段", "时间", "交付检查点"],
            ["进场准备", "第1—10天", "人员、工具和安全交底完成"],
            ["深化设计与现场复核", "第11—25天", "点位与施工条件确认"],
            ["设备采购与进场检验", "第26—55天", "设备数量和质量检验"],
            ["安装施工", "第56—90天", "设备安装与线缆检查"],
            ["联合调试", "第91—110天", "系统联动测试完成"],
            ["试运行与验收", "第111—120天", "连续72小时试运行并验收"],
        ]},
        {"type": "paragraph", "text": "5 质量保证", "style": "Heading1"},
        {"type": "paragraph", "text": f"以“{facts['quality']}”为质量目标，对材料进场、安装过程、测试记录和验收资料实施四级检查；联合调试后执行连续72小时试运行。"},
        {"type": "paragraph", "text": "6 安全文明施工", "style": "Heading1"},
        {"type": "paragraph", "text": f"安全目标为“{facts['safety']}”。进场前完成安全交底，执行临电、动火、高处作业和受限空间检查，异常时立即停工并上报。"},
        {"type": "paragraph", "text": "7 测试与验收", "style": "Heading1"},
        {"type": "table", "rows": [
            ["验收项", "通过条件"],
            ["设备数量", "48套传感器、12台采集柜、36台摄像机、6台网关逐项核对"],
            ["点位连通性", "全部点位通信正常"],
            ["告警联动", "告警产生、转发和处置闭环正常"],
            ["连续试运行", "连续72小时运行完成"],
            ["资料归档", "图纸、清单和测试记录齐全"],
            ["人员培训", "操作与维护培训完成并留存签到"],
        ]},
        {"type": "paragraph", "text": "8 质保与应急", "style": "Heading1"},
        {"type": "paragraph", "text": f"提供{facts['warranty']}质保服务。发生设备或通信异常时，先隔离影响范围、保留日志，再按故障等级组织恢复并复核告警链路。"},
        {"type": "paragraph", "text": "9 条款响应", "style": "Heading1"},
        {"type": "table", "rows": criteria_rows},
        {"type": "paragraph", "text": "本方案仅依据给定合成材料编制，未增加品牌、奖项、类似项目业绩或材料之外的资格证书。"},
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    case_root = args.case_root.resolve()
    workspace = args.workspace.resolve()
    sys.path.insert(0, str(case_root / "environment"))
    from docx_ooxml import render_from_template, sha256_file

    facts, qualifications, criteria = load_inputs(workspace)
    output = args.output or workspace / "outputs/新桥市综合管廊监控升级项目_施工实施方案.docx"
    output.parent.mkdir(parents=True, exist_ok=True)
    render_from_template(
        workspace / "inputs/05_实施方案模板.docx",
        output,
        build_elements(facts, qualifications, criteria),
    )
    print(json.dumps({"status": "solved", "output": str(output), "sha256": sha256_file(output)}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
