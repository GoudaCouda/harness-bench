# HTTP/2 retry handoff

The repaired planner uses the GOAWAY `last-stream-id` as an inclusive protocol
boundary. A completed stream at or below that boundary keeps its response. An
unfinished stream above it was unprocessed by the peer and can retry on a
fresh connection even when its method is POST, provided the request body is
replayable. A `REFUSED_STREAM` reset supplies the same definite non-processing
signal. Those cases are different from merely seeing no response.

An unfinished stream at or below the last stream is ambiguous: the server may
have applied its side effect. Configured idempotent methods can retry. An unsafe
method needs an idempotency key under this policy and retries with that same key;
without one it is blocked. Method safety does not make a consumed request body
replayable, so that check remains independent. Retry budget and retryable
GOAWAY error-code policy are checked before any replay, while a completed
response remains settled. Every retry targets a fresh connection; no new stream
is opened on the draining connection.

Verification passed with `python -m unittest discover -s tests -v`, followed by
`python bin/plan_retries.py`. I parsed both protected JSON files and confirmed
five decisions: one settled, two retries, two blocked, with stream 7 the
highest retry stream. Invalid even client stream IDs and contradictory
completion evidence fail closed in hidden validation. This was an offline,
no-network exercise: I did not reconnect, send HTTP traffic, replay any live
body, or claim production requests were retried.
