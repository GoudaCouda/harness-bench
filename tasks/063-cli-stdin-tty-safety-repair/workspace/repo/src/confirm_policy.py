def decide_run(config, stdin_text):
    """Broken confirmation planner retained for repair."""
    if config.get("target_count", 0) == 0:
        return {"action": "noop", "exit_code": 0, "confirmation": "not_required", "stdin_consumed": False}
    if config.get("no_input"):
        return {"action": "blocked", "exit_code": 2, "confirmation": "no_input", "stdin_consumed": False}
    token = stdin_text.strip().casefold()
    if config.get("yes") or token in ("y", "yes"):
        return {"action": "execute", "exit_code": 0, "confirmation": "pipe", "stdin_consumed": True}
    return {"action": "abort", "exit_code": 0, "confirmation": "pipe", "stdin_consumed": True}
