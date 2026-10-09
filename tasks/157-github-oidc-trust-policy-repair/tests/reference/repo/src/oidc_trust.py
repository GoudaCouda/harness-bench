def _exact(value, keys):
    return isinstance(value, dict) and set(value) == set(keys)


def _token(value):
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.lower()
        and value.isascii()
        and all(char.isalnum() or char in "-_" for char in value)
    )


def _decimal(value):
    return (
        isinstance(value, str) and bool(value) and value.isascii() and value.isdigit()
    )


def _repository(value):
    if (
        not isinstance(value, str)
        or value.count("/") != 1
        or value != value.lower()
        or not value.isascii()
    ):
        return False
    return all(_token(part) for part in value.split("/"))


def _context(value):
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.lower()
        and value.isascii()
        and all(char.isalnum() or char in "-_:/." for char in value)
    )


def _sorted_contexts(values):
    return (
        isinstance(values, list)
        and values == sorted(values)
        and len(set(values)) == len(values)
        and all(_context(value) for value in values)
    )


def _sorted_decimals(values):
    return (
        isinstance(values, list)
        and values == sorted(values)
        and len(set(values)) == len(values)
        and all(_decimal(value) for value in values)
    )


def _workflow(value):
    if value is None:
        return True
    if (
        not isinstance(value, str)
        or value.count("@") != 1
        or value != value.lower()
        or not value.isascii()
    ):
        return False
    path, revision = value.split("@")
    return (
        "/.github/workflows/" in path
        and path.endswith((".yml", ".yaml"))
        and len(revision) == 40
        and all(char in "0123456789abcdef" for char in revision)
    )


def authorize_tokens(roles, tokens, policy):
    if not _exact(
        policy, ("allow_pull_request", "require_immutable_subject")
    ) or not all(isinstance(value, bool) for value in policy.values()):
        raise ValueError("invalid policy")
    if not isinstance(roles, list) or not isinstance(tokens, list):
        raise ValueError("invalid inputs")
    role_keys = (
        "role_id",
        "issuer",
        "audiences",
        "owner_id",
        "repository_ids",
        "subject_mode",
        "allowed_refs",
        "allowed_environments",
        "required_workflow",
    )
    role_map = {}
    order = []
    for role in roles:
        if (
            not _exact(role, role_keys)
            or not _token(role["role_id"])
            or not isinstance(role["issuer"], str)
            or not role["issuer"].startswith("https://")
        ):
            raise ValueError("invalid role")
        if (
            not _sorted_contexts(role["audiences"])
            or not role["audiences"]
            or not _decimal(role["owner_id"])
            or not _sorted_decimals(role["repository_ids"])
            or not role["repository_ids"]
        ):
            raise ValueError("invalid role scope")
        if (
            role["subject_mode"] not in ("legacy", "immutable")
            or not _sorted_contexts(role["allowed_refs"])
            or not _sorted_contexts(role["allowed_environments"])
            or not _workflow(role["required_workflow"])
        ):
            raise ValueError("invalid role context")
        if role["role_id"] in role_map:
            raise ValueError("duplicate role")
        role_map[role["role_id"]] = role
        order.append(role["role_id"])
    if order != sorted(order):
        raise ValueError("roles must be sorted")

    token_keys = (
        "request_id",
        "role_id",
        "iss",
        "aud",
        "sub",
        "repository",
        "owner_id",
        "repository_id",
        "ref",
        "environment",
        "job_workflow_ref",
        "event_name",
        "id_token_permission",
    )
    seen = set()
    decisions = []
    authorized = 0
    for token in tokens:
        if (
            not _exact(token, token_keys)
            or not _token(token["request_id"])
            or not _token(token["role_id"])
            or token["request_id"] in seen
        ):
            raise ValueError("invalid token identity")
        seen.add(token["request_id"])
        if (
            not all(isinstance(token[key], str) for key in ("iss", "aud", "sub", "ref"))
            or not _repository(token["repository"])
            or not _decimal(token["owner_id"])
            or not _decimal(token["repository_id"])
        ):
            raise ValueError("invalid claims")
        if token["environment"] is not None and not _context(token["environment"]):
            raise ValueError("invalid environment")
        if (
            not _workflow(token["job_workflow_ref"])
            or token["event_name"] not in ("push", "workflow_dispatch", "pull_request")
            or token["id_token_permission"] not in ("none", "read", "write")
        ):
            raise ValueError("invalid token controls")
        role = role_map.get(token["role_id"])
        reason = None
        if role is None:
            reason = "unknown_role"
        elif token["id_token_permission"] != "write":
            reason = "id_token_permission"
        elif token["iss"] != role["issuer"]:
            reason = "issuer"
        elif token["aud"] not in role["audiences"]:
            reason = "audience"
        elif token["owner_id"] != role["owner_id"]:
            reason = "owner_id"
        elif token["repository_id"] not in role["repository_ids"]:
            reason = "repository_id"
        elif (
            policy["require_immutable_subject"] and role["subject_mode"] != "immutable"
        ):
            reason = "immutable_required"
        else:
            owner, name = token["repository"].split("/")
            prefix = (
                f"repo:{owner}/{name}"
                if role["subject_mode"] == "legacy"
                else f"repo:{owner}@{token['owner_id']}/{name}@{token['repository_id']}"
            )
            suffix = (
                f":environment:{token['environment'].replace(':', '%3A')}"
                if token["environment"] is not None
                else f":ref:{token['ref']}"
            )
            if token["sub"] != prefix + suffix:
                reason = "subject"
            elif (
                token["event_name"] == "pull_request"
                and not policy["allow_pull_request"]
            ):
                reason = "pull_request"
            elif (
                token["environment"] is not None
                and token["environment"] not in role["allowed_environments"]
            ):
                reason = "environment"
            elif (
                token["environment"] is None
                and token["ref"] not in role["allowed_refs"]
            ):
                reason = "ref"
            elif (
                role["required_workflow"] is not None
                and token["job_workflow_ref"] != role["required_workflow"]
            ):
                reason = "workflow"
        status = "denied" if reason else "authorized"
        if status == "authorized":
            reason = "trusted"
            authorized += 1
        decisions.append(
            {
                "request_id": token["request_id"],
                "role_id": token["role_id"],
                "status": status,
                "reason": reason,
            }
        )
    return {
        "decisions": decisions,
        "summary": {
            "request_count": len(tokens),
            "authorized": authorized,
            "denied": len(tokens) - authorized,
        },
    }
