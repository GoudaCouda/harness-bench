# Build a local spreadsheet grid with protected cells and a visible formula bar

In `$WORKSPACE/web`, replace the starter page with a polished, local-only React TypeScript application grounded in `web/src/data/localRecords.json` and protected image `web/public/grid-frame.png`.

You are building a editable spreadsheet grid, not a card list. The first screen should show the protected grid frame, clickable cells, a formula bar, and selected-cell details.

## Protected local data

Do not edit `web/src/data/localRecords.json` or `web/public/grid-frame.png`. Records contain only `id` and `label` (the A1-style cell address); they identify the features but deliberately carry no geometry or visual attributes.

`web/public/grid-frame.png` is a spreadsheet window with a formula bar, lettered columns, numbered rows, and four seeded cells. Three cells show a number; one is highlighted as an uncommitted formula cell whose formula text is printed in both the cell and the formula bar. It is a raster image: there is no vector source or metadata in the workspace to parse, so open and inspect the image itself.

## Read these facts from the image

- Each cell's marker position (the cell center), the three numeric values, and which cell holds the pending formula plus its formula text. None of these are in the records.

Encode what you read as code you own (for example a typed map under `web/src/utils/` keyed by record id, with positions as percentages of the image width and height). Do not add fields to `localRecords.json`, do not redraw the artwork in code, and do not guess: every value the UI shows must come from the image.

## Required behavior

- Import or otherwise read all protected records; do not retype a smaller dataset.
- Render the protected grid frame inside `data-testid="grid-board"`. Each cell must expose `data-cell-id="<id>"` and visible id text, centered on that cell in the image.
- Provide controls for `Formula`, `Commit formula`, and `Clear sheet`. `Formula` must include a `SUM` option and default to the formula shown in the image.
- Selecting a cell must update a detail panel showing its address and current value. Committing must evaluate the formula over the values read from the image and update `Preview`, `Selected cell`, `Sheet total` (sum of all four cells, counting an uncommitted formula cell as 0 and a committed one as its result), and a visible formula bar with `data-testid="formula-bar"`.
- Make the UI usable on desktop and mobile, with visible focus states, semantic labels, no horizontal overflow, and reduced-motion handling.
- Keep dependencies pinned in `package.json`; do not use `latest`, external APIs, network calls, generated package locks, or remote assets.
- Before finishing, run `npm run build`; the evaluator may serve `web/dist` for browser-driven interaction checks.
- Keep `web/dist/index.html` and the rest of `web/dist`, but remove generated install/build artifacts before finishing.
- Stage local decisions only. Do not claim that you booked, reserved, paid, or changed any real external system.

## Browser verification target

The evaluator serves `web/dist`, measures every marker's center relative to `data-testid="grid-board"` against the true feature positions in the image, clicks protected ids, operates the named controls, checks that the detail panel and summaries show the values printed or encoded in the image, and repeats mobile layout checks. Exact tolerances are evaluator-owned.
