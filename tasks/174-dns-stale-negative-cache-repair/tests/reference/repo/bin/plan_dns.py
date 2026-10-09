import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.dns_cache import plan_dns_responses

result = plan_dns_responses(json.loads((ROOT / "queries.json").read_text()), json.loads((ROOT / "policy.json").read_text()))
output = ROOT / "out"
output.mkdir(exist_ok=True)
for name in ("decisions", "summary"):
    (output / f"{name}.json").write_text(json.dumps(result[name], indent=2, sort_keys=True) + "\n")
