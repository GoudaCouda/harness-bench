# Task Design: `024-repo-architecture-map`

## 1. Workflow identity

- **Primary domain:** Software Engineering
- **Role:** a software engineering practitioner
- **Trigger:** You are given a small Python service repository at `$WORKSPACE/repo`.
- **Objective:** Repository Architecture Map
- **Real-world consequence:** An incorrect `architecture.md` would make the synthetic `Repository Architecture Map` handoff incomplete or operationally misleading.
- **Task family:** `024-repo-architecture-map`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source title | URL | Accessed | Use in this task |
|---|---|---|---|---|
| HB-RETRO-024 | Retrospective HarnessBench project record | https://www.harness-bench.ai/ | 2026-07-29 | Public project-level traceability only; no external workflow source was recorded in the retained package |

- **Origin class:** handcrafted_synthetic
- **Synthetic-data statement:** All fixture people, organizations, identifiers, amounts, events, and records are synthetic.
- **Adaptation:** Retrospective `024-repo-architecture-map` reconstruction: the checked-in package transforms `repo`, `repo/README.md`, `repo/minisvc/__init__.py`, `repo/minisvc/api/__init__.py`, `repo/minisvc/api/handlers.py`, `repo/minisvc/api/routes.py`, and 7 other entries listed in Section 4 into `architecture.md`, `doc_code_discrepancies.csv`, `module_map.json`, `onboarding_plan.md`, `risk_register.csv`, preserving the visible action `Create exactly these deliverables:` and `repo` as the first concrete state anchor; `module_map_content` as the first reference-path scoring anchor. The original external idea source was not recorded and is not inferred.
- **Private user logs:** Not used.

## 3. Real-workflow justification

`Repository Architecture Map` models a Software Engineering handoff in which the agent must reconcile `repo`, `repo/README.md`, `repo/minisvc/__init__.py`, `repo/minisvc/api/__init__.py`, `repo/minisvc/api/handlers.py`, `repo/minisvc/api/routes.py`, and 7 other entries listed in Section 4, apply the visible rule/state clauses `Include a recommended read order, local run/test commands, first debugging breakpoint or trace point, and two safe first changes.`; `Do not modify anything under '$WORKSPACE/repo'. Do not use internet access. Use only the files in the fixture repository.`; `'modules' must be an array of module objects with at least 'name', 'path', and 'purpose'.`, and leave `architecture.md`, `doc_code_discrepancies.csv`, `module_map.json`, `onboarding_plan.md`, `risk_register.csv` as an auditable final state. This description is reconstructed only from the checked-in prompt, fixtures/hooks, reference, and oracle; no unrecorded external workflow is claimed.

## 4. Agent-visible inputs

| Input | Purpose | Trust/precedence |
|---|---|---|
| `repo` | Agent-visible factual working material; explicitly named in the prompt | Prompt clause: Do not modify anything under '$WORKSPACE/repo'. Do not use internet access. Use only the files in the fixture repository. |
| `repo/README.md` | Agent-visible factual working material | Reconcile under the explicit prompt rules; no unstated source priority |
| `repo/minisvc/__init__.py` | Agent-visible factual working material | Reconcile under the explicit prompt rules; no unstated source priority |
| `repo/minisvc/api/__init__.py` | Agent-visible factual working material | Reconcile under the explicit prompt rules; no unstated source priority |
| `repo/minisvc/api/handlers.py` | Agent-visible factual working material | Reconcile under the explicit prompt rules; no unstated source priority |
| `repo/minisvc/api/routes.py` | Agent-visible factual working material | Reconcile under the explicit prompt rules; no unstated source priority |
| `repo/minisvc/audit.py` | Agent-visible factual working material | Reconcile under the explicit prompt rules; no unstated source priority |
| `repo/minisvc/cli.py` | Agent-visible factual working material | Reconcile under the explicit prompt rules; no unstated source priority |
| `repo/minisvc/config.py` | Agent-visible factual working material | Reconcile under the explicit prompt rules; no unstated source priority |
| `repo/minisvc/models.py` | Agent-visible factual working material | Reconcile under the explicit prompt rules; no unstated source priority |
| `repo/minisvc/storage/__init__.py` | Agent-visible factual working material | Reconcile under the explicit prompt rules; no unstated source priority |
| `repo/minisvc/storage/repo.py` | Agent-visible factual working material | Reconcile under the explicit prompt rules; no unstated source priority |
| `repo/pyproject.toml` | Agent-visible factual working material | Reconcile under the explicit prompt rules; no unstated source priority |

## 5. Hidden ground truth

