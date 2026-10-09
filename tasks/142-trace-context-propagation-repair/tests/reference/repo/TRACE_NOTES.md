# Trace propagation repair handoff

Traceparent validation treats duplicate headers, uppercase or malformed hex,
version ff, zero trace/parent IDs, and version-00 extensions as invalid. A
future version retains parseable extension fields for pass-through. Invalid
incoming identity is restarted from the supplied local trace and parent IDs.
A valid forwarding request preserves traceparent bytes; participation emits
version 00 with the local parent and the requested sampled flags.

Tracestate is independent: invalid optional state is dropped without restarting
a valid traceparent. Participation moves or inserts the local vendor member at
the front while retaining the other order and limit. Restart discards inherited
vendor state.

Baggage parsing validates unique lowercase keys, properties, and uppercase
percent escapes. Internal baggage order is preserved. At an external privacy
boundary, configured sensitive entries are filtered while retained member text
remains byte-stable. Invalid baggage is dropped as a unit and metrics distinguish
that from privacy filtering.

`PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` passed.
`PYTHONDONTWRITEBYTECODE=1 python bin/propagate_traces.py` succeeded, and both
JSON outputs were parsed again. No request or telemetry was sent, no span was
exported, and no tracer, collector, mesh, or live service was changed.
