# Build a paginated print preview over synthetic article pages

In `$WORKSPACE/web`, replace the starter page with a polished, local-only React TypeScript application grounded in `web/src/data/localRecords.json` and protected image `web/public/print-pages.png`.

You are building a paginated print preview, not a form builder. The first screen should show the protected page spread, clickable pages, running headers, and selected-page details.

## Protected local data

Do not edit `web/src/data/localRecords.json` or `web/public/print-pages.png`. Records contain only `id` and `title`; they identify the features but deliberately carry no geometry or visual attributes.

`web/public/print-pages.png` is a print-preview spread of several pages on a desk-colored canvas. Each page shows a running header, its section title, a small line printing the page id and its word count, body text rules, and a page number at the bottom. It is a raster image: there is no vector source or metadata in the workspace to parse, so open and inspect the image itself.

## Read these facts from the image

- Each page's marker position (the page center), its `page` number, and its `words` count as printed on the page. None of these are in the records.

Encode what you read as code you own (for example a typed map under `web/src/utils/` keyed by record id, with positions as percentages of the image width and height). Do not add fields to `localRecords.json`, do not redraw the artwork in code, and do not guess: every value the UI shows must come from the image.

## Required behavior

- Import or otherwise read all protected records; do not retype a smaller dataset.
- Render the protected spread inside `data-testid="print-board"`. Each page must expose `data-page-id="<id>"` and visible id text, centered on that page in the image.
- Provide controls for `Paper size`, `Pin page`, and `Clear pins`. `Paper size` must include a `letter` option.
- Selecting a page must update a detail panel showing its title, page number, and word count. Pinning must update `Pinned pages`, `Pinned count`, `Word total` (sum of pinned pages' word counts), and a visible running header with `data-testid="running-header"`.
- Make the UI usable on desktop and mobile, with visible focus states, semantic labels, no horizontal overflow, and reduced-motion handling.
- Keep dependencies pinned in `package.json`; do not use `latest`, external APIs, network calls, generated package locks, or remote assets.
- Before finishing, run `npm run build`; the evaluator may serve `web/dist` for browser-driven interaction checks.
- Keep `web/dist/index.html` and the rest of `web/dist`, but remove generated install/build artifacts before finishing.
- Stage local decisions only. Do not claim that you booked, reserved, paid, or changed any real external system.

## Browser verification target

The evaluator serves `web/dist`, measures every marker's center relative to `data-testid="print-board"` against the true feature positions in the image, clicks protected ids, operates the named controls, checks that the detail panel and summaries show the values printed or encoded in the image, and repeats mobile layout checks. Exact tolerances are evaluator-owned.
