# RPC budget handoff

The repaired planner propagates one incoming deadline rather than granting a
fresh timeout to each attempt. Elapsed work, a fixed completion reserve, and
exponential backoff all consume that same budget. Backoff is capped, and the
remaining amount after delay/reserve is capped again by the per-try timeout.
If no positive budget remains, the call is blocked before starting work.

An OK result is retained. A caller cancellation stops application processing
and cancels every active child RPC; transport cancellation alone cannot clean
up spawned work. Once response headers arrive, gRPC considers the attempt
committed, so the planner does not transparently retry it. Otherwise the status
must be configured retryable, the operation must be idempotent, and the attempt
limit must have room. ABORTED in a parent read-modify-write operation is not a
leaf retry: it returns `restart_parent` so the whole operation can be rebuilt.

Verification passed with `python -m unittest discover -s tests -v` and
`python bin/plan_calls.py`. I parsed both protected JSON outputs and confirmed
six calls: one settled, one retry-ready, three blocked, and one stopped; exactly
two child RPCs are marked for cancellation and one leaf retry is planned. This
was an offline, no-RPC exercise. I did not contact a service, cancel a live
call, restart a parent operation, change retry configuration, or claim a
production retry.
