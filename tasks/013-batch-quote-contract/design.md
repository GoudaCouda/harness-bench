# Task Design: `013-batch-quote-contract`

## 1. Workflow identity

- **Domain:** Software Engineering
- **Role:** backend engineer extending an internal pricing service
- **Trigger:** sales operations needs efficient batch quoting without breaking
  the production single-quote contract
- **Objective:** implement a pure batch-pricing function, publish its OpenAPI
  operation, and leave an evidence-bound verification handoff
- **Irreversible boundary:** no deployment, package installation, network call,
  customer quote publication, or production mutation is authorized

## 2. Idea provenance

| Source ID | Source | URL | Accessed | Adaptation |
|---|---|---|---|---|
| HTTP-SEMANTICS-RFC9110 | RFC 9110 HTTP Semantics | https://www.rfc-editor.org/rfc/rfc9110.html | 2026-08-26 | Motivates explicit retry/side-effect semantics and preservation of an existing HTTP operation |
| HTTP-PROBLEM-RFC9457 | RFC 9457 Problem Details for HTTP APIs | https://www.rfc-editor.org/rfc/rfc9457.html | 2026-08-26 | Motivates stable machine-readable validation codes without leaking implementation details |
| OPENAPI-32 | OpenAPI Specification 3.2 | https://spec.openapis.org/oas/v3.2.0.html | 2026-08-26 | Supplies the operation, request-body, array-bound, and response-description model |

All companies, plans, coupons, prices, requests, and code are synthetic. The
standards shape the interface; no example or answer text is copied from them.

- **Private user logs:** Not used.
- **Adaptation:** A normal repository feature request combines executable
  business rules with a backward-compatible API contract and local verification.

## 3. Real-workflow justification

Batch endpoints commonly fail in the seam between business behavior and the
published interface: implementations reorder results, round money through
binary floats, reject an entire batch for one bad item, or document a contract
that differs from runtime behavior. This task requires a coherent repository
change rather than a report about a hypothetical implementation.

## 4. Agent-visible inputs

| Evidence | Purpose | Precedence |
|---|---|---|
| `repo/docs/feature_request.md` | authoritative pricing, validation, and output rules | highest business authority |
| `repo/catalog.json` | plan limits and prices | authoritative fixture |
| `repo/coupons.json` | coupon scope and validity | authoritative fixture |
| `repo/api/openapi.json` | immutable single-operation baseline and writable API document | preserve existing path exactly |
| `repo/tests/test_public_batch.py` | executable examples | public subset, not exhaustive |
| `repo/src/quote_service/batch.py` | bounded implementation target | writable |

## 5. Hidden ground truth

- Hidden cohorts combine `repo/docs/feature_request.md` with the protected
  `repo/catalog.json` and `repo/coupons.json` values to cover monthly and annual prices, sequential integer discount
  rounding, inclusive coupon expiry, duplicate identifiers, booleans, plan seat
  bounds, unknown plans, and three coupon failure classes.
- The evaluator audits the candidate AST before evaluating the pure function in
  a time- and memory-bounded worker with restricted builtins.
- OpenAPI grading is semantic and requires the new inline request contract while
  proving the existing `/quotes/single` object is unchanged.
- The required final state is `repo/src/quote_service/batch.py`,
  `repo/api/openapi.json`, and `repo/IMPLEMENTATION_NOTES.md`; candidate-authored
  tests are not evidence for that state.

## 6. Expected workflow

1. Read `repo/docs/feature_request.md`, `repo/catalog.json`,
   `repo/coupons.json`, the existing API object, and the public tests.
2. Implement per-item validation and ordered partial success in
   `repo/src/quote_service/batch.py`.
3. Compute the `subtotal_cents`, term-discount, coupon-discount, and final-total
   state in the published order.
4. Add the `POST /quotes/batch` operation to `repo/api/openapi.json` without
   changing the `/quotes/single` state.
5. Run the declared unittest command and record its actual result and a bounded
   compatibility risk in `repo/IMPLEMENTATION_NOTES.md`.

### Novelty review

| Nearest task | Similarity | Substantive differences |
|---|---|---|
| `025-dependency-upgrade-compat` | repository code plus hidden behavior | 013 is normal feature construction with batch partial success and an OpenAPI contract; it has no dependency migration or wrapper audit |
| `030-sql-query-report` | executable business calculation | 013 implements a reusable service function and API schema rather than a reporting query |
| `046-ecommerce-support-routing` | per-record decisions | 013 changes code and a public interface under backward-compatibility constraints rather than reconciling support records |

