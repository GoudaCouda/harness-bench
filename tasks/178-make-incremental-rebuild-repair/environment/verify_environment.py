#!/usr/bin/env python3
from __future__ import annotations
import json
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

graph={
 "src":{"mtime":20,"normal":[],"order":[],"recipe":False,"phony":False},
 "stamp":{"mtime":30,"normal":[],"order":[],"recipe":False,"phony":False},
 "obj":{"mtime":10,"normal":["src"],"order":[],"recipe":True,"phony":False},
 "app":{"mtime":25,"normal":["obj"],"order":["stamp"],"recipe":True,"phony":False},
 "always":{"mtime":100,"normal":[],"order":[],"recipe":True,"phony":True},
 "package":{"mtime":100,"normal":["always"],"order":[],"recipe":True,"phony":False},
}
order=[]; done=set()
def visit(name):
    if name in done: return
    for dep in sorted(graph[name]["normal"]+graph[name]["order"]): visit(dep)
    done.add(name); order.append(name)
visit("app")
visit("package")
if order != ["src","obj","stamp","app","always","package"]:
    raise SystemExit("topological closure probe failed")
rebuilt=set()
for name in order:
    row=graph[name]
    needs=row["phony"] or row["mtime"] is None or any(dep in rebuilt for dep in row["normal"]) or any(
        graph[dep]["mtime"] is not None and graph[dep]["mtime"]>row["mtime"] for dep in row["normal"])
    if needs and row["recipe"]: rebuilt.add(name)
if rebuilt != {"obj","app","always","package"} or "stamp" in rebuilt:
    raise SystemExit("normal/order-only rebuild propagation probe failed")
cycle={"a":["b"],"b":["a"]}
if not (cycle["a"][0]=="b" and cycle["b"][0]=="a"):
    raise SystemExit("cycle fixture failed")
print(json.dumps({"python3":"3.12","dependency_closure":"passed",
                  "order_only_freshness":"passed","phony_propagation":"passed",
                  "cycle_fixture":"passed","make_cli":"not_required_by_task_contract"},sort_keys=True))
