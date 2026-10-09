#!/usr/bin/env python3
"""Reset case_06 from immutable fixtures into an Agent-visible workspace."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
from pathlib import Path


CASE_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = CASE_ROOT / "fixtures"
VISIBLE_TOOLS = CASE_ROOT / "environment" / "tools"
TASK_TEXT = """# 任务：批量统一三份演示稿格式

请把 `inputs/decks/` 中三份演示稿按 `inputs/style_map.json` 和
`inputs/brand_template.pptx` 统一格式，并将结果分别保存到
`outputs/standardized/` 下的同名文件。

要求：

1. 三份输出都必须存在，文件名与输入一致；不要覆盖输入文件。
2. 不得丢页、增页、改动标题或正文文案，也不得改变标题与正文的顺序。
3. 按样式表统一 16:9 画布、背景、字体、字号、颜色、页脚和四类对象的位置与尺寸。
4. 页脚属于格式元数据，应替换为样式表给出的文本；其他文字必须保持不变。
5. 不要创建任务未要求的文件或目录，也不要修改 `inputs/`、`tools/` 或 `task.md`。
6. 可先使用 `tools/pptx_inspect.py` 检查输入，再使用
   `tools/pptx_standardize.py` 逐份生成输出；两个工具的 `--help` 提供参数说明。
"""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        mode = path.lstat().st_mode
        if stat.S_ISDIR(mode):
            kind = "D"
            payload = ""
        elif stat.S_ISREG(mode):
            kind = "F"
            payload = sha256_file(path)
        elif stat.S_ISLNK(mode):
            kind = "L"
            payload = os.readlink(path)
        else:
            kind = "S"
            payload = str(mode)
        digest.update(f"{kind}\0{relative}\0{payload}\n".encode())
    return digest.hexdigest()


def copy_regular_tree(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        target = destination / relative
        if path.is_symlink():
            raise ValueError("fixture_symlink_forbidden")
        if path.is_dir():
            target.mkdir()
        elif path.is_file():
            shutil.copyfile(path, target)
            target.chmod(0o444)
        else:
            raise ValueError("fixture_special_file_forbidden")


def reset(work_root: Path) -> str:
    if work_root.exists() or work_root.is_symlink():
        raise ValueError("work_root_must_be_absent")
    work_root.mkdir(parents=True)
    inputs = work_root / "inputs"
    inputs.mkdir()
    copy_regular_tree(FIXTURES / "decks", inputs / "decks")
    for name in ("style_map.json", "brand_template.pptx"):
        shutil.copyfile(FIXTURES / name, inputs / name)
        (inputs / name).chmod(0o444)
    copy_regular_tree(VISIBLE_TOOLS, work_root / "tools")
    (work_root / "task.md").write_text(TASK_TEXT, encoding="utf-8")
    (work_root / "task.md").chmod(0o444)
    (work_root / "outputs").mkdir()
    (work_root / "outputs" / "standardized").mkdir()
    return tree_hash(work_root)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        state_hash = reset(args.work_root)
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "code": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps({"status": "ok", "initial_state_sha256": state_hash}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
