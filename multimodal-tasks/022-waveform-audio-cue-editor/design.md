# 022-waveform-audio-cue-editor Design

Synthetic frontend-audio-hard workspace, vision-gated. The oracle checks the protected PNG and identity-only records, marker geometry for every feature, image-derived values in the UI, and the safety boundary.

Weights: build 0.22, protected data 0.22, interaction 0.36, responsive 0.20, safety gate.

## Why the image is load-bearing

The shipped `localRecords.json` carries only `id`, `label`. Everything below exists only in `web/public/waveform.png` and in `tests/ground_truth/ground_truth.json` (`visual_facts`), so a candidate that never inspects the image cannot place markers or fill the detail panel:

- `CUE-INTRO`: ms=0, amplitude=0.12, x=12, y=45
- `CUE-VOX`: ms=840, amplitude=0.66, x=37, y=25
- `CUE-BRK`: ms=1620, amplitude=0.21, x=60, y=42
- `CUE-OUT`: ms=2410, amplitude=0.08, x=84, y=47

The PNG is rendered by `tools/task_maintenance/multimodal_raster_assets.py` from these hidden facts at 2x scale with matplotlib's bundled fonts, so it is byte-stable and has no vector or text source inside the workspace. The browser probe checks all 4 marker centers (tolerance 10 percentage points of the board) and requires image-only tokens ['CUE-VOX', 'Vocal in', '840', 'Cue', '1'] in the page body.

- **Synthetic-data statement:** All records, labels, people, owners, statuses, screenshots, and numeric values are synthetic.
