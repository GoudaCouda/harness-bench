import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.watch_reconciler import reconcile_batch


def main():
    policy = json.loads((ROOT / "policy.json").read_text(encoding="utf-8"))
    checkpoint = json.loads((ROOT / "checkpoint.json").read_text(encoding="utf-8"))
    batches = json.loads((ROOT / "batches.json").read_text(encoding="utf-8"))
    ledger = []
    for batch in batches:
        result = reconcile_batch(checkpoint, batch, policy)
        ledger.append({"seq": batch["seq"], "actions": result["actions"]})
        checkpoint = result["checkpoint"]
    out = ROOT / "out"
    out.mkdir(exist_ok=True)
    (out / "actions.json").write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out / "checkpoint.json").write_text(json.dumps(checkpoint, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
