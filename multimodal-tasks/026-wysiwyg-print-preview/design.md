# 026-wysiwyg-print-preview Design

Synthetic frontend-print-hard workspace, vision-gated. The oracle checks the protected PNG and identity-only records, marker geometry for every feature, image-derived values in the UI, and the safety boundary.

Weights: build 0.22, protected data 0.22, interaction 0.36, responsive 0.20, safety gate.

## Why the image is load-bearing

The shipped `localRecords.json` carries only `id`, `title`. Everything below exists only in `web/public/print-pages.png` and in `tests/ground_truth/ground_truth.json` (`visual_facts`), so a candidate that never inspects the image cannot place markers or fill the detail panel:

- `PAGE-1`: page=1, words=180, x=26, y=40
- `PAGE-2`: page=2, words=420, x=74, y=40
- `PAGE-3`: page=3, words=360, x=26, y=78
- `PAGE-4`: page=4, words=90, x=74, y=78

The PNG is rendered by `tools/task_maintenance/multimodal_raster_assets.py` from these hidden facts at 2x scale with matplotlib's bundled fonts, so it is byte-stable and has no vector or text source inside the workspace. The browser probe checks all 4 marker centers (tolerance 10 percentage points of the board) and requires image-only tokens ['PAGE-2', 'Methods', '420', 'Pinned', '1'] in the page body.

- **Synthetic-data statement:** All records, labels, people, owners, statuses, screenshots, and numeric values are synthetic.
