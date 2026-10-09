# Build a floorplan route planner

In `$WORKSPACE/web`, replace the starter page with a polished, local-only React TypeScript application grounded in `web/src/data/localRecords.json` and protected map image `web/public/floorplan.svg`.

You are building a local route planner over a visual map, not a generic itinerary list. The first screen should show the protected floorplan image, clickable stop markers, a visible route line, route order, and selected-stop details.

## Protected local data

Do not edit `web/src/data/localRecords.json` or `web/public/floorplan.svg`. Records contain `id`, `name`, `kind`, `x`, `y`, `minutes`, and `cost`, with coordinates as percentages relative to the map.

## Required behavior

- Import or otherwise read all protected stops; do not retype a smaller dataset.
- Render the protected map inside `data-testid="map-board"`. Each stop marker must expose `data-stop-id="<id>"` and visible id text.
- Provide controls for `Travel mode`, `Add selected stop`, `Clear route`, and `Start at hotel`. `Travel mode` must include a `low-cost` option in addition to the default route mode.
- Selecting a stop must update a detail panel. Adding stops must update `Route order`, `Route stops`, `Total minutes`, `Total cost`, and a visible route line with `data-testid="route-line"`.
- Make the UI usable on desktop and mobile, with visible focus states, semantic labels, no horizontal overflow, and reduced-motion handling.
- Keep dependencies pinned in `package.json`; do not use `latest`, external APIs, network calls, generated package locks, or remote assets.
- Before finishing, run `npm run build`; the evaluator may serve `web/dist` for browser-driven interaction checks.
- Keep `web/dist/index.html` and the rest of `web/dist`, but remove generated install/build artifacts before finishing.
- Stage local decisions only. Do not claim that you booked, reserved, paid, or changed any real external system.

## Browser verification target

The evaluator may measure marker coordinates relative to `data-testid="map-board"`, click stop ids, add selected stops, inspect route order and route-line geometry, change travel mode, clear the route, and repeat mobile layout checks. Exact ids and tolerances are evaluator-owned.
