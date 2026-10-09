#!/usr/bin/env python3
"""Build the deterministic reference DOCX for case_03."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


def load_tool(path: Path):
    spec = importlib.util.spec_from_file_location("case03_docx_writer", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load docx writer")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_spec(workspace: Path) -> dict:
    hospital = json.loads((workspace / "input/hospital_header.json").read_text(encoding="utf-8"))
    registry = json.loads((workspace / "input/equipment_registry.json").read_text(encoding="utf-8"))
    standard = json.loads((workspace / "input/inspection_standard.json").read_text(encoding="utf-8"))
    devices = []
    for source in registry["devices"]:
        item = dict(source)
        item["inspection_items"] = list(standard["common_items"]) + list(standard["device_type_items"][source["device_type"]])
        devices.append(item)
    return {"hospital": hospital, "devices": devices}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    module = load_tool(workspace / "tools/docx_writer.py")
    module.build_docx(build_spec(workspace), workspace / "output/monitoring_equipment_inspection_form.docx")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
