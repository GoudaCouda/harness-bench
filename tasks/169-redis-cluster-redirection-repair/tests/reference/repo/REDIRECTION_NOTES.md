# Redis Cluster redirection repair handoff

The repaired planner performs same-slot preflight before trusting a server
error. A command spanning distinct key slots is blocked as cross-slot work and
cannot turn a contradictory MOVED response into a topology change. Successful
result evidence completes without spending retry or deadline budget.

MOVED and ASK now have deliberately different effects. A valid MOVED is
permanent slot-ownership evidence, so it updates the sparse slot cache and
targets the redirected node. The topology update remains useful even if the
request itself has exhausted attempts or deadline. ASK is one-shot: only that
request targets the importing node, it sends ASKING first, and the cached slot
owner remains unchanged. Redirect slot must equal the command's sole key slot;
contradictory evidence blocks instead of rewriting the cache.

TRYAGAIN uses capped exponential backoff. READONLY and an unassigned slot first
refresh topology, leaving target selection to the refreshed map. CLUSTERDOWN
and transport timeout are treated as ambiguous; a non-idempotent command is
not replayed, while an idempotent command can use capped backoff. Attempt
exhaustion precedes timing, and every retry requires deadline remaining to be
strictly greater than backoff plus reserve (or reserve alone for redirect and
refresh paths).

Verification used `python -m unittest discover -s tests -p test_public.py` and
`python bin/plan_cluster_retries.py`. Public tests passed and decisions, final
slots, and summary were parsed as JSON. The visible replay completes one,
redirects two, backs off one, refreshes one, blocks two, and makes one permanent
topology update.

This was offline deterministic verification only. No Redis server, socket,
cluster refresh, ASKING command, resharding, failover, or production mutation
was executed or claimed.
