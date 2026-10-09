def decide_run(config, stdin_text):
    if not isinstance(config, dict) or set(config) != {"mode", "target_count", "yes", "no_input", "stdin_is_tty"}:
        raise ValueError("invalid config shape")
    mode, count = config["mode"], config["target_count"]
    if mode not in ("apply", "plan") or type(count) is not int or count < 0:
        raise ValueError("invalid mode or target count")
    if any(type(config[name]) is not bool for name in ("yes", "no_input", "stdin_is_tty")) or not isinstance(stdin_text, str):
        raise ValueError("invalid input type")
    def out(action, code, confirmation, consumed=False):
        return {"action": action, "exit_code": code, "confirmation": confirmation, "stdin_consumed": consumed}
    if mode == "plan": return out("preview", 0, "not_required")
    if count == 0: return out("noop", 0, "not_required")
    if config["yes"]: return out("execute", 0, "flag")
    if config["no_input"]: return out("blocked", 2, "no_input")
    if config["stdin_is_tty"]: return out("prompt", None, "tty")
    lines = stdin_text.splitlines()
    if not lines or (len(lines) == 1 and not lines[0].strip()): return out("blocked", 2, "empty_stdin", True)
    if len(lines) != 1: return out("blocked", 2, "multiple_lines", True)
    token = lines[0].strip().casefold()
    if token in ("y", "yes"): return out("execute", 0, "pipe", True)
    if token in ("n", "no"): return out("abort", 1, "pipe", True)
    return out("blocked", 2, "invalid_confirmation", True)
