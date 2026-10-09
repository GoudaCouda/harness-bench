#!/usr/bin/env python3
import argparse,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def rows(path):return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
def inspect():
 c=json.loads((ROOT/"state/checkpoint.json").read_text());p={x["record_id"] for x in rows(ROOT/"state/processed.jsonl")}
 allrows=[x for f in ("logs/service.log.1","logs/service.log") for x in rows(ROOT/f)]
 return c,p,allrows
def main():
 ap=argparse.ArgumentParser();ap.add_argument("command",choices=("inspect","recover"));ap.add_argument("--acknowledge-ledger-ahead",action="store_true");a=ap.parse_args()
 c,processed,allrows=inspect();physical=[x["record_id"] for x in allrows]
 ahead=any(x in processed for x in physical[physical.index(c["last_record_id"])+1:])
 if a.command=="inspect":print(json.dumps({"checkpoint":c,"processed":sorted(processed),"ledger_ahead":ahead},indent=2));return
 if ahead and not a.acknowledge_ledger_ahead:raise SystemExit("refusing recovery: ledger is ahead of checkpoint; pass --acknowledge-ledger-ahead")
 new=[x for x in allrows if x["record_id"] not in processed]
 out=ROOT/"out/recovered.jsonl";out.parent.mkdir(exist_ok=True);out.write_text("".join(json.dumps(x,sort_keys=True)+"\n" for x in new))
 with (ROOT/"state/processed.jsonl").open("a") as f:
  for x in new:f.write(json.dumps({"record_id":x["record_id"],"processed_at":x["ts"]},sort_keys=True)+"\n")
 active=ROOT/"logs/service.log";s=active.stat();last=allrows[-1]["record_id"]
 nc={"schema_version":1,"path":"logs/service.log","device":s.st_dev,"inode":s.st_ino,"byte_offset":active.stat().st_size,"last_record_id":last}
 (ROOT/"state/checkpoint.json").write_text(json.dumps(nc,indent=2,sort_keys=True)+"\n")
 print(json.dumps({"new_record_ids":[x["record_id"] for x in new],"checkpoint":nc},indent=2))
if __name__=="__main__":main()
