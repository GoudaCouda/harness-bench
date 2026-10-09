import hashlib
import hmac


def verify_batch(deliveries, keyring, policy, checkpoint):
    """Broken: verifies every body with the newest key and ignores replay state."""
    newest = max(keyring, key=lambda item: item["not_before"])
    decisions = []
    for delivery in deliveries:
        timestamp = delivery["signature_header"].split(",")[0].split("=")[1]
        expected = hmac.new(
            newest["secret"].encode(),
            (timestamp + "." + delivery["raw_body"]).encode(),
            hashlib.sha256,
        ).hexdigest()
        supplied = delivery["signature_header"].split("v1=")[-1]
        ok = expected == supplied
        decisions.append({"delivery_id": delivery["delivery_id"], "status": "accepted" if ok else "rejected", "reason": "ok" if ok else "bad_signature", "matched_key_ids": [newest["key_id"]] if ok else []})
    return {"decisions": decisions, "checkpoint": checkpoint}
