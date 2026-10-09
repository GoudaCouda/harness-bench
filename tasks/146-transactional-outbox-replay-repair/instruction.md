# Repair transactional-outbox recovery

An outbox relay restarted after acknowledgements, lease expirations, and retry
state diverged. A naive replay can duplicate publication or release later events
for an aggregate out of order. Work only in `/workspace/repo`.

Read `docs/recovery_contract.md`, inspect the captured rows, receipts, policy,
runner, and public tests, then repair `src/outbox_recovery.py` as a general pure
implementation. Do not hard-code event IDs, aggregate IDs, timestamps, or hashes.

Run the public unittest suite and `python bin/recover_outbox.py`. The final run
must create `out/state.json` and `out/actions.json`; parse both again. Write
`OUTBOX_NOTES.md` covering receipt authority, ambiguous outcomes, lease expiry,
retry/dead-letter limits, per-aggregate ordering, idempotency keys, strict
validation, commands, and results.

Do not edit captured evidence, contact a broker or database, publish messages,
or claim that any live queue, relay, or consumer was changed.