- `024-repo-architecture-map` truth reconciliation binds concrete source state `repo`, `repo/README.md`, `repo/minisvc/__init__.py`, `repo/minisvc/api/__init__.py`, `repo/minisvc/api/handlers.py`, `repo/minisvc/api/routes.py`, and 7 other entries listed in Section 4 to required final state `architecture.md`, `doc_code_discrepancies.csv`, `module_map.json`, `onboarding_plan.md`, `risk_register.csv`; hidden materials are ground_truth.json, oracle_grade.py, reference.
- Visible key/state/precedence clauses retained by the oracle-facing design are: `Include a recommended read order, local run/test commands, first debugging breakpoint or trace point, and two safe first changes.`; `Do not modify anything under '$WORKSPACE/repo'. Do not use internet access. Use only the files in the fixture repository.`; `'modules' must be an array of module objects with at least 'name', 'path', and 'purpose'.`.
- `ground_truth.json` exposes maintainer keys `expected_modules`, `expected_entry_points`, `expected_edges`, `expected_typed_edges`, `expected_functions`, `allowed_edge_types`, `required_runtime_flow_terms`, `runtime_flow_sequences`, `architecture_concept_groups`, `architecture_flow_groups`, `discrepancy_required_columns`, `discrepancy_term_groups`, `discrepancy_expectations`, `risk_register_required_columns`, `risk_register_area_groups`, plus 2 more; exact values remain isolated from the agent workspace.
- Reference `architecture.md` has 71 non-empty line(s); its first state/content anchor is `# Draft reference`.
- Reference `doc_code_discrepancies.csv` has exact header `claim`, `doc_source`, `code_evidence`, `assessment`, `risk`, 4 data row(s); `claim` values begin `storage is readonly`, `storage has retry behavior`, `audit is console only`, `validation is complete`.
- Reference `module_map.json` has top-level keys `modules`, `entry_points`, `dependency_edges`, `key_functions`, `runtime_flows`; collection sizes `modules[7]`, `entry_points[2]`, `dependency_edges[15]`, `key_functions[8]`, `runtime_flows[2]`.
- Reference `onboarding_plan.md` has 73 non-empty line(s); its first state/content anchor is `# Draft reference`.
- Reference `risk_register.csv` has exact header `risk_id`, `area`, `evidence`, `impact`, `mitigation`, `owner_hint`, 4 data row(s); `risk_id` values begin `R1`, `R2`, `R3`, `R4`.
- The reference-path scoring ledger contains positive dimensions `module_map_content`, `architecture_markdown`, `doc_code_discrepancies`, `risk_register`, `onboarding_plan`, `fixture_integrity`; `required_artifact_contract` remains a zero-weight hard gate over every declared final path.

## 6. Expected workflow

1. Inventory the actual starting state in `repo`, `repo/README.md`, `repo/minisvc/__init__.py`, `repo/minisvc/api/__init__.py`, `repo/minisvc/api/handlers.py`, `repo/minisvc/api/routes.py`, and 7 other entries listed in Section 4; for `024-repo-architecture-map`, do not substitute an unstated network or host source.
2. Execute visible workflow clause 1 against `repo`: Create exactly these deliverables:.
3. Execute visible workflow clause 2 against `repo`: Include a 'runtime_flows' array describing at least the CLI startup flow and the HTTP create-order flow as ordered steps..
4. Execute visible workflow clause 3 against `repo`: Compare README/design notes against the actual implementation..
5. Execute visible workflow clause 4 against `repo`: Include a recommended read order, local run/test commands, first debugging breakpoint or trace point, and two safe first changes..
6. Materialize the complete declared state `architecture.md`, `doc_code_discrepancies.csv`, `module_map.json`, `onboarding_plan.md`, `risk_register.csv`; preserve the prompt-declared IDs, headers, schema keys, and in-place paths.
7. Cross-reconcile `architecture.md` with every other declared artifact and the source state `repo`; check shared identifiers, counts, decisions, and status transitions where present.
8. Run local parse/structure checks for `architecture.md`, `doc_code_discrepancies.csv`, `module_map.json`, `onboarding_plan.md`, `risk_register.csv` and stop only when `required_artifact_contract` would see all declarations as non-empty, valid, and workspace-local.

## 7. Harness demands

| Demand | Why a high-scoring solution requires it |
|---|---|
| `error_recovery` | The task includes an exception or requires recovery from a failed path. |
| `evidence_grounding` | High-scoring outputs must connect decisions to local task evidence. |
| `multi_step_execution` | The prompt requires several dependent operations and mutually consistent deliverables. |
| `output_contract` | The declared artifacts have a machine-checked structure. |
| `safety_boundary` | The workflow contains an explicit permission, integrity, privacy, or no-execution boundary. |
| `tool_selection` | The task exposes more than one possible operation and rewards the appropriate one. |

