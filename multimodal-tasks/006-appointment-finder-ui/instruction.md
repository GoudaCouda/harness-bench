# Build an appointment finder UI

In `$WORKSPACE/web`, replace the starter page with a polished, local-only React TypeScript application grounded in the protected data file `web/src/data/localRecords.json`.

You are building a real handoff surface for slots. The first screen should make the appointment shortlist workflow recognizable, with task-specific controls and derived state. Do not reduce this to the generic category filter plus selected record pattern: the interaction model should expose appointment, slot, shortlist, travel window as first-class UI concepts.

## Protected local data

Do not edit `web/src/data/localRecords.json`. It contains these eleven synthetic records:

| id | name | category | owner | status | primary | secondary |
|---|---|---|---|---|---:|---:|
| APT-140 | Dermatology Tue 09:20 | medical | North Clinic | clear | 88 | 18 |
| APT-185 | Dental Wed 13:45 | dental | Union Care | watch | 76 | 31 |
| APT-203 | PT Thu 08:10 | therapy | Harbor PT | review | 72 | 27 |
| APT-244 | Vision Fri 15:30 | vision | Linden Eye | clear | 84 | 22 |
| APT-140-R1 | Dermatology Tue 09:20 follow-up | dental | Harbor PT | clear | 102 | 24 |
| APT-185-R2 | Dental Wed 13:45 follow-up | therapy | Linden Eye | watch | 93 | 38 |
| APT-203-R3 | PT Thu 08:10 follow-up | vision | North Clinic | review | 92 | 35 |
| APT-244-R4 | Vision Fri 15:30 follow-up | medical | Union Care | watch | 107 | 31 |
| APT-185-X9 | Dental Wed 13:45 scenario 9 | dental | Union Care | clear | 145 | 35 |
| APT-185-X10 | Dental Wed 13:45 scenario 10 | therapy | North Clinic | watch | 152 | 31 |
| APT-185-X11 | Dental Wed 13:45 scenario 11 | vision | Union Care | review | 159 | 32 |

## Required behavior

- Import or otherwise read the protected local records from `web/src/data/localRecords.json`; do not retype a smaller dataset.
- Build the interface around the appointment workflow: include slot rail, appointment cards, travel window, provider panel as visible UI concepts, not hidden text.
- Provide local controls for `Service type`, `Visit mode`, `Provider search`, `Shortlist only`, and `Travel window`.
- Treat `Shortlist only` as a local fit-review focus: it should surface watch/review slots that need comparison, without claiming any real appointment was booked.
- Compute visible derived summaries for `Fit score`, `Minutes travel`, `Shortlist size`, and `Travel window review`. These summaries must update when the local controls change.
- Show enough detail for the selected slot to support a reviewer decision: status, owner, category, both numeric fields, and a short workflow-specific note.
- Every selectable record card or row, every focus/queue item, and the selected-detail panel must show the protected record `id` as visible text next to the record name; do not rely on hidden text, aria-only labels, title attributes, or only the record name for identity.
- Make the UI usable on desktop and mobile, with visible focus states, semantic labels, and reduced-motion handling.
- Keep dependencies pinned in `package.json`; do not use `latest`, external APIs, network calls, generated package locks, or remote assets.
- Before finishing, run `npm run build`; the evaluator may serve `web/dist` for browser-driven interaction checks.
- Keep `web/dist/index.html` and the rest of `web/dist`, but remove generated install/build artifacts before finishing. In particular, do not leave `web/node_modules`, `web/package-lock.json`, `web/tsconfig.tsbuildinfo`, `/runtime/node_modules`, `/runtime/package-lock.json`, or `/runtime/tsconfig.tsbuildinfo`. Temporary installs are allowed only if they are cleaned up before final handoff.
- The final workspace and runtime must contain only regular files and directories; do not leave npm `.bin` symlinks or other generated tool-install links behind.
- Stage local decisions only. Do not claim that you booked, paid, sent, deployed, approved, submitted, or changed any real external system.

## Browser verification target

Use Playwright or an equivalent browser-driven check while developing, but do not include separate screenshot files in the final handoff. The evaluator will serve the submitted `web/dist` and run a multi-step browser probe across the visible controls.

The probe may combine service filtering, provider search, visit-mode changes, travel-window changes, appointment selection, clearing filters, shortlist focus, and a mobile viewport repeat. The evaluator may locate and click records by their visible protected ids while combining the controls. The rendered page must show that summaries, visible appointments lists, selected appointment details, Shortlist content, and Travel window state update from the protected local records rather than from static placeholder text.

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
      "label": "Service type"
    },
    {
      "kind": "fill",
      "label": "Provider search"
    },
    {
      "kind": "click",
      "target": "a visible appointment card"
    },
    {
      "kind": "select",
      "label": "Visit mode"
    },
    {
      "kind": "set_range",
      "label": "Travel window"
    },
    {
      "kind": "snapshot",
      "name": "appointment-evidence"
    }
  ],
  "notes": [
    "Exact selected records, filter values, and hidden assertions are evaluator-owned.",
    "The browser probe checks behavior, not a specific component tree."
  ]
}
```
