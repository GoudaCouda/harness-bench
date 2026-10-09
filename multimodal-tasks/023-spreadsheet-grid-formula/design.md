# 023-spreadsheet-grid-formula Design

Synthetic frontend-grid-hard workspace, vision-gated. The oracle checks the protected PNG and identity-only records, marker geometry for every feature, image-derived values in the UI, and the safety boundary.

Weights: build 0.22, protected data 0.22, interaction 0.36, responsive 0.20, safety gate.

## Why the image is load-bearing

The shipped `localRecords.json` carries only `id`, `label`. Everything below exists only in `web/public/grid-frame.png` and in `tests/ground_truth/ground_truth.json` (`visual_facts`), so a candidate that never inspects the image cannot place markers or fill the detail panel:

- `CELL-A1`: value=4, kind=input, x=22, y=28
- `CELL-B1`: value=11, kind=input, x=48, y=28
- `CELL-A2`: value=7, kind=input, x=22, y=58
- `CELL-B2`: value=0, kind=formula, x=48, y=58

The PNG is rendered by `tools/task_maintenance/multimodal_raster_assets.py` from these hidden facts at 2x scale with matplotlib's bundled fonts, so it is byte-stable and has no vector or text source inside the workspace. The browser probe checks all 4 marker centers (tolerance 10 percentage points of the board) and requires image-only tokens ['CELL-B2', 'Preview', 'SUM', '33'] in the page body.

- **Synthetic-data statement:** All records, labels, people, owners, statuses, screenshots, and numeric values are synthetic.