## 8. Stressors and difficulty

- **Stressors:** none
- **Plausible failure mode:** For `Repository Architecture Map`, the agent may create `architecture.md` but fail the declared `error_recovery` demand over `repo`, violate the rule/state clause `Include a recommended read order, local run/test commands, first debugging breakpoint or trace point, and two safe first changes.`, or leave another required deliverable inconsistent.
- **Provisional difficulty:** hard
- **Difficulty rationale:** The legacy package provisionally labels `Repository Architecture Map` as `hard`; completing `architecture.md` requires the declared `error_recovery` demand across 13 listed input(s), 5 required artifact(s), 6 positive reference-path oracle dimension(s), and 1 explicit conditional cap(s). The label remains provisional until multi-model, multi-harness pilot calibration.
- **Noise review:** The difficulty comes from workflow decisions and state, not hidden formatting tricks.

## 9. Oracle design

| Dimension | Weight | Observable evidence |
|---|---|---|
| `module_map_content` | returned-check raw=`0.35`; 35.00% of returned positive check metadata (consult aggregation row) | module_map_content; extracted from the reference oracle result |
| `architecture_markdown` | returned-check raw=`0.18`; 18.00% of returned positive check metadata (consult aggregation row) | architecture_markdown; extracted from the reference oracle result |
| `doc_code_discrepancies` | returned-check raw=`0.14`; 14.00% of returned positive check metadata (consult aggregation row) | doc_code_discrepancies; extracted from the reference oracle result |
| `risk_register` | returned-check raw=`0.13`; 13.00% of returned positive check metadata (consult aggregation row) | risk_register; extracted from the reference oracle result |
| `onboarding_plan` | returned-check raw=`0.08`; 8.00% of returned positive check metadata (consult aggregation row) | onboarding_plan; extracted from the reference oracle result |
| `fixture_integrity` | returned-check raw=`0.12`; 12.00% of returned positive check metadata (consult aggregation row) | fixture_integrity; extracted from the reference oracle result |
| `required_artifact_contract` | returned-check raw=`0` (non-rewarding gate/diagnostic) | Hard suite artifact gate over `architecture.md`, `doc_code_discrepancies.csv`, `module_map.json`, `onboarding_plan.md`, `risk_register.csv`; any missing, empty, malformed, escaping, or symlinked declaration forces score `0.0` |
| `aggregation_formula_01` | authoritative executable formula; not an extra check | `total = module_score * weights['module_map'] + md_score * weights['architecture_md'] + discrepancy_score * weights['doc_code_discrepancies'] + risk_score * weights['risk_register'] + onboarding_score * weights['onboarding_plan'] + integrity_score * weights['fixture_integrity']` |

- **Critical gates:** `required_artifact_contract` is a hard suite gate over `architecture.md`, `doc_code_discrepancies.csv`, `module_map.json`, `onboarding_plan.md`, `risk_register.csv`; any missing, empty, malformed, escaping, or symlinked declaration forces final score `0.0`.; Legacy oracle cap: if `risk_score < 0.7 or onboarding_score < 0.6`, final score is capped at `0.82`.
- **Partial-credit rationale:** The table mirrors the successful reference execution's 6 positive dimension(s), including each returned raw check weight, plus every returned zero-weight check. The 1 `aggregation_formula_*` row(s) are AST-extracted executable formulas and therefore distinguish display/check metadata weights from effective scoring coefficients. The conditional caps (1) and suite artifact gate override that formula where stated. No scoring behavior is changed by this retrospective document.
- **Order/format tolerance:** Structured rows are keyed and unordered unless ordering is itself part of the workflow.
- **Empty workspace:** must score `0.0`.
- **Untouched fixtures:** must score `0.0`.
- **Malformed artifacts:** must score `0.0`.
- **Reference workspace:** must score `1.0`.

## 10. Leakage, isolation, and safety review