## 7. Harness demands

| Demand | Why it is necessary |
|---|---|
| `evidence_grounding` | behavior is distributed across prose, two fixtures, an existing API object, and public examples |
| `multi_step_execution` | implementation, contract update, test execution, and handoff must agree |
| `output_contract` | the OpenAPI request and response shapes are part of the user-visible feature |
| `verification_behavior` | hidden cases intentionally exceed the public examples |
| `safety_boundary` | the code must remain pure and no deployment or customer publication is authorized |

## 8. Stressors and difficulty

- **Stressors:** bool/int ambiguity; duplicated IDs amid valid items; inclusive
  expiry boundary; sequential integer rounding; partial success; immutable old
  API path.
- **Difficulty:** medium. The code is compact, but multiple artifacts and edge
  semantics must remain consistent.
- **Plausible failure mode:** implement the happy path and pass public tests
  while rejecting the whole batch, applying coupon discount before annual
  discount, or silently changing the single-quote schema.
- **Difficulty rationale:** difficulty comes from contract precision and hidden
  boundary behavior, not repository size or noisy files.

## 9. Oracle design

| Case | Weight | Deterministic evidence |
|---|---:|---|
| `pricing_behavior` | 0.40 core | isolated evaluation of valid monthly, annual, coupon, and rounding cohorts |
| `validation_and_partial_success` | 0.25 core | isolated evaluation of duplicate, type, bound, plan, and coupon cohorts |
| `api_contract_compatibility` | 0.15 core | semantic OpenAPI checks plus exact preservation of `/quotes/single` |
| `verification_handoff` | 0.20 optional | notes record the feature decision, exact command/result, and a realistic residual risk without deployment claims |
| `source_and_execution_boundary` | gate | immutable inputs plus link, special-file, undeclared-path, and path-escape integrity only |

The three core blocks total 0.80. Equivalent variable names, control flow,
dictionary ordering, JSON formatting, and explanatory prose are accepted.
The behavior blocks directly cover `repo/src/quote_service/batch.py`; the
contract block covers `repo/api/openapi.json`; and the closure block covers
`repo/IMPLEMENTATION_NOTES.md`.
Source-audit failures lose behavior credit and unsupported deployment claims
lose handoff credit without forcing a blanket zero.

### Adjacent examples

- **Nearest valid:** preserve item order, mark both duplicate occurrences
  rejected, continue quoting unrelated items, and round each discount down in
  sequence.
- **Nearest wrong 1:** convert the batch to a dictionary keyed by request ID;
  this loses order and one duplicate occurrence.
- **Nearest wrong 2:** combine annual and coupon basis points before one rounding;
  many examples match, but boundary-cent totals are wrong.

## 10. Leakage, isolation, and safety review

- Tests, reference files, hidden behavior cases, and this design are excluded
  from the agent workspace.
- The candidate source is parsed before execution; imports, dunder access,
  dynamic execution, mutation outside local values, and external I/O are denied.
- The worker has a short CPU timeout and memory limit.
- Only the implementation and API file may be modified and one Markdown handoff
  added; all inputs and package exports are integrity-checked.
- The task is offline and contains no credentials or personal data.

## 11. Pilot plan

- Verify reference `1.0` and empty, untouched, and malformed `0.0`.
- Mutation probes separately remove duplicate handling, change expiry to
  exclusive, accept bool seats, change discount order, broaden an API array,
  and modify `/quotes/single`.
- Pilot at least two coding-oriented harnesses and compare tool calls, public
  test usage, self-correction, tokens, and wall time in addition to score.
- **Expected Gemma/OpenClaw failure modes:** stopping after public happy-path
  tests, treating booleans as integer seats, collapsing duplicate IDs into a
  map, combining discounts before rounding, or changing the old API contract.

## 12. Human validation status

- **Status:** `not_required` for membership under the project owner's current
  acceptance policy; deterministic engineering gates remain mandatory.
- **Current evidence level:** source-researched author review plus executable
  reference, empty, untouched, malformed, and adjacent-mutation checks.
- **Model outcomes used for membership:** false.
- **Canonical registry:** `docs/task_reviews/review_registry.csv`.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `pricing_behavior`.
- `validation_and_replay`: `validation_and_partial_success`, `api_contract_compatibility`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
