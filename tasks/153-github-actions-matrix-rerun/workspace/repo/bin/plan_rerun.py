import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"src"))
from rerun_planner import plan_rerun
def main():
 load=lambda n:json.loads((ROOT/f"{n}.json").read_text());r=plan_rerun(load("workflow"),load("runs"),load("policy"));o=ROOT/"out";o.mkdir(exist_ok=True)
 for n in ("plan","summary"):(o/f"{n}.json").write_text(json.dumps(r[n],indent=2,sort_keys=True)+"\n")
if __name__=="__main__":main()