- **Hidden files:** checked-in `ground_truth.json` (when present), `oracle_grade.py`, `reference/`, and this maintainer design are not copied to the agent workspace.
- **Network:** disabled; only task-declared local services may be used.
- **Input mutation:** prohibited; source/input integrity remains part of the checked-in oracle contract.
- **Destructive-action guard:** For `024-repo-architecture-map`, perform only the isolated workspace actions named in the prompt; never infer production execution, external communication, credentials, or network authority.
- **Sensitive-data review:** all scenario records are synthetic.
- **Host-path dependency:** none.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** Agent omits `architecture.md` while attempting `Repository Architecture Map`.; Agent misreads the `024-repo-architecture-map` rule/state anchor `Include a recommended read order, local run/test commands, first debugging breakpoint or trace point, and two safe first changes.` while reconciling `repo`.; Agent violates the prompt-stated safety boundary while producing `architecture.md`, `doc_code_discrepancies.csv`, `module_map.json`, `onboarding_plan.md`, `risk_register.csv`.
- **Expected strong-harness success band:** To be calibrated from fresh hash-bound pilots for the next additive release.
- **Ambiguity signal:** multiple competent agents make the same unsupported interpretation despite reading all visible evidence.
- **Environment/oracle failure signal:** reference failure, nondeterminism, unreadable artifacts, or semantically equivalent outputs scoring differently.
- **Revision rule:** For `024-repo-architecture-map`, retain this reconstruction until Human review checks the prompt/reference/oracle alignment; revise provenance or executable definitions only in a separately authorized change if ambiguity, leakage, brittle lexical grading, or an unnecessary harness demand is confirmed.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.

## 13. Semantic equivalence policy

- Concrete code evidence may be a repository filename, `module:function` identifier, or dotted Python module/method path. These are equivalent when they resolve to the same implementation site.
- Discrepancy findings are keyed by README claim, assessment, and concrete implementation evidence rather than one preferred filename spelling.
- Regular inflections such as “retry” and “retries” are equivalent when they identify the same documented claim.
- An HTTP flow may place the method before or after its route (for example, `POST /orders` or `/orders POST`) as long as the ordered call path is preserved.
- The concrete repository call may be written as `repo.save`,
  `OrderRepository.save`, or `OrderRepository.save()` when the exact real
  identifier occurs affirmatively in the ordered create-order flow. A
  different class or method, a reversed flow, or an explicit statement that
  `OrderRepository.save` is not called is not equivalent.
- Ordered runtime flows may name the same repository method as `repo.save`, `OrderRepository.save`, or the fully qualified `minisvc.storage.repo.OrderRepository.save`; optional call parentheses do not change that relationship. Reversing `create_order` → repository save → audit event still loses sequence credit.
- Dependency edge types are validated against the public enum. A correct map need not use every enum member when the repository does not contain every relationship type.
- Architecture prose is evaluated by the public concepts and runtime relationships. It need not repeat exact class or function tokens already supplied by a correct structured module map.
- Risk evidence may cite the concrete call site that exposes a risk; audit-risk evidence is not required to name `audit.py` when a precise handler call site establishes the missing persistence.
- The three README claims in this fixture are all contradicted by code, so no discrepancy row is required to use the otherwise valid `unsupported` assessment.
- This fixture has no checked-in test suite. The public local run/test requirement may therefore be met by a concrete smoke recipe that imports the real `minisvc.storage.repo` and `minisvc.api.handlers` modules, initializes the SQLite schema, invokes `create_order` or `get_order`, and observes or asserts the returned result. Schema initialization may be a direct, ordered `repo.init_schema()` call or an earlier real `python -m minisvc.cli` shell command bound to the same concrete database path used by the later repository.
- Onboarding prose may use equivalent headings such as “suggested first tasks” or “recommended first contributions.” A heading and its scoped section body may jointly express “safe changes,” including intervening adjectives such as “safe, high-impact changes.” Likewise, `__init__.py` may be described as a marker with no business logic without requiring the contiguous phrase “package marker.”
- Merely saying “run tests” is not executable verification. A recipe with no schema bootstrap, a CLI bootstrap for a different database path or one that follows the handler, a nonexistent module, missing or null handler inputs, an observation hidden in a dead branch, an assertion that is statically impossible, or no observation/assertion of the handler result is not equivalent.
- Polarity applies to onboarding classifications: “not a package marker” does
  not prove that `__init__.py` is a marker, and “no safe changes are
  available” does not satisfy the requirement to recommend safe first work.


## Refine70 formal outcome audit

This task now uses business-level all-or-nothing cases. The relocated legacy
oracle is retained only as a hidden fact library; none of its historical field
weights contribute to the formal score. The visible instruction is the full
agent contract, and no answer-shape file is exposed in the workspace.

- `system_map` (core): The module map and architecture describe the repository accurately
- `implementation_gaps` (core): Documentation-code discrepancies are identified
- `maintenance_handoff` (core): Risks and onboarding steps are actionable
- `map_consistency` (optional): Every structured module appears in the architecture narrative. Source-fixture preservation is enforced once by the integrity gate, not sold again as optional credit.

The core cases total 0.80 and optional handoff quality totals 0.20. Protected
source mutation and any task-specific redline are evaluated separately by a
zero-weight safety gate. Reference wording and byte layout are not score
requirements; alternate wording remains valid when the same structured facts
and business relationships hold.
