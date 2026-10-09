# Repair notes

The planner now separates TTY prompting from piped stdin and never consumes a
TTY-owned response. `--yes` is explicit authority and precedes `--no-input`;
without it, `--no-input`, empty stdin, multiple lines, and unknown tokens fail
closed. Plan and zero-target paths require no confirmation. Execute, abort,
usage-block, and prompt states have distinct exit-code behavior.

Verification: `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v`
completed successfully with all public tests passing. Residual risk remains in
the caller: it must map the plan to one action exactly once and must not treat a
null prompt exit code as authorization. No deletion or remote action was run.
