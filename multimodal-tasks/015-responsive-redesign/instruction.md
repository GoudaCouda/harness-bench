# Build a responsive visual inspector

In `$WORKSPACE/web`, replace the starter page with a polished, local-only React TypeScript application grounded in `web/src/data/localRecords.json` and protected target image `web/public/responsive-target.svg`.

You are building a visual responsive inspector. The first screen should show a device frame containing the protected page image, visible overflow markers placed from protected coordinates, and controls for viewport changes.

## Protected local data

Do not edit `web/src/data/localRecords.json` or `web/public/responsive-target.svg`. Records contain `id`, `label`, `area`, `x`, `y`, `w`, `h`, and `severity`, with coordinates as percentages relative to the frame.

## Required behavior

- Import or otherwise read all protected records; do not retype a smaller dataset.
- Render `web/public/responsive-target.svg` inside a `data-testid="responsive-frame"` device frame.
- Place each marker/bounding box at the protected coordinates and expose `data-issue-id="<id>"` plus visible id text.
- Provide controls for `Device preset`, `Viewport width`, `Show overflow markers`, and a deterministic `Snap to 390` action.
- Selecting a marker must update an issue detail panel with id, label, area, severity, coordinates, and active frame width.
- Derived summaries for `Viewport width`, `Overflow markers`, `Review breakpoints`, and `Marked area` must update when controls change.
- Make the UI usable on desktop and mobile, with visible focus states, semantic labels, no horizontal overflow, and reduced-motion handling.
- Keep dependencies pinned in `package.json`; do not use `latest`, external APIs, network calls, generated package locks, or remote assets.
- Before finishing, run `npm run build`; the evaluator may serve `web/dist` for browser-driven interaction checks.
- Keep `web/dist/index.html` and the rest of `web/dist`, but remove generated install/build artifacts before finishing.
- Stage local decisions only. Do not claim that you deployed, published, or changed any real page.

## Browser verification target

The evaluator may measure marker geometry relative to `data-testid="responsive-frame"`, change device presets, adjust viewport width, toggle marker visibility, click marker ids, and repeat mobile layout checks. Exact ids and tolerances are evaluator-owned.
