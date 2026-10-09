# Task Design: `009-safe-archive-extraction`

## 1. Workflow identity

- **Domain:** Software Engineering
- **Role:** release-platform engineer repairing an artifact installer
- **Trigger:** archive members escaped staging or collided on another runner
- **Objective:** implement fail-closed preflight and produce a safe visible plan
- **Irreversible boundary:** no extraction, installation, registry access,
  release publication, or production mutation is authorized

## 2. Idea provenance

| Source ID | Source | URL | Accessed | Adaptation |
|---|---|---|---|---|
| PYTHON-TARFILE-FILTERS | Python `tarfile` extraction filters | https://docs.python.org/3/library/tarfile.html#extraction-filters | 2026-08-26 | Motivates pre-inspection, link/special-file restrictions, budgets, and case-collision checks beyond a default filter |
| POSIX-PATHNAME-RESOLUTION | POSIX.1-2024 pathname resolution | https://pubs.opengroup.org/onlinepubs/9799919799/basedefs/V1_chap04.html#tag_04_16 | 2026-08-26 | Grounds absolute, dot, dot-dot, and component semantics |

All names, members, sizes, and incident details are synthetic. The task adapts
security semantics and does not copy implementation or answer text.

- **Private user logs:** None were used.
- **Adaptation:** Archive metadata is represented as JSON for deterministic policy
  repair, while the visible integration suite constructs real in-memory tar headers
  for safe and path-escaping members without extracting either payload.

## 3. Real-workflow justification

Release tooling routinely extracts third-party artifacts. A check that blocks
only `../` can still fail on absolute Windows paths, links, case-insensitive
collisions, file-as-parent conflicts, duplicate members, or decompression
budgets. The deliverable is executable repository code plus an incident plan,
not a generic security memo.

## 4. Agent-visible inputs

| Evidence | Purpose | Precedence |
|---|---|---|
| `repo/docs/security_contract.md` | full validation and fail-closed contract | highest |
| `repo/release_manifest.json` | safe release cohort for the final plan | authoritative fixture |
| `repo/extraction_policy.json` | target-platform and resource limits | authoritative fixture |
| `repo/tests/test_public.py` | public examples | illustrative subset |
| `repo/tests/test_tar_integration.py` | real `tarfile` header integration checks | executable verification |
| `repo/src/archive_preflight.py` | implementation target | writable |

## 5. Hidden ground truth

- Concrete inputs are `repo/release_manifest.json` and
  `repo/extraction_policy.json`; required final state is
  `repo/src/archive_preflight.py`, `repo/extraction_plan.json`, and
  `repo/SECURITY_NOTES.md`.
- The key invariant is validate-before-write. Path validity and member type have
  priority over collision and budget accounting; any violation rejects the
  complete manifest with `ValueError`.
- Hidden cohorts cover POSIX/Windows absolute paths, UNC/backslash forms,
  controls, dot components, links and special files, bool sizes, duplicate and
  case-fold collisions, file parents, exact budget boundaries, and input
  immutability.
- Candidate source is AST-audited and executed as a pure function with
  restricted builtins in a bounded worker.

## 6. Expected workflow

1. Read `repo/docs/security_contract.md`, `repo/release_manifest.json`, and
   `repo/extraction_policy.json`.
2. Run `repo/tests/test_public.py` to reproduce the missing implementation.
3. Implement all path, type, collision, and budget checks in
   `repo/src/archive_preflight.py` without filesystem access.
4. Re-run the exact unittest command and generate `repo/extraction_plan.json`
   from the protected visible inputs.
5. Record design choices, observed verification, and residual risk in
   `repo/SECURITY_NOTES.md` without claiming extraction or installation.

### Novelty review

