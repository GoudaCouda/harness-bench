from __future__ import annotations
import json, os
from pathlib import Path
from typing import Any

def _baseline(workspace: Path):
    root=workspace/"repo"; rotated=root/"logs/service.log.1"; lines=rotated.read_bytes().splitlines(keepends=True)
    stat=rotated.stat()
    checkpoint={"schema_version":1,"path":"logs/service.log.1","device":stat.st_dev,"inode":stat.st_ino,"byte_offset":len(lines[0])+len(lines[1]),"last_record_id":"r401"}
    target=root/"state/checkpoint.json";target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(checkpoint,indent=2,sort_keys=True)+"\n")
    return checkpoint

def prepare_runtime(context: dict[str, Any]) -> dict[str, Any]:
    return {"baseline_checkpoint":_baseline(Path(context["workspace"]))}

def after_round(context: dict[str, Any], runtime_state: dict[str, Any], adapter_result: Any) -> dict[str, Any]:
    del context,adapter_result;return runtime_state

def cleanup_runtime(context: dict[str, Any], runtime_state: dict[str, Any]) -> None:
    del context,runtime_state
