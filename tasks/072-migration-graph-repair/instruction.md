# Repair a split migration graph and prove replay safety

You are the framework migration maintainer. Two accepted branches created competing migration heads and the draft merge is not safe on fresh, upgrade, repeat, and reverse paths.

Your job is to make the smallest repository repair, run the local validator, and leave a maintainer-ready explanation of the graph and rollback behavior.

Work only in `$WORKSPACE`. Start by inspecting the local evidence; useful inputs include:
- `policy.md`
- `repo/config.json`
- `repo/graph.json`
- `repo/sample_rows.json`
- `repo/simulate.py`
- `repo/validate.py`

## Deliverables

- `repo/config.json`: Modify this existing configuration in place; keep one canonical merge head and the required replay and reverse properties.
- `validation.json`: Record the validator status and the checks actually exercised.
- `change_log.md`: Explain the split heads, minimal repair, fresh/upgrade/repeat/reverse evidence, and remaining operational boundary.

These files are a handoff to another practitioner, so choose clear prose and stable local identifiers. The named business fields are required where stated, but prose layout, explanation style, and additional useful context are up to you.

## Working rules

1. Read graph.json, sample_rows.json, policy.md, simulate.py, and validate.py before changing config.json.
2. Preserve both accepted branch dependencies, historical-model access, idempotence, and a real reverse operation; do not delete a branch or disable validation.
3. Run python3 repo/validate.py repo/config.json and reconcile its result with validation.json.
4. Modify only repo/config.json and the two declared handoff artifacts.

Keep all source evidence byte-for-byte unchanged except for a path explicitly named as an in-place deliverable. Work offline. Do not execute or claim an external, production, payment, filing, deletion, message-send, booking, or account action. Before finishing, re-open the final JSON files and reconcile their keys and results across the handoff.
