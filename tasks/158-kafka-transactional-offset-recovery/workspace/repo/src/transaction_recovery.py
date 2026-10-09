def plan_transaction_recovery(batches, policy):
    # Broken: state names are trusted without reconciling offsets or output.
    decisions = []
    for batch in batches:
        decisions.append(
            {
                "batch_id": batch["batch_id"],
                "status": "ready",
                "action": "replay_batch",
                "reason": "safe_replay",
                "next_offset": batch["first_offset"],
            }
        )
    return {
        "decisions": decisions,
        "summary": {
            "batch_count": len(batches),
            "settled": 0,
            "ready": len(batches),
            "blocked": 0,
            "replay_records": 0,
        },
    }
