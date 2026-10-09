import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from stream_consumer import consume_segments


def main():
    load = lambda name: json.loads((ROOT / name).read_text(encoding="utf-8"))
    result = consume_segments(load("checkpoint.json"), load("segments.json"), load("policy.json"))
    out = ROOT / "out"
    out.mkdir(exist_ok=True)
    for name in ("records", "quarantine", "checkpoint"):
        (out / f"{name}.json").write_text(json.dumps(result[name], indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
