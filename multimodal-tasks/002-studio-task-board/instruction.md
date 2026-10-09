# Repair a studio production board

In `$WORKSPACE/web`, replace the starter page with a polished, local-only React TypeScript application grounded in the protected data file `web/src/data/localRecords.json`.

You are building a real handoff surface for tasks. The first screen should make the production board workflow recognizable, with task-specific controls and derived state. Do not reduce this to the generic category filter plus selected record pattern: the interaction model should expose kanban, production lane, blocked work, wip limit as first-class UI concepts.

## Protected local data

Do not edit `web/src/data/localRecords.json`. It contains these seven synthetic records:

| id | name | category | owner | status | primary | secondary |
|---|---|---|---|---|---:|---:|
| TASK-18 | Brand kit cleanup | backlog | Nora Singh | clear | 8 | 0 |
| TASK-24 | Motion export QA | in-progress | Felix Cho | watch | 13 | 2 |
| TASK-29 | Landing comp fixes | review | Ivy Chen | review | 5 | 1 |
| TASK-37 | Illustration handoff | blocked | Omar Reed | watch | 21 | 4 |
| TASK-18-R1 | Brand kit cleanup follow-up | in-progress | Ivy Chen | clear | 22 | 6 |
| TASK-24-R2 | Motion export QA follow-up | review | Omar Reed | watch | 30 | 9 |
| TASK-29-R3 | Landing comp fixes follow-up | blocked | Nora Singh | review | 25 | 9 |

## Required behavior

- Import or otherwise read the protected local records from `web/src/data/localRecords.json`; do not retype a smaller dataset.
- Build the interface around the kanban workflow: include kanban board, lane stack, blocked card, capacity meter as visible UI concepts, not hidden text.
- Provide local controls for `Lane filter`, `Capacity mode`, `Task search`, `Show blockers`, and `WIP limit`.
- Treat `Show blockers` as a risk/blocker focus: it should surface review-risk or non-clear blocked work, not only the literal `blocked` lane.
- Compute visible derived summaries for `Effort points`, `Days blocked`, `Blocked lane count`, and `WIP capacity warning`. These summaries must update when the local controls change.
- Show enough detail for the selected task to support a reviewer decision: status, owner, category, both numeric fields, and a short workflow-specific note.
- Every selectable record card or row, every focus/queue item, and the selected-detail panel must show the protected record `id` as visible text next to the record name; do not rely on hidden text, aria-only labels, title attributes, or only the record name for identity.
- Make the UI usable on desktop and mobile, with visible focus states, semantic labels, and reduced-motion handling.
- Keep dependencies pinned in `package.json`; do not use `latest`, external APIs, network calls, generated package locks, or remote assets.
- Before finishing, run `npm run build`; the evaluator may serve `web/dist` for browser-driven interaction checks.
- Keep `web/dist`, but remove generated install/build artifacts before finishing. In particular, do not leave `web/node_modules`, `web/package-lock.json`, `web/tsconfig.tsbuildinfo`, `/runtime/node_modules`, `/runtime/package-lock.json`, or `/runtime/tsconfig.tsbuildinfo`. Temporary installs are allowed only if they are cleaned up before final handoff.
- The final workspace and runtime must contain only regular files and directories; do not leave npm `.bin` symlinks or other generated tool-install links behind.
- Stage local decisions only. Do not claim that you booked, paid, sent, deployed, approved, submitted, or changed any real external system.

## Browser verification target

Use Playwright or an equivalent browser-driven check while developing, but do not include separate screenshot files in the final handoff. The evaluator will serve the submitted `web/dist` and run a multi-step browser probe across the visible controls.

The probe may combine lane filtering, task search, capacity-mode changes, WIP-limit changes, task card selection, clearing filters, blocker-focused mode, and a mobile viewport repeat. The evaluator may locate and click records by their visible protected ids while combining the controls. The rendered page must show that summaries, visible task lists, selected task details, lane/blocker content, and WIP capacity state update from the protected local records rather than from static placeholder text.

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
      "label": "Lane filter"
    },
    {
      "kind": "fill",
      "label": "Task search"
    },
    {
      "kind": "click",
      "target": "a visible task card"
    },
    {
      "kind": "select",
      "label": "Capacity mode"
    },
    {
      "kind": "set_range",
      "label": "WIP limit"
    },
    {
      "kind": "snapshot",
      "name": "kanban-evidence"
    }
  ],
  "notes": [
    "Exact selected tasks, filter values, and hidden assertions are evaluator-owned.",
    "The browser probe checks behavior, not a specific component tree."
  ]
}
```
