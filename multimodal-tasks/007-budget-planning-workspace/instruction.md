# Build a budget planning matrix

In `$WORKSPACE/web`, replace the starter page with a polished, local-only React TypeScript application grounded in the protected data file `web/src/data/localRecords.json`.

You are building a real handoff surface for budget items. The first screen should make the budget matrix workflow recognizable, with task-specific controls and derived state. Do not reduce this to the generic category filter plus selected record pattern: the interaction model should expose allocation, matrix, reserve, scenario planning as first-class UI concepts.

## Protected local data

Do not edit `web/src/data/localRecords.json`. It contains these seven synthetic records:

| id | name | category | owner | status | primary | secondary |
|---|---|---|---|---|---:|---:|
| BUD-HOME | Rent and utilities | fixed | Alex | clear | 2680 | 0 |
| BUD-FOOD | Groceries | variable | Nia | watch | 740 | 85 |
| BUD-CARE | Care expenses | family | Remy | review | 620 | 110 |
| BUD-SAVE | Emergency savings | reserve | Alex | clear | 900 | -75 |
| BUD-HOME-R1 | Rent and utilities follow-up | variable | Remy | clear | 2694 | 6 |
| BUD-FOOD-R2 | Groceries follow-up | family | Alex | watch | 757 | 92 |
| BUD-CARE-R3 | Care expenses follow-up | reserve | Alex | review | 640 | 118 |

## Required behavior

- Import or otherwise read the protected local records from `web/src/data/localRecords.json`; do not retype a smaller dataset.
- Build the interface around the matrix workflow: include matrix, allocation cells, reserve panel, budget grid as visible UI concepts, not hidden text.
- Provide local controls for `Budget bucket`, `Scenario`, `Budget search`, `Reserve view`, and `Adjustment percent`.
- Treat `Reserve view` as a budget-risk focus: it should surface reserve gaps or review lines, not only a static reserve label.
- Compute visible derived summaries for `Planned spend`, `Variance`, `Reserve gap`, and `Allocation scenario`. These summaries must update when the local controls change.
- Show enough detail for the selected budget item to support a reviewer decision: status, owner, category, both numeric fields, and a short workflow-specific note.
- Every selectable record card or row, every focus/queue item, and the selected-detail panel must show the protected record `id` as visible text next to the record name; do not rely on hidden text, aria-only labels, title attributes, or only the record name for identity.
- Make the UI usable on desktop and mobile, with visible focus states, semantic labels, and reduced-motion handling.
- Keep dependencies pinned in `package.json`; do not use `latest`, external APIs, network calls, generated package locks, or remote assets.
- Before finishing, run `npm run build`; the evaluator may serve `web/dist` for browser-driven interaction checks.
- Keep `web/dist/index.html` and the rest of `web/dist`, but remove generated install/build artifacts before finishing. In particular, do not leave `web/node_modules`, `web/package-lock.json`, `web/tsconfig.tsbuildinfo`, `/runtime/node_modules`, `/runtime/package-lock.json`, or `/runtime/tsconfig.tsbuildinfo`. Temporary installs are allowed only if they are cleaned up before final handoff.
- The final workspace and runtime must contain only regular files and directories; do not leave npm `.bin` symlinks or other generated tool-install links behind.
- Stage local decisions only. Do not claim that you booked, paid, sent, deployed, approved, submitted, or changed any real external system.

## Browser verification target

Use Playwright or an equivalent browser-driven check while developing, but do not include separate screenshot files in the final handoff. The evaluator will serve the submitted `web/dist` and run a multi-step browser probe across the visible controls.

The probe may combine budget-bucket filtering, budget search, scenario changes, adjustment-percent changes, budget-line selection, clearing filters, reserve-view focus, and a mobile viewport repeat. The evaluator may locate and click records by their visible protected ids while combining the controls. The rendered page must show that summaries, visible budget lines lists, selected budget line details, Reserve view content, and Adjustment percent state update from the protected local records rather than from static placeholder text.

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
      "label": "Budget bucket"
    },
    {
      "kind": "fill",
      "label": "Budget search"
    },
    {
      "kind": "click",
      "target": "a visible budget line card"
    },
    {
      "kind": "select",
      "label": "Scenario"
    },
    {
      "kind": "set_range",
      "label": "Adjustment percent"
    },
    {
      "kind": "snapshot",
      "name": "matrix-evidence"
    }
  ],
  "notes": [
    "Exact selected records, filter values, and hidden assertions are evaluator-owned.",
    "The browser probe checks behavior, not a specific component tree."
  ]
}
```
