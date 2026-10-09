import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"src"))
from trace_context import propagate_contexts

def main():
    load=lambda name:json.loads((ROOT/f"{name}.json").read_text(encoding="utf-8"))
    result=propagate_contexts(load("requests"),load("policy")); out=ROOT/"out"; out.mkdir(exist_ok=True)
    for name in ("decisions","metrics"):
        (out/f"{name}.json").write_text(json.dumps(result[name],indent=2,sort_keys=True)+"\n",encoding="utf-8")

if __name__=="__main__": main()
