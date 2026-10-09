# Build a support ticket routing desk

In `$WORKSPACE/web`, replace the starter page with a polished, local-only React TypeScript application grounded in the protected data file `web/src/data/localRecords.json`.

You are building a real handoff surface for tickets. The first screen should make the ticket router workflow recognizable, with task-specific controls and derived state. Do not reduce this to the generic category filter plus selected record pattern: the interaction model should expose routing, queue, assignee, priority as first-class UI concepts.

## Protected local data

Do not edit `web/src/data/localRecords.json`. It contains these six synthetic records:

| id | name | category | owner | status | primary | secondary |
|---|---|---|---|---|---:|---:|
| TCK-7004 | Chargeback threat | billing | Gold customer | review | 96 | 9 |
| TCK-7011 | Late replacement | fulfillment | Standard customer | watch | 74 | 28 |
| TCK-7020 | Sizing confusion | returns | Silver customer | clear | 45 | 6 |
| TCK-7033 | Damaged bundle | warehouse | Gold customer | watch | 82 | 17 |
| TCK-7004-R1 | Chargeback threat follow-up | fulfillment | Silver customer | clear | 110 | 15 |
| TCK-7011-R2 | Late replacement follow-up | returns | Gold customer | watch | 91 | 35 |

## Required behavior

- Import or otherwise read the protected local records from `web/src/data/localRecords.json`; do not retype a smaller dataset.
- Build the interface around the router workflow: include routing desk, queue lanes, assignee panel, priority meter as visible UI concepts, not hidden text.
- Provide local controls for `Queue filter`, `Routing mode`, `Ticket search`, `Urgent only`, and `Agent capacity`.
- `Queue filter` must expose protected ticket category options `billing`, `fulfillment`, `returns`, and `warehouse`; routing lanes such as attention/auto/overflow may be shown separately but must not replace the category filter.
- Treat `Urgent only` as a triage-risk focus: it should surface tickets that need routing attention, not only high-priority decoration.
- Compute visible derived summaries for `Priority score`, `Age hours`, `Queue load`, and `Routing confidence`. These summaries must update when the local controls change.
- Show enough detail for the selected ticket to support a reviewer decision: status, owner, category, both numeric fields, and a short workflow-specific note.
- Every selectable record card or row, every focus/queue item, and the selected-detail panel must show the protected record `id` as visible text next to the record name; do not rely on hidden text, aria-only labels, title attributes, or only the record name for identity.
- Make the UI usable on desktop and mobile, with visible focus states, semantic labels, and reduced-motion handling.
- Keep dependencies pinned in `package.json`; do not use `latest`, external APIs, network calls, generated package locks, or remote assets.
- Before finishing, run `npm run build`; the evaluator may serve `web/dist` for browser-driven interaction checks.
- Keep `web/dist/index.html` and the rest of `web/dist`, but remove generated install/build artifacts before finishing. In particular, do not leave `web/node_modules`, `web/package-lock.json`, `web/tsconfig.tsbuildinfo`, `/runtime/node_modules`, `/runtime/package-lock.json`, or `/runtime/tsconfig.tsbuildinfo`. Temporary installs are allowed only if they are cleaned up before final handoff.
- The final workspace and runtime must contain only regular files and directories; do not leave npm `.bin` symlinks or other generated tool-install links behind.
- Stage local decisions only. Do not claim that you booked, paid, sent, deployed, approved, submitted, or changed any real external system.

## Browser verification target

Use Playwright or an equivalent browser-driven check while developing, but do not include separate screenshot files in the final handoff. The evaluator will serve the submitted `web/dist` and run a multi-step browser probe across the visible controls.

The probe may combine queue filtering, ticket search, routing-mode changes, agent-capacity changes, ticket selection, clearing filters, urgent-only focus, and a mobile viewport repeat. The evaluator may locate and click records by their visible protected ids while combining the controls. The rendered page must show that summaries, visible tickets lists, selected ticket details, Urgent queue content, and Agent capacity state update from the protected local records rather than from static placeholder text.

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
      "label": "Queue filter"
    },
    {
      "kind": "fill",
      "label": "Ticket search"
    },
    {
      "kind": "click",
      "target": "a visible ticket card"
    },
    {
      "kind": "select",
      "label": "Routing mode"
    },
    {
      "kind": "set_range",
      "label": "Agent capacity"
    },
    {
      "kind": "snapshot",
      "name": "router-evidence"
    }
  ],
  "notes": [
    "Exact selected records, filter values, and hidden assertions are evaluator-owned.",
    "The browser probe checks behavior, not a specific component tree."
  ]
}
```
