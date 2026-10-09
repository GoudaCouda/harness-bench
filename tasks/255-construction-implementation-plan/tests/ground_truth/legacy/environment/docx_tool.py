"""CLI for inspecting and rendering editable DOCX files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from docx_ooxml import inspect_docx, render_from_template


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("--input", type=Path, required=True)
    render = sub.add_parser("render")
    render.add_argument("--template", type=Path, required=True)
    render.add_argument("--plan", type=Path, required=True)
    render.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "inspect":
        print(json.dumps(inspect_docx(args.input), ensure_ascii=False, sort_keys=True))
        return 0
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    render_from_template(args.template, args.output, plan["elements"])
    print(json.dumps({"output": str(args.output), "editable_ooxml": True}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
