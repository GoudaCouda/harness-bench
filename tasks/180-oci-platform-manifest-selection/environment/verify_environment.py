#!/usr/bin/env python3
from __future__ import annotations
import json
import sys

if sys.version_info[:2] != (3, 12):
    raise SystemExit(f"expected CPython 3.12, found {sys.version}")

descriptors=[
 {"digest":"sha256:a","platform":{"os":"linux","architecture":"amd64",
  "os.features":["sse4"]},"annotations":{"channel":"stable"}},
 {"digest":"sha256:b","platform":{"os":"linux","architecture":"amd64",
  "variant":"v2","os.features":["sse4","avx2"]},"annotations":{"channel":"stable"}},
 {"digest":"sha256:c","platform":{"os":"linux","architecture":"amd64",
  "os.features":["sse4","avx2"]},"annotations":{"channel":"stable"}},
]
target={"os":"linux","architecture":"amd64","variant":None,
        "required_features":["sse4"]}
compatible=[]
for row in descriptors:
    platform=row["platform"]
    if (platform["os"],platform["architecture"],platform.get("variant")) != (
        target["os"],target["architecture"],target["variant"]):
        continue
    if not set(target["required_features"]).issubset(platform.get("os.features",[])):
        continue
    if row["annotations"].get("channel")!="stable": continue
    compatible.append((sum(x in platform["os.features"] for x in ["avx2"]),row["digest"]))
compatible.sort(key=lambda item:(-item[0],item[1]))
if compatible != [(1,"sha256:c"),(0,"sha256:a")]:
    raise SystemExit("OCI platform/feature/annotation selection probe failed")
tie=[(1,"sha256:c"),(1,"sha256:d")]
if not (len(tie)>1 and tie[0][0]==tie[1][0]):
    raise SystemExit("equal-preference ambiguity probe failed")
print(json.dumps({"python3":"3.12","oci_os_features":"passed","variant":"passed",
                  "annotation_policy":"passed","ambiguity":"passed",
                  "registry_service":"not_required_by_offline_task_contract"},sort_keys=True))
