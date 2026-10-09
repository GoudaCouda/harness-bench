# Trace propagation contract

Implement `propagate_contexts(requests, policy)` without mutating inputs. Exact
structural violations raise `ValueError` before producing partial output.

Policy has `vendor_key`, sorted unique `sensitive_baggage_keys`,
`max_tracestate_entries` (1..32), and `max_baggage_entries` (1..180).
Each request has exact keys: `request_id`, `traceparent` (list of header values),
`tracestate` (list), `baggage` (list), `participate`, `boundary`
(`internal`/`external`), `local_parent_id`, `fallback_trace_id`,
`vendor_value`, and `sampled`. IDs supplied locally are lowercase nonzero hex
of length 16 or 32 as appropriate; malformed local IDs are structural errors.

Incoming traceparent is valid only when exactly one value exists. Version `00`
is exactly `00-<32hex trace>-<16hex parent>-<2hex flags>`. Version `ff`, uppercase
hex, zero trace/parent IDs, bad separators, and version-00 suffixes are invalid.
A future version `01`..`fe` accepts the same four fields plus zero or more
nonempty dash-separated lowercase hex extension fields. Only bit 0 of flags is
known; clear all other bits on a participating or restarted outgoing header.

A valid pass-through request emits traceparent byte-for-byte. A valid
participating request emits version `00`, preserves trace ID, uses
`local_parent_id`, and sets flags to `01` when `sampled`, else `00`. Invalid or
missing traceparent restarts using `fallback_trace_id`, `local_parent_id`, and
the sampled flag, with disposition `restarted`; inherited tracestate is dropped.

Combine tracestate header values with commas. It is valid when total length is
at most 512, entries are 1..policy maximum, keys are unique lowercase tokens,
and values are printable ASCII excluding comma and equals. Invalid tracestate
is dropped but does not affect valid traceparent. Pass-through preserves the
combined string exactly. Participation removes the local vendor key if present,
prepends `vendor_key=vendor_value`, and keeps remaining order.

Combine baggage values with commas. Each member is `key=value` with optional
`;property` segments. Keys are lowercase tokens and unique. Values/properties
use printable ASCII without comma, semicolon, or controls; every `%` must be
followed by two uppercase hex digits. Invalid baggage is dropped. On external
requests, remove policy-sensitive keys; preserve order and original member text
for all retained entries. Enforce the configured entry limit after filtering.

Emit one decision per input in order with `request_id`, `disposition`
(`forwarded`, `participated`, `restarted`), and nullable outgoing
`traceparent`, `tracestate`, and `baggage`. Metrics count forwarded,
participated, restarted, dropped_tracestate, dropped_baggage, and
filtered_baggage_entries. No clock, random, network, or telemetry capability is allowed.
