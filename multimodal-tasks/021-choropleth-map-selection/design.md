# 021-choropleth-map-selection Design

Synthetic frontend-map-hard workspace, vision-gated. The oracle checks the protected PNG and identity-only records, marker geometry for every feature, image-derived values in the UI, and the safety boundary.

Weights: build 0.22, protected data 0.22, interaction 0.36, responsive 0.20, safety gate.

## Why the image is load-bearing

The shipped `localRecords.json` carries only `id`, `name`. Everything below exists only in `web/public/districts.png` and in `tests/ground_truth/ground_truth.json` (`visual_facts`), so a candidate that never inspects the image cannot place markers or fill the detail panel:

- `REG-NORTH`: rate=18.4, band=high, x=28, y=24
- `REG-EAST`: rate=9.1, band=mid, x=68, y=30
- `REG-WEST`: rate=6.2, band=low, x=22, y=64
- `REG-SOUTH`: rate=14.7, band=high, x=62, y=70

The PNG is rendered by `tools/task_maintenance/multimodal_raster_assets.py` from these hidden facts at 2x scale with matplotlib's bundled fonts, so it is byte-stable and has no vector or text source inside the workspace. The browser probe checks all 4 marker centers (tolerance 10 percentage points of the board) and requires image-only tokens ['REG-NORTH', 'North quay', '18.4', 'high', 'Pinned', '1'] in the page body.

- **Synthetic-data statement:** All records, labels, people, owners, statuses, screenshots, and numeric values are synthetic.
