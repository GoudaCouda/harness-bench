# Confirmation contract

`decide_run(config, stdin_text)` plans behavior; it never performs the action.
`config` has exactly `mode`, `target_count`, `yes`, `no_input`, and
`stdin_is_tty`. `mode` is `apply` or `plan`; booleans must be real booleans and
`target_count` a non-negative integer (not a boolean). Invalid state raises
`ValueError`.

Return `action`, `exit_code`, `confirmation`, and `stdin_consumed`.

1. `plan` returns `preview`, code 0, `not_required`, and never consumes stdin.
2. An apply with zero targets returns `noop`, code 0, `not_required`.
3. Explicit `yes` is next and returns `execute`, code 0, `flag`; it is valid
   with `no_input` because no prompt is required.
4. Otherwise `no_input` returns `blocked`, code 2, `no_input`.
5. Otherwise a TTY returns `prompt`, a null exit code, `tty`, without consuming
   the supplied text. The caller owns the actual prompt.
6. Non-TTY stdin consumes exactly one logical line. `y`/`yes` executes with
   `pipe`; `n`/`no` aborts with code 1 and `pipe`; matching ignores surrounding
   space and case. Empty, unknown, or multiple lines are `blocked`, code 2,
   with `empty_stdin`, `invalid_confirmation`, or `multiple_lines`.

No ambiguous state may return `execute`.
