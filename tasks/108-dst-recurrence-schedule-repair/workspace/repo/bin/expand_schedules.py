import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from recurrence_engine import expand_schedules


def main():
    load=lambda name: json.loads((ROOT/f"{name}.json").read_text())
    result=expand_schedules(load("schedules"),load("window"),load("overrides"))
    out=ROOT/"out"; out.mkdir(exist_ok=True)
    for name in ("occurrences","skipped"):
        (out/f"{name}.json").write_text(json.dumps(result[name],indent=2,sort_keys=True)+"\n")


if __name__=="__main__": main()
