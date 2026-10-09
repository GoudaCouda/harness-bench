#!/usr/bin/env python3
"""Build the hidden deterministic reference or a minimal verifier test variant."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
from pathlib import Path
from typing import Any


def _load_writer(case_root: Path) -> Any:
    path = case_root / "environment/public/document_writer.py"
    spec = importlib.util.spec_from_file_location("case02_document_writer", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load document writer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _variant(plan: dict[str, Any], name: str) -> dict[str, Any]:
    value = copy.deepcopy(plan)
    if name == "gold":
        return value
    root_table = next(
        block
        for block in value["blocks"]
        if block.get("type") == "table"
        and block.get("headers") == ["链路环节", "事实", "证据"]
    )
    if name == "distractor_root":
        root_table["rows"][-1] = [
            "直接根因",
            "ALT-CPU-112 表明 checkout-canary 的 CPU 告警是本事故直接根因",
            "ALERT-EV-CPU-112",
        ]
        return value
    if name == "missing_causal_evidence":
        root_table["rows"][2] = [
            "因果闭环",
            "回滚后服务似乎恢复",
            "LOG-SVC-044",
        ]
        return value
    if name == "wrong_impact":
        impact_table = next(
            block
            for block in value["blocks"]
            if block.get("type") == "table"
            and block.get("headers") == ["指标", "结果", "证据"]
        )
        impact_table["rows"][1][1] = "1,250 / 4,200，失败率29.8%"
        return value
    if name == "missing_action_owner":
        action_table = next(
            block
            for block in value["blocks"]
            if block.get("type") == "table"
            and block.get("headers") == ["行动项", "负责人", "完成期限", "验收标准"]
        )
        action_table["rows"][0][1] = ""
        return value
    if name == "unsupported_claim":
        summary = next(
            block
            for block in value["blocks"]
            if block.get("type") == "paragraph"
        )
        summary["text"] += "数据库发生永久损坏。"
        return value
    raise ValueError("unknown variant")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument(
        "--variant",
        choices=[
            "gold",
            "distractor_root",
            "missing_action_owner",
            "missing_causal_evidence",
            "unsupported_claim",
            "wrong_impact",
        ],
        default="gold",
    )
    args = parser.parse_args()
    plan = json.loads(
        (args.case_root / "oracle/reference_plan.json").read_text(encoding="utf-8")
    )
    writer = _load_writer(args.case_root)
    output = args.workspace / "output/incident_postmortem.docx"
    writer.write_docx(_variant(plan, args.variant), output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
