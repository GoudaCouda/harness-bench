# Repair Redis Cluster request recovery

A Redis Cluster client updates its slot cache for both MOVED and ASK and
retries every transport timeout. Work only in `/workspace/repo`.

Read `docs/cluster_retry_contract.md`, inspect request observations, slot cache,
policy, runner, and public tests, then repair `src/cluster_retry.py` as a
general pure implementation. Run public tests and
`python bin/plan_cluster_retries.py`; re-parse all files in `out/`. Write
`REDIRECTION_NOTES.md` covering same-slot preflight, MOVED permanence, ASK as a
one-shot redirect with ASKING and no cache update, contradictory redirect
evidence, TRYAGAIN backoff, READONLY/unassigned refresh, CLUSTERDOWN/timeout
ambiguity, idempotency, retry/deadline budgets, commands/results, and the
offline/no-Redis boundary.

Do not contact Redis, open sockets, mutate a cluster, or claim live resharding,
failover, cache refresh, or production validation.
