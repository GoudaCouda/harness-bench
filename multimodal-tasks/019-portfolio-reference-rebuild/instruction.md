# Rebuild a portfolio reference page

In `$WORKSPACE/web`, replace the starter page with a polished, local-only React TypeScript application grounded in the protected data file `web/src/data/localRecords.json`.

You are building a real handoff surface for projects. The first screen should make the portfolio case studies workflow recognizable, with task-specific controls and derived state. Do not reduce this to the generic category filter plus selected record pattern: the interaction model should expose portfolio, case study, hero, story section as first-class UI concepts.

## Protected local data

Do not edit `web/src/data/localRecords.json`. It contains these nine synthetic records:

| id | name | category | owner | status | primary | secondary |
|---|---|---|---|---|---:|---:|
| PORT-HELIOS | Helios dashboard | analytics | Lio Kane | clear | 92 | 88 |
| PORT-ORBIT | Orbit service kit | systems | Lio Kane | watch | 81 | 76 |
| PORT-MARSH | Marshland field log | research | Lio Kane | review | 74 | 69 |
| PORT-VALE | Vale checkout repair | commerce | Lio Kane | watch | 89 | 73 |
| PORT-HELIOS-R1 | Helios dashboard follow-up | systems | Lio Kane | clear | 106 | 94 |
| PORT-ORBIT-R2 | Orbit service kit follow-up | research | Lio Kane | watch | 98 | 83 |
| PORT-MARSH-R3 | Marshland field log follow-up | commerce | Lio Kane | review | 94 | 77 |
| PORT-VALE-R4 | Vale checkout repair follow-up | analytics | Lio Kane | watch | 112 | 82 |
| PORT-ORBIT-X9 | Orbit service kit scenario 9 | systems | Lio Kane | watch | 163 | 81 |

## Required behavior

- Import or otherwise read the protected local records from `web/src/data/localRecords.json`; do not retype a smaller dataset.
- Build the interface around the portfolio workflow: include hero, portfolio grid, project narrative, theme preview as visible UI concepts, not hidden text.
- Provide local controls for `Project type`, `Theme mode`, `Project search`, `Featured only`, and `Hero emphasis`.
- Treat `Featured only` as a curation-risk focus: it should surface watch/review case studies, not only a decorative featured badge.
- Compute visible derived summaries for `Impact score`, `Delivery weeks`, `Case study count`, and `Hero narrative`. These summaries must update when the local controls change.
- Show enough detail for the selected project to support a reviewer decision: status, owner, category, both numeric fields, and a short workflow-specific note.
- Every selectable record card or row, every focus/queue item, and the selected-detail panel must show the protected record `id` as visible text next to the record name; do not rely on hidden text, aria-only labels, title attributes, or only the record name for identity.
- Make the UI usable on desktop and mobile, with visible focus states, semantic labels, and reduced-motion handling.
- Keep dependencies pinned in `package.json`; do not use `latest`, external APIs, network calls, generated package locks, or remote assets.
- Before finishing, run `npm run build`; the evaluator may serve `web/dist` for browser-driven interaction checks.
- Keep `web/dist/index.html` and the rest of `web/dist`, but remove generated install/build artifacts before finishing. In particular, do not leave `web/node_modules`, `web/package-lock.json`, `web/tsconfig.tsbuildinfo`, `/runtime/node_modules`, `/runtime/package-lock.json`, or `/runtime/tsconfig.tsbuildinfo`. Temporary installs are allowed only if they are cleaned up before final handoff.
- The final workspace and runtime must contain only regular files and directories; do not leave npm `.bin` symlinks or other generated tool-install links behind.
- Stage local decisions only. Do not claim that you booked, paid, sent, deployed, approved, submitted, or changed any real external system.

## Browser verification target

Use Playwright or an equivalent browser-driven check while developing, but do not include separate screenshot files in the final handoff. The evaluator will serve the submitted `web/dist` and run a multi-step browser probe across the visible controls.

The probe may combine project-type filtering, project search, theme-mode changes, hero-emphasis changes, project selection, clearing filters, featured-only focus, and a mobile viewport repeat. The evaluator may locate and click records by their visible protected ids while combining the controls. The rendered page must show that summaries, visible projects lists, selected project details, Featured work content, and Hero emphasis state update from the protected local records rather than from static placeholder text.

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
      "label": "Project type"
    },
    {
      "kind": "fill",
      "label": "Project search"
    },
    {
      "kind": "click",
      "target": "a visible project card"
    },
    {
      "kind": "select",
      "label": "Theme mode"
    },
    {
      "kind": "set_range",
      "label": "Hero emphasis"
    },
    {
      "kind": "snapshot",
      "name": "portfolio-evidence"
    }
  ],
  "notes": [
    "Exact selected records, filter values, and hidden assertions are evaluator-owned.",
    "The browser probe checks behavior, not a specific component tree."
  ]
}
```
