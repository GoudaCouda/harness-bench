# Create a research lab project site

In `$WORKSPACE/web`, replace the starter page with a polished, local-only React TypeScript application grounded in the protected data file `web/src/data/localRecords.json`.

You are building a real handoff surface for projects. The first screen should make the research project site workflow recognizable, with task-specific controls and derived state. Do not reduce this to the generic category filter plus selected record pattern: the interaction model should expose lab, laboratory, publication, collaboration as first-class UI concepts.

## Protected local data

Do not edit `web/src/data/localRecords.json`. It contains these eight synthetic records:

| id | name | category | owner | status | primary | secondary |
|---|---|---|---|---|---:|---:|
| LAB-A11 | Wetland Sensors | field | Dr. Vale | clear | 6 | 18 |
| LAB-B24 | Urban Heat Maps | climate | Dr. Hsu | watch | 4 | 35 |
| LAB-C31 | Open Soil Models | modeling | Dr. Okafor | review | 8 | 42 |
| LAB-D09 | River DNA Atlas | bioinformatics | Dr. Marin | watch | 3 | 27 |
| LAB-A11-R1 | Wetland Sensors follow-up | climate | Dr. Okafor | clear | 20 | 24 |
| LAB-B24-R2 | Urban Heat Maps follow-up | modeling | Dr. Marin | watch | 21 | 42 |
| LAB-C31-R3 | Open Soil Models follow-up | bioinformatics | Dr. Vale | review | 28 | 50 |
| LAB-D09-R4 | River DNA Atlas follow-up | field | Dr. Hsu | watch | 26 | 36 |

## Required behavior

- Import or otherwise read the protected local records from `web/src/data/localRecords.json`; do not retype a smaller dataset.
- Build the interface around the site workflow: include hero, lab site, collaborator rail, project profile as visible UI concepts, not hidden text.
- Provide local controls for `Research area`, `Review lens`, `Project search`, `Replication watch`, and `Evidence weight`.
- `Review lens` must include a `site-review` option that changes review weighting without acting as a simple status-only filter.
- Treat `Replication watch` as a research-risk focus: it should surface projects that need replication or review attention, not only a decorative lab-site theme.
- Compute visible derived summaries for `Publication count`, `Replication risk`, `Collaboration depth`, and `Lab contact triage`. These summaries must update when the local controls change.
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

The probe may combine research-area filtering, project search, review-lens changes, evidence-weight changes, project selection, clearing filters, replication-watch focus, and a mobile viewport repeat. The evaluator may locate and click records by their visible protected ids while combining the controls. The rendered page must show that summaries, visible projects lists, selected project details, Replication watch content, and Evidence weight state update from the protected local records rather than from static placeholder text.

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
      "label": "Research area"
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
      "label": "Review lens"
    },
    {
      "kind": "set_range",
      "label": "Evidence weight"
    },
    {
      "kind": "snapshot",
      "name": "site-evidence"
    }
  ],
  "notes": [
    "Exact selected records, filter values, and hidden assertions are evaluator-owned.",
    "The browser probe checks behavior, not a specific component tree."
  ]
}
```
