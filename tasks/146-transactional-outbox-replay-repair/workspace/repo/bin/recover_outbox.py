import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"src"))
from outbox_recovery import recover_outbox

def main():
    load=lambda name:json.loads((ROOT/f"{name}.json").read_text(encoding="utf-8"))
    result=recover_outbox(load("events"),load("receipts"),load("policy")); out=ROOT/"out"; out.mkdir(exist_ok=True)
    for name in ("state","actions"):
        (out/f"{name}.json").write_text(json.dumps(result[name],indent=2,sort_keys=True)+"\n",encoding="utf-8")

if __name__=="__main__": main()
