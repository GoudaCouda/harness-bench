from pathlib import Path
from typing import Any
import json,subprocess
def apply_reference(workspace:Path,runtime:Path,runtime_state:dict[str,Any])->None:
 del runtime
 (workspace/"repo/state/checkpoint.json").write_text(json.dumps(runtime_state["baseline_checkpoint"],indent=2,sort_keys=True)+"\n")
 subprocess.run(["python3","tools/tailer_recovery.py","recover","--acknowledge-ledger-ahead"],cwd=workspace/"repo",check=True,stdout=subprocess.PIPE,text=True)
