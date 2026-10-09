# Multimodal Tasks

**English** | [简体中文](README.zh-CN.md)

This directory contains a 26-task multimodal frontend suite. It is
kept outside `tasks/` so the original task tree and its existing numbering stay
unchanged.

These are agent workflow tasks centered on multimodal frontend implementation
and browser-verifiable handoff evidence. They require multi-step workspace
inspection, local data grounding, source edits, interaction-state handling, and
verification behavior rather than a single static answer.

## Scope

The suite uses local Vite React TypeScript workspaces. Each task asks an agent
to turn a protected local dataset and starter frontend into a browser-usable UI
with responsive layout, interaction state, and clear handoff evidence. The 26
tasks intentionally exercise different frontend workflow surfaces: dashboards,
production boards, game-like controls, incident timelines, research sites,
appointment planners, allocation matrices, media timelines, curriculum
outlines, routing desks, data tables, policy diffs, build-repair boards,
accessibility audits, viewport previews, feature-flag matrices, itineraries,
simulation controls, portfolio rebuilds, and form builders.

The suite now mixes two task families:

- baseline data-driven frontend tasks that test local data grounding, filtering,
  search, derived summaries, selection state, detail panels, responsive layout,
  and accessibility contracts;
- richer interaction tasks that require geometry, multi-step state, movement,
  annotation, route building, form validation, or browser-measurable visual
  state.

Task IDs are local to this suite:

- `001-creator-revenue-dashboard`
- `002-studio-task-board`
- `003-pet-care-game`
- `004-incident-command-console`
- `005-research-lab-site`
- `006-appointment-finder-ui`
- `007-budget-planning-workspace`
- `008-media-timeline-editor`
- `009-course-builder-app`
- `010-support-ticket-router`
- `011-local-data-explorer`
- `012-policy-diff-viewer`
- `013-kanban-build-repair`
- `014-accessibility-retrofit`
- `015-responsive-redesign`
- `016-feature-flag-admin`
- `017-travel-itinerary-planner`
- `018-scientific-simulation-controls`
- `019-portfolio-reference-rebuild`
- `020-form-builder-validation`
- `021-choropleth-map-selection`
- `022-waveform-audio-cue-editor`
- `023-spreadsheet-grid-formula`
- `024-image-pair-diff-annotation`
- `025-network-graph-explorer`
- `026-wysiwyg-print-preview`

The original `FE-201` through `FE-226` source IDs are retained as provenance
labels.

## Type Coverage

The 26 tasks are intentionally not one repeated UI template. They currently
cover:

- data-driven command surfaces: `001`, `002`, `004`, `005`, `006`, `007`,
  `010`, `011`, `012`, `016`, `018`, and `019`;
- game-like care controls: `003`;
- timeline seek and trim editing: `008`;
- multi-step wizard validation: `009`;
- move-aware Kanban repair: `013`;
- screenshot/image annotation: `014`;
- responsive visual inspection: `015`;
- floorplan route planning: `017`;
- live form-builder validation: `020`;
- choropleth district map: `021`;
- waveform cue editing: `022`;
- spreadsheet grid formulas: `023`;
- before/after image-pair annotation: `024`;
- node-link graph exploration: `025`;
- paginated print preview: `026`.

This keeps a stable baseline layer while adding interaction shapes that are
harder to solve by copying a single filter/search/detail pattern.

## Vision-gated tasks (`021`-`026`)

Tasks `021` through `026` are the only ones where the image is load-bearing
rather than decorative. Each ships a rendered PNG (no SVG or other vector
source in the workspace) and an identity-only `localRecords.json`; feature
positions, colors, printed values, and graph edges exist solely in the image
and in the hidden `visual_facts` of the ground truth. The browser probe
measures every marker's center against the true position and requires
image-only values (rates, milliseconds, cell totals, severities, neighbor
counts, word counts) to appear in the page body. A candidate that never opens
the image cannot pass. The PNGs are regenerated deterministically by
`tools/task_maintenance/emit_multimodal_021_026.py` via
`multimodal_raster_assets.py` (matplotlib Agg + bundled DejaVu fonts).

## Difficulty Distribution

Difficulty is assigned by task shape and browser-verifiable interaction
complexity, not by one model's current score.

| Difficulty | Tasks | Count |
| --- | --- | ---: |
| Easy | `003`, `004`, `011`, `019` | 4 |
| Medium | `001`, `002`, `005`, `006`, `007`, `010`, `012`, `016`, `018` | 9 |
| Hard | `008`, `009`, `013`, `014`, `015`, `017`, `020`, `021`–`026` | 13 |

