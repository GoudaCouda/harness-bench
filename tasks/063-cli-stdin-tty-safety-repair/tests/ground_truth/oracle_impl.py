def decide_run(config, stdin_text):
    if not isinstance(config, dict) or set(config) != {"mode", "target_count", "yes", "no_input", "stdin_is_tty"}:
        raise ValueError("invalid config shape")
    mode = config["mode"]
    count = config["target_count"]
    if mode not in ("apply", "plan") or type(count) is not int or count < 0:
        raise ValueError("invalid mode or target count")
    if any(type(config[name]) is not bool for name in ("yes", "no_input", "stdin_is_tty")) or not isinstance(stdin_text, str):
        raise ValueError("invalid input type")

    def result(action, exit_code, confirmation, consumed=False):
        return {"action": action, "exit_code": exit_code, "confirmation": confirmation, "stdin_consumed": consumed}

    if mode == "plan":
        return result("preview", 0, "not_required")
    if count == 0:
        return result("noop", 0, "not_required")
    if config["yes"]:
        return result("execute", 0, "flag")
    if config["no_input"]:
        return result("blocked", 2, "no_input")
    if config["stdin_is_tty"]:
        return result("prompt", None, "tty")
    lines = stdin_text.splitlines()
    if not lines or (len(lines) == 1 and not lines[0].strip()):
        return result("blocked", 2, "empty_stdin", True)
    if len(lines) != 1:
        return result("blocked", 2, "multiple_lines", True)
    token = lines[0].strip().casefold()
    if token in ("y", "yes"):
        return result("execute", 0, "pipe", True)
    if token in ("n", "no"):
        return result("abort", 1, "pipe", True)
    return result("blocked", 2, "invalid_confirmation", True)
