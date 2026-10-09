# Kafka transaction recovery handoff

The repaired planner treats the decoded transaction state as context, not as
proof. A batch is settled only when a `read_committed` observation contains
every deterministic output key and the consumer-group offset is exactly the
input batch's last offset plus one. This joint evidence resolves an ambiguous
or unknown commit response without replaying work that already committed. A
partial key set, a mid-batch or advanced offset without all outputs, or outputs
without the exact next offset is an atomicity violation and halts recovery.

Replay is allowed only with read-committed isolation and transactional offset
commits (`sendOffsetsToTransaction` semantics). Independent offset commits can
lose output/offset atomicity. The transactional ID is policy scoped. Producer
epoch ownership is checked before retry: an older epoch is fenced and may not
continue. A current open transaction uses abort and replay; a commit-unknown or
fenced state with no committed evidence requires reinitialize and replay; an
aborted or not-started batch uses replay. Every retry uses the original
deterministic keys, starts at `first_offset`, and respects the retry budget.

Verification passed with `python -m unittest discover -s tests -v`, followed by
`python bin/plan_recovery.py`. I parsed both JSON outputs and confirmed five
decisions: one settled, two ready, two blocked, with four replay records. The
source is pure and the evidence files stayed unchanged. This was an offline
exercise with no cluster connection: I did not initialize or fence a real
producer, publish records, reset offsets, change a consumer group, or perform
production recovery.
