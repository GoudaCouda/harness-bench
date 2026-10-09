import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"src"))
from restore_planner import plan_restore
def main():
 load=lambda n:json.loads((ROOT/f"{n}.json").read_text());result=plan_restore(load("snapshots"),load("destination"),load("request"));out=ROOT/"out";out.mkdir(exist_ok=True)
 for name in ("plan","summary"):(out/f"{name}.json").write_text(json.dumps(result[name],indent=2,sort_keys=True)+"\n")
if __name__=="__main__":main()
