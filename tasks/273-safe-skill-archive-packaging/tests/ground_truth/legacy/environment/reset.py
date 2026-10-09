from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from pathlib import Path


TASK_TEXT = """# 任务：校验并打包可安装技能包

请检查 `input/calendar_briefing_skill/`。保持整个 `input/` 与本任务文件不变，只在
`output/` 交付一个 `calendar_briefing_skill.zip`。

压缩包必须满足：

1. 顶层目录固定为 `calendar_briefing_skill/`。
2. 只包含 `SKILL.md`、`assets/template.txt`、`scripts/main.py` 和补齐后的 `manifest.json`。
3. `manifest.json` 使用 `manifest.template.json` 中的固定元数据；`files` 按
   `SKILL.md`、`assets/template.txt`、`scripts/main.py` 的顺序记录相对路径、
   SHA-256 和字节数。
4. 不得打包 `.private/`、`manifest.template.json` 或任何其他文件。
5. ZIP 中不得出现重复条目、绝对路径、路径穿越、反斜线、符号链接或特殊文件。
6. 交付前使用可用校验工具确认清单与压缩包可安全解包并可运行。
"""


def hash_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        info = path.lstat()
        kind = "d" if stat.S_ISDIR(info.st_mode) else "f" if stat.S_ISREG(info.st_mode) else "x"
        digest.update(f"{kind}\0{relative}\0{stat.S_IMODE(info.st_mode):04o}\0".encode())
        if kind == "f":
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def copy_regular_tree(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, mode=0o755)
    destination.chmod(0o755)
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        info = path.lstat()
        target = destination / relative
        if stat.S_ISDIR(info.st_mode):
            target.mkdir(mode=0o755)
            target.chmod(0o755)
        elif stat.S_ISREG(info.st_mode):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
            target.chmod(0o444)
        else:
            raise ValueError("fixture_contains_non_regular_entry")


def reset(case_root: Path, workspace: Path) -> dict[str, str]:
    if workspace.exists() or workspace.is_symlink():
        raise ValueError("workspace_must_not_exist")
    workspace.mkdir(parents=True, mode=0o755)
    workspace.chmod(0o755)
    task_path = workspace / "TASK.md"
    task_path.write_text(TASK_TEXT, encoding="utf-8")
    task_path.chmod(0o444)
    input_root = workspace / "input"
    input_root.mkdir(mode=0o755)
    input_root.chmod(0o755)
    copy_regular_tree(
        case_root / "fixtures/source_skill/calendar_briefing_skill",
        workspace / "input/calendar_briefing_skill",
    )
    output_root = workspace / "output"
    output_root.mkdir(mode=0o755)
    output_root.chmod(0o755)
    state = hash_tree(workspace)
    return {"schema_version": "case19_reset_result_v1", "initial_state_sha256": state}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    result = reset(args.case_root, args.workspace)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    os.umask(0o022)
    raise SystemExit(main())
