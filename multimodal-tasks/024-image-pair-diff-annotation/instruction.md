# Annotate a synthetic before/after image pair

In `$WORKSPACE/web`, replace the starter page with a polished, local-only React TypeScript application grounded in `web/src/data/localRecords.json` and protected image `web/public/before-after.png`.

You are building a before/after visual diff annotator, not a single screenshot audit. The first screen should show the protected paired image, clickable diff markers, and selected-diff details.

## Protected local data

Do not edit `web/src/data/localRecords.json` or `web/public/before-after.png`. Records contain only `id` and `label`; they identify the features but deliberately carry no geometry or visual attributes.

`web/public/before-after.png` is a side-by-side capture of two browser windows headed BEFORE and AFTER. Each diff is drawn as a dashed box with a crosshair at its center and a colored badge carrying the diff id; the badge color encodes severity according to the legend at the bottom of the image. It is a raster image: there is no vector source or metadata in the workspace to parse, so open and inspect the image itself.

## Read these facts from the image

- Each diff's marker position (the crosshair), which `side` it sits on (`before` or `after`, from the window it is drawn in), and its `severity` (`review`, `watch`, or `info`, from the badge color against the legend). None of these are in the records.

Encode what you read as code you own (for example a typed map under `web/src/utils/` keyed by record id, with positions as percentages of the image width and height). Do not add fields to `localRecords.json`, do not redraw the artwork in code, and do not guess: every value the UI shows must come from the image.

## Required behavior

- Import or otherwise read all protected records; do not retype a smaller dataset.
- Render the protected pair inside `data-testid="diff-board"`. Each marker must expose `data-diff-id="<id>"` and visible id text, placed over that diff's crosshair.
- Provide controls for `Diff side`, `Mark diff`, and `Hide marks`. `Diff side` must include an `after` option.
- Selecting a mark must update a detail panel showing its label, side, and severity. Marking must update `Open diffs`, `Diff count`, `After-only` (how many marked diffs sit on the after side), and a visible overlay.
- Make the UI usable on desktop and mobile, with visible focus states, semantic labels, no horizontal overflow, and reduced-motion handling.
- Keep dependencies pinned in `package.json`; do not use `latest`, external APIs, network calls, generated package locks, or remote assets.
- Before finishing, run `npm run build`; the evaluator may serve `web/dist` for browser-driven interaction checks.
- Keep `web/dist/index.html` and the rest of `web/dist`, but remove generated install/build artifacts before finishing.
- Stage local decisions only. Do not claim that you booked, reserved, paid, or changed any real external system.

## Browser verification target

The evaluator serves `web/dist`, measures every marker's center relative to `data-testid="diff-board"` against the true feature positions in the image, clicks protected ids, operates the named controls, checks that the detail panel and summaries show the values printed or encoded in the image, and repeats mobile layout checks. Exact tolerances are evaluator-owned.
