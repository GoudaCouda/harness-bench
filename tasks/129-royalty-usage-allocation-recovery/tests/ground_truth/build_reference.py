#!/usr/bin/env python3
"""Build reference outputs from hidden truth through the public workflow."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


TASK = Path(__file__).resolve().parents[2]


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="hb129-reference-") as temporary:
        workspace = Path(temporary) / "workspace"
        shutil.copytree(TASK / "workspace", workspace)
        spec = importlib.util.spec_from_file_location(
            "reference_royalty_outcome", TASK / "tests/test_outcome.py"
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load hidden royalty truth")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        settings = json.loads(
            (workspace / "policy/royalty_policy.json").read_text(encoding="utf-8")
        )
        plan = {
            "schema_version": 1,
            "statement_id": settings["statement_id"],
            "recovery_id": settings["recovery_id"],
            "source_checkpoint": module._checkpoint(),
            "actions": [
                module._expected_actions()[key]
                for key in sorted(module._expected_actions())
            ],
            "external_actions_executed": False,
        }
        (workspace / "royalty_allocation_plan.json").write_text(
            json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        shutil.copy2(TASK / "tests/reference/royalty_handoff.md", workspace / "royalty_handoff.md")
        for command in ("preview", "apply", "verify", "stage", "replay"):
            subprocess.run(
                ["python3", "royaltyctl.py", command, "royalty_allocation_plan.json"],
                cwd=workspace,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        reference = TASK / "tests/reference"
        (reference / "state").mkdir(parents=True, exist_ok=True)
        shutil.copy2(workspace / "royalty_allocation_plan.json", reference / "royalty_allocation_plan.json")
        for name in (
            "royalty_ledger.db", "royalty_verification.json",
            "internal_statement_receipt.json", "replay_report.json",
        ):
            shutil.copy2(workspace / "state" / name, reference / "state" / name)
        shutil.copy2(workspace / ".royalty_preview.json", reference / ".royalty_preview.json")


if __name__ == "__main__":
    main()
