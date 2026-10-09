import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.dpop_policy import verify_dpop


inputs = {name: json.loads((ROOT / f"{name}.json").read_text()) for name in ("requests", "proofs", "replay_cache", "policy")}
result = verify_dpop(**inputs)
output = ROOT / "out"
output.mkdir(exist_ok=True)
for name in ("decisions", "replay_cache", "summary"):
    (output / f"{name}.json").write_text(json.dumps(result[name], indent=2, sort_keys=True) + "\n")
