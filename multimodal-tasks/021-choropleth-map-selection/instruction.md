# Build a choropleth map filter over synthetic districts

In `$WORKSPACE/web`, replace the starter page with a polished, local-only React TypeScript application grounded in `web/src/data/localRecords.json` and protected image `web/public/districts.png`.

You are building a choropleth map of synthetic districts, not a generic data table. The first screen should show the protected district map, clickable regions, a color legend, and selected-district details.

## Protected local data

Do not edit `web/src/data/localRecords.json` or `web/public/districts.png`. Records contain only `id` and `name`; they identify the features but deliberately carry no geometry or visual attributes.

`web/public/districts.png` is a choropleth map. Every surveyed district is a shaded region labeled with its name, its id, and a printed `rate` value; its fill color encodes the rate band according to the legend drawn in the corner of the map. Pale gray regions are unsurveyed and have no record. It is a raster image: there is no vector source or metadata in the workspace to parse, so open and inspect the image itself.

## Read these facts from the image

- Each district's marker position (the labeled centroid dot), its `rate` value, and its `band` (read the fill color against the map legend). None of these are in the records.

Encode what you read as code you own (for example a typed map under `web/src/utils/` keyed by record id, with positions as percentages of the image width and height). Do not add fields to `localRecords.json`, do not redraw the artwork in code, and do not guess: every value the UI shows must come from the image.

## Required behavior

- Import or otherwise read all protected records; do not retype a smaller dataset.
- Render the protected map inside `data-testid="map-board"`. Each district marker must expose `data-region-id="<id>"` and visible id text, placed over that district's labeled centroid.
- Provide controls for `Rate band`, `Pin district`, and `Clear pins`. `Rate band` must include a `high` option.
- Selecting a district must update a detail panel showing its name, rate, and band. Pinning must update `Pinned districts`, `Pinned count`, `Mean rate` (mean of the pinned districts' rates), and a visible selection mark.
- Make the UI usable on desktop and mobile, with visible focus states, semantic labels, no horizontal overflow, and reduced-motion handling.
- Keep dependencies pinned in `package.json`; do not use `latest`, external APIs, network calls, generated package locks, or remote assets.
- Before finishing, run `npm run build`; the evaluator may serve `web/dist` for browser-driven interaction checks.
- Keep `web/dist/index.html` and the rest of `web/dist`, but remove generated install/build artifacts before finishing.
- Stage local decisions only. Do not claim that you booked, reserved, paid, or changed any real external system.

## Browser verification target

The evaluator serves `web/dist`, measures every marker's center relative to `data-testid="map-board"` against the true feature positions in the image, clicks protected ids, operates the named controls, checks that the detail panel and summaries show the values printed or encoded in the image, and repeats mobile layout checks. Exact tolerances are evaluator-owned.
