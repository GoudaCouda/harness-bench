import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.cluster_retry import plan_cluster_retries


inputs = {
    name: json.loads((ROOT / f"{name}.json").read_text(encoding="utf-8"))
    for name in ("requests", "slots", "policy")
}
result = plan_cluster_retries(**inputs)
output = ROOT / "out"
output.mkdir(exist_ok=True)
for name in ("decisions", "slots", "summary"):
    (output / f"{name}.json").write_text(
        json.dumps(result[name], indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
