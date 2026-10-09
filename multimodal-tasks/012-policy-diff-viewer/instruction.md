# Build a policy diff viewer

In `$WORKSPACE/web`, replace the starter page with a polished, local-only React TypeScript application grounded in the protected data file `web/src/data/localRecords.json`.

You are building a real handoff surface for sections. The first screen should make the policy diff workflow recognizable, with task-specific controls and derived state. Do not reduce this to the generic category filter plus selected record pattern: the interaction model should expose diff, redline, release review, clause notes as first-class UI concepts.

## Protected local data

Do not edit `web/src/data/localRecords.json`. It contains these eight synthetic records:

| id | name | category | owner | status | primary | secondary |
|---|---|---|---|---|---:|---:|
| POL-2.1 | Data retention window | privacy | Legal | review | 91 | 14 |
| POL-3.4 | Vendor access | security | GRC | watch | 76 | 8 |
| POL-5.2 | Training evidence | operations | People Ops | clear | 44 | 3 |
| POL-7.8 | Incident notice | response | GRC | watch | 83 | 5 |
| POL-2.1-R1 | Data retention window follow-up | security | People Ops | clear | 105 | 20 |
| POL-3.4-R2 | Vendor access follow-up | operations | GRC | watch | 93 | 15 |
| POL-5.2-R3 | Training evidence follow-up | response | Legal | review | 64 | 11 |
| POL-7.8-R4 | Incident notice follow-up | privacy | GRC | watch | 106 | 14 |

## Required behavior

- Import or otherwise read the protected local records from `web/src/data/localRecords.json`; do not retype a smaller dataset.
- Build the interface around the diff workflow: include split diff, comparison pane, clause list, version lens as visible UI concepts, not hidden text.
- Provide local controls for `Policy area`, `Version lens`, `Clause search`, `Changed only`, and `Review strictness`.
- Treat `Changed only` as a release-risk focus: it should surface changed or review clauses, not only visual redline decoration.
- When `Changed only` is enabled, clear policy records should be hidden from the main changed/focus list while review or watch clauses remain visible.
- Compute visible derived summaries for `Impact score`, `Review days`, `Change count`, and `Policy release review`. These summaries must update when the local controls change.
- Show enough detail for the selected section to support a reviewer decision: status, owner, category, both numeric fields, and a short workflow-specific note.
- Every selectable record card or row, every focus/queue item, and the selected-detail panel must show the protected record `id` as visible text next to the record name; do not rely on hidden text, aria-only labels, title attributes, or only the record name for identity.
- Make the UI usable on desktop and mobile, with visible focus states, semantic labels, and reduced-motion handling.
- Keep dependencies pinned in `package.json`; do not use `latest`, external APIs, network calls, generated package locks, or remote assets.
- Before finishing, run `npm run build`; the evaluator may serve `web/dist` for browser-driven interaction checks.
- Keep `web/dist/index.html` and the rest of `web/dist`, but remove generated install/build artifacts before finishing. In particular, do not leave `web/node_modules`, `web/package-lock.json`, `web/tsconfig.tsbuildinfo`, `/runtime/node_modules`, `/runtime/package-lock.json`, or `/runtime/tsconfig.tsbuildinfo`. Temporary installs are allowed only if they are cleaned up before final handoff.
- The final workspace and runtime must contain only regular files and directories; do not leave npm `.bin` symlinks or other generated tool-install links behind.
- Stage local decisions only. Do not claim that you booked, paid, sent, deployed, approved, submitted, or changed any real external system.

## Browser verification target

Use Playwright or an equivalent browser-driven check while developing, but do not include separate screenshot files in the final handoff. The evaluator will serve the submitted `web/dist` and run a multi-step browser probe across the visible controls.

The probe may combine policy-area filtering, clause search, version-lens changes, review-strictness changes, clause selection, clearing filters, changed-only focus, and a mobile viewport repeat. The evaluator may locate and click records by their visible protected ids while combining the controls. The rendered page must show that summaries, visible clauses lists, selected clause details, Changed clauses content, and Review strictness state update from the protected local records rather than from static placeholder text.

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
      "label": "Policy area"
    },
    {
      "kind": "fill",
      "label": "Clause search"
    },
    {
      "kind": "click",
      "target": "a visible clause card"
    },
    {
      "kind": "select",
      "label": "Version lens"
    },
    {
      "kind": "set_range",
      "label": "Review strictness"
    },
    {
      "kind": "snapshot",
      "name": "diff-evidence"
    }
  ],
  "notes": [
    "Exact selected records, filter values, and hidden assertions are evaluator-owned.",
    "The browser probe checks behavior, not a specific component tree."
  ]
}
```
