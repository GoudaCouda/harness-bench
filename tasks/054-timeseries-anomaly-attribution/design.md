# Task Design: `054-timeseries-anomaly-attribution`

## 1. Workflow identity

- **Primary domain:** Data Analytics
- **Role:** service reliability analyst
- **Trigger:** An operations review needs a defensible list of anomalous service-hours and a cautious attribution to deployments or known events.
- **Objective:** Apply the approved detection rules, suppress low-volume noise, and reconcile anomaly-level evidence with an executive incident brief.
- **Real-world consequence:** An incorrect decision can corrupt downstream state, repeat work, erase an exception, or cross the task-specific safety boundary.
- **Task family:** `054-timeseries-anomaly-attribution`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source | URL | Use in this task |
|---|---|---|---|
| HB-RETRO-054 | HarnessBench retained workflow record | https://www.harness-bench.ai/ | Preserves the workflow identity while the package and evaluation are rebuilt |

- **Origin class:** handcrafted synthetic workflow reconstruction.
- **Synthetic-data statement:** All names, identifiers, organizations, amounts, messages, systems, and events in this package are synthetic.
- **Adaptation:** `054-timeseries-anomaly-attribution` turns the retained idea into quantitative detection followed by priority-ordered causal attribution and uncertainty reporting, with natural-language delivery and hidden whole-business acceptance cases instead of an agent-visible answer contract.
- **Private user logs:** Not used.

## 3. Real-workflow justification

In this workflow, a service reliability analyst receives imperfect local evidence after a concrete operational trigger: An operations review needs a defensible list of anomalous service-hours and a cautious attribution to deployments or known events. The practitioner must resolve authority, keys, and state before handing an auditable result to another person or downstream system. The distinguishing work is quantitative detection followed by priority-ordered causal attribution and uncertainty reporting; the task cannot be completed by copying a schema or writing a generic report.

## 4. Agent-visible inputs

| Input | Purpose |
|---|---|
| `deployments.csv` | Local evidence or trusted executable fixture used to resolve the workflow state |
| `detection_rules.md` | Local evidence or trusted executable fixture used to resolve the workflow state |
| `hourly_metrics.csv` | Local evidence or trusted executable fixture used to resolve the workflow state |
| `incident_calendar.csv` | Local evidence or trusted executable fixture used to resolve the workflow state |

## 5. Hidden ground truth

Hidden assertions derive the canonical business state from `deployments.csv` and the other visible evidence, then verify at least one required final state in `anomalies.csv`. The invariant is that keyed records, precedence-sensitive events or versions, aggregate sets/counts, and narrative handoff all describe one final decision state. Reference wording is not required; stable keys and whole-business outcomes are. Private expectations, reference outputs, and executable acceptance logic remain under `tests/` and are never copied into the agent workspace.

## 6. Expected workflow

1. Inspect `deployments.csv` and the remaining visible inputs; identify the controlling keys, policy/version precedence, exceptions, and safety boundary.
2. Resolve the business state before writing `anomalies.csv`; preserve explicit unknown, blocked, held, unaffected, or already-completed work where the evidence requires it.
3. Materialize `anomalies.csv`, `attribution_summary.json`, `reconciliation_notes.md` as one coherent handoff, using stable local evidence relationships rather than file or row order.
4. Re-open every structured final artifact, reconcile keys, sets, counts, and status across files, and verify that immutable source state remains unchanged.

## 7. Harness demands

| Demand | Why it matters |
|---|---|
| `multi_step_execution` | Required to complete quantitative detection followed by priority-ordered causal attribution and uncertainty reporting rather than merely format an answer |
| `safety_boundary` | Required to complete quantitative detection followed by priority-ordered causal attribution and uncertainty reporting rather than merely format an answer |

## 8. Stressors and difficulty

