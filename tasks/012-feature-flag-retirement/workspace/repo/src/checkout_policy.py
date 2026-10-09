def select_checkout_engine(event, policy):
    """Return the checkout engine decision for one event."""
    # The rollout is complete, but this stub incorrectly ignores replay history.
    return {
        "event_id": event["event_id"],
        "engine": "v2",
        "decision_source": "retired_default",
    }
