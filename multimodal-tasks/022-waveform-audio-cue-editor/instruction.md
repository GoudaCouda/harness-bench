# Build a waveform cue editor over a synthetic amplitude plot

In `$WORKSPACE/web`, replace the starter page with a polished, local-only React TypeScript application grounded in `web/src/data/localRecords.json` and protected image `web/public/waveform.png`.

You are building a waveform cue editor, not a generic media playlist. The first screen should show the protected amplitude plot, clickable cue markers, a playhead, and selected-cue details.

## Protected local data

Do not edit `web/src/data/localRecords.json` or `web/public/waveform.png`. Records contain only `id` and `label`; they identify the features but deliberately carry no geometry or visual attributes.

`web/public/waveform.png` is a dark waveform panel with a time ruler in milliseconds along the bottom. Each cue is drawn as a flag carrying its id at the top of the panel, a dashed vertical rule, and a crosshair where the cue meets the amplitude envelope, with the cue's time printed in `ms` beside the crosshair. It is a raster image: there is no vector source or metadata in the workspace to parse, so open and inspect the image itself.

## Read these facts from the image

- Each cue's marker position (the crosshair on the envelope) and its time in `ms` as printed next to the crosshair. Neither is in the records.

Encode what you read as code you own (for example a typed map under `web/src/utils/` keyed by record id, with positions as percentages of the image width and height). Do not add fields to `localRecords.json`, do not redraw the artwork in code, and do not guess: every value the UI shows must come from the image.

## Required behavior

- Import or otherwise read all protected records; do not retype a smaller dataset.
- Render the protected waveform inside `data-testid="wave-board"`. Each cue marker must expose `data-cue-id="<id>"` and visible id text, placed over that cue's crosshair.
- Provide controls for `Cue lane`, `Drop cue`, and `Clear cues`. `Cue lane` must include a `vocal` option.
- Selecting a cue must update a detail panel showing its label and time in ms. Dropping cues must update `Cue list`, `Cue count`, `Span ms` (latest minus earliest dropped cue), and a visible playhead with `data-testid="playhead"`.
- Make the UI usable on desktop and mobile, with visible focus states, semantic labels, no horizontal overflow, and reduced-motion handling.
- Keep dependencies pinned in `package.json`; do not use `latest`, external APIs, network calls, generated package locks, or remote assets.
- Before finishing, run `npm run build`; the evaluator may serve `web/dist` for browser-driven interaction checks.
- Keep `web/dist/index.html` and the rest of `web/dist`, but remove generated install/build artifacts before finishing.
- Stage local decisions only. Do not claim that you booked, reserved, paid, or changed any real external system.

## Browser verification target

The evaluator serves `web/dist`, measures every marker's center relative to `data-testid="wave-board"` against the true feature positions in the image, clicks protected ids, operates the named controls, checks that the detail panel and summaries show the values printed or encoded in the image, and repeats mobile layout checks. Exact tolerances are evaluator-owned.