| Nearest task | Similarity | Substantive differences |
|---|---|---|
| `112-container-sbom-remediation` | release artifact security | 009 repairs extraction-path semantics and resource bounds; 112 remediates image packages and ABI |
| `051-smallfile-batch-reject-ledger` | per-file validation | 009 is a fail-closed archive namespace and filesystem-safety contract, not data normalization |
| `078-artifact-provenance-gate` | artifact release gate | 009 evaluates member-level extraction safety rather than signatures/provenance |

## 7. Harness demands

| Demand | Why it is necessary |
|---|---|
| `evidence_grounding` | policy, manifest, contract, and examples have different roles |
| `multi_step_execution` | code, tests, visible plan, and notes must agree |
| `output_contract` | stable normalized entries and aggregate fields feed the installer |
| `verification_behavior` | hidden cross-platform and collision cases exceed public tests |
| `safety_boundary` | no candidate archive member or external system is touched |

## 8. Stressors and difficulty

- **Stressors:** mixed platform paths, links, collisions, file-parent conflicts,
  malformed booleans, exact resource boundaries, and archive order.
- **Difficulty:** medium; many near-valid paths defeat simplistic prefix checks.
- **Plausible failure mode:** call string normalization and accidentally accept
  a dangerous spelling, or check each entry without global namespace budgets.
- **Difficulty rationale:** correctness comes from interacting security
  invariants, not file count or prose volume.

## 9. Oracle design

| Case | Weight | Deterministic evidence |
|---|---:|---|
| `safe_manifest_behavior` | 0.40 core | pure-function safe cohorts and archive-order preservation for `repo/src/archive_preflight.py` |
| `fail_closed_security_edges` | 0.30 core | adversarial paths, types, collisions, parents, limits, and malformed policy for `repo/src/archive_preflight.py` |
| `visible_extraction_plan` | 0.10 core | exact protected-manifest result in `repo/extraction_plan.json` |
| `verification_handoff` | 0.20 optional | decisions, exact observed command/result, and residual risk in `repo/SECURITY_NOTES.md` |
| `source_and_workspace_boundary` | gate | immutable inputs plus link, special-file, undeclared-path, and path-escape integrity only |

Core blocks total 0.80. Equivalent control flow, helper names, JSON formatting,
and explanatory prose are accepted; candidate-authored tests are not evidence.
Unsafe implementation details lose behavior cases and unsupported action claims
lose handoff credit without erasing independently correct work.

### Adjacent examples

- **Nearest valid:** `pkg/readme.txt` at the exact byte budget remains accepted.
- **Nearest wrong 1:** normalize `pkg/../escape` to `escape` and accept it.
- **Nearest wrong 2:** accept both `Readme` and `README` on a case-insensitive
  destination because their original strings differ.

## 10. Leakage, isolation, and safety review

- Hidden cases, reference outputs, and this design are excluded from the agent.
- Ordinary computation-only standard-library imports are allowed. Dynamic
  execution, private/dunder access, filesystem writes, processes, network, clocks,
  and environment access remain blocked in the hidden pure-function grader; a
  short worker timeout limits hostile loops.
- The candidate receives metadata only, never an archive payload or credential.
- Immutable inputs and allowed final paths are integrity checked.

## 11. Pilot plan

- Require reference `1.0`; empty, untouched, and malformed `0.0`.
- Mutation probes remove backslash, link, case-collision, parent-file, and total
  budget checks and change exact-bound comparisons.
- Pilot coding harnesses on contract reading, public test use, self-correction,
  tokens, and elapsed time.
- **Expected Gemma/OpenClaw failure modes:** use `normpath` as validation, treat
  booleans as sizes, count directories as files, or generate a plan without
  running the repaired function.

## 12. Human validation status

- **Status:** `not_required` under current project policy; deterministic gates
  remain mandatory.
- **Current evidence level:** official-source review plus executable reference,
  negative controls, and adjacent mutations.
- **Model outcomes used for membership:** false.
- **Canonical registry:** `docs/task_reviews/review_registry.csv`.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `safe_manifest_behavior`.
- `validation_and_replay`: `fail_closed_security_edges`, `visible_extraction_plan`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
