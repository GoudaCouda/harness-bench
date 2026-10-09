#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json
from datetime import datetime
from pathlib import Path
ROOT=Path.cwd()
def load(n):return json.loads((ROOT/n).read_text(encoding="utf-8"))
def derive(aid):
 req=load("release_request.json");hist=load("repo_history.json");reg=load("artifact_registry.json");sboms=load("sbom_records.json")["records"];base=load("base_image_policy.json");art=next((x for x in reg["artifacts"] if x["artifact_id"]==aid),{});problems=[]
 tag=next((x for x in hist["tags"] if x["tag"]==req["tag"]),{});parents=[next((x for x in reg["artifacts"] if x["artifact_id"]==pid),{}) for pid in art.get("parents",[])];pd=[x.get("digest") for x in parents]
 if tag.get("commit")!=req["requested_commit"] or not tag.get("signed"):problems.append("tag mismatch")
 if art.get("kind")!="bundle" or art.get("package")!=req["package"] or art.get("version")!=req["version"] or art.get("commit")!=tag.get("commit") or art.get("install")!="pass":problems.append("bundle request mismatch")
 locked=req["component_lock"]
 if {x.get("package"):x.get("commit") for x in parents}!=locked:problems.append("component lock mismatch")
 sigs={x["signature_id"]:x for x in reg["signatures"]}
 for x in parents+[art]:
  s=sigs.get(x.get("signature_id"),{})
  if not s.get("verified") or s.get("artifact_digest")!=x.get("digest") or s.get("identity")!=req["required_builder"]:problems.append(f"signature mismatch for {x.get('artifact_id')}")
 att=next((x for x in reg["attestations"] if x["attestation_id"]==art.get("attestation_id")),{})
 if not att.get("verified") or att.get("artifact_digest")!=art.get("digest") or att.get("source_commit")!=req["requested_commit"] or att.get("parent_digests")!=pd or att.get("builder")!=req["required_builder"]:problems.append("attestation mismatch")
 sbom=next((x for x in sboms if x["artifact_digest"]==art.get("digest")),{})
 if sbom.get("status")!="complete" or sbom.get("commit")!=req["requested_commit"] or sbom.get("parent_digests")!=pd:problems.append("SBOM mismatch")
 scan=next((x for x in base["scan_records"] if x["artifact_digest"]==art.get("digest")),{})
 if art.get("base_digest") not in base["allowed_digests"] or scan.get("status")!="pass" or scan.get("base_digest")!=art.get("base_digest"):problems.append("base/scan blocked")
 approvals=list(csv.DictReader((ROOT/"approval_ledger.csv").open()));matching=[x for x in approvals if x["request_id"]==req["request_id"] and x["artifact_digest"]==art.get("digest")];latest=max(matching,key=lambda x:datetime.fromisoformat(x["recorded_at"].replace("Z","+00:00"))) if matching else None;active=latest if latest and latest["status"]=="approved" else None
 state={"request_id":req["request_id"],"selected_artifact_id":art.get("artifact_id"),"artifact_digest":art.get("digest"),"component_artifact_ids":art.get("parents",[]),"sbom_id":sbom.get("sbom_id"),"signature_id":art.get("signature_id"),"attestation_id":art.get("attestation_id"),"scan_id":scan.get("scan_id"),"approval_id":active.get("approval_id") if active else None,"state":"ready_for_promotion" if active else "pending_human_reapproval"}
 return state,problems,latest
def append_event(path,event):
 rows=[json.loads(x) for x in path.read_text().splitlines() if x.strip()];event={"event_id":f"EV-{len(rows)+1:03d}","request_id":event["request_id"],**event,"previous":rows[-1]["event_id"]}
 if not any(x.get("event")==event.get("event") and x.get("subject")==event.get("subject") for x in rows):
  with path.open("a") as h:h.write(json.dumps(event,separators=(",",":"))+"\n")
def main():
 p=argparse.ArgumentParser();sub=p.add_subparsers(dest="cmd",required=True);i=sub.add_parser("inspect");i.add_argument("--artifact-id",required=True);s=sub.add_parser("select");s.add_argument("state",type=Path);s.add_argument("events",type=Path);s.add_argument("--artifact-id",required=True);q=sub.add_parser("request-approval");q.add_argument("state",type=Path);q.add_argument("out",type=Path);v=sub.add_parser("verify");v.add_argument("state",type=Path);v.add_argument("approval_request",type=Path);a=p.parse_args()
 if a.cmd=="inspect":state,problems,latest=derive(a.artifact_id);print(json.dumps({"candidate":a.artifact_id,"eligible":not problems,"derived_state":state,"latest_approval":latest,"problems":problems},indent=2));return 0
 if a.cmd=="select":
  state,problems,_=derive(a.artifact_id)
  if problems:print(json.dumps({"status":"fail","problems":problems}));return 2
  a.state.write_text(json.dumps(state,indent=2)+"\n");append_event(a.events,{"request_id":state["request_id"],"event":"rebuilt_bundle_selected_pending_reapproval","subject":a.artifact_id});print(json.dumps({"status":"pass","state":state["state"]}));return 0
 state=json.loads(a.state.read_text());derived,problems,_=derive(state.get("selected_artifact_id",""))
 if state!=derived:problems.append("state differs from evidence")
 expected={"request_id":state.get("request_id"),"artifact_digest":state.get("artifact_digest"),"artifact_id":state.get("selected_artifact_id"),"requested_status":"human_reapproval_required","owner":"release-board","reason":"rebuilt digest after revoked approval"}
 if a.cmd=="request-approval":a.out.write_text(json.dumps(expected,indent=2)+"\n");print("REQUEST_PREPARED");return 0
 try:actual=json.loads(a.approval_request.read_text())
 except Exception:actual={}
 if actual!=expected:problems.append("approval request is absent or not digest-bound")
 print(json.dumps({"status":"pass" if not problems else "fail","problems":problems},indent=2));return 0 if not problems else 2
if __name__=="__main__":raise SystemExit(main())
