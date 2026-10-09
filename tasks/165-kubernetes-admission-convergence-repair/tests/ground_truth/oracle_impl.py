def _exact(value, keys):
    return isinstance(value, dict) and set(value) == set(keys)


def _token(value, path=False):
    chars = "-_/." if path else "-_"
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.lower()
        and value.isascii()
        and all(char.isalnum() or char in chars for char in value)
    )


def _sorted_tokens(values, path=False):
    return (
        isinstance(values, list)
        and values == sorted(values)
        and len(set(values)) == len(values)
        and all(_token(value, path) for value in values)
    )


def _sorted_upper(values):
    return (
        isinstance(values, list)
        and values == sorted(values)
        and len(set(values)) == len(values)
        and all(
            isinstance(value, str) and value in ("CREATE", "UPDATE") for value in values
        )
    )


def evaluate_admission(requests, webhooks, policy):
    if (
        not _exact(policy, ("require_side_effect_free", "immutable_paths"))
        or not isinstance(policy["require_side_effect_free"], bool)
        or not _sorted_tokens(policy["immutable_paths"], True)
    ):
        raise ValueError("invalid policy")
    if not isinstance(requests, list) or not isinstance(webhooks, list):
        raise ValueError("invalid inputs")
    webhook_keys = (
        "name",
        "operations",
        "resources",
        "excluded_namespaces",
        "side_effects",
        "failure_policy",
        "reinvocation_policy",
        "available",
        "mutations",
    )
    mutation_keys = ("path", "mode", "value")
    hooks = []
    names = []
    for hook in webhooks:
        if (
            not _exact(hook, webhook_keys)
            or not _token(hook["name"])
            or not _sorted_upper(hook["operations"])
            or not _sorted_tokens(hook["resources"])
            or not _sorted_tokens(hook["excluded_namespaces"])
        ):
            raise ValueError("invalid webhook identity")
        if (
            not hook["operations"]
            or not hook["resources"]
            or any(value not in ("CREATE", "UPDATE") for value in hook["operations"])
            or hook["side_effects"] not in ("None", "NoneOnDryRun", "Some")
            or hook["failure_policy"] not in ("Fail", "Ignore")
            or hook["reinvocation_policy"] not in ("Never", "IfNeeded")
            or not isinstance(hook["available"], bool)
            or not isinstance(hook["mutations"], list)
        ):
            raise ValueError("invalid webhook controls")
        paths = []
        for mutation in hook["mutations"]:
            if (
                not _exact(mutation, mutation_keys)
                or not _token(mutation["path"], True)
                or mutation["mode"] not in ("set_if_missing", "ensure_value", "append")
                or not isinstance(mutation["value"], (str, int, bool))
            ):
                raise ValueError("invalid mutation")
            paths.append(mutation["path"])
        if paths != sorted(paths) or len(set(paths)) != len(paths):
            raise ValueError("mutations must be sorted")
        names.append(hook["name"])
        hooks.append(hook)
    if names != sorted(names) or len(set(names)) != len(names):
        raise ValueError("webhooks must be sorted")
    request_keys = (
        "request_id",
        "operation",
        "resource",
        "namespace",
        "dry_run",
        "mirror_pod",
        "fields",
    )
    decisions = []
    objects = []
    request_ids = []
    counts = {"admitted": 0, "unchanged": 0, "blocked": 0}
    for request in requests:
        if (
            not _exact(request, request_keys)
            or not _token(request["request_id"])
            or request["operation"] not in ("CREATE", "UPDATE")
            or not _token(request["resource"])
            or not _token(request["namespace"])
            or not isinstance(request["dry_run"], bool)
            or not isinstance(request["mirror_pod"], bool)
            or not isinstance(request["fields"], dict)
        ):
            raise ValueError("invalid request")
        if any(
            not _token(path, True) or not isinstance(value, (str, int, bool))
            for path, value in request["fields"].items()
        ):
            raise ValueError("invalid fields")
        request_ids.append(request["request_id"])
        applicable = [
            hook
            for hook in hooks
            if request["operation"] in hook["operations"]
            and request["resource"] in hook["resources"]
            and request["namespace"] not in hook["excluded_namespaces"]
        ]
        reason = None
        if request["mirror_pod"]:
            reason = "immutable_object"
        elif any(
            not hook["available"] and hook["failure_policy"] == "Fail"
            for hook in applicable
        ):
            reason = "webhook_unavailable"
        else:
            active = [hook for hook in applicable if hook["available"]]
            if policy["require_side_effect_free"] and any(
                hook["side_effects"] != "None" for hook in active
            ):
                reason = "side_effect_policy"
            elif request["dry_run"] and any(
                hook["side_effects"] not in ("None", "NoneOnDryRun") for hook in active
            ):
                reason = "dry_run_side_effects"
            else:
                writes = {}
                for hook in active:
                    for mutation in hook["mutations"]:
                        path = mutation["path"]
                        if path in policy["immutable_paths"]:
                            reason = "immutable_path"
                        elif mutation["mode"] == "append":
                            reason = "non_idempotent_mutation"
                        elif path in writes and writes[path] != mutation["value"]:
                            reason = "mutation_conflict"
                        else:
                            writes[path] = mutation["value"]
        if reason is not None:
            status, action = "blocked", "reject"
            final_fields = dict(request["fields"])
        elif not applicable or not any(hook["available"] for hook in applicable):
            status, action, reason = "unchanged", "unchanged", "no_matching_webhook"
            final_fields = dict(request["fields"])
        else:
            status, action, reason = "admitted", "emit_object", "converged"
            final_fields = dict(request["fields"])
            for hook in applicable:
                if hook["available"]:
                    for mutation in hook["mutations"]:
                        if mutation["mode"] == "set_if_missing":
                            if mutation["path"] not in final_fields:
                                final_fields[mutation["path"]] = mutation["value"]
                        else:
                            final_fields[mutation["path"]] = mutation["value"]
        final_fields = {path: final_fields[path] for path in sorted(final_fields)}
        objects.append({"request_id": request["request_id"], "fields": final_fields})
        decisions.append(
            {
                "request_id": request["request_id"],
                "status": status,
                "action": action,
                "reason": reason,
                "webhook_count": len(applicable),
            }
        )
        counts[status] += 1
    if request_ids != sorted(request_ids) or len(set(request_ids)) != len(request_ids):
        raise ValueError("requests must be sorted")
    return {
        "decisions": decisions,
        "objects": objects,
        "summary": {
            "request_count": len(requests),
            "admitted": counts["admitted"],
            "unchanged": counts["unchanged"],
            "blocked": counts["blocked"],
        },
    }
