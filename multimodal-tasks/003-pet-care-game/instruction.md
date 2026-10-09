# Build a pet care game stage

In `$WORKSPACE/web`, replace the starter page with a polished, local-only React TypeScript application grounded in the protected data file `web/src/data/localRecords.json`.

You are building a real handoff surface for pets. The first screen should make the care game stage workflow recognizable, with task-specific controls and derived state. Do not reduce this to the generic category filter plus selected record pattern: the interaction model should expose feed, play, pet care loop, action streak as first-class UI concepts.

## Protected local data

Do not edit `web/src/data/localRecords.json`. It contains these ten synthetic records:

| id | name | category | owner | status | primary | secondary |
|---|---|---|---|---|---:|---:|
| PET-FINCH | Comet Finch | bird | Rae | clear | 76 | 18 |
| PET-CAT | Miso Cat | cat | Dee | watch | 64 | 31 |
| PET-PUP | Juniper Pup | dog | Ash | review | 58 | 44 |
| PET-LIZ | Pixel Lizard | reptile | Sol | watch | 69 | 26 |
| PET-FINCH-R1 | Comet Finch follow-up | cat | Ash | clear | 90 | 24 |
| PET-CAT-R2 | Miso Cat follow-up | dog | Sol | watch | 81 | 38 |
| PET-PUP-R3 | Juniper Pup follow-up | reptile | Rae | review | 78 | 52 |
| PET-LIZ-R4 | Pixel Lizard follow-up | bird | Dee | watch | 92 | 35 |
| PET-CAT-X9 | Miso Cat scenario 9 | cat | Ash | clear | 130 | 35 |
| PET-CAT-X10 | Miso Cat scenario 10 | dog | Sol | watch | 137 | 31 |

## Required behavior

- Import or otherwise read the protected local records from `web/src/data/localRecords.json`; do not retype a smaller dataset.
- Build the interface around the game workflow: include game stage, care meter, routine tray, energy meter as visible UI concepts, not hidden text.
- Provide local controls for `Species filter`, `Care mode`, `Companion search`, `Night routine`, and `Energy boost`.
- Treat `Night routine` as a care-needs filter: when enabled, hide `clear` companions from the companion roster while keeping `watch` and `review` companions visible; do not implement it as only a decorative night theme.
- Compute visible derived summaries for `Care score`, `Hunger risk`, `Action streak`, and `Energy forecast`. These summaries must update when the local controls change.
- Show enough detail for the selected pet to support a reviewer decision: status, owner, category, both numeric fields, and a short workflow-specific note.
- Every selectable record card or row, every focus/queue item, and the selected-detail panel must show the protected record `id` as visible text next to the record name; do not rely on hidden text, aria-only labels, title attributes, or only the record name for identity.
- Make the UI usable on desktop and mobile, with visible focus states, semantic labels, and reduced-motion handling.
- Keep dependencies pinned in `package.json`; do not use `latest`, external APIs, network calls, generated package locks, or remote assets.
- Before finishing, run `npm run build`; the evaluator may serve `web/dist` for browser-driven interaction checks.
- Keep `web/dist`, but remove generated install/build artifacts before finishing. In particular, do not leave `web/node_modules`, `web/package-lock.json`, `web/tsconfig.tsbuildinfo`, `/runtime/node_modules`, `/runtime/package-lock.json`, or `/runtime/tsconfig.tsbuildinfo`. Temporary installs are allowed only if they are cleaned up before final handoff.
- The final workspace and runtime must contain only regular files and directories; do not leave npm `.bin` symlinks or other generated tool-install links behind.
- Stage local decisions only. Do not claim that you booked, paid, sent, deployed, approved, submitted, or changed any real external system.

## Browser verification target

Use Playwright or an equivalent browser-driven check while developing, but do not include separate screenshot files in the final handoff. The evaluator will serve the submitted `web/dist` and run a multi-step browser probe across the visible controls.

The probe may combine species filtering, companion search, care-mode changes, energy-boost changes, pet selection, clearing filters, night-routine care focus, and a mobile viewport repeat. The evaluator may locate and click records by their visible protected ids while combining the controls. The rendered page must show that summaries, visible pet lists, selected pet details, routine tray content, and energy state update from the protected local records rather than from static placeholder text.

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
      "label": "Species filter"
    },
    {
      "kind": "fill",
      "label": "Companion search"
    },
    {
      "kind": "click",
      "target": "a visible pet card"
    },
    {
      "kind": "select",
      "label": "Care mode"
    },
    {
      "kind": "set_range",
      "label": "Energy boost"
    },
    {
      "kind": "snapshot",
      "name": "game-evidence"
    }
  ],
  "notes": [
    "Exact selected pets, filter values, and hidden assertions are evaluator-owned.",
    "The browser probe checks behavior, not a specific component tree."
  ]
}
```
