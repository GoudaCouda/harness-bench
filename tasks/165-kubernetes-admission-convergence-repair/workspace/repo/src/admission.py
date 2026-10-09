def _matches(request, webhook):
    return (
        request["operation"] in webhook["operations"]
        and request["resource"] in webhook["resources"]
        and request["namespace"] not in webhook["excluded_namespaces"]
    )


def evaluate_admission(requests, webhooks, policy):
    """Replay deterministic webhook mutations over AdmissionReview captures.

    Normal set-if-missing behavior is idempotent.  Reinvocation convergence,
    conflicting patches, dry-run side effects, failure policy, and immutable
    path enforcement remain incomplete.
    """
    objects = []
    decisions = []
    for request in requests:
        fields = dict(request["fields"])
        changed = []
        blocked = None
        for webhook in sorted(webhooks, key=lambda row: row["name"]):
            if not _matches(request, webhook):
                continue
            if not webhook["available"] and webhook["failure_policy"] == "Fail":
                blocked = "webhook_unavailable"
                break
            for mutation in webhook["mutations"]:
                if mutation["mode"] == "set_if_missing" and mutation["path"] not in fields:
                    fields[mutation["path"]] = mutation["value"]
                    changed.append(mutation["path"])
                elif mutation["mode"] == "set":
                    fields[mutation["path"]] = mutation["value"]
                    changed.append(mutation["path"])
        status = "blocked" if blocked else "admitted" if changed else "unchanged"
        decisions.append({"request_id": request["request_id"], "status": status, "reason": blocked or "converged", "changed_paths": sorted(set(changed))})
        objects.append({**request, "fields": fields})
    return {"decisions": decisions, "objects": objects, "summary": {"request_count": len(requests), "admitted": sum(row["status"] == "admitted" for row in decisions), "unchanged": sum(row["status"] == "unchanged" for row in decisions), "blocked": sum(row["status"] == "blocked" for row in decisions)}}
