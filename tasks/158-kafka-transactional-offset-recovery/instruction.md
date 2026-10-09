# Repair Kafka transactional offset recovery

An exactly-once consume-transform-produce worker crashed around transaction
commits. Its recovery planner may replay committed work, trust partial evidence,
or continue with a fenced producer. Work only in `/workspace/repo`.

Read `docs/recovery_contract.md`, inspect the incident batches, policy, runner,
and public tests, then repair `src/transaction_recovery.py` as a general pure
implementation. Run the public tests and `python bin/plan_recovery.py`; re-parse
`out/decisions.json` and `out/summary.json`. Write `RECOVERY_NOTES.md` covering
read-committed evidence, transactional offset commits, ambiguous outcomes,
deterministic output keys, producer epochs and fencing, abort/reinitialize/
replay choices, retry budgets, atomicity violations, validation, commands and
results, and the offline/no-cluster boundary.

Do not connect to Kafka, reset consumer offsets, publish records, initialize a
producer, alter a consumer group, or claim production recovery.
