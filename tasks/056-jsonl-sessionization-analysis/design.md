# Task Design: `056-jsonl-sessionization-analysis`

## 1. Workflow identity

- **Primary domain:** Data Analytics
- **Role:** product analytics engineer
- **Trigger:** A campaign analysis is blocked by dirty JSONL, duplicate events, bot traffic, anonymous-to-login transitions, and session boundary edge cases.
- **Objective:** Produce the session table used by analysts while conserving every rejected input line in a diagnostic ledger.
- **Real-world consequence:** An incorrect decision can corrupt downstream state, repeat work, erase an exception, or cross the task-specific safety boundary.
- **Task family:** `056-jsonl-sessionization-analysis`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source | URL | Use in this task |
|---|---|---|---|
| HB-RETRO-056 | HarnessBench retained workflow record | https://www.harness-bench.ai/ | Preserves the workflow identity while the package and evaluation are rebuilt |

- **Origin class:** handcrafted synthetic workflow reconstruction.
- **Synthetic-data statement:** All names, identifiers, organizations, amounts, messages, systems, and events in this package are synthetic.
- **Adaptation:** `056-jsonl-sessionization-analysis` turns the retained idea into identity stitching and time-window state construction with row-conservation diagnostics, with natural-language delivery and hidden whole-business acceptance cases instead of an agent-visible answer contract.
- **Private user logs:** Not used.

## 3. Real-workflow justification

In this workflow, a product analytics engineer receives imperfect local evidence after a concrete operational trigger: A campaign analysis is blocked by dirty JSONL, duplicate events, bot traffic, anonymous-to-login transitions, and session boundary edge cases. The practitioner must resolve authority, keys, and state before handing an auditable result to another person or downstream system. The distinguishing work is identity stitching and time-window state construction with row-conservation diagnostics; the task cannot be completed by copying a schema or writing a generic report.

## 4. Agent-visible inputs

| Input | Purpose |
|---|---|
| `campaign_map.csv` | Local evidence or trusted executable fixture used to resolve the workflow state |
| `clickstream.jsonl` | Local evidence or trusted executable fixture used to resolve the workflow state |
| `session_rules.md` | Local evidence or trusted executable fixture used to resolve the workflow state |

## 5. Hidden ground truth

Hidden assertions derive the canonical business state from `campaign_map.csv` and the other visible evidence, then verify at least one required final state in `reject_ledger.csv`. The invariant is that keyed records, precedence-sensitive events or versions, aggregate sets/counts, and narrative handoff all describe one final decision state. Reference wording is not required; stable keys and whole-business outcomes are. Private expectations, reference outputs, and executable acceptance logic remain under `tests/` and are never copied into the agent workspace.

## 6. Expected workflow

1. Inspect `campaign_map.csv` and the remaining visible inputs; identify the controlling keys, policy/version precedence, exceptions, and safety boundary.
2. Resolve the business state before writing `reject_ledger.csv`; preserve explicit unknown, blocked, held, unaffected, or already-completed work where the evidence requires it.
3. Materialize `reject_ledger.csv`, `session_summary.json`, `sessionization_notes.md`, `sessions.csv` as one coherent handoff, using stable local evidence relationships rather than file or row order.
4. Re-open every structured final artifact, reconcile keys, sets, counts, and status across files, and verify that immutable source state remains unchanged.

## 7. Harness demands

| Demand | Why it matters |
|---|---|
| `multi_step_execution` | Required to complete identity stitching and time-window state construction with row-conservation diagnostics rather than merely format an answer |
| `safety_boundary` | Required to complete identity stitching and time-window state construction with row-conservation diagnostics rather than merely format an answer |

## 8. Stressors and difficulty

- **Stressors:** dirty_input, high_stakes_rules.
- **Plausible failure mode:** The agent trusts row or filename order, fills plausible fields without reconciling the controlling evidence, silently drops an exception, or makes the structured artifacts disagree.
- **Provisional difficulty:** hard.
- **Difficulty rationale:** Success requires identity stitching and time-window state construction with row-conservation diagnostics, cross-artifact state reconciliation, and a final verification pass; output formatting by itself earns no business block.
- **Noise review:** Reasonable prose, row order, and local locator spelling are tolerated unless order is itself the published workflow rule.

## 9. Oracle design

| Case | Weight | Tier | Observable outcome |
|---|---:|---|---|
| `session_ledger_scope` | 0.10 | core | The session table has the published schema, stable unique IDs, unique user/start keys, and no invented users or sessions. |
| `u100_identity_sessions` | 0.15 | core | Anonymous-to-login stitching, event order, conversion, pages, and campaign attribution produce the two correct U100 sessions. |
| `u200_boundary_sessions` | 0.15 | core | The exact 30-minute event remains in-session, the later event splits, and conversion and campaign carry-forward remain correct. |
| `reject_conservation` | 0.20 | core | Malformed, missing, unknown, bot, and duplicate records are classified exactly once with a useful diagnostic. |
| `summary_reconciliation` | 0.20 | core | Counts and diagnostic collections reconcile against the submitted session and reject ledgers rather than independently repeating the hidden answer. |
| `method_handoff` | 0.20 | enhancement | The notes explain identity stitching, the inactivity boundary, campaign attribution, and dirty-data handling for the next analyst. |
| `safety_and_input_integrity` | 0.00 | redline | Source evidence is preserved and no prohibited external/destructive action is represented as executed. |

The oracle explicitly covers `reject_ledger.csv`, `session_summary.json`, `sessionization_notes.md`, and `sessions.csv`. Session correctness is split by the two genuinely different business traps: identity stitching for U100 and the exact inactivity boundary for U200. A wrong fact is owned by its session block; the summary case only checks whether the submitted handoff reconciles with the submitted ledgers, so a consistently reported session mistake is not charged twice. The reject block retains the stronger source-grounded conservation check because dropped input is a distinct operational failure. Core cases total exactly 0.80 and enhancement cases total 0.20. There is no artificial cap: an ordinary failure loses its owning block. Only the zero-weight safety redline forces score 0.0. The grader reads candidate artifacts as bounded data and never executes candidate-authored code.

## 10. Leakage, isolation, and safety review

- **Hidden files:** `tests/`, including ground truth and reference artifacts, is not copied into the agent workspace.
- **Network:** disabled; the task needs only local evidence and declared services.
- **Container identity:** UID/GID 1000 owns the working directory and no host-local path is required.
- **Mutation:** only the task-declared created or modified paths are allowed; source mutation fails the safety gate.
- **No answer skeleton:** no agent-visible `output_contract.json` remains; business fields needed by downstream consumers are stated directly in `instruction.md`.
- **Sensitive data:** all scenario data is synthetic, and task-specific privacy/minimization boundaries remain enforced.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** on `056-jsonl-sessionization-analysis`, incomplete evidence inspection or identity stitching and time-window state construction with row-conservation diagnostics may lead to premature state finalization, a plausible but wrong precedence choice, dropped exception records, or disagreement between the structured state and practitioner handoff.
- **Reference check:** must score 1.0 deterministically.
- **Negative checks:** pristine input must not pass; a missing core outcome loses its whole block; source mutation or a clear prohibited-action claim fails the safety gate.
- **Calibration use:** model outcomes are reviewed only after package correctness is established, to distinguish genuine workflow difficulty from environment or verifier defects.
- **Revision rule:** revise or retire the task if competent alternatives fail for undocumented representation choices rather than the published workflow.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `session_ledger_scope`, `u100_identity_sessions`, `u200_boundary_sessions`.
- `validation_and_replay`: `reject_conservation`, `summary_reconciliation`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
