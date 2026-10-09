import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.early_data import plan_early_data

inputs = {
    name: json.loads((ROOT / f"{name}.json").read_text(encoding="utf-8"))
    for name in ("requests", "session", "policy")
}
result = plan_early_data(**inputs)
output = ROOT / "out"
output.mkdir(exist_ok=True)
for name in ("decisions", "summary"):
    (output / f"{name}.json").write_text(
        json.dumps(result[name], indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
