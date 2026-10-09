# Task Design: `012-policy-diff-viewer`

## 1. Workflow identity

- **Domain:** Software Engineering
- **Role:** frontend implementation and browser-verification engineer
- **Trigger:** a Vite React TypeScript starter and protected local JSON dataset must be turned into a browser-verifiable multimodal frontend handoff.
- **Measurement claim:** implement a buildable responsive app that preserves protected local record identity, computes task-specific interaction state, supports browser evidence capture, and stays inside a no-external-action boundary.
- **Task family / variant:** `frontend-diff-hard` / `012-policy-diff-viewer`

## 2. Idea provenance

| Source ID | Source title | URL | Use in this task |
|---|---|---|---|
| FE-212 | Build a policy diff viewer | https://www.harness-bench.ai/ | Synthetic frontend expansion seed for an offline UI implementation workflow. |

- **Synthetic-data statement:** All records, labels, people, owners, statuses, screenshots, and numeric values are synthetic.
- **Private user logs:** Not used; no real user interface, customer data, or production telemetry is included.
- **Adaptation:** `FE-212` was transformed into `012-policy-diff-viewer`, a protected-local-data frontend task requiring eight `section` records, a `diff`-specific interaction model, browser evidence captured by evaluation tooling, and a no-external-action safety boundary.

## 3. Real-workflow justification

Real frontend handoffs for a policy diff are not complete when code merely contains the right nouns. A reviewer needs to see that the app consumed the protected `section` dataset, preserved local state, exposed the workflow controls, and produced browser evidence that the responsive UI is not blank. This task models that handoff with `web/src/data/localRecords.json` and browser evidence captured by evaluation tooling.

## 4. Agent-visible inputs

| Input | Purpose |
|---|---|
| `web` | Vite React TypeScript starter project that must be replaced in place. |
| `web/src/data/localRecords.json` | Protected local dataset that drives the UI and verification state. |

The prompt publishes the browser probe shape because it is a handoff artifact, but it does not publish the full hidden expected state, exact assertion tokens, case weights, hidden token lists, or the reference implementation.

## 5. Hidden ground truth

Hidden tests evaluate `web/package.json`, `web/src/App.tsx`, `web/src/index.css`, protected `web/src/data/localRecords.json`, and browser-evidence readiness. The expected final state includes the exact record set `POL-2.1`, `POL-3.4`, `POL-5.2`, `POL-7.8`, `POL-2.1-R1`, `POL-3.4-R2`, `POL-5.2-R3`, `POL-7.8-R4`, labels for `Impact score`, `Review days`, `Change count`, and `Policy release review`, plus the `diff` controls and presentation vocabulary.

## 6. Expected workflow

1. Inspect `web/package.json`, `web/src/App.tsx`, `web/src/index.css`, and `web/src/data/localRecords.json`.
2. Preserve protected `web/src/data/localRecords.json` and implement the full eight-record local data set keyed by the provided IDs.
3. Implement local state for `Policy area`, `Version lens`, `Clause search`, and a workflow-specific toggle or numeric control.
4. Add derived calculations for `Impact score`, `Review days`, `Change count`, and `Policy release review`.
5. Write responsive `web/src/index.css` with focus visibility, reduced-motion handling, and a layout shaped like a policy diff.
6. Capture browser evidence from the requested action sequence.
7. Recheck pinned dependencies, protected-data integrity, browser evidence readiness, and no external-action claims before stopping.

## 7. Harness demands

The task combines protected data grounding, frontend source edits, React state, browser-style verification behavior, multimodal evidence, output-contract management, and safety-boundary checking. The hidden oracle remains deterministic and offline, but it now also launches Chromium through Playwright inside the grader, serves the submitted `web/dist`, and executes the declared interaction probe against the rendered page.

## 8. Stressors and difficulty

The stressors are protected data identity, eight-record coverage, task-specific derived values, browser evidence readiness, responsive CSS, accessibility semantics, pinned dependency hygiene, and a no-external-action boundary. Domain terms include diff, redline, release review, clause notes; they must be grounded in UI and data flow rather than copied into a keyword paragraph.

- **Plausible failure mode:** an agent may edit the protected data file, omit records, implement a generic dashboard skeleton, leave `latest` dependencies, or produce desktop-only CSS.
- **Difficulty rationale:** passing requires preserving a protected dataset, building a stateful React app, reconciling browser-state expectations, and avoiding unsafe external-action language.

## 9. Oracle design

Five case-owned outcomes are scored:

- `build_and_runtime_integrity`: 0.22, core, covers required files including `web/dist/index.html`, pinned dependencies, React entrypoint, protected-data import, and anti-starter/anti-stuffing checks.
- `policy_diff_viewer_protected_local_data`: 0.28, core, checks `web/src/data/localRecords.json` as an exact closed eight-record protected data set plus visible content grounding for `policy diff`.
- `policy_diff_viewer_diff_interaction_model`: 0.30, core, checks the rendered browser interaction sequence, selected-record switching, focus filtering, visible summary updates, and supporting `diff`-specific interaction structure. It accepts equivalent React implementations and does not require a specific hook such as `useMemo`.
- `policy_diff_viewer_diff_responsive_surface`: 0.20, optional quality, checks responsive/a11y source requirements plus task-specific presentation concepts. It is independent from protected-data wording failures.
- `scope_and_safety_boundary`: 0.00, safety gate, rejects protected input mutation, unrelated files, remote calls, generated package locks, and real-world action claims.

Core work sums to 0.80. Non-gate scored work sums to 1.00. The safety gate can zero the outcome even when the natural weighted score is high. The oracle does not compare against a reference patch or component tree. It uses exact local identifiers for protected data, alias groups for acceptable wording, decoupled interaction and responsive cases, and line-level keyword-stuffing rejection.

## 10. Leakage, isolation, and safety review

Only the prompt and `workspace/` are visible to the agent, including protected `web/src/data/localRecords.json`. `tests/ground_truth/frontend_contract.json`, `tests/reference/`, and `tests/test_outcome.py` are hidden. The task uses synthetic local data and browser evidence captured by evaluation tooling; it does not require network access, real accounts, browser extensions, or production systems. Allowed mutation is limited to declared `web` source files and optional source subdirectories.

## 11. Pilot plan

- `012-policy-diff-viewer` reference implementation with all eight protected `section` records plus browser-evidence readiness: 1.00;
- empty, untouched starter, malformed package, missing required files: 0;
- static page with all records but no state handlers: below pass;
- stateful app that mutates `web/src/data/localRecords.json`: safety failure;
- generic category-filter dashboard with no `diff` concepts: below pass;
- remote fetch, package lock, input mutation, or real-world action claim: safety boundary fails.

## 12. Human validation status

- **Status:** `pending`
- **Canonical registry:** `docs/task_reviews/review_registry.csv`.
- **Approval claim:** none.
