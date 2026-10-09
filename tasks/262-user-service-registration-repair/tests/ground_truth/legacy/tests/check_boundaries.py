from __future__ import annotations

import argparse
import ast
import hashlib
import json
import locale
from pathlib import Path


OLD_TREE_SHA256 = "dfab9e9f0e67abdc631585e084a77122b619c7636077b06246191e91ca07d511"
FORBIDDEN_CONTROLLER_IMPORTS = {"importlib", "nami_service", "runpy"}
FORBIDDEN_CONTROLLER_CALLS = {"__import__", "compile", "eval", "exec"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check case_08 isolation boundaries")
    parser.add_argument("--topic-root", required=True, type=Path)
    parser.add_argument("--case-dir", required=True, type=Path)
    return parser.parse_args()


def old_tree_hash(topic_root: Path) -> str:
    old_case = (
        topic_root
        / "artifacts/envs/nami_work_gold20_history/case_08_isolation_v1"
    )
    lines: list[str] = []
    locale.setlocale(locale.LC_COLLATE, "")
    paths = [item for item in old_case.rglob("*") if item.is_file()]
    for path in sorted(paths, key=lambda item: locale.strxfrm(item.as_posix())):
        relative = path.relative_to(old_case).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {relative}\n")
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def controller_ast_checks(controller: Path) -> dict[str, bool]:
    tree = ast.parse(controller.read_text(encoding="utf-8"), filename=str(controller))
    imported: set[str] = set()
    called: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".", 1)[0])
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called.add(node.func.id)
    return {
        "no_candidate_or_dynamic_import": not imported.intersection(
            FORBIDDEN_CONTROLLER_IMPORTS
        ),
        "no_exec_eval_compile": not called.intersection(FORBIDDEN_CONTROLLER_CALLS),
    }


def main() -> int:
    args = parse_args()
    topic_root = args.topic_root.resolve(strict=True)
    case_dir = args.case_dir.resolve(strict=True)
    python_files = sorted(case_dir.rglob("*.py"))
    syntax_ok = True
    for path in python_files:
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeError):
            syntax_ok = False
    symlinks = [path for path in case_dir.rglob("*") if path.is_symlink()]
    controller = case_dir / "verifier/controller.py"
    controller_checks = controller_ast_checks(controller)
    adapter_text = (case_dir / "environment/runtime/adapter.py").read_text(
        encoding="utf-8"
    )
    dockerfile = (case_dir / "environment/Sandbox.Dockerfile").read_text(
        encoding="utf-8"
    )
    launcher = (case_dir / "tests/create_sandbox.py").read_text(encoding="utf-8")
    reset_text = (case_dir / "environment/reset.py").read_text(encoding="utf-8")
    state_hash_text = (case_dir / "environment/state_hash.py").read_text(
        encoding="utf-8"
    )
    contract_envelope = json.loads(
        (case_dir / "environment/sandbox_contract.json").read_text(encoding="utf-8")
    )
    contract_digest = hashlib.sha256(
        json.dumps(
            contract_envelope["contract"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    generated_caches = [
        path
        for path in case_dir.rglob("*")
        if path.name == "__pycache__" or path.suffix == ".pyc"
    ]
    dynamic_literals = (
        '"nami_work_gold20_v1"',
        '"20260719_nami_work_gold20_v1"',
    )
    checks = {
        "all_python_ast_valid": syntax_ok,
        "no_symlinks": not symlinks,
        "no_generated_python_cache": not generated_caches,
        "old_sealed_case_unchanged": old_tree_hash(topic_root) == OLD_TREE_SHA256,
        "controller_no_candidate_import": controller_checks[
            "no_candidate_or_dynamic_import"
        ],
        "controller_no_exec_eval_compile": controller_checks["no_exec_eval_compile"],
        "candidate_import_only_in_sandbox_adapter": (
            'importlib.import_module("nami_service.users")' in adapter_text
        ),
        "sandbox_image_copies_only_runtime": (
            "COPY runtime/ /opt/case08-runtime/" in dockerfile
            and "COPY fixtures" not in dockerfile
            and "COPY oracle" not in dockerfile
            and "COPY verifier" not in dockerfile
            and "COPY tests" not in dockerfile
        ),
        "sandbox_contract_hash_canonical": (
            contract_envelope.get("contract_sha256") == contract_digest
        ),
        "sandbox_contract_hash_labelled": (
            "agent_sft.sandbox_contract_sha256" in dockerfile
            and "agent_sft.sandbox_contract_sha256" in launcher
            and "agent_sft.sandbox_contract_sha256" in controller.read_text(
                encoding="utf-8"
            )
        ),
        "static_code_has_no_run_or_host_literal": not any(
            literal in "\n".join((dockerfile, launcher, controller.read_text(encoding="utf-8")))
            for literal in dynamic_literals
        ),
        "launcher_network_none": (
            '"--network"' in launcher and 'contract["network_mode"]' in launcher
        ),
        "launcher_no_ports": '"--publish"' not in launcher and '"-p"' not in launcher,
        "launcher_readonly_nonroot": (
            '"--read-only"' in launcher
            and '"--user"' in launcher
            and '"--cap-drop"' in launcher
            and '"no-new-privileges:true"' in launcher
        ),
        "launcher_workspace_only_mount": (
            "dst=/workspace" in launcher
            and "dst=/case" not in launcher
            and "docker.sock" not in launcher
            and "workspace.parent != root" in launcher
            and "require_no_symlink_components" in launcher
        ),
        "controller_rejects_all_artifacts": (
            "IGNORED_NAMES" not in controller.read_text(encoding="utf-8")
            and "IGNORED_SUFFIXES" not in controller.read_text(encoding="utf-8")
            and "IGNORED_NAMES" not in state_hash_text
            and "IGNORED_SUFFIXES" not in state_hash_text
            and "runtime_unexpected_files" in controller.read_text(encoding="utf-8")
        ),
        "reset_exposes_fixture_only": (
            "shutil.copytree(fixture, target" in reset_text
            and "oracle" not in reset_text
            and "verifier" not in reset_text
            and "validation" not in reset_text
        ),
    }
    valid = all(checks.values())
    print(
        json.dumps(
            {
                "schema_version": "case08_isolation_boundary_check_v1",
                "valid": valid,
                "checks": checks,
                "python_file_count": len(python_files),
                "old_tree_sha256": old_tree_hash(topic_root),
            },
            sort_keys=True,
        )
    )
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
