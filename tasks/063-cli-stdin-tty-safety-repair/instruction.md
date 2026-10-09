# Repair a destructive CLI confirmation policy

An administration CLI can hang in automation, consume unrelated piped input,
or execute after an empty confirmation. Repair its local decision policy before
the command is enabled again.

Work only in `repo/`. Read the contract, broken implementation, visible cases,
and public tests. Preserve
`decide_run(config, stdin_text)`.

Deliver the repaired `repo/src/confirm_policy.py`, an ordered
`repo/decision_report.json` containing every visible `case_id` and exact result,
and `repo/REPAIR_NOTES.md`. Explain TTY versus piped stdin, `--yes` and
`--no-input` precedence, empty or ambiguous input, dry-run behavior, exit codes,
the exact verification command/result, and residual risk.

Run `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` from
`repo/`. The visible suite invokes `bin/confirm_cli.py` through real subprocess
stdin and a POSIX pseudo-terminal; no destructive command is present. Do not
edit evidence or claim that any deletion, remote command, or production action
was executed.
