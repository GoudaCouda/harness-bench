def _exact(v, k):
    return isinstance(v, dict) and set(v) == set(k)


def _token(v):
    return (
        isinstance(v, str)
        and bool(v)
        and v == v.lower()
        and v.isascii()
        and all(c.isalnum() or c in "-_" for c in v)
    )


def plan_rerun(workflow, runs, policy):
    if (
        not isinstance(workflow, list)
        or not isinstance(runs, list)
        or not _exact(policy, ("rerun_cancelled", "allow_side_effects"))
        or not all(isinstance(policy[k], bool) for k in policy)
    ):
        raise ValueError("invalid inputs")
    jobs = {}
    order = []
    for j in workflow:
        if (
            not _exact(j, ("job_id", "needs", "shards", "consumes", "side_effect"))
            or not _token(j["job_id"])
            or not isinstance(j["side_effect"], bool)
        ):
            raise ValueError("invalid job")
        if (
            not all(
                isinstance(j[k], list)
                and j[k] == sorted(j[k])
                and len(set(j[k])) == len(j[k])
                for k in ("needs", "shards", "consumes")
            )
            or not j["shards"]
            or not all(_token(x) for k in ("needs", "shards", "consumes") for x in j[k])
        ):
            raise ValueError("invalid job lists")
        if j["job_id"] in jobs or not set(j["consumes"]).issubset(set(j["needs"])):
            raise ValueError("duplicate job or invalid consumes")
        jobs[j["job_id"]] = j
        order.append(j["job_id"])
    if order != sorted(order) or any(
        n not in jobs or n == j["job_id"] for j in workflow for n in j["needs"]
    ):
        raise ValueError("invalid job order or need")
    indegree = {k: len(v["needs"]) for k, v in jobs.items()}
    ready = sorted([k for k, v in indegree.items() if v == 0])
    topo = []
    while ready:
        name = ready.pop(0)
        topo.append(name)
        for child in sorted(jobs):
            if name in jobs[child]["needs"]:
                indegree[child] -= 1
                if indegree[child] == 0:
                    ready.append(child)
                    ready.sort()
    if len(topo) != len(jobs):
        raise ValueError("cyclic workflow")
    observed = {}
    for r in runs:
        if (
            not _exact(r, ("job_id", "shard", "status", "attempt", "artifact_fresh"))
            or r["job_id"] not in jobs
            or not _token(r["shard"])
            or r["shard"] not in jobs[r["job_id"]]["shards"]
        ):
            raise ValueError("invalid run")
        if (
            r["status"] not in ("success", "failure", "cancelled", "skipped")
            or not isinstance(r["attempt"], int)
            or isinstance(r["attempt"], bool)
            or r["attempt"] < 1
            or not isinstance(r["artifact_fresh"], bool)
        ):
            raise ValueError("invalid run state")
        key = (r["job_id"], r["shard"])
        if key in observed:
            raise ValueError("duplicate run")
        observed[key] = r
    expected = {(j, s) for j in jobs for s in jobs[j]["shards"]}
    if set(observed) != expected:
        raise ValueError("incomplete runs")
    plan = []
    selected = set()
    counts = {"rerun": 0, "manual": 0, "keep": 0}
    for job_id in topo:
        job = jobs[job_id]
        impacted = {n for n in job["needs"] if n in selected}
        for shard in job["shards"]:
            r = observed[(job_id, shard)]
            status = r["status"]
            action = "keep"
            reason = "successful" if status == "success" else status + "_by_policy"
            if status == "failure":
                action = "rerun"
                reason = "direct_failure"
            elif status == "cancelled" and policy["rerun_cancelled"]:
                action = "rerun"
                reason = "direct_cancellation"
            elif status == "success" and not r["artifact_fresh"]:
                action = "rerun"
                reason = "stale_output"
            elif impacted and status in ("failure", "cancelled", "skipped"):
                action = "rerun"
                reason = "upstream_dependency"
            elif status == "success" and impacted & set(job["consumes"]):
                action = "rerun"
                reason = "stale_artifact"
            if (
                action == "rerun"
                and job["side_effect"]
                and not policy["allow_side_effects"]
            ):
                action = "manual"
                reason = "side_effect_approval"
            attempt = (
                r["attempt"] + 1 if action in ("rerun", "manual") else r["attempt"]
            )
            plan.append(
                {
                    "job_id": job_id,
                    "shard": shard,
                    "action": action,
                    "reason": reason,
                    "attempt": attempt,
                }
            )
            counts[action] += 1
            if action in ("rerun", "manual"):
                selected.add(job_id)
    return {
        "plan": plan,
        "summary": {
            "instance_count": len(plan),
            "rerun": counts["rerun"],
            "manual": counts["manual"],
            "keep": counts["keep"],
        },
    }
