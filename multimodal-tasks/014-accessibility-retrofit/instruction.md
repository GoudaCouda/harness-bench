# Build an accessibility screenshot annotation workspace

In `$WORKSPACE/web`, replace the starter page with a polished, local-only React TypeScript application grounded in the protected data file `web/src/data/localRecords.json` and protected target image `web/public/audit-target.svg`.

You are building an accessibility annotation tool for a synthetic product page screenshot. This is not a generic audit list: the first screen should show the target image with visible issue markers or bounding boxes placed on the corresponding parts of the page.

## Protected local data

Do not edit `web/src/data/localRecords.json` or `web/public/audit-target.svg`. The data contains these four synthetic accessibility findings. Coordinates are percentages relative to the target image.

| id | label | category | owner | severity | x | y | w | h |
|---|---|---|---|---|---:|---:|---:|---:|
| A11Y-NAV | Keyboard focus gap | focus | Design Systems | watch | 18 | 18 | 30 | 12 |
| A11Y-FORM | Missing input label | label | Growth | review | 59 | 44 | 24 | 14 |
| A11Y-CARD | Low contrast price text | contrast | Catalog | review | 18 | 67 | 26 | 16 |
| A11Y-MODAL | Modal close target | keyboard | Marketing | watch | 70 | 16 | 17 | 12 |

## Required behavior

- Import or otherwise read the protected local records from `web/src/data/localRecords.json`; do not retype a smaller dataset.
- Render the protected target image from `web/public/audit-target.svg` and place issue markers or bounding boxes over the image using the protected coordinates.
- The annotation board must expose a stable `data-testid="annotation-board"`. Each marker/bounding box must expose `data-issue-id="<protected id>"` and show the protected id as visible text near the marker.
- Provide local controls for `Issue category`, `Severity filter`, and `Show remediations`. `Show remediations` may be implemented as a labelled checkbox, switch, or button, but it must be keyboard-operable.
- `Show remediations` must default off. Remediation copy and marker fix labels should be hidden until this control is enabled.
- Selecting a marker must update a finding detail panel with id, label, owner, severity, category, coordinates, and the remediation text when remediations are enabled.
- Filtering by category or severity must update marker visibility, visible finding count, and the detail panel without moving the underlying target image.
- Derived summaries for `Visible findings`, `Review severity`, `Keyboard blockers`, and `Annotated area` must update when filters or `Show remediations` change.
- Make the UI usable on desktop and mobile, with visible focus states, semantic labels, no horizontal overflow, and reduced-motion handling.
- Keep dependencies pinned in `package.json`; do not use `latest`, external APIs, network calls, generated package locks, or remote assets.
- Before finishing, run `npm run build`; the evaluator may serve `web/dist` for browser-driven interaction checks.
- Keep `web/dist/index.html` and the rest of `web/dist`, but remove generated install/build artifacts before finishing. In particular, do not leave `web/node_modules`, `web/package-lock.json`, `web/tsconfig.tsbuildinfo`, `/runtime/node_modules`, `/runtime/package-lock.json`, or `/runtime/tsconfig.tsbuildinfo`.
- Stage local decisions only. Do not claim that you fixed, shipped, approved, or changed any real external system.

## Browser verification target

Use Playwright or an equivalent browser-driven check while developing, but do not include separate screenshot files in the final handoff. The evaluator will serve the submitted `web/dist` and run a browser probe. It may measure marker bounding boxes relative to `data-testid="annotation-board"`, click markers by `data-issue-id`, filter categories, toggle remediation text, and repeat layout checks on a mobile viewport. Exact ids, coordinates, and tolerances are evaluator-owned.
