# Repair trace-context propagation

A service mesh adapter breaks traces when `tracestate` is malformed and leaks
sensitive baggage across an external trust boundary. Work only in
`/workspace/repo`.

Read `docs/trace_contract.md`, inspect request contexts, policy, runner, and
public tests, then repair `src/trace_context.py` as a general pure
implementation. Do not hard-code fixture IDs, vendors, or baggage keys.

Run the public unittest suite and `python bin/propagate_traces.py`. The final
run must create `out/decisions.json` and `out/metrics.json`; parse both again.
Write `TRACE_NOTES.md` covering traceparent validation/restart, pass-through
versus participation, tracestate independence and vendor ordering, baggage
parsing/privacy filtering, sampling flags, strict validation, commands, and results.

Do not edit evidence, send requests, export telemetry, or claim that a live
tracer, collector, mesh, or service was changed.
