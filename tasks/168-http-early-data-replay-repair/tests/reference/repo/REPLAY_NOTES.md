# Early-data replay repair handoff

The repaired planner treats a TLS ticket as transport evidence, not as blanket
application replay permission. A new request enters 0-RTT only when its method
is in the configured safe methods, the application has an explicit opt-in,
and the request body is replayable. These checks are ordered so an unsafe
method remains the primary reason even when later checks also fail.

The resumed profile is all-or-nothing for this planner. Ticket age is accepted
at the inclusive policy boundary, while an older ticket waits. Remembered ALPN
must equal current ALPN, and both transport parameters and application settings
must match. When required by policy, anti-replay consistency across serving
instances must also hold. The code does not cherry-pick a favorable remembered
setting while ignoring an incompatible one.

An intermediary has a separate provenance check. Any received Early-Data
header list is a marker, so malformed values and multiple values are treated as
normalized value `1`. A proxy can forward in early data only when the origin
supports 425 and the request was marked or the route was explicitly configured
safe. Forwarded early data propagates the normalized marker. Marked input whose
origin cannot support 425 is rejected with 425; unmarked traffic waits for the
handshake instead of manufacturing an early-data path.

Accepted requests with ordinary responses are complete. A 425 response is
never retried as early data: a replayable request with remaining attempt budget
is scheduled after the handshake, its attempt is incremented, and application
state is reset. QUIC/TLS rejection follows the same after-handshake rule and
reset requirement. Non-replayable bodies and exhausted attempts block. A
pending attempt waits for the handshake without claiming completion or reset.

Verification used `python -m unittest discover -s tests -p test_public.py` and
`python bin/plan_early_data.py`; the public tests passed and the generated
decisions and summary were parsed as JSON. The visible replay contains seven
requests: two send in 0-RTT, one waits for the handshake, two retry after the
handshake, one is complete, and one is rejected with 425.

This was an offline deterministic verification only. No network socket, live
QUIC connection, TLS ticket, intermediary, or origin was contacted, and no
production behavior or cryptographic validation is claimed.
