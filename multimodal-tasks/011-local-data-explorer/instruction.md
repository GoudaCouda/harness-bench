# Build a local data explorer

In `$WORKSPACE/web`, replace the starter page with a polished, local-only React TypeScript application grounded in the protected data file `web/src/data/localRecords.json`.

You are building a real handoff surface for records. The first screen should make the data explorer workflow recognizable, with task-specific controls and derived state. Do not reduce this to the generic category filter plus selected record pattern: the interaction model should expose facet, column, sort, pagination as first-class UI concepts.

## Protected local data

Do not edit `web/src/data/localRecords.json`. It contains these twelve synthetic records:

| id | name | category | owner | status | primary | secondary |
|---|---|---|---|---|---:|---:|
| REC-EAST | East sensor batch | sensor | Ops North | clear | 128 | 2 |
| REC-WEST | West sample batch | sample | Ops West | watch | 96 | 6 |
| REC-CENT | Central import | import | Ops Core | review | 141 | 9 |
| REC-SOUTH | South ledger | ledger | Ops South | watch | 117 | 4 |
| REC-EAST-R1 | East sensor batch follow-up | sample | Ops Core | clear | 142 | 8 |
| REC-WEST-R2 | West sample batch follow-up | import | Ops South | watch | 113 | 13 |
| REC-CENT-R3 | Central import follow-up | ledger | Ops North | review | 161 | 17 |
| REC-SOUTH-R4 | South ledger follow-up | sensor | Ops West | watch | 140 | 13 |
| REC-WEST-X9 | West sample batch scenario 9 | sample | Ops Core | review | 170 | 12 |
| REC-WEST-X10 | West sample batch scenario 10 | import | Ops South | clear | 177 | 8 |
| REC-WEST-X11 | West sample batch scenario 11 | ledger | Ops North | watch | 184 | 9 |
| REC-WEST-X12 | West sample batch scenario 12 | sample | Ops West | review | 191 | 10 |

## Required behavior

- Import or otherwise read the protected local records from `web/src/data/localRecords.json`; do not retype a smaller dataset.
- Build the interface around the table workflow: include data table, facet rail, pagination, row inspector as visible UI concepts, not hidden text.
- Provide local controls for `Facet`, `Sort mode`, `Global search`, `Hide clear records`, and `Rows per page`.
- Treat `Hide clear records` as a data-quality focus: it should remove clear rows and surface watch/review records that need inspection.
- Compute visible derived summaries for `Total value`, `Freshness days`, `Facet matches`, and `Column audit`. These summaries must update when the local controls change.
- Show enough detail for the selected record to support a reviewer decision: status, owner, category, both numeric fields, and a short workflow-specific note.
- Every selectable record card or row, every focus/queue item, and the selected-detail panel must show the protected record `id` as visible text next to the record name; do not rely on hidden text, aria-only labels, title attributes, or only the record name for identity.
- Make the UI usable on desktop and mobile, with visible focus states, semantic labels, and reduced-motion handling.
- Keep dependencies pinned in `package.json`; do not use `latest`, external APIs, network calls, generated package locks, or remote assets.
- Before finishing, run `npm run build`; the evaluator may serve `web/dist` for browser-driven interaction checks.
- Keep `web/dist/index.html` and the rest of `web/dist`, but remove generated install/build artifacts before finishing. In particular, do not leave `web/node_modules`, `web/package-lock.json`, `web/tsconfig.tsbuildinfo`, `/runtime/node_modules`, `/runtime/package-lock.json`, or `/runtime/tsconfig.tsbuildinfo`. Temporary installs are allowed only if they are cleaned up before final handoff.
- The final workspace and runtime must contain only regular files and directories; do not leave npm `.bin` symlinks or other generated tool-install links behind.
- Stage local decisions only. Do not claim that you booked, paid, sent, deployed, approved, submitted, or changed any real external system.

## Browser verification target

Use Playwright or an equivalent browser-driven check while developing, but do not include separate screenshot files in the final handoff. The evaluator will serve the submitted `web/dist` and run a multi-step browser probe across the visible controls.

The probe may combine facet filtering, global search, sort-mode changes, rows-per-page changes, row selection, clearing filters, hide-clear focus, and a mobile viewport repeat. The evaluator may locate and click records by their visible protected ids while combining the controls. The rendered page must show that summaries, visible rows lists, selected row details, Data-quality focus content, and Rows per page state update from the protected local records rather than from static placeholder text.

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
      "label": "Facet"
    },
    {
      "kind": "fill",
      "label": "Global search"
    },
    {
      "kind": "click",
      "target": "a visible row card"
    },
    {
      "kind": "select",
      "label": "Sort mode"
    },
    {
      "kind": "set_range",
      "label": "Rows per page"
    },
    {
      "kind": "snapshot",
      "name": "table-evidence"
    }
  ],
  "notes": [
    "Exact selected records, filter values, and hidden assertions are evaluator-owned.",
    "The browser probe checks behavior, not a specific component tree."
  ]
}
```
