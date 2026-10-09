# Build an incident command console

In `$WORKSPACE/web`, replace the starter page with a polished, local-only React TypeScript application grounded in the protected data file `web/src/data/localRecords.json`.

You are building a real handoff surface for incidents. The first screen should make the incident timeline workflow recognizable, with task-specific controls and derived state. Do not reduce this to the generic category filter plus selected record pattern: the interaction model should expose timeline, incident log, commander notes, response plan as first-class UI concepts.

## Protected local data

Do not edit `web/src/data/localRecords.json`. It contains these six synthetic records:

| id | name | category | owner | status | primary | secondary |
|---|---|---|---|---|---:|---:|
| INC-4081 | Checkout latency | payments | SRE Blue | review | 92 | 47 |
| INC-4084 | Search error rate | search | SRE Green | watch | 66 | 28 |
| INC-4087 | Webhook backlog | integrations | SRE Gold | clear | 39 | 11 |
| INC-4090 | CDN purge delay | edge | SRE Red | watch | 71 | 33 |
| INC-4081-R1 | Checkout latency follow-up | search | SRE Gold | clear | 106 | 53 |
| INC-4084-R2 | Search error rate follow-up | integrations | SRE Red | watch | 83 | 35 |

## Required behavior

- Import or otherwise read the protected local records from `web/src/data/localRecords.json`; do not retype a smaller dataset.
- Build the interface around the timeline workflow: include timeline, command log, severity ribbon, response pane as visible UI concepts, not hidden text.
- Provide local controls for `Service filter`, `Response mode`, `Incident search`, `Escalated only`, and `SLA pressure`.
- Treat `Escalated only` as an escalation-risk focus: it should surface incidents that need response attention such as review/watch incidents, not only decorative severity labels.
- Compute visible derived summaries for `Impact score`, `Minutes open`, `Escalation queue`, and `Response checkpoint`. These summaries must update when the local controls change.
- Show enough detail for the selected incident to support a reviewer decision: status, owner, category, both numeric fields, and a short workflow-specific note.
- Every selectable record card or row, every focus/queue item, and the selected-detail panel must show the protected record `id` as visible text next to the record name; do not rely on hidden text, aria-only labels, title attributes, or only the record name for identity.
- Make the UI usable on desktop and mobile, with visible focus states, semantic labels, and reduced-motion handling.
- Keep dependencies pinned in `package.json`; do not use `latest`, external APIs, network calls, generated package locks, or remote assets.
- Before finishing, run `npm run build`; the evaluator may serve `web/dist` for browser-driven interaction checks.
- Keep `web/dist/index.html` and the rest of `web/dist`, but remove generated install/build artifacts before finishing. In particular, do not leave `web/node_modules`, `web/package-lock.json`, `web/tsconfig.tsbuildinfo`, `/runtime/node_modules`, `/runtime/package-lock.json`, or `/runtime/tsconfig.tsbuildinfo`. Temporary installs are allowed only if they are cleaned up before final handoff.
- The final workspace and runtime must contain only regular files and directories; do not leave npm `.bin` symlinks or other generated tool-install links behind.
- Stage local decisions only. Do not claim that you booked, paid, sent, deployed, approved, submitted, or changed any real external system.

## Browser verification target

Use Playwright or an equivalent browser-driven check while developing, but do not include separate screenshot files in the final handoff. The evaluator will serve the submitted `web/dist` and run a multi-step browser probe across the visible controls.

The probe may combine service filtering, incident search, response-mode changes, SLA-pressure changes, incident selection, clearing filters, escalation-queue focus, and a mobile viewport repeat. The evaluator may locate and click records by their visible protected ids while combining the controls. The rendered page must show that summaries, visible incidents lists, selected incident details, Escalation queue content, and SLA pressure state update from the protected local records rather than from static placeholder text.

```json
{
  "schema": "action_sequence_v1",
  "target_viewport": {
    "width": 1440,
    "height": 900
  },
  "actions": [
    {
      "kind": "select",
      "label": "Service filter"
    },
    {
      "kind": "fill",
      "label": "Incident search"
    },
    {
      "kind": "click",
      "target": "a visible incident card"
    },
    {
      "kind": "select",
      "label": "Response mode"
    },
    {
      "kind": "set_range",
      "label": "SLA pressure"
    },
    {
      "kind": "snapshot",
      "name": "timeline-evidence"
    }
  ],
  "notes": [
    "Exact selected records, filter values, and hidden assertions are evaluator-owned.",
    "The browser probe checks behavior, not a specific component tree."
  ]
}
```
