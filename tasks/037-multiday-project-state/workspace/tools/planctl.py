#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,re
from pathlib import Path

ROOT=Path.cwd()
def j(name): return json.loads((ROOT/name).read_text(encoding="utf-8"))
def ids(value): return set(re.findall(r"[A-Z]{2,}-\d+",str(value or "")))
def verify(plan_path,register_path,risk_path):
    plan=json.loads(Path(plan_path).read_text(encoding="utf-8")); rules=j("dependency_map.json"); ms={m.get("id"):m for m in plan.get("milestones",[]) if isinstance(m,dict)}; problems=[]
    if set(ms)!=set(f"M{i}" for i in range(1,9)): problems.append("milestone IDs must remain M1..M8")
    for mid in ("M1","M2"):
        if ms.get(mid,{}).get("status")!="completed": problems.append(f"{mid}: completed history changed")
    option=plan.get("recovery_option"); opt=rules["recovery_options"].get(option)
    if not opt: problems.append("choose a documented recovery_option")
    else:
        if ms.get("M3",{}).get("day",0)<opt["M3_not_before"]: problems.append("M3 begins before selected recovery option permits")
        expected=sum(int(x.get("cost_usd",0)) for x in ms.values())+int(opt["incremental_cost_usd"])
        if plan.get("budget_usd",{}).get("planned")!=expected: problems.append(f"planned budget must equal derived cost {expected}")
        if expected>plan.get("budget_usd",{}).get("ceiling",0): problems.append("selected recovery exceeds budget ceiling")
    calendars={r["owner"]:r for r in csv.DictReader((ROOT/"owner_calendar.csv").open())}; rule_by={r["milestone"]:r for r in rules["rules"]}
    for mid,m in ms.items():
        if mid in ("M1","M2"): continue
        if mid=="M3" and m.get("status")!="planned": problems.append("M3 failed checkpoint must be replanned")
        owner=m.get("owner"); cal=calendars.get(owner,{}); end=m.get("day",0)+m.get("duration_days",0)-1
        if owner not in rule_by.get(mid,{}).get("eligible_owners",[]): problems.append(f"{mid}: ineligible owner {owner}")
        if not cal or m.get("day",0)<int(cal.get("available_from_day",999)) or end>int(cal.get("available_through_day",-1)): problems.append(f"{mid}: owner unavailable for full interval")
        for dep in m.get("depends_on",[]):
            d=ms.get(dep,{})
            if m.get("day",0)<d.get("day",0)+d.get("duration_days",0)+rules["minimum_gap_days"]: problems.append(f"{mid}: starts before {dep} clears dependency gap")
        required=[]
        if mid=="M3" and opt: required.append(opt["evidence_id"])
        gate=rule_by.get(mid,{}).get("required_gate","")
        required += [x for x in ("PRIV-77","SEC-204") if x in gate]
        if any(x not in str(m.get("condition","")) for x in required): problems.append(f"{mid}: condition omits applicable evidence ID")
    freeze=rules["launch_blackout"]; launch=ms.get("M8",{}).get("day",0)
    if freeze["start_day"]<=launch<=freeze["end_day"]: problems.append("M8 falls inside launch freeze")
    # The task deliberately leaves the conflict record's prose/schema open.  Accept
    # either bare evidence IDs or review-friendly descriptions that cite both IDs.
    conflict_text=json.dumps(plan.get("open_conflicts",[]),sort_keys=True)
    if not all(x in conflict_text for x in ("SALES-31","PRIV-77")): problems.append("Sales/Privacy conflict not preserved")
    rows=list(csv.DictReader(Path(register_path).open(encoding="utf-8",newline="")))
    if [r.get("decision_id") for r in rows[:3]] != ["DEC-001","DEC-002","DEC-003"]: problems.append("decision history prefix changed")
    decision_ids=[r.get("decision_id") for r in rows]
    if len(decision_ids)!=len(set(decision_ids)): problems.append("decision_id values must be unique; append a new ID instead of duplicating history")
    if not any(r.get("supersedes")=="DEC-002" and "OPS-61" in ids(r.get("evidence_ids")) for r in rows[3:]): problems.append("append a recovery decision that supersedes DEC-002 and cites failed checkpoint OPS-61")
    if not any({"SALES-31","PRIV-77"}.issubset(ids(r.get("evidence_ids"))) for r in rows[3:]): problems.append("append an open conflict decision citing both SALES-31 and PRIV-77")
    try: risks=list(csv.DictReader(Path(risk_path).open(encoding="utf-8",newline="")))
    except Exception: risks=[]
    evidence=set().union(*(ids(r.get("evidence_ids")) for r in risks)) if risks else set()
    required_risks={"PRIV-77", opt["evidence_id"] if opt else "", "CS-90"}
    if not required_risks.issubset(evidence): problems.append(f"risk evidence must cover {sorted(x for x in required_risks if x)}")
    print(json.dumps({"status":"PASS" if not problems else "FAIL","problems":problems},indent=2)); return not problems
def main():
    p=argparse.ArgumentParser();p.add_argument("command",choices=("verify",));p.add_argument("plan");p.add_argument("register");p.add_argument("risks");a=p.parse_args();return 0 if verify(a.plan,a.register,a.risks) else 2
if __name__=="__main__":raise SystemExit(main())
