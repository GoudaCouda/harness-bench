import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.api_compat import compare_api_schemas


inputs = {
    name: json.loads((ROOT / f"{name}.json").read_text(encoding="utf-8"))
    for name in ("old_schemas", "new_schemas", "policy")
}
result = compare_api_schemas(**inputs)
output = ROOT / "out"
output.mkdir(exist_ok=True)
for name in ("findings", "summary"):
    (output / f"{name}.json").write_text(
        json.dumps(result[name], indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
