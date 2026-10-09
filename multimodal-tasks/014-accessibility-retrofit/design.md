# 014 Accessibility Annotation Design

This task is a replacement prototype for the old accessibility audit list. It evaluates a more visual multimodal shape: a protected local target image, overlay markers/bounding boxes, coordinate geometry, filtering, and selected finding details.

The hidden oracle is browser-driven. It serves `web/dist`, measures marker boxes with `data-issue-id` relative to `data-testid="annotation-board"`, applies coordinate tolerances, clicks markers, filters by category and severity, verifies that remediation copy is controlled by the `Show remediations` state, and checks mobile overflow plus a mobile marker click. The exact marker ids and coordinate assertions remain hidden, while the public prompt states the required DOM hooks.

Scoring weights:

- `build_and_runtime_integrity`: 0.22
- `accessibility_retrofit_protected_assets`: 0.22
- `accessibility_retrofit_annotation_interaction_model`: 0.36
- `accessibility_retrofit_responsive_surface`: 0.20
- `scope_and_safety_boundary`: gate
