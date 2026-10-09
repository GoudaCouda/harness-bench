#!/usr/bin/env python3
from __future__ import annotations
import argparse,json
from pathlib import Path
ROOT=Path.cwd()
def load(p):return json.loads(Path(p).read_text())
def derive(dep,svc,ext):
 inv=load(ROOT/"secret_inventory.json");configs=load(ROOT/"config_inventory.json");contract=load(ROOT/"image_contract.json");container=dep["spec"]["template"]["spec"]["containers"][0];env={x["name"]:x for x in container["env"]};remote=ext["spec"]["data"][0];record=next((x for x in inv["records"] if x["remote_key"]==remote["remoteRef"]["key"] and x["version"]==remote["remoteRef"].get("version")),{});secret_ok=record.get("state")=="current" and remote["remoteRef"].get("property") in record.get("properties",[]) and ext["spec"]["target"]["name"]==env["DATABASE_URL"]["valueFrom"]["secretKeyRef"]["name"] and remote["secretKey"]==env["DATABASE_URL"]["valueFrom"]["secretKeyRef"]["key"]
 cmref=env["HTTP_PORT"]["valueFrom"]["configMapKeyRef"];cm=next((x for x in configs["config_maps"] if x["name"]==cmref["name"]),{});port=int(cm.get("data",{}).get(cmref.get("key"),0) or 0);startup=secret_ok and cm.get("state")=="current" and port==contract["runtime"]["supported_port"]
 probe=container["readinessProbe"]["httpGet"];named={x["name"]:x["containerPort"] for x in container["ports"]};ready=startup and probe["path"]==contract["runtime"]["readiness_path"] and named.get(probe["port"])==port
 selector=all(dep["spec"]["template"]["metadata"]["labels"].get(k)==v for k,v in svc["spec"]["selector"].items());target=svc["spec"]["ports"][0]["targetPort"];routing=ready and selector and isinstance(target,str) and named.get(target)==port
 return {"generation":dep["metadata"]["generation"],"secret_sync":{"status":"current" if secret_ok else "blocked","remote_version":remote["remoteRef"].get("version"),"property":remote["remoteRef"].get("property")},"startup":{"status":"listening" if startup else "blocked","config_map":cmref["name"],"resolved_port":port},"readiness":{"status":"ready" if ready else "failed","path":probe["path"]},"routing":{"status":"endpoints_ready" if routing else "no_ready_endpoints","target_port":target},"replicas":{"desired":dep["spec"]["replicas"],"ready":dep["spec"]["replicas"] if routing else 0},"smoke":{"request":"GET /health/ready via service/invoice-api:80","result":"HTTP 200" if routing else "FAILED"},"simulator":"offline-clusterctl-v2"}
def valid(x):return all((x["secret_sync"]["status"]=="current",x["startup"]["status"]=="listening",x["readiness"]["status"]=="ready",x["routing"]["status"]=="endpoints_ready",x["replicas"]=={"desired":3,"ready":3},x["smoke"]["result"]=="HTTP 200"))
def main():
 p=argparse.ArgumentParser();sub=p.add_subparsers(dest="cmd",required=True)
 for n in ("observe","reconcile","verify"):
  q=sub.add_parser(n);q.add_argument("--deployment",required=True);q.add_argument("--service",required=True);q.add_argument("--external-secret",required=True);q.add_argument("--out" if n!="verify" else "--observed",required=True)
 a=p.parse_args();derived=derive(load(a.deployment),load(a.service),load(a.external_secret))
 if a.cmd in ("observe","reconcile"):Path(a.out).write_text(json.dumps(derived,indent=2)+"\n");print(json.dumps(derived));return 0 if valid(derived) else 2
 ok=load(a.observed)==derived and valid(derived);print("PASS" if ok else json.dumps({"status":"FAIL","derived":derived}));return 0 if ok else 2
if __name__=="__main__":raise SystemExit(main())
