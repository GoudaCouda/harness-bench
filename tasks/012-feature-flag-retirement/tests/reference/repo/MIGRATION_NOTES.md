# Checkout flag retirement handoff

Historical replay and current traffic now take deliberately different paths.
An event strictly before the retirement cutoff uses its recorded
`checkout_v2` boolean snapshot, even when `received_at` is much later; this
keeps reconciliation deterministic. At the cutoff and afterward, the code
ignores the obsolete snapshot and uses the retired v2 default. Invalid history
fails closed instead of silently selecting an engine. The local registry removes
only `checkout_v2` and preserves the two unrelated active flags.

I ran `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` from
`repo/`; both public tests passed successfully.

Remaining risk: an upstream adapter could normalize timestamps or booleans
before this pure boundary and hide malformed wire data. Deployment and remote
control-plane flag deletion were not performed and require separate approval.
