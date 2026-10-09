import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from goaway_recovery import plan_goaway_retries  # noqa: E402


def main():
    def load(name):
        return json.loads((ROOT / f"{name}.json").read_text())

    result = plan_goaway_retries(load("requests"), load("goaway"), load("policy"))
    out = ROOT / "out"
    out.mkdir(exist_ok=True)
    for name in ("decisions", "summary"):
        (out / f"{name}.json").write_text(json.dumps(result[name], indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
