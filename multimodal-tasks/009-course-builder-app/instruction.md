# Build a multi-step course setup wizard

In `$WORKSPACE/web`, replace the starter page with a polished, local-only React TypeScript application grounded in `web/src/data/localRecords.json`.

You are building a course setup wizard, not a generic lesson list. The first screen should show wizard progress and guide a user through audience choice, lesson selection, prerequisite review, and final outline review.

## Protected local data

Do not edit `web/src/data/localRecords.json`. It contains protected lesson records with `id`, `title`, `module`, `minutes`, `level`, and `prereq`.

## Required behavior

- Import or otherwise read all protected lessons; do not retype a smaller dataset.
- Show a four-step wizard: `Audience`, `Lessons`, `Prerequisites`, and `Review`.
- Every selectable lesson and the review summary must show the protected lesson `id` as visible text.
- `Next` must be disabled until the current step is valid. Choosing an audience enables step 1; choosing at least one lesson enables step 2; unresolved prerequisite gaps should block review unless `Include prerequisites` is enabled.
- Provide visible summaries for `Selected lessons`, `Total minutes`, `Prerequisite gaps`, and `Review status`.
- Make the UI usable on desktop and mobile, with visible focus states, semantic labels, no horizontal overflow, and reduced-motion handling.
- Keep dependencies pinned in `package.json`; do not use `latest`, external APIs, network calls, generated package locks, or remote assets.
- Before finishing, run `npm run build`; the evaluator may serve `web/dist` for browser-driven interaction checks.
- Keep `web/dist/index.html` and the rest of `web/dist`, but remove generated install/build artifacts before finishing.
- Stage local decisions only. Do not claim that you enrolled learners, sent invitations, or changed any real external system.

## Browser verification target

The evaluator may validate disabled/enabled step controls, select an audience, select hidden lesson ids, trigger prerequisite validation, enable `Include prerequisites`, and inspect the final review summary. Exact ids and step paths are evaluator-owned.
