def plan_rerun(workflow, runs, policy):
    # Broken implementation reruns only red cells and ignores the DAG.
    return {"plan": [], "summary": {"instance_count": len(runs)}}
