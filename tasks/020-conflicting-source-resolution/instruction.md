# Recover the Kestrel launch control room after late evidence

You are taking over Project Kestrel's launch gate on 2025-08-21. The current
control state was prepared from an early communications draft. Later scoped
records have arrived, and several queued actions may no longer be safe.

Work only in `$WORKSPACE`. Start by running:

```bash
python3 bin/kestrelctl.py inspect
python3 bin/kestrelctl.py verify
```

Read the authority and launch policy under `governance/`, then reconcile all
records under `briefs/`. Authority is claim-scoped: do not apply one source's
authority to facts that it does not certify.

Repair the operational state in place:

- `control/launch_gate.json`: replace stale facts with the current scoped
  decision, represent unresolved prerequisites as blockers, and keep contracted
  future scope distinct from currently authorized scope;
- `control/action_queue.json`: stop unsafe queued external actions while
  preserving the four existing action identities and any safe internal check;
- `control/decision_events.jsonl`: preserve the two historical lines byte for
  byte and append exactly one current review event with workspace-relative
  primary evidence and a `supersedes` link to the stale decision;
- `decision_handoff.md`: explain the gate, scoped source choices, queue changes,
  open prerequisites, and what evidence would permit a later release.

Run `python3 bin/kestrelctl.py verify` again and leave it passing. Re-open all
modified JSON/JSONL before finishing. Do not edit evidence, policy, governance,
or the verifier; do not use the network; and do not claim that a real customer
announcement or service activation occurred.
