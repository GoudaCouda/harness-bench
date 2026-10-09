def verify_bundles(artifacts, bundles, roots, policy):
    # Broken: cryptographic signature alone is treated as the complete policy.
    decisions = [
        {
            "artifact_id": item["artifact_id"],
            "status": "verified",
            "reason": "trusted",
            "signing_time": None,
            "tlog_operator_count": 0,
        }
        for item in artifacts
    ]
    return {
        "decisions": decisions,
        "summary": {
            "artifact_count": len(artifacts),
            "verified": len(artifacts),
            "blocked": 0,
        },
    }
