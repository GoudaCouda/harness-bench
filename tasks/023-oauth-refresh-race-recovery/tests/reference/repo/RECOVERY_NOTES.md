# OAuth refresh race recovery

The reconciler validates the session and sorts attempts by completion sequence.
Only the current generation and current refresh token may compete. The first
valid success is the winner; a rotated refresh token advances the generation,
and later losing invalid_grant responses are ignored. A stale generation can
never overwrite current state.

An invalid_grant before any winner invalidates local credentials and requires
reauthorization rather than retry. Transient server errors schedule one future
single-flight retry. Scope widening, missing required rotation, token mismatch,
or two successes fail closed for manual review.

I ran `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` from
`repo/`; both public tests passed successfully.

Remaining risk: a real persistence adapter still needs a compare-and-swap on
generation so state cannot change between reconciliation and commit. No token
endpoint call, revocation, credential disclosure, or production change occurred.
