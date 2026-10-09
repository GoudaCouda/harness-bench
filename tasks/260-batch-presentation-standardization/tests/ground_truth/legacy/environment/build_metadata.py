#!/usr/bin/env python3
"""Build case.json and an auditable draft manifest from actual case files."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CASE_ROOT = Path(__file__).resolve().parents[1]
IMAGE_DIGEST = "sha256:a1e8e20f3a376cb27651a0b14f250b28872c1879819d92026cf11bf1b236d2d5"
DECK_NAMES = ("market_brief.pptx", "project_update.pptx", "service_review.pptx")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_spec_hash(spec: dict[str, Any]) -> str:
    value = dict(spec)
    value.pop("spec_sha256", None)
    data = json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def file_role(relative: str) -> str:
    if relative == "case.json":
        return "spec"
    if relative == "README.md":
        return "documentation"
    return {
        "environment": "environment",
        "fixtures": "fixture",
        "oracle": "oracle",
        "tests": "test",
        "validation": "validation_evidence",
        "verifier": "verifier",
    }[relative.split("/", 1)[0]]


def make_spec(validation_status: str) -> dict[str, Any]:
    workspace_manifest_path = CASE_ROOT / "environment/workspace_manifest.json"
    workspace_manifest = json.loads(workspace_manifest_path.read_text(encoding="utf-8"))
    reference_manifest = CASE_ROOT / "oracle/reference_output_manifest.json"
    verifier = CASE_ROOT / "verifier/verify.py"
    input_assets = []
    for name in DECK_NAMES:
        path = CASE_ROOT / "fixtures/decks" / name
        input_assets.append(
            {
                "asset_id": f"input_deck_{name.removesuffix('.pptx')}",
                "logical_path": f"fixtures/decks/{name}",
                "media_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                "sha256": sha256_file(path),
                "purpose": "待统一格式的完全合成演示稿，不含真实用户内容。",
                "provenance_ref": "prov_synthetic_inputs",
                "license_ref": "license_synthetic_cc0",
                "visible_to_agent": True,
            }
        )
    for asset_id, relative, media_type, purpose in (
        (
            "brand_template",
            "fixtures/brand_template.pptx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "展示目标字体、颜色、页脚、对象位置和画布比例的合成模板。",
        ),
        (
            "style_map",
            "fixtures/style_map.json",
            "application/json",
            "机器可读的确定性样式映射和批量文件合同。",
        ),
    ):
        path = CASE_ROOT / relative
        input_assets.append(
            {
                "asset_id": asset_id,
                "logical_path": relative,
                "media_type": media_type,
                "sha256": sha256_file(path),
                "purpose": purpose,
                "provenance_ref": "prov_synthetic_inputs",
                "license_ref": "license_synthetic_cc0",
                "visible_to_agent": True,
            }
        )

    tools = [
        {
            "tool_id": "workspace_filesystem",
            "version": "1.0.0",
            "description": "列出并读取工作区输入，只能在 outputs/standardized 写入任务要求的三份输出。",
            "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
            "output_schema": {"type": "object", "properties": {"status": {"type": "string"}}, "required": ["status"]},
            "errors": [{"code": "path_outside_workspace", "retryable": False}],
            "implementation_ref": "environment/tool_contract.json",
            "side_effect": "workspace_write",
            "idempotent": True,
        },
        {
            "tool_id": "pptx_inspect",
            "version": "1.0.0",
            "description": "安全解析一份输入 PPTX，返回页数、对象角色、几何和段落摘要。",
            "input_schema": {"type": "object", "properties": {"input": {"type": "string"}}, "required": ["input"]},
            "output_schema": {"type": "object", "properties": {"status": {"type": "string"}, "deck": {"type": "object"}}, "required": ["status"]},
            "errors": [{"code": "invalid_pptx_package", "retryable": False}, {"code": "path_outside_workspace", "retryable": False}],
            "implementation_ref": "environment/tools/pptx_inspect.py",
            "side_effect": "read_only",
            "idempotent": True,
        },
        {
            "tool_id": "pptx_standardize",
            "version": "1.0.0",
            "description": "按可见 style_map 将一份输入 PPTX 转换到声明的输出路径，保持标题和正文不变。",
            "input_schema": {"type": "object", "properties": {"input": {"type": "string"}, "output": {"type": "string"}, "style_map": {"type": "string"}}, "required": ["input", "output"]},
            "output_schema": {"type": "object", "properties": {"status": {"type": "string"}, "sha256": {"type": "string"}}, "required": ["status"]},
            "errors": [{"code": "input_hash_mismatch", "retryable": False}, {"code": "batch_path_not_declared", "retryable": False}],
            "implementation_ref": "environment/tools/pptx_standardize.py",
            "side_effect": "workspace_write",
            "idempotent": True,
        },
    ]
    permissions = [
        {
            "tool_id": "workspace_filesystem",
            "effect": "allow",
            "actions": ["list", "read", "write_declared_outputs"],
            "resource_scope": ["task.md", "inputs/**", "tools/**", "outputs/standardized/*.pptx"],
        },
        {
            "tool_id": "pptx_inspect",
            "effect": "allow",
            "actions": ["inspect"],
            "resource_scope": ["inputs/decks/*.pptx"],
        },
        {
            "tool_id": "pptx_standardize",
            "effect": "allow",
            "actions": ["read_input", "read_style_map", "write_output"],
            "resource_scope": ["inputs/decks/*.pptx", "inputs/style_map.json", "outputs/standardized/*.pptx"],
        },
    ]
    spec: dict[str, Any] = {
        "schema_version": "nami_work_env_case_v1",
        "case_version": "1.0.0",
        "spec_sha256": "0" * 64,
        "task_id": "case_06",
        "source_cluster_id": "dup_7b3d0b9940a163f299c05aec",
        "raw_or_reconstructed_instruction": {
            "mode": "synthetic",
            "text": "将输入目录中的三份演示稿按统一模板批量规范为 16:9：统一 Noto Sans SC 字体、字号、颜色、页脚、背景和四类对象的位置与尺寸。输出到 outputs/standardized 下的同名文件；不得覆盖输入，不得丢页、增页或修改标题与正文文案，也不得创建额外文件。页脚属于格式元数据，按样式表替换。",
            "redacted": True,
            "evidence_refs": [],
            "reconstruction_confidence": "authored",
        },
        "task_type": {
            "taxonomy_version": "nami_work_task_taxonomy_v1",
            "primary": "office_content_delivery",
            "secondary": "presentation_batch_revision",
            "capability_tags": ["goal_understanding", "planning", "tool_use", "workspace_operation", "self_correction", "deliverable_completion", "safety_cost_awareness"],
        },
        "deliverable_type": {
            "primary": "presentation",
            "items": [
                {
                    "deliverable_id": f"standardized_{name.removesuffix('.pptx')}",
                    "kind": "presentation",
                    "logical_path": f"outputs/standardized/{name}",
                    "media_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    "required": True,
                }
                for name in DECK_NAMES
            ],
        },
        "initial_environment": {
            "environment_template_id": "nami_office_pptx_batch_v1",
            "environment_version": "1.0.0",
            "image_digest": IMAGE_DIGEST,
            "workspace_manifest_path": "environment/workspace_manifest.json",
            "workspace_manifest_sha256": sha256_file(workspace_manifest_path),
            "initial_state_sha256": workspace_manifest["initial_state_sha256"],
            "fixed_time": "2026-07-20T00:00:00Z",
            "timezone": "UTC",
            "locale": "zh-CN",
            "network_policy": {"mode": "offline", "allowed_hosts": [], "deterministic_scoring": True},
        },
        "input_assets": input_assets,
        "available_tools": tools,
        "tool_permissions": permissions,
        "required_state_changes": [
            {
                "assertion_id": f"output_{name.removesuffix('.pptx')}_exists",
                "type": "file_exists",
                "target": f"outputs/standardized/{name}",
                "expected": True,
                "required": True,
                "verifier_check_id": "workspace_exact_tree",
            }
            for name in DECK_NAMES
        ]
        + [
            {
                "assertion_id": "all_decks_match_standard",
                "type": "custom",
                "target": "outputs/standardized/*.pptx",
                "expected": "3 safe PPTX packages; 9 original slides; exact visible style contract",
                "required": True,
                "verifier_check_id": "canvas_alignment_and_geometry",
            }
        ],
        "acceptance_rubric": [
            {"rubric_id": "rubric_exact_delivery", "description": "只交付声明的三份同名输出。", "kind": "hard_gate", "weight": 0.15, "required": True, "evidence_location": "verifier.result.checks.workspace_exact_tree", "pass_condition": "目录、文件和安全类型完全匹配。", "verifier_check_id": "workspace_exact_tree"},
            {"rubric_id": "rubric_package_integrity", "description": "三份 PPTX 均为安全且结构完整的包。", "kind": "hard_gate", "weight": 0.15, "required": True, "evidence_location": "verifier.result.checks.pptx_package_integrity", "pass_condition": "包成员无缺失、无额外活动内容、关系合法。", "verifier_check_id": "pptx_package_integrity"},
            {"rubric_id": "rubric_content_preserved", "description": "九页标题、正文、页序和对象身份保持不变。", "kind": "deterministic", "weight": 0.25, "required": True, "evidence_location": "verifier.result.checks.slide_and_content_preservation", "pass_condition": "忽略允许替换的页脚后，语义快照与输入一致。", "verifier_check_id": "slide_and_content_preservation"},
            {"rubric_id": "rubric_typography", "description": "字体、字号、粗细、文字颜色和背景统一。", "kind": "deterministic", "weight": 0.15, "required": True, "evidence_location": "verifier.result.checks.uniform_typography_and_color", "pass_condition": "所有相关文字属性逐段符合 style_map。", "verifier_check_id": "uniform_typography_and_color"},
            {"rubric_id": "rubric_footer", "description": "每页页脚使用统一文本并包含两位页码。", "kind": "deterministic", "weight": 0.1, "required": True, "evidence_location": "verifier.result.checks.uniform_footer", "pass_condition": "九页页脚逐页精确匹配。", "verifier_check_id": "uniform_footer"},
            {"rubric_id": "rubric_geometry", "description": "画布、对象对齐、位置和尺寸统一且不拉伸。", "kind": "hard_gate", "weight": 0.15, "required": True, "evidence_location": "verifier.result.checks.canvas_alignment_and_geometry", "pass_condition": "16:9 画布与四类对象几何逐项精确匹配。", "verifier_check_id": "canvas_alignment_and_geometry"},
            {"rubric_id": "rubric_protected_state", "description": "输入、工具和任务说明保持原样。", "kind": "hard_gate", "weight": 0.05, "required": True, "evidence_location": "verifier.result.checks.protected_input_integrity", "pass_condition": "所有受保护文件的 SHA-256 不变。", "verifier_check_id": "protected_input_integrity"},
        ],
        "automatic_verifier": {
            "entrypoint": "verifier/verify.py",
            "version": "1.0.0",
            "timeout_seconds": 60,
            "result_schema_path": "verifier/result.schema.json",
            "sha256": sha256_file(verifier),
            "hidden_from_agent": True,
            "test_suite_path": "tests/run_validation.py",
        },
        "reference_output": {
            "status": "available",
            "path": "oracle/reference_output_manifest.json",
            "sha256": sha256_file(reference_manifest),
            "provenance_ref": "prov_reference_output",
            "explanation": "清单固定三份可信工具生成的参考演示稿及其逐文件哈希；参考文件只用于隐藏环境验证。",
        },
        "side_effect_constraints": [
            {"constraint_id": "no_modify_inputs", "type": "no_modify", "target": "inputs/**", "description": "不得覆盖、删除或改写输入演示稿、模板和样式表。", "verifier_check_id": "protected_input_integrity"},
            {"constraint_id": "no_modify_visible_tools", "type": "no_modify", "target": "tools/**", "description": "不得修改候选可见工具。", "verifier_check_id": "protected_input_integrity"},
            {"constraint_id": "no_network", "type": "no_network", "target": "all", "description": "任务完全离线，不允许网络访问。", "verifier_check_id": "workspace_exact_tree"},
            {"constraint_id": "no_extra_artifacts", "type": "custom", "target": "workspace", "description": "不得创建未声明文件、目录、符号链接或特殊文件。", "verifier_check_id": "workspace_exact_tree"},
            {"constraint_id": "no_content_rewrite", "type": "custom", "target": "outputs/standardized/*.pptx", "description": "除页脚格式元数据外，不得修改标题或正文。", "verifier_check_id": "slide_and_content_preservation"},
        ],
        "difficulty": {
            "level": "medium",
            "rationale": "需要理解批量映射、检查三份异构比例演示稿、逐份调用工具，并同时满足内容保持、格式统一和副作用约束。",
            "calibration_status": "initial",
            "signals": {"meaningful_steps": 9, "tool_count": 3, "dependency_count": 6, "recoverable_failure_count": 3},
        },
        "expected_trajectory_length": {
            "meaningful_steps": {"min": 7, "max": 18},
            "tool_calls": {"min": 4, "max": 12},
            "input_tokens": {"min": 2500, "max": 12000},
            "output_tokens": {"min": 500, "max": 4000},
        },
        "language": {"instruction": "zh", "assets": "zh", "deliverables": "zh"},
        "provenance": [
            {"provenance_id": "prov_instruction", "component": "instruction", "source_kind": "hybrid", "source_ref": "tasks/20260719_nami_work_gold20_v1/source_packets/case_06.json", "transformation": "仅使用受限用户意图的脱敏任务类型和约束，由构建者重写为不含原文的合成任务说明。", "checked_at": "2026-07-20"},
            {"provenance_id": "prov_synthetic_inputs", "component": "input_asset", "source_kind": "synthetic", "source_ref": "environment/build_fixtures.py", "transformation": "从零生成三份无真实人员、组织、数据或用户文本的 PPTX、模板和样式表。", "checked_at": "2026-07-20"},
            {"provenance_id": "prov_environment", "component": "environment", "source_kind": "human", "source_ref": "environment/", "transformation": "人工定义离线工作区、可见工具、固定时间与精确路径边界。", "checked_at": "2026-07-20"},
            {"provenance_id": "prov_verifier", "component": "verifier", "source_kind": "human", "source_ref": "verifier/verify.py", "transformation": "独立实现 OOXML、内容、样式、几何、页脚和副作用检查，不导入候选工具。", "checked_at": "2026-07-20"},
            {"provenance_id": "prov_rubric", "component": "rubric", "source_kind": "human", "source_ref": "case.json", "transformation": "把批量格式修订目标拆成七项确定性验收门。", "checked_at": "2026-07-20"},
            {"provenance_id": "prov_reference_output", "component": "reference_output", "source_kind": "synthetic", "source_ref": "oracle/reference_output_manifest.json", "transformation": "可信 oracle 在固定输入上调用可见转换工具并经独立 verifier 验收。", "checked_at": "2026-07-20"},
        ],
        "license": [
            {"license_id": "license_synthetic_cc0", "component_refs": ["input_deck_market_brief", "input_deck_project_update", "input_deck_service_review", "brand_template", "style_map", "prov_reference_output"], "spdx_id": "CC0-1.0", "status": "cleared", "commercial_training_allowed": True, "attribution_required": False, "terms_ref": "https://creativecommons.org/publicdomain/zero/1.0/", "checked_at": "2026-07-20"},
            {"license_id": "license_internal_task_intent", "component_refs": ["prov_instruction"], "status": "conditional", "commercial_training_allowed": True, "attribution_required": False, "terms_ref": "internal-authorized-derived-intent-only", "checked_at": "2026-07-20"},
        ],
        "split": "development",
        "source_status": {"status": "synthetic_authorized", "evidence_complete": True, "authorization_status": "approved", "checked_at": "2026-07-20"},
        "contamination": {"status": "clear", "tags": ["fully_synthetic_assets", "no_public_benchmark_task", "derived_intent_only"], "upstream_task_ids": [], "asset_family_ids": ["case06_synthetic_presentation_family_v1"], "checked_at": "2026-07-20"},
        "resource_limits": {"cpu_cores": 2, "memory_mib": 1024, "disk_mib": 512, "wall_time_seconds": 900, "max_agent_steps": 40},
        "reset_entrypoint": "environment/reset.py",
        "oracle_entrypoint": "oracle/solve.py",
        "build_status": "built",
        "validation_status": validation_status,
        "admission_status": "not_reviewed",
    }
    spec["spec_sha256"] = canonical_spec_hash(spec)
    return spec


def write_json(path: Path, value: dict[str, Any]) -> None:
    staging = path.with_name(path.name + ".next")
    staging.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    staging.replace(path)


def build_manifest(spec: dict[str, Any]) -> dict[str, Any]:
    files = []
    for path in sorted(CASE_ROOT.rglob("*"), key=lambda item: item.relative_to(CASE_ROOT).as_posix()):
        relative = path.relative_to(CASE_ROOT).as_posix()
        if path.is_symlink():
            raise ValueError("formal_case_symlink_forbidden")
        if not path.is_file() or relative == "manifest.json":
            continue
        files.append({"path": relative, "sha256": sha256_file(path), "size_bytes": path.stat().st_size, "role": file_role(relative)})
    old_manifest = CASE_ROOT / "manifest.json"
    created_at = "2026-07-20T00:00:00Z"
    if old_manifest.is_file():
        old = json.loads(old_manifest.read_text(encoding="utf-8"))
        created_at = old.get("created_at", created_at)
    return {
        "schema_version": "nami_work_env_case_manifest_v1",
        "directory_contract_version": "nami_work_gold20_directory_v1",
        "task_id": "case_06",
        "case_version": "1.0.0",
        "spec_path": "case.json",
        "spec_sha256": spec["spec_sha256"],
        "created_at": created_at,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "status": "draft",
        "builder": {"name": "case06.build_metadata", "version": "1.0.0", "code_revision": "case06-uncommitted"},
        "files": files,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validation-status", choices=("not_run", "passed", "failed", "invalid"), required=True)
    args = parser.parse_args()
    spec = make_spec(args.validation_status)
    write_json(CASE_ROOT / "case.json", spec)
    write_json(CASE_ROOT / "manifest.json", build_manifest(spec))
    print(json.dumps({"spec_sha256": spec["spec_sha256"], "validation_status": args.validation_status, "manifest_status": "draft"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

