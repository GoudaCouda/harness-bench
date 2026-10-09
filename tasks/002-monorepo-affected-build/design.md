# Task Design: `002-monorepo-affected-build`

## 1. Workflow identity

- **Domain:** Software Engineering
- **Role:** build-platform engineer repairing an affected-project planner
- **Trigger:** a generated API change reused stale downstream cache entries
- **Objective:** repair executable dependency-graph behavior and leave the
  exact plan for the incident change set
- **Irreversible boundary:** no package installation, CI trigger, merge,
  cache purge, or deployment is authorized

## 2. Idea provenance

| Source ID | Source | URL | Accessed | Adaptation |
|---|---|---|---|---|
| BAZEL-BUILD-SYSTEMS | Bazel build-system concepts | https://bazel.build/basics/build-systems | 2026-08-26 | Motivates dependency-graph correctness and stale-output prevention |
| NX-AFFECTED | Nx affected-project documentation | https://nx.dev/ci/features/affected | 2026-08-26 | Motivates computing work from changed files plus project dependencies |
| GIT-DIFF | Git diff documentation | https://git-scm.com/docs/git-diff | 2026-08-26 | Motivates treating deleted and renamed-path evidence as changes rather than reading current file contents |

All package names, paths, graph records, and incident details are synthetic.
The sources establish the workflow pattern; no answer or fixture is copied.

- **Private user logs:** None were used.
- **Adaptation:** The task condenses a normal monorepo cache incident into a
  pure planner, an auditable visible plan, and a truthful verification handoff.

## 3. Real-workflow justification

Affected-build selection is production engineering work: too narrow a plan
ships stale artifacts, while rebuilding everything hides dependency errors and
wastes CI capacity. Real failures occur around generated inputs, global files,
documentation-only edits, deleted paths, and dependency cycles—not only the
happy path shown by a small public test.

## 4. Agent-visible inputs

| Evidence | Purpose | Precedence |
|---|---|---|
| `repo/docs/planner_contract.md` | full ownership, propagation, cycle, and ordering rules | highest |
| `repo/build_graph.json` | package roots, generated inputs, dependencies, and global rules | authoritative fixture |
| `repo/changed_paths.json` | visible incident change set, including a deleted path | authoritative fixture |
| `repo/tests/test_public.py` | executable examples | illustrative subset |
| `repo/src/affected_build.py` | implementation target | writable |

## 5. Hidden ground truth

- The concrete visible inputs are `repo/build_graph.json` and
  `repo/changed_paths.json`. The required final workspace state is
  `repo/src/affected_build.py`, `repo/affected_plan.json`, and
  `repo/REPAIR_NOTES.md`.
- The central invariant is dependency-before-dependant ordering: graph validity
  has priority over change selection, exact global/generated matches have
  priority over source-root ownership, and the longest matching root wins.
- Hidden cohorts cover source ownership, longest-root selection, exact
  generated-input ownership, global lock/toolchain rules, duplicate paths,
  documentation-only changes, deleted paths, non-buildable nodes, transitive
  dependants, deterministic dependency depth, and cycles.
- Candidate source is AST-audited and evaluated as a pure function with
  restricted builtins in a bounded worker.
- The visible plan is recomputed from protected fixtures. Direct causes and
  transitive effects are graded separately.
- Immutable inputs and the allowed output tree are integrity checked.

## 6. Expected workflow

1. Read `repo/docs/planner_contract.md`, `repo/build_graph.json`, and
   `repo/changed_paths.json` rather than infer behavior from one public test.
2. Reproduce the stale-cache symptom with `repo/tests/test_public.py` and the
   supplied generated-path change.
3. Implement ownership, global invalidation, and transitive propagation in
   `repo/src/affected_build.py`.
4. Detect graph cycles and order dependency depth before lexical tie-breaking
   in the same planner function.
5. Run the exact unittest command, generate `repo/affected_plan.json`, and
   record the observed result and residual risk in `repo/REPAIR_NOTES.md`.

### Novelty review