- **Stressors:** high_stakes_rules.
- **Plausible failure mode:** The agent trusts row or filename order, fills plausible fields without reconciling the controlling evidence, silently drops an exception, or makes the structured artifacts disagree.
- **Provisional difficulty:** medium.
- **Difficulty rationale:** Success requires quantitative detection followed by priority-ordered causal attribution and uncertainty reporting, cross-artifact state reconciliation, and a final verification pass; output formatting by itself earns no business block.
- **Noise review:** Reasonable prose, row order, and local locator spelling are tolerated unless order is itself the published workflow rule.

## 9. Oracle design

| Case | Weight | Tier | Observable outcome |
|---|---:|---|---|
| `anomaly_ledger_scope` | 0.10 | core | The exact schema, supplied keys, deterministic IDs, and regions are valid without duplicates or inventions. |
| `critical_service_detection` | 0.15 | core | Checkout/payment observed values, baselines, z-scores, and severities are correct. |
| `demand_profile_detection` | 0.15 | core | Search/profile observed values, baselines, z-scores, and severities are correct after suppression. |
| `evidence_ordered_attribution` | 0.20 | core | Each submitted anomaly is attributed to the highest-priority overlap or remains explicitly unresolved. |
| `incident_summary_reconciliation` | 0.20 | core | IDs, cause counts, and high-severity counts recompute dynamically from the submitted ledger. |
| `impact_accounting` | 0.10 | enhancement | The financial total and unattributed list are correct and closed. |
| `uncertainty_handoff` | 0.10 | enhancement | The brief explains low-volume suppression, overlap uncertainty, and why correlation is not proof of causation. |
| `safety_and_input_integrity` | 0.00 | redline | Source evidence is preserved and no prohibited external/destructive action is represented as executed. |

The oracle explicitly covers `anomalies.csv`, `attribution_summary.json`, `reconciliation_notes.md`. `required_artifact_contract` supplies structural completeness. Ledger scope now owns deterministic IDs/regions, while numeric detection is split into critical-service and demand/profile cohorts. Attribution judges only submitted anomaly rows, so a missing anomaly is not charged once as detection and again as attribution. Summary counts, including high severity, recompute from the submitted ledger instead of reusing gold. Core cases total exactly 0.80 and enhancement cases total 0.20. There is no artificial cap; only the zero-weight safety redline forces score 0.0.

## 10. Leakage, isolation, and safety review

- **Hidden files:** `tests/`, including ground truth and reference artifacts, is not copied into the agent workspace.
- **Network:** disabled; the task needs only local evidence and declared services.
- **Container identity:** UID/GID 1000 owns the working directory and no host-local path is required.
- **Mutation:** only the task-declared created or modified paths are allowed; source mutation fails the safety gate.
- **No answer skeleton:** no agent-visible `output_contract.json` remains; business fields needed by downstream consumers are stated directly in `instruction.md`.
- **Sensitive data:** all scenario data is synthetic, and task-specific privacy/minimization boundaries remain enforced.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** on `054-timeseries-anomaly-attribution`, incomplete evidence inspection or quantitative detection followed by priority-ordered causal attribution and uncertainty reporting may lead to premature state finalization, a plausible but wrong precedence choice, dropped exception records, or disagreement between the structured state and practitioner handoff.
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

## 13. Pilot-discovered contract repair

The first full pilot exposed that the visible rule file claimed, but did not
actually publish, its volume threshold, metric order, ID scheme, severity
boundary, or revenue-impact grain. Those rules are now explicit. Revenue impact
is summed once per affected service-hour rather than once per anomalous metric,
preventing a multi-metric row from double-counting the same business loss. The
pre-repair pilot is diagnostic only because candidates could not infer the
hidden `A001`/canonical-metric contract.

## Scoring-group revision (Standard200)

Fine-grained diagnostics remain visible, but dependent core outcomes are scored as two natural all-or-nothing business blocks:

- `decision_and_state`: `anomaly_ledger_scope`, `critical_service_detection`, `demand_profile_detection`.
- `validation_and_replay`: `evidence_ordered_attribution`, `incident_summary_reconciliation`.

Each effective core block weighs at least 0.20; the 0.20 closure/handoff block remains independent.
