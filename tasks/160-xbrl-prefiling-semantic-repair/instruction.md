# Repair a synthetic filing without semantic regression

You are the pre-filing validation analyst. A filing package has five deterministic validation issues, including duplicate contexts, while critical fact values must remain unchanged.

Your job is to produce a repaired candidate, run the supplied validator, and leave a traceable internal pre-filing package with no live submission.

Work only in `$WORKSPACE`. Start by inspecting the local evidence; useful inputs include:
- `filing.json`
- `rulebook.md`
- `validate_filing.py`
- `validation_results.csv`

## Deliverables

- `repair_actions.csv`
- `repaired_filing.json`
- `validator_report.json`
- `validation_state.json`
- `verification.md`

These files are a handoff to another practitioner, so choose clear prose and stable local identifiers. The named business fields are required where stated, but prose layout, explanation style, and additional useful context are up to you.

## Working rules

1. Use validation_results.csv and rulebook.md to resolve every listed issue; do not remove facts or change protected values to make validation pass.
2. Write repair_actions.csv with columns issue_id, severity, action, target, new_value, status, evidence_refs and one row per issue.
3. Write repaired_filing.json with the same logical filing structure, merging equivalent contexts without dropping facts.
4. Run python3 validate_filing.py --source filing.json --candidate repaired_filing.json --report validator_report.json. Derive validation_state.json from that report and summarize issue closure, context merge, fact preservation, and no-live-filing status in verification.md.

Keep all source evidence byte-for-byte unchanged except for a path explicitly named as an in-place deliverable. Work offline. Do not execute or claim an external, production, payment, filing, deletion, message-send, booking, or account action. Before finishing, re-open the final CSV/JSON files and reconcile their keys and totals across the handoff.
