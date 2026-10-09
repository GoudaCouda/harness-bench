#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json
from datetime import datetime,timedelta
from pathlib import Path
ROOT=Path.cwd()
def j(n):return json.loads((ROOT/n).read_text(encoding="utf-8"))
def dt(s):return datetime.fromisoformat(s)
def main():
 p=argparse.ArgumentParser();p.add_argument("command",choices=("verify",));p.add_argument("plan");a=p.parse_args();plan=json.loads(Path(a.plan).read_text());base=j("baseline_plan.json");notice=j("round2_update_notice.json");cap=j("team_capacity.json");checkpoint=j("execution_checkpoint.json");problems=[]
 cur={x.get("decision_id"):x for x in plan.get("decisions",[]) if isinstance(x,dict)};old={x["decision_id"]:x for x in base["decisions"]};regions={r["region"]:r for r in csv.DictReader((ROOT/"regional_constraints.csv").open())};comms={(r["region"],r["audience"]):r for r in csv.DictReader((ROOT/"communications_matrix.csv").open())};exposure={r["region"]:r for r in csv.DictReader((ROOT/"exposure_forecast.csv").open())}
 if plan.get("notice_id")!=notice["notice_id"]:problems.append("plan does not record active notice")
 expected=set(old)|{f"{r}-supervisor_sampling" for r,v in exposure.items() if int(v["monthly_exception_cases"])>=int(v["sampling_threshold"])}
 if set(cur)!=expected:problems.append(f"decision ID set mismatch; expected {sorted(expected)}")
 for did in checkpoint["completed_decision_ids"]:
  if cur.get(did)!=old.get(did):problems.append(f"{did}: completed decision changed")
 for reg in ("AMER","EU","APAC"):
  train=cur.get(f"{reg}-support_training",{});launch=cur.get(f"{reg}-launch_gate",{});communication=cur.get(f"{reg}-customer_comms",{})
  if "refund exception drill v3" not in str(train.get("artifact","")).casefold():problems.append(f"{reg}: training lacks drill v3")
  try:
   start,end=dt(launch["start"]),dt(launch["end"]);constraint=regions[reg];latest=notice.get("constraint_overrides",{}).get(reg,{}).get("latest_launch_gate",constraint["latest_launch_gate"])
   if start<dt(constraint["earliest_launch_gate"]) or end>dt(latest):problems.append(f"{reg}: launch outside active window")
   if start.date().isoformat() in constraint["blackout_dates"].split(";"):problems.append(f"{reg}: launch on blackout")
   lead=(start-dt(communication["end"])).total_seconds()/3600;minimum=int(comms[(reg,"enterprise_admins")]["minimum_notice_hours"])
   if lead<minimum:problems.append(f"{reg}: communications lead {lead}h below {minimum}h")
   if dt(train["end"])>start:problems.append(f"{reg}: training ends after launch")
  except (KeyError,ValueError,TypeError):problems.append(f"{reg}: invalid timestamps or missing core decision")
 if "EU-launch_gate" in cur:
  if dt(cur["EU-launch_gate"]["start"])-dt(old["EU-launch_gate"]["start"])<timedelta(hours=48):problems.append("EU launch delay below 48 hours")
 for did,row in cur.items():
  if row.get("region")=="APAC" and did not in checkpoint["completed_decision_ids"] and row.get("owner")=="Priya":problems.append(f"{did}: unavailable APAC owner")
  owner=cap["owners"].get(row.get("owner"),{})
  try:
   if not owner.get("available_from") or not owner.get("available_through") or not (datetime.fromisoformat(owner["available_from"]).date()<=dt(row["start"]).date()<=dt(row["end"]).date()<=datetime.fromisoformat(owner["available_through"]).date()):problems.append(f"{did}: owner unavailable for scheduled interval")
  except (KeyError,ValueError,TypeError):problems.append(f"{did}: owner availability cannot be verified")
  for dep in row.get("dependencies",[]):
   if dep not in cur or dt(cur[dep]["end"])>dt(row["start"]):problems.append(f"{did}: dependency {dep} incomplete")
 for reg,v in exposure.items():
  if int(v["monthly_exception_cases"])<int(v["sampling_threshold"]):continue
  did=f"{reg}-supervisor_sampling";sample=cur.get(did,{});train=cur.get(f"{reg}-support_training",{});launch=cur.get(f"{reg}-launch_gate",{})
  try:
   if sample.get("owner") not in cap["workstream_owners"]["supervisor_sampling"]:problems.append(f"{did}: owner not eligible")
   if (dt(sample["end"])-dt(sample["start"])).total_seconds()!=7200:problems.append(f"{did}: sampling must last two hours")
   if dt(sample["start"])<dt(train["end"]) or dt(sample["end"])>dt(launch["start"]):problems.append(f"{did}: sampling not between training and launch")
   if did not in launch.get("dependencies",[]):problems.append(f"{reg}: launch missing sampling dependency")
  except (KeyError,ValueError,TypeError):problems.append(f"{did}: malformed sampling decision")
 intervals=[]
 for did,row in cur.items():
  if row.get("owner"):
   try:intervals.append((row["owner"],dt(row["start"]),dt(row["end"]),did))
   except Exception:pass
 for i,x in enumerate(intervals):
  for y in intervals[i+1:]:
   if x[0]==y[0] and max(x[1],y[1])<min(x[2],y[2]):problems.append(f"owner overlap: {x[3]} / {y[3]}")
 print(json.dumps({"status":"PASS" if not problems else "FAIL","problems":problems},indent=2));return 0 if not problems else 2
if __name__=="__main__":raise SystemExit(main())
