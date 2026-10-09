# 024-image-pair-diff-annotation Design

Synthetic frontend-diff-hard workspace, vision-gated. The oracle checks the protected PNG and identity-only records, marker geometry for every feature, image-derived values in the UI, and the safety boundary.

Weights: build 0.22, protected data 0.22, interaction 0.36, responsive 0.20, safety gate.

## Why the image is load-bearing

The shipped `localRecords.json` carries only `id`, `label`. Everything below exists only in `web/public/before-after.png` and in `tests/ground_truth/ground_truth.json` (`visual_facts`), so a candidate that never inspects the image cannot place markers or fill the detail panel:

- `DIFF-NAV`: side=before, severity=review, x=17, y=24
- `DIFF-BTN`: side=after, severity=review, x=69, y=30
- `DIFF-PRICE`: side=after, severity=watch, x=73, y=62
- `DIFF-GAP`: side=after, severity=info, x=73, y=84

The PNG is rendered by `tools/task_maintenance/multimodal_raster_assets.py` from these hidden facts at 2x scale with matplotlib's bundled fonts, so it is byte-stable and has no vector or text source inside the workspace. The browser probe checks all 4 marker centers (tolerance 10 percentage points of the board) and requires image-only tokens ['DIFF-PRICE', 'Price recolored', 'after', 'watch', 'Open diffs', '1'] in the page body.

- **Synthetic-data statement:** All records, labels, people, owners, statuses, screenshots, and numeric values are synthetic.
