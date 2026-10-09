# Explore a synthetic node-link graph with neighbor highlighting

In `$WORKSPACE/web`, replace the starter page with a polished, local-only React TypeScript application grounded in `web/src/data/localRecords.json` and protected image `web/public/graph.png`.

You are building a node-link graph explorer, not a table of edges. The first screen should show the protected graph image, clickable nodes, visible edges, and selected-node details.

## Protected local data

Do not edit `web/src/data/localRecords.json` or `web/public/graph.png`. Records contain only `id` and `label`; they identify the features but deliberately carry no geometry or visual attributes.

`web/public/graph.png` is a node-link diagram on a grid. Each node is a rounded card showing its id and label with a colored dot whose color encodes the node kind according to the legend in the corner; directed edges are drawn as curved arrows between cards. It is a raster image: there is no vector source or metadata in the workspace to parse, so open and inspect the image itself.

## Read these facts from the image

- Each node's marker position (the card center), its `kind` (dot color against the legend), and its neighbors (which cards its arrows connect to, in either direction). None of these are in the records; there is no edge list.

Encode what you read as code you own (for example a typed map under `web/src/utils/` keyed by record id, with positions as percentages of the image width and height). Do not add fields to `localRecords.json`, do not redraw the artwork in code, and do not guess: every value the UI shows must come from the image.

## Required behavior

- Import or otherwise read all protected records; do not retype a smaller dataset.
- Render the protected graph inside `data-testid="graph-board"`. Each node must expose `data-node-id="<id>"` and visible id text, centered on that node's card.
- Provide controls for `Node kind`, `Pin node`, and `Clear pins`. `Node kind` must include a `bridge` option.
- Selecting a node must update a detail panel showing its label, kind, and neighbors. Pinning must update `Pinned nodes`, `Pinned count`, `Neighbor count` (distinct nodes adjacent to the pinned set), and a visible neighbor highlight.
- Make the UI usable on desktop and mobile, with visible focus states, semantic labels, no horizontal overflow, and reduced-motion handling.
- Keep dependencies pinned in `package.json`; do not use `latest`, external APIs, network calls, generated package locks, or remote assets.
- Before finishing, run `npm run build`; the evaluator may serve `web/dist` for browser-driven interaction checks.
- Keep `web/dist/index.html` and the rest of `web/dist`, but remove generated install/build artifacts before finishing.
- Stage local decisions only. Do not claim that you booked, reserved, paid, or changed any real external system.

## Browser verification target

The evaluator serves `web/dist`, measures every marker's center relative to `data-testid="graph-board"` against the true feature positions in the image, clicks protected ids, operates the named controls, checks that the detail panel and summaries show the values printed or encoded in the image, and repeats mobile layout checks. Exact tolerances are evaluator-owned.
