"""Create the fully synthetic and deterministic input package for case_01."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from docx_ooxml import create_template, dump_json, sha256_file


TENDER = """# 新桥市综合管廊监控升级项目招标要求（合成）

本材料中的项目、机构、人员、证书和编号均为虚构，仅用于确定性环境测试。

## 基本信息

- 项目名称：新桥市综合管廊监控升级项目
- 招标编号：XQ-GGL-2026-017
- 招标人：新桥市城市设施服务中心
- 实施地点：新桥市东港片区
- 计划工期：120日历天
- 质量目标：一次验收合格
- 安全目标：零较大及以上安全事故
- 质保期：24个月

## 实施范围

完成环境传感器48套、边缘采集柜12台、高清摄像机36台和通信网关6台的供货、安装、联调、试运行与验收。关键设备安装不得分包。

## 强制里程碑

1. 第1—10天：进场准备。
2. 第11—25天：深化设计与现场复核。
3. 第26—55天：设备采购与进场检验。
4. 第56—90天：安装施工。
5. 第91—110天：联合调试。
6. 第111—120天：试运行与验收。

## 验收要求

验收必须覆盖设备数量核对、点位连通性、告警联动、连续72小时试运行、资料归档和人员培训。不得承诺招标材料未提供的品牌、奖项或业绩。
"""


QUALIFICATIONS = {
    "synthetic_notice": "全部实体与证书编号均为虚构，仅用于环境测试。",
    "bidder": "澄岳工程技术有限公司（虚构）",
    "credit_code": "SYNTHETIC-91310000-XQ017",
    "team": [
        {"role": "项目经理", "name": "林致远", "credential": "合成注册证 XQ-JZ-0418", "years": 8},
        {"role": "技术负责人", "name": "何沐言", "credential": "合成高级工程师证 XQ-GJ-1120", "years": 10},
        {"role": "安全负责人", "name": "周芮", "credential": "合成安全证 XQ-AQ-0731", "years": 7},
    ],
    "available_resources": {
        "installation_teams": 3,
        "commissioning_engineers": 4,
        "test_instruments": 6,
    },
}


CONSTRAINTS = """# 编制约束（合成）

1. 使用给定 DOCX 模板，保持 `Title`、`Heading1`、`Heading2` 和 `TableGrid` 样式。
2. 输出文件固定为 `outputs/新桥市综合管廊监控升级项目_施工实施方案.docx`，必须可编辑。
3. 必须覆盖项目理解、施工部署与组织、施工方法、进度计划、质量保证、安全文明施工、测试验收、质保应急和条款响应九个一级章节。
4. 必须逐字准确引用招标编号、招标人、地点、工期、质量目标、安全目标、质保期、设备数量、里程碑和项目团队信息。
5. 至少使用五个可编辑表格，分别呈现项目事实、项目团队、设备清单、里程碑和评分响应。
6. 不得修改 `inputs/` 中的任何文件，不得新增指定输出之外的任务文件，不得访问网络。
7. 不得虚构品牌、奖项、类似项目业绩或额外证书。
"""


CRITERIA = [
    ["评审项", "分值", "最低响应要求"],
    ["技术响应", "25", "覆盖全部实施范围和设备数量"],
    ["进度计划", "20", "完整列出六个强制里程碑"],
    ["质量保证", "15", "写明一次验收合格和72小时试运行"],
    ["安全文明", "15", "写明零较大及以上安全事故"],
    ["组织配置", "10", "准确列出三名项目人员及合成证书"],
    ["测试验收", "10", "覆盖六项验收要求"],
    ["质保服务", "5", "写明24个月质保期"],
]


def write_csv(path: Path, rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", type=Path, required=True)
    args = parser.parse_args()
    case_root = args.case_root.resolve()
    input_dir = case_root / "fixtures/input"
    input_dir.mkdir(parents=True, exist_ok=True)
    (input_dir / "01_招标要求.md").write_text(TENDER, encoding="utf-8")
    dump_json(input_dir / "02_公司资质.json", QUALIFICATIONS)
    write_csv(input_dir / "03_评审标准.csv", CRITERIA)
    (input_dir / "04_编制约束.md").write_text(CONSTRAINTS, encoding="utf-8")
    create_template(input_dir / "05_实施方案模板.docx")

    files = []
    for path in sorted(input_dir.iterdir()):
        files.append(
            {
                "logical_path": f"inputs/{path.name}",
                "fixture_path": path.relative_to(case_root).as_posix(),
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
                "provenance": "fully_synthetic_case01_v1",
                "license": "project_synthetic_cc0_1_0",
            }
        )
    fixture_manifest = {
        "schema_version": "case01_fixture_manifest_v1",
        "case_id": "case_01",
        "synthetic": True,
        "fixed_time": "2026-04-08T09:00:00+08:00",
        "files": files,
    }
    dump_json(case_root / "fixtures/fixture_manifest.json", fixture_manifest)

    marker_hash = hashlib.sha256(b"case_01\n").hexdigest()
    workspace_manifest = {
        "schema_version": "case01_workspace_manifest_v1",
        "case_id": "case_01",
        "fixed_time": "2026-04-08T09:00:00+08:00",
        "timezone": "Asia/Shanghai",
        "locale": "zh-CN",
        "network_policy": "offline",
        "state_hash_algorithm": "sha256_sorted_directory_and_file_records_v1",
        "expected_initial_files": [
            {"logical_path": ".case_id", "sha256": marker_hash},
            *[{"logical_path": item["logical_path"], "sha256": item["sha256"]} for item in files],
        ],
        "required_output": "outputs/新桥市综合管廊监控升级项目_施工实施方案.docx",
        "protected_paths": [item["logical_path"] for item in files],
        "allowed_final_files": [
            ".case_id",
            *[item["logical_path"] for item in files],
            "outputs/新桥市综合管廊监控升级项目_施工实施方案.docx",
        ],
    }
    dump_json(case_root / "environment/workspace_manifest.json", workspace_manifest)
    print(json.dumps({"status": "built", "files": len(files)}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
