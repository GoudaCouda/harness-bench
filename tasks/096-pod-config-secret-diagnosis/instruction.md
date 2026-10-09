# Recover a stalled `invoice-api` rollout from mixed-generation evidence

You are the on-call platform engineer for a synthetic offline Kubernetes incident. The current rollout is stalled across secret synchronization, process startup, readiness, and Service routing. The workspace includes historical events from more than one generation, so chronology and evidence authority matter.

Inspect policy, manifests, rollout history, image contract, configuration inventory, secret-provider metadata, events, and logs. First run the protected simulator's `observe` operation against the unmodified manifests and save `cluster/before_state.json`. Diagnose the causal sequence, then make the smallest policy-allowed changes to the mutable manifests. Do not expose or invent secret values, change the approved image/replicas/selectors/labels/strategy, or weaken probes.

Run `reconcile` to produce `cluster/observed_state.json`, followed by `verify`; use staged diagnostics until all four layers pass. Create `repair_handoff.md` that maps each changed field to current evidence, distinguishes stale observations, records before/after commands and results, lists invariants, and gives a field-level rollback checkpoint. There is no live cluster: do not claim a production rollout or customer recovery.
