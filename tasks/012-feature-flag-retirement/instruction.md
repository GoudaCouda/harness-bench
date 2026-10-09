# Retire `checkout_v2` without breaking replay

The checkout team finished the `checkout_v2` rollout. Remove the retired flag
from the local registry while preserving deterministic behavior when historical
checkout events are replayed.

Work only inside `repo/`. Read `repo/docs/retirement_contract.md`,
`repo/policy.json`, `repo/replay_events.json`, the current flag registry, source,
and public tests before editing.

Deliver all three artifacts:

1. Repair `repo/src/checkout_policy.py`. Keep the public function
   `select_checkout_engine(event, policy)` and its return contract. It must use
   the event's business timestamp—not receipt time—to distinguish historical
   replay from the retired default, validate malformed input rather than guess,
   and leave both inputs unchanged.
2. Update `repo/config/flags.json`: remove only `checkout_v2`; preserve the
   registry schema and every unrelated flag record exactly.
3. Create `repo/MIGRATION_NOTES.md` explaining the historical/live split, the
   exact verification command and observed result, and one remaining adapter
   risk. Do not claim a deployment, control-plane deletion, or production
   change occurred.

Run verification from `repo/` with exactly:

```text
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
```

Do not edit the policy, replay fixture, contract, or public tests. Do not call a
flag service, deploy code, or modify anything outside `repo/`.
