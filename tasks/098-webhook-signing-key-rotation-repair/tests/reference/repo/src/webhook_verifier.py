import hashlib
import hmac


def _integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _exact(value, keys):
    return isinstance(value, dict) and set(value) == set(keys)


def _preflight(deliveries, keyring, policy, checkpoint):
    if (not _exact(policy, ("algorithm", "signature_version", "tolerance_seconds")) or policy["algorithm"] != "hmac-sha256" or policy["signature_version"] != "v1" or not _integer(policy["tolerance_seconds"]) or not 0 <= policy["tolerance_seconds"] <= 900):
        raise ValueError("invalid policy")
    if not _exact(checkpoint, ("seen_delivery_ids",)) or not isinstance(checkpoint["seen_delivery_ids"], list):
        raise ValueError("invalid checkpoint")
    seen = checkpoint["seen_delivery_ids"]
    if any(not isinstance(item, str) or not item for item in seen) or len(seen) != len(set(seen)):
        raise ValueError("invalid seen ids")
    if not isinstance(keyring, list):
        raise ValueError("invalid keyring")
    key_ids = []
    for key in keyring:
        if (not _exact(key, ("key_id", "endpoint", "secret", "not_before", "not_after")) or any(not isinstance(key[name], str) or not key[name] for name in ("key_id", "endpoint", "secret")) or not _integer(key["not_before"]) or not _integer(key["not_after"]) or key["not_before"] < 0 or key["not_before"] >= key["not_after"]):
            raise ValueError("invalid key")
        key_ids.append(key["key_id"])
    if len(key_ids) != len(set(key_ids)) or not isinstance(deliveries, list):
        raise ValueError("invalid deliveries")
    delivery_ids = []
    for delivery in deliveries:
        if (not _exact(delivery, ("delivery_id", "endpoint", "received_at", "raw_body", "signature_header")) or any(not isinstance(delivery[name], str) for name in ("delivery_id", "endpoint", "raw_body", "signature_header")) or not delivery["delivery_id"] or not delivery["endpoint"] or not _integer(delivery["received_at"]) or delivery["received_at"] < 0):
            raise ValueError("invalid delivery")
        delivery_ids.append(delivery["delivery_id"])
    if len(delivery_ids) != len(set(delivery_ids)):
        raise ValueError("duplicate delivery")


def _header(value):
    timestamps, signatures = [], []
    try:
        for part in value.split(","):
            part = part.strip()
            if part.count("=") != 1:
                raise ValueError
            name, item = part.split("=", 1)
            if not name or not item:
                raise ValueError
            if name == "t":
                timestamps.append(item)
            elif name == "v1":
                signatures.append(item)
        if len(timestamps) != 1 or not timestamps[0].isascii() or not timestamps[0].isdigit() or not signatures:
            raise ValueError
        if any(len(item) != 64 or any(ch not in "0123456789abcdef" for ch in item) for item in signatures):
            raise ValueError
        return int(timestamps[0]), signatures
    except ValueError:
        return None


def verify_batch(deliveries, keyring, policy, checkpoint):
    _preflight(deliveries, keyring, policy, checkpoint)
    seen, decisions = set(checkpoint["seen_delivery_ids"]), []
    for delivery in deliveries:
        parsed = _header(delivery["signature_header"])
        status, reason, matched = "rejected", "malformed_header", []
        if parsed is not None:
            timestamp, signatures = parsed
            if abs(delivery["received_at"] - timestamp) > policy["tolerance_seconds"]:
                reason = "outside_tolerance"
            else:
                eligible = [key for key in keyring if key["endpoint"] == delivery["endpoint"] and key["not_before"] <= timestamp < key["not_after"]]
                if not eligible:
                    reason = "no_eligible_key"
                else:
                    payload = f'{timestamp}.{delivery["raw_body"]}'.encode("utf-8")
                    for key in eligible:
                        expected = hmac.new(key["secret"].encode("utf-8"), payload, hashlib.sha256).hexdigest()
                        if any(hmac.compare_digest(expected, supplied) for supplied in signatures):
                            matched.append(key["key_id"])
                    matched.sort()
                    if not matched:
                        reason = "bad_signature"
                    elif delivery["delivery_id"] in seen:
                        status, reason = "duplicate", "already_seen"
                    else:
                        status, reason = "accepted", "ok"
                        seen.add(delivery["delivery_id"])
        decisions.append({"delivery_id": delivery["delivery_id"], "status": status, "reason": reason, "matched_key_ids": matched})
    return {"decisions": decisions, "checkpoint": {"seen_delivery_ids": sorted(seen)}}
