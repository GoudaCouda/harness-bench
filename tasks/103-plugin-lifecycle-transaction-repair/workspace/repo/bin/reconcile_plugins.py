import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from plugin_lifecycle import reconcile_plugins


def main():
    load = lambda name: json.loads((ROOT / f"{name}.json").read_text())
    result = reconcile_plugins(load("state"), load("catalog"), load("request"), load("faults"))
    out = ROOT / "out"; out.mkdir(exist_ok=True)
    for name in ("state", "journal"):
        (out / f"{name}.json").write_text(json.dumps(result[name], indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
