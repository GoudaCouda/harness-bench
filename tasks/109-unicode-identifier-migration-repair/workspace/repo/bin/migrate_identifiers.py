import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"src"))
from identifier_migrator import migrate_identifiers


def main():
    load=lambda name:json.loads((ROOT/f"{name}.json").read_text())
    result=migrate_identifiers(load("records"),load("reserved"),load("policy"))
    out=ROOT/"out"; out.mkdir(exist_ok=True)
    for name in ("records","conflicts"):
        (out/f"{name}.json").write_text(json.dumps(result[name],ensure_ascii=False,indent=2,sort_keys=True)+"\n")


if __name__=="__main__": main()
