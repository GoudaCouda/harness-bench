def _exact(value, keys):
    return isinstance(value, dict) and set(value) == set(keys)


def _token(value):
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.lower()
        and value.isascii()
        and all(char.isalnum() or char == "-" for char in value)
    )


def _domain(value):
    if (
        not isinstance(value, str)
        or not value
        or value != value.lower()
        or not value.isascii()
    ):
        return False
    labels = value.split(".")
    return all(
        label
        and label[0].isalnum()
        and label[-1].isalnum()
        and all(char.isalnum() or char == "-" for char in label)
        for label in labels
    )


def _origin(value):
    return (
        isinstance(value, str) and value.startswith("https://") and _domain(value[8:])
    )


def _count(value):
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and 0 <= value <= 4294967295
    )


def _clone_credential(value):
    return {
        key: value[key]
        for key in (
            "credential_id",
            "user_id",
            "sign_count",
            "backup_eligible",
            "backup_state",
            "status",
            "risk",
            "last_assertion",
        )
    }


def _credential(value):
    keys = (
        "credential_id",
        "user_id",
        "sign_count",
        "backup_eligible",
        "backup_state",
        "status",
        "risk",
        "last_assertion",
    )
    if (
        not _exact(value, keys)
        or not _token(value["credential_id"])
        or not _token(value["user_id"])
        or not _count(value["sign_count"])
    ):
        raise ValueError("invalid credential")
    if (
        not isinstance(value["backup_eligible"], bool)
        or not isinstance(value["backup_state"], bool)
        or (value["backup_state"] and not value["backup_eligible"])
    ):
        raise ValueError("invalid backup flags")
    if value["status"] not in ("active", "revoked") or value["risk"] not in (
        "normal",
        "elevated",
        "compromised",
    ):
        raise ValueError("invalid credential state")
    if value["last_assertion"] is not None and not _token(value["last_assertion"]):
        raise ValueError("invalid last assertion")
    return _clone_credential(value)


def _assertion(value):
    keys = (
        "assertion_id",
        "credential_id",
        "user_id",
        "sign_count",
        "backup_eligible",
        "backup_state",
        "signature_valid",
        "user_verified",
        "origin",
        "rp_id",
    )
    if (
        not _exact(value, keys)
        or not all(
            _token(value[key]) for key in ("assertion_id", "credential_id", "user_id")
        )
        or not _count(value["sign_count"])
    ):
        raise ValueError("invalid assertion")
    if not all(
        isinstance(value[key], bool)
        for key in (
            "backup_eligible",
            "backup_state",
            "signature_valid",
            "user_verified",
        )
    ):
        raise ValueError("invalid assertion flags")
    if not _origin(value["origin"]) or not _domain(value["rp_id"]):
        raise ValueError("invalid assertion scope")
    return value


def _policy(value):
    keys = (
        "allowed_origins",
        "rp_id",
        "require_user_verification",
        "device_counter_action",
        "synced_counter_action",
    )
    if (
        not _exact(value, keys)
        or not isinstance(value["allowed_origins"], list)
        or not value["allowed_origins"]
    ):
        raise ValueError("invalid policy")
    origins = value["allowed_origins"]
    if (
        origins != sorted(origins)
        or len(set(origins)) != len(origins)
        or not all(_origin(item) for item in origins)
    ):
        raise ValueError("invalid origins")
    if not _domain(value["rp_id"]) or not isinstance(
        value["require_user_verification"], bool
    ):
        raise ValueError("invalid relying party policy")
    if value["device_counter_action"] not in ("reject", "flag") or value[
        "synced_counter_action"
    ] not in ("flag", "ignore"):
        raise ValueError("invalid counter policy")


def _decision(assertion, decision, reason, counter_status, risk):
    return {
        "assertion_id": assertion["assertion_id"],
        "credential_id": assertion["credential_id"],
        "decision": decision,
        "reason": reason,
        "counter_status": counter_status,
        "risk_after": risk,
    }


def assess_assertions(credentials, assertions, policy):
    _policy(policy)
    if not isinstance(credentials, list) or not isinstance(assertions, list):
        raise ValueError("inputs must be lists")
    records = {}
    order = []
    for item in credentials:
        record = _credential(item)
        credential_id = record["credential_id"]
        if credential_id in records:
            raise ValueError("duplicate credential")
        records[credential_id] = record
        order.append(credential_id)
    if order != sorted(order):
        raise ValueError("credentials must be sorted")
    seen = set()
    decisions = []
    for raw in assertions:
        assertion = _assertion(raw)
        assertion_id = assertion["assertion_id"]
        if assertion_id in seen:
            raise ValueError("duplicate assertion")
        seen.add(assertion_id)
        record = records.get(assertion["credential_id"])
        if record is None:
            decisions.append(
                _decision(
                    assertion,
                    "rejected",
                    "unknown_credential",
                    "not_evaluated",
                    "unknown",
                )
            )
            continue
        failure = None
        if record["status"] == "revoked":
            failure = "revoked_credential"
        elif assertion["user_id"] != record["user_id"]:
            failure = "user_mismatch"
        elif not assertion["signature_valid"]:
            failure = "invalid_signature"
        elif assertion["origin"] not in policy["allowed_origins"]:
            failure = "disallowed_origin"
        elif assertion["rp_id"] != policy["rp_id"]:
            failure = "rp_id_mismatch"
        elif policy["require_user_verification"] and not assertion["user_verified"]:
            failure = "user_verification_required"
        elif assertion["backup_eligible"] != record["backup_eligible"]:
            failure = "backup_eligibility_mismatch"
        elif assertion["backup_state"] and not assertion["backup_eligible"]:
            failure = "illegal_backup_state"
        if failure is not None:
            decisions.append(
                _decision(
                    assertion, "rejected", failure, "not_evaluated", record["risk"]
                )
            )
            continue
        stored = record["sign_count"]
        current = assertion["sign_count"]
        if stored == 0 and current == 0:
            counter_status = "unavailable"
        elif current > stored:
            counter_status = "advanced"
        else:
            counter_status = "regression"
        if counter_status == "regression":
            action = (
                policy["synced_counter_action"]
                if record["backup_eligible"]
                else policy["device_counter_action"]
            )
            if action == "reject":
                record["risk"] = "compromised"
                decisions.append(
                    _decision(
                        assertion,
                        "rejected",
                        "counter_regression",
                        counter_status,
                        record["risk"],
                    )
                )
                continue
            if action == "flag" and record["risk"] == "normal":
                record["risk"] = "elevated"
            reason = "counter_flagged" if action == "flag" else "accepted"
            record["sign_count"] = max(stored, current)
        else:
            reason = "accepted"
            if counter_status == "advanced":
                record["sign_count"] = current
        record["backup_state"] = assertion["backup_state"]
        record["last_assertion"] = assertion_id
        decisions.append(
            _decision(assertion, "accepted", reason, counter_status, record["risk"])
        )
    return {
        "credentials": [_clone_credential(records[key]) for key in sorted(records)],
        "decisions": decisions,
    }
