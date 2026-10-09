"""Priority-stable topological scheduler for mill jobs."""


def schedule_jobs(jobs):
    by_id = {}
    for job in jobs:
        job_id = job["job_id"]
        if job_id in by_id:
            raise ValueError("duplicate_job")
        by_id[job_id] = job
    indeg = {}
    succ = {}
    for job_id in by_id:
        indeg[job_id] = 0
        succ[job_id] = []
    for job in jobs:
        for dep in job["deps"]:
            if dep not in by_id:
                raise ValueError("unknown_dependency")
            succ[dep].append(job["job_id"])
            indeg[job["job_id"]] = indeg[job["job_id"]] + 1
    order = []
    remaining = list(by_id)
    for _step in range(len(by_id)):
        ready = []
        for job_id in remaining:
            if indeg[job_id] == 0:
                ready.append(job_id)
        if not ready:
            raise ValueError("cycle")
        ready.sort(key=lambda job_id: (-int(by_id[job_id]["priority"]), job_id))
        chosen = ready[0]
        order.append(chosen)
        remaining = [job_id for job_id in remaining if job_id != chosen]
        for nxt in succ[chosen]:
            indeg[nxt] = indeg[nxt] - 1
    return {"order": order}
