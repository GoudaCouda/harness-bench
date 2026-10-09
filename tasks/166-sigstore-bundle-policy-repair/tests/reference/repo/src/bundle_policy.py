def _exact(value, keys):
    return isinstance(value, dict) and set(value) == set(keys)


def _token(value):
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.lower()
        and value.isascii()
        and all(char.isalnum() or char in "-_." for char in value)
    )


def _text(value):
    return isinstance(value, str) and bool(value) and value.isascii()


def _digest(value):
    return (
        isinstance(value, str)
        and value.startswith("sha256:")
        and len(value) > 7
        and all(char in "0123456789abcdef" for char in value[7:])
    )


def _sorted_strings(values):
    return (
        isinstance(values, list)
        and values == sorted(values)
        and len(set(values)) == len(values)
        and all(_text(value) for value in values)
    )


def verify_bundles(artifacts, bundles, roots, policy):
    policy_keys = (
        "require_tlog",
        "require_timestamp",
        "min_tlog_operators",
        "accepted_payload_types",
    )
    if (
        not _exact(policy, policy_keys)
        or not isinstance(policy["require_tlog"], bool)
        or not isinstance(policy["require_timestamp"], bool)
        or not isinstance(policy["min_tlog_operators"], int)
        or isinstance(policy["min_tlog_operators"], bool)
        or policy["min_tlog_operators"] < 0
        or not _sorted_strings(policy["accepted_payload_types"])
    ):
        raise ValueError("invalid policy")
    if policy["require_tlog"] and policy["min_tlog_operators"] <= 0:
        raise ValueError("invalid tlog threshold")
    if (
        not isinstance(artifacts, list)
        or not isinstance(bundles, list)
        or not isinstance(roots, list)
    ):
        raise ValueError("invalid inputs")
    root_keys = (
        "root_id",
        "valid_from",
        "valid_until",
        "ca_operator",
        "tlog_operators",
        "timestamp_operators",
    )
    root_map = {}
    root_ids = []
    for root in roots:
        if (
            not _exact(root, root_keys)
            or not _token(root["root_id"])
            or not _token(root["ca_operator"])
            or not isinstance(root["valid_from"], int)
            or isinstance(root["valid_from"], bool)
            or not isinstance(root["valid_until"], int)
            or isinstance(root["valid_until"], bool)
            or root["valid_from"] < 0
            or root["valid_from"] > root["valid_until"]
            or not _sorted_strings(root["tlog_operators"])
            or not _sorted_strings(root["timestamp_operators"])
        ):
            raise ValueError("invalid root")
        root_ids.append(root["root_id"])
        root_map[root["root_id"]] = root
    if root_ids != sorted(root_ids) or len(set(root_ids)) != len(root_ids):
        raise ValueError("roots must be sorted")
    bundle_keys = (
        "artifact_id",
        "digest",
        "payload_type",
        "signature_verified",
        "chain_verified",
        "identity",
        "issuer",
        "root_id",
        "cert_not_before",
        "cert_not_after",
        "tlog_entries",
        "timestamps",
    )
    evidence_keys = ("operator", "verified", "time")
    bundle_map = {}
    bundle_ids = []
    for bundle in bundles:
        if (
            not _exact(bundle, bundle_keys)
            or not _token(bundle["artifact_id"])
            or not _digest(bundle["digest"])
            or not _text(bundle["payload_type"])
            or not isinstance(bundle["signature_verified"], bool)
            or not isinstance(bundle["chain_verified"], bool)
            or not _text(bundle["identity"])
            or not _text(bundle["issuer"])
            or not _token(bundle["root_id"])
        ):
            raise ValueError("invalid bundle")
        if (
            not isinstance(bundle["cert_not_before"], int)
            or isinstance(bundle["cert_not_before"], bool)
            or not isinstance(bundle["cert_not_after"], int)
            or isinstance(bundle["cert_not_after"], bool)
            or bundle["cert_not_before"] < 0
            or bundle["cert_not_before"] > bundle["cert_not_after"]
        ):
            raise ValueError("invalid certificate window")
        for field in ("tlog_entries", "timestamps"):
            if not isinstance(bundle[field], list):
                raise ValueError("invalid evidence")
            ordering = []
            for item in bundle[field]:
                if (
                    not _exact(item, evidence_keys)
                    or not _text(item["operator"])
                    or not isinstance(item["verified"], bool)
                    or not isinstance(item["time"], int)
                    or isinstance(item["time"], bool)
                    or item["time"] < 0
                ):
                    raise ValueError("invalid evidence item")
                ordering.append((item["operator"], item["time"]))
            if ordering != sorted(ordering):
                raise ValueError("evidence must be sorted")
        bundle_ids.append(bundle["artifact_id"])
        bundle_map[bundle["artifact_id"]] = bundle
    if bundle_ids != sorted(bundle_ids) or len(set(bundle_ids)) != len(bundle_ids):
        raise ValueError("bundles must be sorted")
    artifact_keys = ("artifact_id", "digest", "identity", "issuer", "payload_type")
    decisions = []
    artifact_ids = []
    verified_count = 0
    for artifact in artifacts:
        if (
            not _exact(artifact, artifact_keys)
            or not _token(artifact["artifact_id"])
            or not _digest(artifact["digest"])
            or not _text(artifact["identity"])
            or not _text(artifact["issuer"])
            or not _text(artifact["payload_type"])
        ):
            raise ValueError("invalid artifact")
        artifact_ids.append(artifact["artifact_id"])
        bundle = bundle_map.get(artifact["artifact_id"])
        reason = None
        signing_time = None
        operator_count = 0
        if bundle is None:
            reason = "missing_bundle"
        elif bundle["digest"] != artifact["digest"]:
            reason = "digest"
        elif (
            bundle["payload_type"] != artifact["payload_type"]
            or bundle["payload_type"] not in policy["accepted_payload_types"]
        ):
            reason = "payload_type"
        elif not bundle["signature_verified"]:
            reason = "signature"
        elif not bundle["chain_verified"]:
            reason = "certificate_chain"
        elif bundle["identity"] != artifact["identity"]:
            reason = "identity"
        elif bundle["issuer"] != artifact["issuer"]:
            reason = "issuer"
        elif bundle["root_id"] not in root_map:
            reason = "unknown_root"
        else:
            root = root_map[bundle["root_id"]]
            trusted_tlogs = [
                item
                for item in bundle["tlog_entries"]
                if item["verified"] and item["operator"] in root["tlog_operators"]
            ]
            trusted_timestamps = [
                item
                for item in bundle["timestamps"]
                if item["verified"] and item["operator"] in root["timestamp_operators"]
            ]
            operator_count = len(set(item["operator"] for item in trusted_tlogs))
            if policy["require_tlog"] and not trusted_tlogs:
                reason = "tlog_evidence"
            elif policy["require_timestamp"] and not trusted_timestamps:
                reason = "timestamp_evidence"
            elif (
                policy["require_tlog"] and operator_count < policy["min_tlog_operators"]
            ):
                reason = "tlog_operator_threshold"
            else:
                valid_tlogs = [
                    item["time"]
                    for item in trusted_tlogs
                    if bundle["cert_not_before"]
                    <= item["time"]
                    <= bundle["cert_not_after"]
                    and root["valid_from"] <= item["time"] <= root["valid_until"]
                ]
                valid_timestamps = [
                    item["time"]
                    for item in trusted_timestamps
                    if bundle["cert_not_before"]
                    <= item["time"]
                    <= bundle["cert_not_after"]
                    and root["valid_from"] <= item["time"] <= root["valid_until"]
                ]
                if (policy["require_tlog"] and not valid_tlogs) or (
                    policy["require_timestamp"] and not valid_timestamps
                ):
                    reason = "signing_time"
                else:
                    times = valid_tlogs + valid_timestamps
                    signing_time = min(times) if times else None
        status = "blocked" if reason else "verified"
        if status == "verified":
            reason = "trusted"
            verified_count += 1
        decisions.append(
            {
                "artifact_id": artifact["artifact_id"],
                "status": status,
                "reason": reason,
                "signing_time": signing_time,
                "tlog_operator_count": operator_count,
            }
        )
    if (
        artifact_ids != sorted(artifact_ids)
        or len(set(artifact_ids)) != len(artifact_ids)
        or any(bundle_id not in set(artifact_ids) for bundle_id in bundle_ids)
    ):
        raise ValueError("artifacts must be sorted and cover bundles")
    return {
        "decisions": decisions,
        "summary": {
            "artifact_count": len(artifacts),
            "verified": verified_count,
            "blocked": len(artifacts) - verified_count,
        },
    }
