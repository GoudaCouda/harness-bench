import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"src"))
from field_ownership import apply_intents

def main():
    load=lambda name:json.loads((ROOT/f"{name}.json").read_text(encoding="utf-8"))
    result=apply_intents(load("live"),load("ownership"),load("defaults"),load("intents"),load("policy")); out=ROOT/"out"; out.mkdir(exist_ok=True)
    for name in ("object","ownership","decisions"):
        (out/f"{name}.json").write_text(json.dumps(result[name],indent=2,sort_keys=True)+"\n",encoding="utf-8")

if __name__=="__main__": main()
