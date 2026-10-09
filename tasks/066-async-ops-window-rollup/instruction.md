# Reconcile an asynchronous operations update window

You are the incident handoff coordinator. Status updates arrive as files during the handoff window, including a duplicate and out-of-window records.

Your job is to observe the full window, preserve first-seen semantics, distinguish root components from downstream symptoms, and hand off one consistent operational state.

Work only in `$WORKSPACE`. Start by inspecting the local evidence; useful inputs include:
- `ops_updates/update_001.json`
- `ops_updates/update_002.json`
- `service_topology.json`
- `window.json`

## Deliverables

- `ops_rollup.md`: Provide incident, blocker, healthy-component, ignored-update, duplicate-update, and root-versus-downstream sections.
- `seen_state.json`: Record the inclusive window, observed/duplicate/ignored IDs, latest first-seen state by component, and real poll start/finish evidence.
- `update_ledger.csv`: Use columns update_id, component, timestamp, classification, status, reason; include one row per observed update file.

These files are a handoff to another practitioner, so choose clear prose and stable local identifiers. The named business fields are required where stated, but prose layout, explanation style, and additional useful context are up to you.

## Working rules

1. Poll ops_updates for at least 30 seconds before finalizing; files may appear while you work.
2. Keep the first observed in-window record for an update_id. Record later copies separately and do not let them replace component state.
3. Exclude out-of-window updates from latest state but preserve them in the observation ledger.
4. Use service_topology.json to separate a plausible root component from dependent symptoms; this is an analysis handoff, not authority to change production.

Keep all source evidence byte-for-byte unchanged except for a path explicitly named as an in-place deliverable. Work offline. Do not execute or claim an external, production, payment, filing, deletion, message-send, booking, or account action. Before finishing, re-open the final CSV/JSON files and reconcile their keys and totals across the handoff.
