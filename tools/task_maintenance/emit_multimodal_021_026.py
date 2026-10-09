#!/usr/bin/env python3
"""Emit multimodal-tasks 021-026: vision-gated frontend tasks over synthetic PNGs.

Each task ships identity-only records plus a rendered PNG. Feature positions,
colors, and printed values exist only in the PNG (and in the hidden ground
truth), so the candidate must actually look at the image to pass the browser
probe.
"""

from __future__ import annotations

import json
import shutil
import textwrap
from pathlib import Path

from multimodal_raster_assets import render as render_asset

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "multimodal-tasks" / "017-travel-itinerary-planner"
STARTER = ROOT / "multimodal-tasks" / "011-local-data-explorer" / "workspace" / "web"
OUT = ROOT / "multimodal-tasks"

DOCKERFILE = (SRC / "environment" / "Dockerfile").read_text(encoding="utf-8")
TEST_OUTCOME = (SRC / "tests" / "test_outcome.py").read_text(encoding="utf-8")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")


def _dump(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _copy_starter(task_dir: Path) -> None:
    web = task_dir / "workspace" / "web"
    if web.exists():
        shutil.rmtree(web)
    shutil.copytree(STARTER, web)
    (web / "public").mkdir(exist_ok=True)


PROBE_HELPER = '''
def _run_browser_assertions(page) -> tuple[bool, Any]:
    problems: list[Any] = []
    probe = GROUND_TRUTH["interaction_probe"]
    board_sel = probe["board"]
    board = _box(page, board_sel)
    marker = probe["marker"]
    child = _box(page, f'[{marker["attr"]}="{marker["id"]}"]')
    cx, cy = _center_pct(board, child)
    if abs(cx - marker["x"]) > marker["tol"] or abs(cy - marker["y"]) > marker["tol"]:
        problems.append({"marker_position": [round(cx, 2), round(cy, 2)]})
    for extra in probe.get("markers", []):
        try:
            extra_box = _box(page, f'[{extra["attr"]}="{extra["id"]}"]')
            ex, ey = _center_pct(board, extra_box)
        except Exception as exc:  # missing marker counts as a misplaced one
            problems.append({"marker_missing": extra["id"], "error": repr(exc)})
            continue
        if abs(ex - extra["x"]) > extra["tol"] or abs(ey - extra["y"]) > extra["tol"]:
            problems.append({"marker_position": {extra["id"]: [round(ex, 2), round(ey, 2)]}})
    _click_by_attr_or_text(page, marker["attr"], marker["id"])
    for role, name in probe.get("clicks", []):
        _click_role(page, role, name)
    page.wait_for_timeout(200)
    body = _body_text(page)
    for token in probe.get("body_has", []):
        if token not in body:
            problems.append({"missing": token})
    for label, value in probe.get("selects", []):
        _select_by_label(page, label, value)
        page.wait_for_timeout(100)
        if value not in _body_text(page):
            problems.append({"select_missing": value})
    for label in probe.get("toggles", []):
        _enable_toggle(page, label)
        page.wait_for_timeout(100)
    for token in probe.get("after_toggle", []):
        if token not in _body_text(page):
            problems.append({"toggle_missing": token})
    layout_ok, layout_detail = _layout_ok(page)
    if not layout_ok:
        problems.append({"layout": layout_detail})
    return not problems, {"browser_check": probe.get("name", "probe"), "problems": problems}
'''


def _outcome_src() -> str:
    start = TEST_OUTCOME.index("def _run_browser_assertions")
    end = TEST_OUTCOME.index("\n\ndef evaluate_cases")
    return TEST_OUTCOME[:start] + PROBE_HELPER.strip() + "\n\n\n" + TEST_OUTCOME[end + 2 :]


TASKS = [
    {
        "id": "021-choropleth-map-selection",
        "title": "Build a choropleth map filter over synthetic districts",
        "family": "frontend-map-hard",
        "fe": "FE-221",
        "asset": "districts.png",
        "board": "map-board",
        "attr": "data-region-id",
        "instruction_kind": "choropleth map of synthetic districts, not a generic data table. The first screen should show the protected district map, clickable regions, a color legend, and selected-district details.",
        "fields": "only `id` and `name`",
        "visible_fields": ["id", "name"],
        "image_note": "a choropleth map. Every surveyed district is a shaded region labeled with its name, its id, and a printed `rate` value; its fill color encodes the rate band according to the legend drawn in the corner of the map. Pale gray regions are unsurveyed and have no record.",
        "visual_reading": [
            "Each district's marker position (the labeled centroid dot), its `rate` value, and its `band` (read the fill color against the map legend). None of these are in the records.",
        ],
        "behavior": [
            "Render the protected map inside `data-testid=\"map-board\"`. Each district marker must expose `data-region-id=\"<id>\"` and visible id text, placed over that district's labeled centroid.",
            "Provide controls for `Rate band`, `Pin district`, and `Clear pins`. `Rate band` must include a `high` option.",
            "Selecting a district must update a detail panel showing its name, rate, and band. Pinning must update `Pinned districts`, `Pinned count`, `Mean rate` (mean of the pinned districts' rates), and a visible selection mark.",
        ],
        "domain_groups": [["choropleth", "map"], ["district"], ["legend"], ["Rate band"], ["Pinned count"], ["Mean rate"]],
        "interaction_groups": [["data-testid", "map-board"], ["data-region-id"], ["Pin district"], ["Clear pins"], ["Rate band"]],
        "presentation_groups": [["Pinned districts"], ["Mean rate"], ["Selected district"], ["legend"], ["aria-label"]],
        "records": [
            {"id": "REG-NORTH", "name": "North quay", "rate": 18.4, "band": "high", "x": 28, "y": 24},
            {"id": "REG-EAST", "name": "East marsh", "rate": 9.1, "band": "mid", "x": 68, "y": 30},
            {"id": "REG-WEST", "name": "West mill", "rate": 6.2, "band": "low", "x": 22, "y": 64},
            {"id": "REG-SOUTH", "name": "South harbor", "rate": 14.7, "band": "high", "x": 62, "y": 70},
        ],
        "marker": {"attr": "data-region-id", "id": "REG-NORTH", "x": 28, "y": 24, "tol": 10},
        "clicks": [["button", r"pin district"]],
        "body_has": ["REG-NORTH", "North quay", "18.4", "high", "Pinned", "1"],
        "selects": [["Rate band", "high"]],
        "toggles": [],
        "after_toggle": [],
    },
    {
        "id": "022-waveform-audio-cue-editor",
        "title": "Build a waveform cue editor over a synthetic amplitude plot",
        "family": "frontend-audio-hard",
        "fe": "FE-222",
        "asset": "waveform.png",
        "board": "wave-board",
        "attr": "data-cue-id",
        "instruction_kind": "waveform cue editor, not a generic media playlist. The first screen should show the protected amplitude plot, clickable cue markers, a playhead, and selected-cue details.",
        "fields": "only `id` and `label`",
        "visible_fields": ["id", "label"],
        "image_note": "a dark waveform panel with a time ruler in milliseconds along the bottom. Each cue is drawn as a flag carrying its id at the top of the panel, a dashed vertical rule, and a crosshair where the cue meets the amplitude envelope, with the cue's time printed in `ms` beside the crosshair.",
        "visual_reading": [
            "Each cue's marker position (the crosshair on the envelope) and its time in `ms` as printed next to the crosshair. Neither is in the records.",
        ],
        "behavior": [
            "Render the protected waveform inside `data-testid=\"wave-board\"`. Each cue marker must expose `data-cue-id=\"<id>\"` and visible id text, placed over that cue's crosshair.",
            "Provide controls for `Cue lane`, `Drop cue`, and `Clear cues`. `Cue lane` must include a `vocal` option.",
            "Selecting a cue must update a detail panel showing its label and time in ms. Dropping cues must update `Cue list`, `Cue count`, `Span ms` (latest minus earliest dropped cue), and a visible playhead with `data-testid=\"playhead\"`.",
        ],
        "domain_groups": [["waveform"], ["cue"], ["playhead"], ["Cue lane"], ["Cue count"], ["Span ms"]],
        "interaction_groups": [["data-testid", "wave-board"], ["data-cue-id"], ["Drop cue"], ["Clear cues"], ["playhead"]],
        "presentation_groups": [["Cue list"], ["Span ms"], ["Selected cue"], ["amplitude"], ["aria-label"]],
        "records": [
            {"id": "CUE-INTRO", "label": "Intro swell", "ms": 0, "amplitude": 0.12, "x": 12, "y": 45},
            {"id": "CUE-VOX", "label": "Vocal in", "ms": 840, "amplitude": 0.66, "x": 37, "y": 25},
            {"id": "CUE-BRK", "label": "Break", "ms": 1620, "amplitude": 0.21, "x": 60, "y": 42},
            {"id": "CUE-OUT", "label": "Outro", "ms": 2410, "amplitude": 0.08, "x": 84, "y": 47},
        ],
        "marker": {"attr": "data-cue-id", "id": "CUE-VOX", "x": 37, "y": 25, "tol": 10},
        "clicks": [["button", r"drop cue"]],
        "body_has": ["CUE-VOX", "Vocal in", "840", "Cue", "1"],
        "selects": [["Cue lane", "vocal"]],
        "toggles": [],
        "after_toggle": [],
    },
    {
        "id": "023-spreadsheet-grid-formula",
        "title": "Build a local spreadsheet grid with protected cells and a visible formula bar",
        "family": "frontend-grid-hard",
        "fe": "FE-223",
        "asset": "grid-frame.png",
        "board": "grid-board",
        "attr": "data-cell-id",
        "instruction_kind": "editable spreadsheet grid, not a card list. The first screen should show the protected grid frame, clickable cells, a formula bar, and selected-cell details.",
        "fields": "only `id` and `label` (the A1-style cell address)",
        "visible_fields": ["id", "label"],
        "image_note": "a spreadsheet window with a formula bar, lettered columns, numbered rows, and four seeded cells. Three cells show a number; one is highlighted as an uncommitted formula cell whose formula text is printed in both the cell and the formula bar.",
        "visual_reading": [
            "Each cell's marker position (the cell center), the three numeric values, and which cell holds the pending formula plus its formula text. None of these are in the records.",
        ],
        "behavior": [
            "Render the protected grid frame inside `data-testid=\"grid-board\"`. Each cell must expose `data-cell-id=\"<id>\"` and visible id text, centered on that cell in the image.",
            "Provide controls for `Formula`, `Commit formula`, and `Clear sheet`. `Formula` must include a `SUM` option and default to the formula shown in the image.",
            "Selecting a cell must update a detail panel showing its address and current value. Committing must evaluate the formula over the values read from the image and update `Preview`, `Selected cell`, `Sheet total` (sum of all four cells, counting an uncommitted formula cell as 0 and a committed one as its result), and a visible formula bar with `data-testid=\"formula-bar\"`.",
        ],
        "domain_groups": [["spreadsheet", "grid"], ["formula"], ["cell"], ["Sheet total"], ["formula-bar"]],
        "interaction_groups": [["data-testid", "grid-board"], ["data-cell-id"], ["Commit formula"], ["Clear sheet"], ["formula-bar"]],
        "presentation_groups": [["Selected cell"], ["Sheet total"], ["Preview"], ["Formula"], ["aria-label"]],
        "records": [
            {"id": "CELL-A1", "label": "A1", "value": 4, "kind": "input", "x": 22, "y": 28},
            {"id": "CELL-B1", "label": "B1", "value": 11, "kind": "input", "x": 48, "y": 28},
            {"id": "CELL-A2", "label": "A2", "value": 7, "kind": "input", "x": 22, "y": 58},
            {"id": "CELL-B2", "label": "B2", "value": 0, "kind": "formula", "x": 48, "y": 58},
        ],
        "marker": {"attr": "data-cell-id", "id": "CELL-B2", "x": 48, "y": 58, "tol": 10},
        "clicks": [["button", r"commit formula"]],
        "body_has": ["CELL-B2", "Preview", "SUM", "33"],
        "selects": [["Formula", "SUM"]],
        "toggles": [],
        "after_toggle": [],
    },
    {
        "id": "024-image-pair-diff-annotation",
        "title": "Annotate a synthetic before/after image pair",
        "family": "frontend-diff-hard",
        "fe": "FE-224",
        "asset": "before-after.png",
        "board": "diff-board",
        "attr": "data-diff-id",
        "instruction_kind": "before/after visual diff annotator, not a single screenshot audit. The first screen should show the protected paired image, clickable diff markers, and selected-diff details.",
        "fields": "only `id` and `label`",
        "visible_fields": ["id", "label"],
        "image_note": "a side-by-side capture of two browser windows headed BEFORE and AFTER. Each diff is drawn as a dashed box with a crosshair at its center and a colored badge carrying the diff id; the badge color encodes severity according to the legend at the bottom of the image.",
        "visual_reading": [
            "Each diff's marker position (the crosshair), which `side` it sits on (`before` or `after`, from the window it is drawn in), and its `severity` (`review`, `watch`, or `info`, from the badge color against the legend). None of these are in the records.",
        ],
        "behavior": [
            "Render the protected pair inside `data-testid=\"diff-board\"`. Each marker must expose `data-diff-id=\"<id>\"` and visible id text, placed over that diff's crosshair.",
            "Provide controls for `Diff side`, `Mark diff`, and `Hide marks`. `Diff side` must include an `after` option.",
            "Selecting a mark must update a detail panel showing its label, side, and severity. Marking must update `Open diffs`, `Diff count`, `After-only` (how many marked diffs sit on the after side), and a visible overlay.",
        ],
        "domain_groups": [["before"], ["after"], ["diff"], ["Diff side"], ["Diff count"], ["After-only"]],
        "interaction_groups": [["data-testid", "diff-board"], ["data-diff-id"], ["Mark diff"], ["Hide marks"], ["Diff side"]],
        "presentation_groups": [["Open diffs"], ["After-only"], ["Selected diff"], ["severity"], ["aria-label"]],
        "records": [
            {"id": "DIFF-NAV", "label": "Nav row dropped", "side": "before", "severity": "review", "x": 17, "y": 24},
            {"id": "DIFF-BTN", "label": "Button moved up", "side": "after", "severity": "review", "x": 69, "y": 30},
            {"id": "DIFF-PRICE", "label": "Price recolored", "side": "after", "severity": "watch", "x": 73, "y": 62},
            {"id": "DIFF-GAP", "label": "Footer spacing gap", "side": "after", "severity": "info", "x": 73, "y": 84},
        ],
        "marker": {"attr": "data-diff-id", "id": "DIFF-PRICE", "x": 73, "y": 62, "tol": 10},
        "clicks": [["button", r"mark diff"]],
        "body_has": ["DIFF-PRICE", "Price recolored", "after", "watch", "Open diffs", "1"],
        "selects": [["Diff side", "after"]],
        "toggles": ["Hide marks"],
        "after_toggle": ["Hide"],
    },
    {
        "id": "025-network-graph-explorer",
        "title": "Explore a synthetic node-link graph with neighbor highlighting",
        "family": "frontend-graph-hard",
        "fe": "FE-225",
        "asset": "graph.png",
        "board": "graph-board",
        "attr": "data-node-id",
        "instruction_kind": "node-link graph explorer, not a table of edges. The first screen should show the protected graph image, clickable nodes, visible edges, and selected-node details.",
        "fields": "only `id` and `label`",
        "visible_fields": ["id", "label"],
        "image_note": "a node-link diagram on a grid. Each node is a rounded card showing its id and label with a colored dot whose color encodes the node kind according to the legend in the corner; directed edges are drawn as curved arrows between cards.",
        "visual_reading": [
            "Each node's marker position (the card center), its `kind` (dot color against the legend), and its neighbors (which cards its arrows connect to, in either direction). None of these are in the records; there is no edge list.",
        ],
        "behavior": [
            "Render the protected graph inside `data-testid=\"graph-board\"`. Each node must expose `data-node-id=\"<id>\"` and visible id text, centered on that node's card.",
            "Provide controls for `Node kind`, `Pin node`, and `Clear pins`. `Node kind` must include a `bridge` option.",
            "Selecting a node must update a detail panel showing its label, kind, and neighbors. Pinning must update `Pinned nodes`, `Pinned count`, `Neighbor count` (distinct nodes adjacent to the pinned set), and a visible neighbor highlight.",
        ],
        "domain_groups": [["graph"], ["node"], ["edge", "neighbor"], ["Node kind"], ["Pinned count"], ["Neighbor count"]],
        "interaction_groups": [["data-testid", "graph-board"], ["data-node-id"], ["Pin node"], ["Clear pins"], ["Node kind"]],
        "presentation_groups": [["Pinned nodes"], ["Neighbor count"], ["Selected node"], ["bridge"], ["aria-label"]],
        "records": [
            {"id": "NODE-A", "label": "Intake", "kind": "source", "degree": 2, "x": 18, "y": 30},
            {"id": "NODE-B", "label": "Join", "kind": "bridge", "degree": 3, "x": 50, "y": 48},
            {"id": "NODE-C", "label": "Store", "kind": "sink", "degree": 2, "x": 82, "y": 28},
            {"id": "NODE-D", "label": "Audit", "kind": "sink", "degree": 1, "x": 78, "y": 72},
        ],
        "asset_args": {
            "edges": [
                ("NODE-A", "NODE-B"),
                ("NODE-A", "NODE-C"),
                ("NODE-B", "NODE-C"),
                ("NODE-B", "NODE-D"),
            ]
        },
        "marker": {"attr": "data-node-id", "id": "NODE-B", "x": 50, "y": 48, "tol": 10},
        "clicks": [["button", r"pin node"]],
        "body_has": ["NODE-B", "Join", "bridge", "Neighbor count", "3", "Pinned", "1"],
        "selects": [["Node kind", "bridge"]],
        "toggles": [],
        "after_toggle": [],
    },
    {
        "id": "026-wysiwyg-print-preview",
        "title": "Build a paginated print preview over synthetic article pages",
        "family": "frontend-print-hard",
        "fe": "FE-226",
        "asset": "print-pages.png",
        "board": "print-board",
        "attr": "data-page-id",
        "instruction_kind": "paginated print preview, not a form builder. The first screen should show the protected page spread, clickable pages, running headers, and selected-page details.",
        "fields": "only `id` and `title`",
        "visible_fields": ["id", "title"],
        "image_note": "a print-preview spread of several pages on a desk-colored canvas. Each page shows a running header, its section title, a small line printing the page id and its word count, body text rules, and a page number at the bottom.",
        "visual_reading": [
            "Each page's marker position (the page center), its `page` number, and its `words` count as printed on the page. None of these are in the records.",
        ],
        "behavior": [
            "Render the protected spread inside `data-testid=\"print-board\"`. Each page must expose `data-page-id=\"<id>\"` and visible id text, centered on that page in the image.",
            "Provide controls for `Paper size`, `Pin page`, and `Clear pins`. `Paper size` must include a `letter` option.",
            "Selecting a page must update a detail panel showing its title, page number, and word count. Pinning must update `Pinned pages`, `Pinned count`, `Word total` (sum of pinned pages' word counts), and a visible running header with `data-testid=\"running-header\"`.",
        ],
        "domain_groups": [["print"], ["page"], ["header"], ["Paper size"], ["Pinned count"], ["Word total"]],
        "interaction_groups": [["data-testid", "print-board"], ["data-page-id"], ["Pin page"], ["Clear pins"], ["running-header"]],
        "presentation_groups": [["Pinned pages"], ["Word total"], ["Selected page"], ["letter"], ["aria-label"]],
        "records": [
            {"id": "PAGE-1", "title": "Abstract", "page": 1, "words": 180, "x": 26, "y": 40},
            {"id": "PAGE-2", "title": "Methods", "page": 2, "words": 420, "x": 74, "y": 40},
            {"id": "PAGE-3", "title": "Results", "page": 3, "words": 360, "x": 26, "y": 78},
            {"id": "PAGE-4", "title": "Notes", "page": 4, "words": 90, "x": 74, "y": 78},
        ],
        "marker": {"attr": "data-page-id", "id": "PAGE-2", "x": 74, "y": 40, "tol": 10},
        "clicks": [["button", r"pin page"]],
        "body_has": ["PAGE-2", "Methods", "420", "Pinned", "1"],
        "selects": [["Paper size", "letter"]],
        "toggles": [],
        "after_toggle": [],
    },
]


def emit(spec: dict) -> None:
    task_id = spec["id"]
    task_dir = OUT / task_id
    if task_dir.exists():
        shutil.rmtree(task_dir)
    _copy_starter(task_dir)
    asset = spec["asset"]
    render_asset(asset, spec["records"], task_dir / "workspace/web/public" / asset, **spec.get("asset_args", {}))
    visible_records = [{key: record[key] for key in spec["visible_fields"]} for record in spec["records"]]
    _dump(task_dir / "workspace/web/src/data/localRecords.json", visible_records)
    _write(task_dir / "environment/Dockerfile", DOCKERFILE)
    _write(
        task_dir / "task.yaml",
        textwrap.dedent(
            f"""\
            task_id: {task_id}
            title: {spec['title']}
            prompt_file: instruction.md
            timeout_sec: 2400
            domain: Software Engineering
            difficulty: hard
            capability_tags:
            - filesystem
            - frontend
            - code_execution
            - browser
            - multimodal
            - structured_data
            harness_demands:
            - evidence_grounding
            - multi_step_execution
            - state_management
            - verification_behavior
            - output_contract
            - safety_boundary
            stressors:
            - dirty_input
            - state_coupling
            - responsive_layout
            - safety_boundary
            - visual_regression
            required_artifacts:
            - web/package.json
            - web/src/App.tsx
            - web/src/index.css
            - web/public/{asset}
            - web/dist/index.html
            task_family: {spec['family']}
            variant: {task_id.split('-', 1)[1]}
            design_file: design.md
            provenance:
              origin: handcrafted_synthetic
              real_user_log_derived: false
              source_ids:
              - {spec['fe']}
            workspace_dir: workspace
            mutation_contract:
              allowed_created:
              - web/dist/
              - web/src/components/
              - web/src/hooks/
              - web/src/utils/
              allowed_modified:
              - web/package.json
              - web/index.html
              - web/vite.config.ts
              - web/tsconfig.json
              - web/src/main.tsx
              - web/src/App.tsx
              - web/src/index.css
              - web/src/hooks/useReveal.ts
              - web/src/utils/cn.ts
              allowed_deleted: []
            outcome_test: tests/test_outcome.py
            cases_file: tests/cases.yaml
            schema_version: 2
            """
        ),
    )
    slug = task_id.split("-", 1)[1].replace("-", "_")
    behaviors = "\n".join(f"- {line}" for line in spec["behavior"])
    visual_reading = "\n".join(f"- {line}" for line in spec["visual_reading"])
    _write(
        task_dir / "instruction.md",
        f"""# {spec['title']}

In `$WORKSPACE/web`, replace the starter page with a polished, local-only React TypeScript application grounded in `web/src/data/localRecords.json` and protected image `web/public/{asset}`.

You are building a {spec['instruction_kind']}

## Protected local data

Do not edit `web/src/data/localRecords.json` or `web/public/{asset}`. Records contain {spec['fields']}; they identify the features but deliberately carry no geometry or visual attributes.

`web/public/{asset}` is {spec['image_note']} It is a raster image: there is no vector source or metadata in the workspace to parse, so open and inspect the image itself.

## Read these facts from the image

{visual_reading}

Encode what you read as code you own (for example a typed map under `web/src/utils/` keyed by record id, with positions as percentages of the image width and height). Do not add fields to `localRecords.json`, do not redraw the artwork in code, and do not guess: every value the UI shows must come from the image.

## Required behavior

- Import or otherwise read all protected records; do not retype a smaller dataset.
{behaviors}
- Make the UI usable on desktop and mobile, with visible focus states, semantic labels, no horizontal overflow, and reduced-motion handling.
- Keep dependencies pinned in `package.json`; do not use `latest`, external APIs, network calls, generated package locks, or remote assets.
- Before finishing, run `npm run build`; the evaluator may serve `web/dist` for browser-driven interaction checks.
- Keep `web/dist/index.html` and the rest of `web/dist`, but remove generated install/build artifacts before finishing.
- Stage local decisions only. Do not claim that you booked, reserved, paid, or changed any real external system.

## Browser verification target

The evaluator serves `web/dist`, measures every marker's center relative to `data-testid="{spec['board']}"` against the true feature positions in the image, clicks protected ids, operates the named controls, checks that the detail panel and summaries show the values printed or encoded in the image, and repeats mobile layout checks. Exact tolerances are evaluator-owned.
""",
    )
    hidden_fields = [key for key in spec["records"][0] if key not in spec["visible_fields"]]
    facts = "\n".join(
        "- `" + record["id"] + "`: " + ", ".join(f"{key}={record[key]}" for key in hidden_fields) for record in spec["records"]
    )
    _write(
        task_dir / "design.md",
        f"""# {task_id} Design

Synthetic {spec['family']} workspace, vision-gated. The oracle checks the protected PNG and identity-only records, marker geometry for every feature, image-derived values in the UI, and the safety boundary.

Weights: build 0.22, protected data 0.22, interaction 0.36, responsive 0.20, safety gate.

## Why the image is load-bearing

The shipped `localRecords.json` carries only {", ".join(f"`{key}`" for key in spec["visible_fields"])}. Everything below exists only in `web/public/{asset}` and in `tests/ground_truth/ground_truth.json` (`visual_facts`), so a candidate that never inspects the image cannot place markers or fill the detail panel:

{facts}

The PNG is rendered by `tools/task_maintenance/multimodal_raster_assets.py` from these hidden facts at 2x scale with matplotlib's bundled fonts, so it is byte-stable and has no vector or text source inside the workspace. The browser probe checks all {len(spec['records'])} marker centers (tolerance {spec['marker']['tol']} percentage points of the board) and requires image-only tokens {spec['body_has']} in the page body.

- **Synthetic-data statement:** All records, labels, people, owners, statuses, screenshots, and numeric values are synthetic.
""",
    )
    case_ids = [
        "build_and_runtime_integrity",
        f"{slug}_protected_inputs",
        f"{slug}_interaction_model",
        f"{slug}_responsive_surface",
        "scope_and_safety_boundary",
    ]
    _write(
        task_dir / "tests/cases.yaml",
        textwrap.dedent(
            f"""\
            schema_version: 2
            task_id: {task_id}
            pass_threshold: 0.8
            cases:
            - id: {case_ids[0]}
              title: Buildable frontend runtime contract
              description: Required Vite React files exist, dependencies are pinned, local data is imported, and the app is not a starter or keyword-stuffed shell.
              weight: 0.22
              core: true
            - id: {case_ids[1]}
              title: Protected records and local image
              description: The protected records and local image are unchanged and the UI exposes the required vocabulary.
              weight: 0.22
              core: true
            - id: {case_ids[2]}
              title: Marker, selection, and summary behavior
              description: Browser checks marker coordinates, selection, named controls, and derived summaries.
              weight: 0.36
              core: true
            - id: {case_ids[3]}
              title: Responsive accessible presentation
              description: CSS and source expose responsive layout, focus treatment, reduced-motion handling, semantic controls, and the expected visual surface.
              weight: 0.20
              core: false
            - id: {case_ids[4]}
              title: Scope and safety boundary
              description: The candidate does not mutate protected inputs, create unrelated files, call remote services, add package locks, or claim real-world external actions.
              weight: 0.00
              gate: true
            """
        ),
    )
    gt = {
        "task_id": task_id,
        "case_ids": case_ids,
        "required_files": [
            "web/package.json",
            "web/index.html",
            "web/vite.config.ts",
            "web/tsconfig.json",
            "web/src/main.tsx",
            "web/src/App.tsx",
            "web/src/index.css",
            "web/src/data/localRecords.json",
            f"web/public/{asset}",
            "web/dist/index.html",
        ],
        "records": visible_records,
        "visual_facts": spec["records"],
        "minimum_handlers": 6,
        "domain_groups": spec["domain_groups"],
        "interaction_groups": spec["interaction_groups"],
        "presentation_groups": spec["presentation_groups"],
        "interaction_probe": {
            "target_viewport": {"width": 1440, "height": 900},
            "mobile_viewport": {"width": 390, "height": 844},
            "board": f'[data-testid="{spec["board"]}"]',
            "marker": spec["marker"],
            "markers": [
                {"attr": spec["attr"], "id": record["id"], "x": record["x"], "y": record["y"], "tol": spec["marker"]["tol"]}
                for record in spec["records"]
            ],
            "clicks": spec["clicks"],
            "body_has": spec["body_has"],
            "selects": spec["selects"],
            "toggles": spec["toggles"],
            "after_toggle": spec["after_toggle"],
            "name": slug,
        },
    }
    _dump(task_dir / "tests/ground_truth/ground_truth.json", gt)
    _dump(task_dir / "tests/ground_truth/frontend_contract.json", gt)
    _write(task_dir / "tests/test_outcome.py", _outcome_src())
    print(task_id)


def main() -> None:
    for spec in TASKS:
        emit(spec)


if __name__ == "__main__":
    main()
