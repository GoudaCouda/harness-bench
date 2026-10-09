# Provider-boundary session traces

HarnessBench records the common model boundary instead of depending on a
harness to export its private session format. Every agent generation passes
through the per-trial `ModelBudgetProxy`, so this is the only layer that can
apply one trace and token-accounting contract to Chat Completions, Responses,
and Anthropic Messages without changing a harness.

## Files

Every new task result owns a trusted `provider-trace/` directory:

- `transactions.jsonl` is the authoritative append-only record. One line
  contains the exact rewritten request body, the exact response body observed
  from the model service, hashes, byte counts, protocol, timestamps, response
  status, completion state, normalized events, and request token usage.
- `trajectory.jsonl` is the protocol-neutral observation stream. Entries use
  `system`, `developer`, `user`, `assistant`, `assistant_reasoning`,
  `tool_call`, and `tool_result` event types and identify whether the event
  came from a request-context snapshot or the corresponding response.
- `session-summary.json` contains the session token totals, token coverage,
  transaction counts, normalized trajectory lengths, and raw byte lengths.

`result.json` embeds the session summary as `provider_trace` and lists all
three files in `provider_trace_files`. The harness-native trace remains useful
for product-specific debugging, but it is no longer the accounting source of
truth.

The request context in `trajectory.jsonl` is intentionally an observation,
not a claim that every repeated message is a new turn. Stateless model APIs
resend accumulated context, so the same earlier message may be observed in
several provider transactions. `provider_transactions` is the stable turn
count. Analysts that need a compact conversation can deduplicate common
request-context prefixes while retaining `transactions.jsonl` as evidence.

## Token accounting

The wrapper reads usage from the provider response, never from a harness
estimate:

- Chat Completions streaming requests are rewritten to set
  `stream_options.include_usage=true`.
- Responses usage is read from the completed response object.
- Anthropic Messages combines the message-start input usage and final
  message-delta output usage.

The normalized totals are:

- `input_tokens`;
- `cached_input_tokens`;
- `cache_write_input_tokens`;
- `output_tokens`;
- `reasoning_output_tokens`, when the protocol reports it (a subset of output,
  not added twice);
- `total_tokens`.

`token_coverage` is the fraction of forwarded model transactions that ended
with a parseable provider usage record. A local request-151 rejection is
recorded in the trajectory but excluded from the usage denominator because it
never reached the model. A timeout, upstream error, or downstream disconnect
that prevents the usage trailer remains visibly partial instead of being
estimated.

The 200,000-token fairness setting is a per-request context ceiling. Session
input totals can be much larger because each agent turn may resend the growing
conversation.

## Completeness and failure behavior

The recorder writes each completed or partial provider transaction with flush
and `fsync`, then atomically replaces the session summary. The controller
compares the number of persisted transactions with accepted plus locally
rejected requests. A mismatch is an infrastructure error; it cannot silently
produce a score with a missing provider trace.

Raw request and response bodies are retained because normalized schemas will
evolve. Authorization headers and transport headers are never recorded. The
formal local vLLM service is credential-free, but run roots should still be
treated as evaluation evidence with the same access controls and retention
policy as prompts and terminal workspaces.

## Schema evolution

All three files carry `schema_version`. Additive normalizer improvements must
not rewrite old raw transactions. A future compactor may create a deduplicated
conversation view from request-context prefixes, but it must preserve the raw
JSONL hashes and distinguish derived message count from observed trajectory
length.
