# Build a creator revenue command desk

In `$WORKSPACE/web`, replace the starter page with a polished, local-only React TypeScript application grounded in the protected data file `web/src/data/localRecords.json`.

You are building a real handoff surface for campaigns. The first screen should make the revenue console workflow recognizable, with task-specific controls and derived state. Do not reduce this to the generic category filter plus selected record pattern: the interaction model should expose cohort, channel mix, risk queue, sponsorship review as first-class UI concepts.

## Protected local data

Do not edit `web/src/data/localRecords.json`. It contains these nine synthetic records:

| id | name | category | owner | status | primary | secondary |
|---|---|---|---|---|---:|---:|
| CMP-017 | Studio Launch | video | Mina Park | watch | 18420 | 12 |
| CMP-022 | Course Bundle | newsletter | Jules Hart | clear | 9650 | 7 |
| CMP-031 | Sponsor Sprint | shorts | Tariq West | review | 12110 | -3 |
| CMP-044 | Member Drive | community | Lena Ortiz | watch | 14680 | 9 |
| CMP-017-R1 | Studio Launch follow-up | newsletter | Tariq West | clear | 18434 | 18 |
| CMP-022-R2 | Course Bundle follow-up | shorts | Lena Ortiz | watch | 9667 | 14 |
| CMP-031-R3 | Sponsor Sprint follow-up | community | Mina Park | review | 12130 | 5 |
| CMP-044-R4 | Member Drive follow-up | video | Jules Hart | watch | 14703 | 18 |
| CMP-022-X9 | Course Bundle scenario 9 | newsletter | Tariq West | watch | 9714 | 12 |

## Required behavior

- Import or otherwise read the protected local records from `web/src/data/localRecords.json`; do not retype a smaller dataset.
- Build the interface around the dashboard workflow: include dashboard, command desk, cohort rail, risk queue as visible UI concepts, not hidden text.
- Provide local controls for `Channel cohort`, `Forecast mode`, `Creator search`, `Review queue only`, and `Sponsor pressure`.
- Compute visible derived summaries for `Net revenue`, `Audience growth`, `Review backlog`, and `Sponsorship risk review`. These summaries must update when the local controls change.
- Show enough detail for the selected campaign to support a reviewer decision: status, owner, category, both numeric fields, and a short workflow-specific note.
- Every selectable record card or row, every focus/queue item, and the selected-detail panel must show the protected record `id` as visible text next to the record name; do not rely on hidden text, aria-only labels, title attributes, or only the record name for identity.
- Make the UI usable on desktop and mobile, with visible focus states, semantic labels, and reduced-motion handling.
- Keep dependencies pinned in `package.json`; do not use `latest`, external APIs, network calls, generated package locks, or remote assets.
- Before finishing, run `npm run build`; the evaluator may serve `web/dist` for browser-driven interaction checks.
- Keep `web/dist`, but remove generated install/build artifacts before finishing. In particular, do not leave `web/node_modules`, `web/package-lock.json`, `web/tsconfig.tsbuildinfo`, `/runtime/node_modules`, `/runtime/package-lock.json`, or `/runtime/tsconfig.tsbuildinfo`. Temporary installs are allowed only if they are cleaned up before final handoff.
- The final workspace and runtime must contain only regular files and directories; do not leave npm `.bin` symlinks or other generated tool-install links behind.
- Stage local decisions only. Do not claim that you booked, paid, sent, deployed, approved, submitted, or changed any real external system.

## Browser verification target

Use Playwright or an equivalent browser-driven check while developing, but do not include separate screenshot files in the final handoff. The evaluator will serve the submitted `web/dist` and run a multi-step browser probe across the visible controls.

The probe may combine channel cohort filtering, creator search, forecast-mode changes, sponsor-pressure changes, record selection, clearing filters, review-queue-only mode, and a mobile viewport repeat. The evaluator may locate and click records by their visible protected ids while combining the controls. The rendered page must show that summaries, visible campaign lists, selected campaign details, and review queue content update from the protected local records rather than from static placeholder text.

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
      "label": "Channel cohort"
    },
    {
      "kind": "fill",
      "label": "Creator search"
    },
    {
      "kind": "click",
      "target": "a visible campaign"
    },
    {
      "kind": "select",
      "label": "Forecast mode"
    },
    {
      "kind": "set_range",
      "label": "Sponsor pressure"
    },
    {
      "kind": "snapshot",
      "name": "dashboard-evidence"
    }
  ],
  "notes": [
    "Exact selected records, filter values, and hidden assertions are evaluator-owned.",
    "The browser probe checks behavior, not a specific component tree."
  ]
}
```
