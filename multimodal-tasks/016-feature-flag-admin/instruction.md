# Build a feature flag rollout matrix

In `$WORKSPACE/web`, replace the starter page with a polished, local-only React TypeScript application grounded in the protected data file `web/src/data/localRecords.json`.

You are building a real handoff surface for flags. The first screen should make the rollout matrix workflow recognizable, with task-specific controls and derived state. Do not reduce this to the generic category filter plus selected record pattern: the interaction model should expose feature flag, rollout, guardrail, environment as first-class UI concepts.

## Protected local data

Do not edit `web/src/data/localRecords.json`. It contains these eight synthetic records:

| id | name | category | owner | status | primary | secondary |
|---|---|---|---|---|---:|---:|
| FLAG-CART | Cart drawer v2 | production | Checkout | watch | 35 | 62 |
| FLAG-SEARCH | Search facets | staging | Discovery | clear | 80 | 21 |
| FLAG-LOYAL | Loyalty wallet | canary | Growth | review | 12 | 86 |
| FLAG-RET | Returns portal | production | CX | watch | 54 | 49 |
| FLAG-CART-R1 | Cart drawer v2 follow-up | staging | Growth | clear | 49 | 68 |
| FLAG-SEARCH-R2 | Search facets follow-up | canary | CX | watch | 97 | 28 |
| FLAG-LOYAL-R3 | Loyalty wallet follow-up | production | Checkout | review | 32 | 94 |
| FLAG-RET-R4 | Returns portal follow-up | production | Discovery | watch | 77 | 58 |

## Required behavior

- Import or otherwise read the protected local records from `web/src/data/localRecords.json`; do not retype a smaller dataset.
- Build the interface around the flags workflow: include flag matrix, environment cells, rollout slider, cohort meter as visible UI concepts, not hidden text.
- Provide local controls for `Environment`, `Rollout mode`, `Flag search`, `Guardrails only`, and `Cohort percent`.
- Treat `Guardrails only` as a rollout-risk focus: it should surface flags with guardrail or review pressure, without claiming any real flag was changed.
- Compute visible derived summaries for `Exposure percent`, `Error budget`, `Guardrail trips`, and `Rollout decision`. These summaries must update when the local controls change.
- Show enough detail for the selected flag to support a reviewer decision: status, owner, category, both numeric fields, and a short workflow-specific note.
- Every selectable record card or row, every focus/queue item, and the selected-detail panel must show the protected record `id` as visible text next to the record name; do not rely on hidden text, aria-only labels, title attributes, or only the record name for identity.
- Make the UI usable on desktop and mobile, with visible focus states, semantic labels, and reduced-motion handling.
- Keep dependencies pinned in `package.json`; do not use `latest`, external APIs, network calls, generated package locks, or remote assets.
- Before finishing, run `npm run build`; the evaluator may serve `web/dist` for browser-driven interaction checks.
- Keep `web/dist/index.html` and the rest of `web/dist`, but remove generated install/build artifacts before finishing. In particular, do not leave `web/node_modules`, `web/package-lock.json`, `web/tsconfig.tsbuildinfo`, `/runtime/node_modules`, `/runtime/package-lock.json`, or `/runtime/tsconfig.tsbuildinfo`. Temporary installs are allowed only if they are cleaned up before final handoff.
- The final workspace and runtime must contain only regular files and directories; do not leave npm `.bin` symlinks or other generated tool-install links behind.
- Stage local decisions only. Do not claim that you booked, paid, sent, deployed, approved, submitted, or changed any real external system.

## Browser verification target

Use Playwright or an equivalent browser-driven check while developing, but do not include separate screenshot files in the final handoff. The evaluator will serve the submitted `web/dist` and run a multi-step browser probe across the visible controls.

The probe may combine environment filtering, flag search, rollout-mode changes, cohort-percent changes, flag selection, clearing filters, guardrails-only focus, and a mobile viewport repeat. The evaluator may locate and click records by their visible protected ids while combining the controls. The rendered page must show that summaries, visible flags lists, selected flag details, Guardrail rail content, and Cohort percent state update from the protected local records rather than from static placeholder text.

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
      "label": "Environment"
    },
    {
      "kind": "fill",
      "label": "Flag search"
    },
    {
      "kind": "click",
      "target": "a visible flag card"
    },
    {
      "kind": "select",
      "label": "Rollout mode"
    },
    {
      "kind": "set_range",
      "label": "Cohort percent"
    },
    {
      "kind": "snapshot",
      "name": "flags-evidence"
    }
  ],
  "notes": [
    "Exact selected records, filter values, and hidden assertions are evaluator-owned.",
    "The browser probe checks behavior, not a specific component tree."
  ]
}
```
