from __future__ import annotations
import subprocess
from pathlib import Path
from typing import Any
def apply_reference(workspace:Path,runtime:Path,runtime_state:dict[str,Any])->None:
 del runtime,runtime_state
 for command in (["fence"],["quiesce"],["confirm-checkpoints"],["cancel"],["apply-cleanup","cleanup_plan.csv"]):
  subprocess.run(["python3","-B","tools/privacyctl.py",*command],cwd=workspace,check=True,stdout=subprocess.PIPE,text=True)
