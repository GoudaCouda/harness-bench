# Transaction recovery contract

`plan_transaction_recovery(batches, policy)` is pure and returns exactly
`{"decisions": [...], "summary": {...}}` without mutating either argument.

Inputs use exact schemas and sorted unique batch IDs. Integer fields are
non-negative, `first_offset <= last_offset`, `producer_epoch <= owner_epoch`,
and expected output keys are sorted, unique, non-empty lowercase tokens.
Visible keys must be a subset of expected keys. A transactional ID must begin
with the configured lowercase prefix. Policy has exactly `max_retries`,
`require_read_committed`, `require_transactional_offsets`, and
`transactional_id_prefix`; retry budget is a positive integer.

The only definitive success evidence is both the group offset at
`last_offset + 1` and every deterministic output key visible under
`read_committed`. That evidence is settled even after an ambiguous response.
Any partial output, an offset inside/past the batch without complete output, or
complete output without the exact next offset is an `atomicity_violation`.

Before replay, require policy and batch isolation `read_committed`, policy and
batch offset mode `transactional`, current producer ownership, and remaining
retry budget. An open transaction is `abort_and_replay`; `commit_unknown` or
`fenced` with no committed evidence is `reinitialize_and_replay`; `aborted` or
`not_started` is `replay_batch`. A stale epoch is blocked as
`producer_fenced`. Unsafe configuration and exhausted retry budget are blocked.

Each decision has exactly `batch_id`, `status`, `action`, `reason`, and
`next_offset`. Settled uses `acknowledge_committed`, reason
`atomic_commit_visible`, and next offset `last_offset + 1`. Ready decisions use
the action above, reason `safe_replay`, and `first_offset`. Blocked decisions
use action `halt` and the observed `committed_offset`. Summary has exactly
`batch_count`, `settled`, `ready`, `blocked`, and `replay_records`; the last is
the inclusive input-record count of ready batches.
