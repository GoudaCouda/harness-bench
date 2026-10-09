# Task Design: `017-http-cache-revalidation`

## 1. Workflow identity

- **Domain:** Software Engineering
- **Role:** edge-platform engineer repairing conditional cache middleware
- **Trigger:** a refactor emits 304 for a mismatched language variant and treats
  weak and strong ETags inconsistently
- **Objective:** restore standards-grounded local revalidation and produce a
  reproducible visible-case report
- **Irreversible boundary:** no origin request, purge, deployment, or shared
  cache mutation is authorized

## 2. Idea provenance

| Source ID | Source | URL | Accessed | Adaptation |
|---|---|---|---|---|
| HTTP-SEMANTICS-RFC9110 | RFC 9110 HTTP Semantics | https://www.rfc-editor.org/rfc/rfc9110.html | 2026-08-26 | Grounds If-None-Match weak comparison, If-Modified-Since precedence, and 304 behavior |
| HTTP-CACHING-RFC9111 | RFC 9111 HTTP Caching | https://www.rfc-editor.org/rfc/rfc9111.html | 2026-08-26 | Grounds Vary-based stored-response selection and revalidation boundaries |

All requests, URIs, tags, dates, and cache records are synthetic.

- **Private user logs:** None were used.
- **Adaptation:** Standards semantics are narrowed to a pure repository repair
  that can expose realistic middleware mistakes without a networked origin.

## 3. Real-workflow justification

Cache regressions often survive happy-path tests because validator syntax,
precondition precedence, and representation selection interact. A wrong 304
can serve stale or cross-language content, while over-bypassing erases cache
benefits. The work naturally spans reusable code, executable examples, and an
integration handoff.

## 4. Agent-visible inputs

`repo/docs/cache_contract.md` is authoritative. Visible requests are in
`repo/revalidation_cases.json`; code and tests are
`repo/src/cache_revalidation.py` and `repo/tests/test_public.py`.

## 5. Hidden ground truth

The selected stored record must first match the URI and every `Vary` key.
`If-None-Match` has precedence over `If-Modified-Since` and uses weak entity-tag
comparison; date validation applies only when no entity-tag precondition is
present. Invalid client conditional values bypass to origin rather than
manufacturing a 304. Required final state is correct pure code in
`repo/src/cache_revalidation.py`, an exact `repo/revalidation_report.json`, and
a truthful `repo/REPAIR_NOTES.md`. Inputs remain unchanged.

## 6. Expected workflow

1. Read `repo/docs/cache_contract.md` and inventory each visible request state.
2. Run `repo/tests/test_public.py` and inspect the failed key and validator paths.
3. Repair decision state in `repo/src/cache_revalidation.py`; only `datetime` may be imported and I/O remains forbidden.
4. Generate `repo/revalidation_report.json` from the visible case events.
5. Rerun tests and record verification and risk in `repo/REPAIR_NOTES.md`.

### Novelty review

| Nearest task | Similarity | Substantive differences |
|---|---|---|
| `050-http-range-download-resume-repair` (reserved) | HTTP validators | 017 evaluates conditional cache reuse and Vary; 050 handles resumable transfer state and Range responses |
| `010-layered-config-resolution` | precedence code | 017 uses protocol preconditions and representation keys rather than configuration sources |
| `094-alert-routing-repair` | configuration-driven service repair | 017 is a pure HTTP decision engine with date/tag parsing and no routing tree |

## 7. Harness demands

The task requires multi-file grounding, code execution, stateful reasoning across
stored/current headers, exact report generation, verification, and restraint at
the origin/deployment boundary.

## 8. Stressors and difficulty

- **Stressors:** weak ETags, comma lists, exact validator precedence, Vary
  wildcard/missing headers, fixed HTTP dates, malformed bypass, and immutability.
- **Plausible failure mode:** compare ETags byte-for-byte, evaluate both
  conditionals, ignore Vary, treat an invalid date as equal, or mutate headers.
- **Difficulty:** hard.
- **Difficulty rationale:** several individually plausible shortcuts pass public
  examples while violating independent hidden protocol cohorts.

## 9. Oracle design

`validator_and_variant_behavior` (0.45 core) and `malformed_and_boundary_edges`
(0.25 core) execute `repo/src/cache_revalidation.py` in a restricted worker.
`visible_revalidation_report` (0.10 core) recomputes and checks
`repo/revalidation_report.json`. `verification_handoff` (0.20 optional) checks
`repo/REPAIR_NOTES.md`. `source_and_workspace_boundary` is a zero-weight
integrity gate limited to protected-input and workspace redlines. Source defects
and unsupported action claims lose their ordinary scored cases. Core weight is
0.80; equivalent pure implementations pass.

### Adjacent examples

- **Nearest valid:** `W/"rev-7"` matches stored `"rev-7"` for If-None-Match.
- **Nearest wrong 1:** a matching tag returns 304 even though `Accept-Language`
  differs from the stored Vary key.
- **Nearest wrong 2:** a nonmatching If-None-Match falls through to a matching
  If-Modified-Since and incorrectly returns 304.

## 10. Leakage, isolation, and safety review

Hidden cases, references, and design are excluded from the agent. Candidate
source is AST-audited and executed with only a static `datetime` import and no I/O, filesystem, or network.
Protected fixtures are integrity-checked and all identifiers are synthetic.

## 11. Pilot plan

Require reference `1.0` and empty/untouched/malformed `0.0`. Mutate weak
comparison, precondition precedence, Vary selection, date boundaries, malformed
bypass, report order, and input mutation independently. Pilot Gemma + OpenClaw
on a healthy CPU pool and target a first-pass score around 0.30–0.70.

- **Expected Gemma/OpenClaw failure modes:** strong ETag comparison, date
  fallback after tag mismatch, case-sensitive header names, Vary omission,
  malformed-value 304, or a hard-coded visible report.

## 12. Human validation status

- **Status:** `not_required`; deterministic gates and model pilot are required.
- **Current evidence level:** official-source design and executable Oracle.
- **Model outcomes used for membership:** false.
- **Canonical registry:** `docs/task_reviews/review_registry.csv`.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `validator_and_variant_behavior`.
- `validation_and_replay`: `malformed_and_boundary_edges`, `visible_revalidation_report`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
