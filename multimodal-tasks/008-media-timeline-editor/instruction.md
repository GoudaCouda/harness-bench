# Build a timeline seek and trim editor

In `$WORKSPACE/web`, replace the starter page with a polished, local-only React TypeScript application grounded in `web/src/data/localRecords.json`.

You are building a media timeline editor, not a generic record dashboard. The first screen should show visible timeline tracks, positioned clip blocks, a playhead, trim range, transport controls, and selected-clip details.

## Protected local data

Do not edit `web/src/data/localRecords.json`. It contains protected clip records with `id`, `title`, `track`, `start`, `duration`, `owner`, and `status`.

## Required behavior

- Import or otherwise read all protected clip records; do not retype a smaller dataset.
- Render at least three visible tracks: `Video`, `Audio`, and `Graphics`. Clip blocks must be positioned from the protected `start` and `duration` values.
- Expose the timeline surface with `data-testid="timeline-board"`, the playhead with `data-testid="playhead"`, and the trim range band with `data-testid="trim-band"` so browser checks can measure geometry.
- Every selectable clip block and selected detail panel must show the protected clip `id` as visible text.
- Provide keyboard-operable controls for `Play`, `Current time`, `Set trim in`, and `Set trim out`.
- Moving `Current time` must move the playhead. `Set trim in` and `Set trim out` must update a visible trim range and selected-clip summary.
- Derived summaries for `Current time`, `Trim range`, `Selected clip`, and `Review clips` must update from local state.
- Make the UI usable on desktop and mobile, with visible focus states, semantic labels, no horizontal overflow, and reduced-motion handling.
- Keep dependencies pinned in `package.json`; do not use `latest`, external APIs, network calls, generated package locks, or remote assets.
- Before finishing, run `npm run build`; the evaluator may serve `web/dist` for browser-driven interaction checks.
- Keep `web/dist/index.html` and the rest of `web/dist`, but remove generated install/build artifacts before finishing.
- Stage local decisions only. Do not claim that you published, exported, uploaded, or changed any real external system.

## Browser verification target

The evaluator may locate clips by visible protected ids or `data-clip-id`, locate the timeline/playhead/trim band by the required `data-testid` hooks, move the scrubber, click trim controls, verify playhead/trim geometry, switch selected clips, and repeat layout checks on a mobile viewport. Exact ids, times, and geometry tolerances are evaluator-owned.