Easy tasks are intentionally kept as baseline coverage. Medium tasks remain
data-driven but add stronger domain workflow requirements and browser state
checks. Hard tasks require nontrivial interaction state, geometry, movement,
validation, or visual-coordinate behavior.

## Package Layout

Each task follows the same formal package shape:

- `task.yaml`: task metadata, required artifacts, mutation contract, and hidden
  outcome-case paths.
- `instruction.md`: agent-visible task instructions.
- `workspace/`: initial agent workspace, including protected local records.
- `environment/Dockerfile`: task runtime image contract.
- `tests/cases.yaml`: hidden weighted case manifest.
- `tests/test_outcome.py`: deterministic outcome evaluator.
- `tests/ground_truth/frontend_contract.json`: hidden deterministic contract and
  browser interaction probe.
- `design.md`: maintainer design and leakage review record.

## Task Environment

Each multimodal task declares a browser-capable frontend environment in
`environment/Dockerfile`. The image keeps the formal `agent:agent` user contract
and adds the toolchain expected by these Vite React workspaces:

- Node.js and npm;
- Git and ripgrep for workspace inspection;
- Playwright `1.48.2` with Chromium installed under `/ms-playwright`;
- a `chromium` symlink on `PATH` for direct browser smoke checks;
- `NODE_PATH=/usr/local/lib/node_modules` so temporary Node scripts can
  `require("playwright")`;
- an npm cache seeded with the pinned React, Vite, TypeScript, and `lucide-react`
  versions used by this suite.

The task environment can be smoke-tested from any task directory, for example:

```bash
docker build -t harnessbench-multimodal-env multimodal-tasks/001-creator-revenue-dashboard/environment
docker run --rm harnessbench-multimodal-env node --version
docker run --rm harnessbench-multimodal-env npm --version
docker run --rm harnessbench-multimodal-env playwright --version
docker run --rm harnessbench-multimodal-env chromium --version
docker run --rm harnessbench-multimodal-env node -e 'require("playwright"); console.log("ok")'
```

This package-level Dockerfile documents the runtime contract for the
multimodal tasks. The benchmark runner does not build per-task
`environment/Dockerfile` images; instead, every harness image and the grader
image embed the same frontend toolchain (Node.js, the pinned Vite/React
dependencies, Playwright and Chromium). Run all 26 tasks through the suite in
[`suites/multimodal26`](../suites/multimodal26/README.md):

```bash
python tools/run_benchmark.py --suite-root suites/multimodal26 \
  --base-url "$HB_MODEL_URL" --model MODEL_ID --harness openclaw \
  --run-root artifacts/evaluations/multimodal26-shard-0
```

## Current Scoring

The current oracle is deterministic, offline, and browser-aware. It focuses on
source, text, data, dependency, safety, and Playwright-verifiable interaction
checks that are stable across runs:

- required Vite React files exist and use pinned dependencies;
- protected `web/src/data/localRecords.json` keeps the expected closed record
  set;
- source text exposes required labels, domain concepts, task-specific workflow
  concepts, state, handlers, and derived logic, using alias groups where
  equivalent wording is acceptable;
- hidden contracts vary by archetype, with different record counts, handler
  thresholds, interaction groups, calculation groups, logic groups, and browser
  action probes instead of one shared filter/selected/scenario skeleton;
- Playwright probes serve the submitted `web/dist`, operate the page, inspect
  visible state, and check responsive behavior where the task requires it;
- CSS and source include basic responsive and accessibility signals plus the
  task-specific presentation surface;
- mutation stays within the declared contract;
- the solution does not call remote services, add package locks, or claim real
  external actions.

This oracle is the scoring authority for this suite. It is designed to provide
stable, repeatable scores and protect against incomplete, unsafe, or
keyword-stuffed submissions while still checking real browser interaction.

## Browser Checks

The hidden outcome tests use Playwright to serve the submitted `web/dist` and
run task-specific browser probes. Depending on the task, those probes may:

- click protected record ids or stable `data-*` hooks;
- move sliders, select modes, toggle switches, type into fields, or press
  movement buttons;
- measure playhead, trim band, marker, route-line, or frame geometry;
- repeat layout checks at mobile viewport sizes.

The browser probes belong to the harness/oracle layer. They are not separate
agent-generated deliverables.