| Nearest task | Similarity | Substantive differences |
|---|---|---|
| `024-repo-architecture-map` | repository dependency reasoning | 002 changes executable build selection and proves hidden behavior; 024 documents architecture |
| `070-ci-attempt-diagnosis` | CI context | 002 repairs graph/cache semantics before CI rather than classifying past attempts |
| `076-transitive-security-upgrade` | transitive graph | 002 computes affected build scope from files and generated inputs, not dependency version remediation |

## 7. Harness demands

| Demand | Why it is necessary |
|---|---|
| `evidence_grounding` | rules are split across a contract, graph, changes, and examples |
| `multi_step_execution` | code, tests, generated plan, and handoff must agree |
| `output_contract` | deterministic ordering and direct-cause shape are review interfaces |
| `verification_behavior` | public tests omit several stale-cache edge cases |
| `safety_boundary` | the candidate must not trigger CI or mutate external caches |

## 8. Stressors and difficulty

- **Stressors:** longest-root ownership, generated paths, global invalidation,
  non-buildable nodes, transitive closure, deleted paths, and cycles.
- **Difficulty:** medium; the implementation is small but graph semantics are
  coupled and several plausible shortcuts pass public examples.
- **Plausible failure mode:** scan only existing source files, miss generated
  inputs, return graph declaration order, or rebuild every package.
- **Difficulty rationale:** correctness depends on behavior across hidden graph
  shapes, not on code volume.

## 9. Oracle design

| Case | Weight | Deterministic evidence |
|---|---:|---|
| `ownership_and_propagation` | 0.45 core | pure-function hidden source/generated/global cohorts |
| `ordering_and_fail_closed_edges` | 0.25 core | dependency-depth ordering, duplicate/docs handling, longest roots, and cycle rejection |
| `visible_incident_plan` | 0.10 core | exact affected package list plus grounded direct causes from protected fixtures |
| `verification_handoff` | 0.20 optional | decision, exact observed command/result, and realistic residual risk |
| `source_and_workspace_boundary` | gate | immutable inputs plus link, special-file, undeclared-path, and path-escape integrity only |

Core blocks total 0.80. The behavior cases cover
`repo/src/affected_build.py`; the visible-state case covers
`repo/affected_plan.json`; and the handoff case covers `repo/REPAIR_NOTES.md`.
Equivalent algorithms, helper names, formatting, and prose are accepted.
Pure-source failures lose the behavior blocks, while unsupported action claims
lose the handoff block; neither ordinary defect zeroes unrelated correct work.
Candidate-authored tests are never ground truth.

### Adjacent examples

- **Nearest valid:** generated API input directly invalidates `api`; `web`
  follows transitively; unrelated docs do not enter the build.
- **Nearest wrong 1:** rebuild only the owner and omit reverse dependants.
- **Nearest wrong 2:** topologically sort declaration order, producing
  nondeterministic ties and unstable cache keys.

## 10. Leakage, isolation, and safety review

- Hidden cases, reference files, and this design are excluded from the agent.
- Source is parsed before restricted pure execution; imports, dynamic access,
  external I/O, and unbounded constructs are rejected.
- Graph and changed-path fixtures are immutable and contain no credentials or
  personal data.
- The task remains offline and authorizes no external build-system action.

## 11. Pilot plan

- Require reference `1.0`; empty, untouched, and malformed `0.0`.
- Mutation probes remove reverse propagation, ignore generated files, rebuild
  docs, change tie order, and suppress cycle failure.
- Compare at least two coding harnesses on test use, contract reading,
  self-correction, tokens, and elapsed time.
- **Expected Gemma/OpenClaw failure modes:** hard-code the visible package list,
  treat `README.md` as source, miss deleted paths, or use alphabetical order
  without dependency depth.

## 12. Human validation status

- **Status:** `not_required` under the current project policy; deterministic
  engineering gates remain mandatory.
- **Current evidence level:** source-researched design plus executable
  reference, negative controls, and adjacent mutations.
- **Model outcomes used for membership:** false.
- **Canonical registry:** `docs/task_reviews/review_registry.csv`.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `ownership_and_propagation`.
- `validation_and_replay`: `ordering_and_fail_closed_edges`, `visible_incident_plan`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
