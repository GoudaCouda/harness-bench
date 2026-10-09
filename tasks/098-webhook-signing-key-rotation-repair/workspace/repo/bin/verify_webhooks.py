import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from webhook_verifier import verify_batch


def main():
    load = lambda name: json.loads((ROOT / f"{name}.json").read_text(encoding="utf-8"))
    result = verify_batch(load("deliveries"), load("keyring"), load("policy"), load("checkpoint"))
    out = ROOT / "out"
    out.mkdir(exist_ok=True)
    (out / "decisions.json").write_text(json.dumps(result["decisions"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "checkpoint.json").write_text(json.dumps(result["checkpoint"], indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
