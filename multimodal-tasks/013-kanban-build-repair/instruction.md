# Repair a drag-aware Kanban build board

In `$WORKSPACE/web`, replace the starter page with a polished, local-only React TypeScript application grounded in the protected data file `web/src/data/localRecords.json`.

You are building a build repair board, not a generic record filter. The first screen should make four kanban lanes, card movement, blocked work, lane counts, and selected-card details immediately visible.

## Protected local data

Do not edit `web/src/data/localRecords.json`. It contains these eight synthetic build cards:

| id | title | lane | owner | status | estimate | blockers |
|---|---|---|---|---|---:|---:|
| KAN-101 | Restore drag fallback | Backlog | Kai | blocked | 8 | 3 |
| KAN-108 | Fix card overflow | In Progress | Mira | active | 5 | 1 |
| KAN-117 | Column count audit | Review | Leo | ready | 3 | 0 |
| KAN-126 | Release note cleanup | Done | Mira | done | 2 | 0 |
| KAN-132 | Repair flaky smoke test | Backlog | Ari | blocked | 6 | 2 |
| KAN-144 | Keyboard reorder path | In Progress | Kai | active | 4 | 1 |
| KAN-155 | Regression checklist | Review | Mira | ready | 7 | 0 |
| KAN-166 | Archive stale fixture | Done | Leo | done | 1 | 0 |

## Required behavior

- Import or otherwise read the protected local records from `web/src/data/localRecords.json`; do not retype a smaller dataset.
- Render four visible lanes named `Backlog`, `In Progress`, `Review`, and `Done`. Each lane must expose its current card count and total estimate.
- Every selectable card, every lane summary, and the selected-card panel must show the protected record `id` as visible text next to the title; do not rely on hidden text, aria-only labels, title attributes, or only the title for identity.
- Support card movement between lanes. Drag and drop is encouraged, but you must also provide deterministic button controls for the selected card, including `Move selected to Review`, `Move selected to Done`, and `Undo last move`. These movement buttons must be visible on the first screen; if no card is selected, show them disabled rather than hiding them.
- Selecting a card must update a detail panel with id, title, owner, status, lane, estimate, blockers, and the current action history.
- Derived summaries for `Blocked points`, `Review count`, `Active WIP`, and `Last move` must update when a card moves.
- Make the UI usable on desktop and mobile, with visible focus states, semantic labels, no horizontal overflow, and reduced-motion handling.
- Keep dependencies pinned in `package.json`; do not use `latest`, external APIs, network calls, generated package locks, or remote assets.
- Before finishing, run `npm run build`; the evaluator may serve `web/dist` for browser-driven interaction checks.
- Keep `web/dist/index.html` and the rest of `web/dist`, but remove generated install/build artifacts before finishing. In particular, do not leave `web/node_modules`, `web/package-lock.json`, `web/tsconfig.tsbuildinfo`, `/runtime/node_modules`, `/runtime/package-lock.json`, or `/runtime/tsconfig.tsbuildinfo`.
- Stage local decisions only. Do not claim that you deployed, merged, approved, or changed any real external system.

## Browser verification target

Use Playwright or an equivalent browser-driven check while developing, but do not include separate screenshot files in the final handoff. The evaluator will serve the submitted `web/dist` and run a multi-step browser probe. It may locate cards by visible protected ids, select cards, use movement buttons, verify lane text and counts, undo a move, and repeat core checks on a mobile viewport. Exact card ids and assertions are evaluator-owned.
