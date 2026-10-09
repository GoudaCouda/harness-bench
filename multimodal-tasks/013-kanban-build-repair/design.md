# 013 Kanban Build Repair Design

This task is a replacement prototype for the old filter/search kanban variant. It evaluates a different interaction shape: visible board lanes, selected card movement, undo state, and lane-derived metrics.

The hidden oracle is browser-driven. It serves `web/dist`, selects `KAN-101`, uses the deterministic `Move selected to Review` control, verifies lane membership and metric changes, uses `Undo last move`, then moves another selected card to `Done`. Drag and drop is allowed in implementations, but the button fallback is required to keep grading deterministic.

Scoring weights:

- `build_and_runtime_integrity`: 0.22
- `kanban_build_repair_protected_local_data`: 0.22
- `kanban_build_repair_migration_interaction_model`: 0.36
- `kanban_build_repair_responsive_surface`: 0.20
- `scope_and_safety_boundary`: gate
