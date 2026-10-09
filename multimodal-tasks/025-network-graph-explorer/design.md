# 025-network-graph-explorer Design

Synthetic frontend-graph-hard workspace, vision-gated. The oracle checks the protected PNG and identity-only records, marker geometry for every feature, image-derived values in the UI, and the safety boundary.

Weights: build 0.22, protected data 0.22, interaction 0.36, responsive 0.20, safety gate.

## Why the image is load-bearing

The shipped `localRecords.json` carries only `id`, `label`. Everything below exists only in `web/public/graph.png` and in `tests/ground_truth/ground_truth.json` (`visual_facts`), so a candidate that never inspects the image cannot place markers or fill the detail panel:

- `NODE-A`: kind=source, degree=2, x=18, y=30
- `NODE-B`: kind=bridge, degree=3, x=50, y=48
- `NODE-C`: kind=sink, degree=2, x=82, y=28
- `NODE-D`: kind=sink, degree=1, x=78, y=72

The PNG is rendered by `tools/task_maintenance/multimodal_raster_assets.py` from these hidden facts at 2x scale with matplotlib's bundled fonts, so it is byte-stable and has no vector or text source inside the workspace. The browser probe checks all 4 marker centers (tolerance 10 percentage points of the board) and requires image-only tokens ['NODE-B', 'Join', 'bridge', 'Neighbor count', '3', 'Pinned', '1'] in the page body.

- **Synthetic-data statement:** All records, labels, people, owners, statuses, screenshots, and numeric values are synthetic.
