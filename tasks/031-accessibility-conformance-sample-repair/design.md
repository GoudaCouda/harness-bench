# Task Design: `031-accessibility-conformance-sample-repair`

## 1. Workflow identity

- **Domain:** Compliance / digital accessibility
- **Role:** accessibility specialist
- **Trigger:** a scoped offline portal review needs a defensible representative
  sample and repairs across a shared component and critical process state
- **Objective:** select the sample, repair semantic and keyboard failures,
  certify the changed files, and communicate limited evidence without a
  whole-site claim
- **Final state:** digest-bound offline sample report and reviewer handoff

## 2. Idea provenance

| Source ID | Source | URL | Accessed | Adaptation |
|---|---|---|---|---|
| W3C-CONFORMANCE | W3C WAI conformance evaluation overview | https://www.w3.org/WAI/test-evaluate/conformance/ | 2026-08-17 | Adapts scope definition, exploration, representative sampling, evaluation, and reporting |
| W3C-EM | WCAG-EM 2.0 Working Draft | https://www.w3.org/TR/wcag-em-2/ | 2026-08-17 | Adapts common/critical/distinct-state sampling and explicit evaluation limitations |

- **Origin class:** public workflow adaptation.
- **Synthetic-data statement:** the portal, pages, organization, products, and
  evaluation identity are synthetic.
- **Private user logs:** Not used.
- **Adaptation:** The W3C sampling workflow becomes a synthetic portal repair
  in which representative page-state selection, shared-component remediation,
  certification, and scope-limited reporting form one offline evidence chain.

## 3. Real-workflow justification

Accessibility evaluation is not equivalent to running a linter on one file.
The W3C workflow establishes scope, explores pages and technologies, chooses a
representative sample, evaluates it, and reports findings. This task requires a
sample that covers shared/common ownership, a complete critical process with an
error state, and representative structured content. The repair crosses a shared
navigation component, page HTML, form/error relations, and CSS focus behavior,
then binds the actual changed files to a local certification receipt.

## 4. Agent-visible inputs

| Input | Purpose | Precedence |
|---|---|---|
| `evaluation_scope.json` | standard, boundary, and sample rules | authoritative scope |
| `page_inventory.json` | page roles, processes, states, duplication | authoritative inventory |
| `remediation_policy.md` | acceptable repair semantics and safety limits | authoritative repair policy |
| `site/` | offline pages, shared component, and CSS | repairable snapshot at declared paths |
| `a11yctl.py` | sample/repair diagnostics and digest-bound certification | executable local feedback |

## 5. Hidden ground truth

- The representative set is derived from inventory roles rather than a hidden
  list: two common owners, two purchase states, and structured catalog content.
- Independent HTML parsing checks the shared button name, two meaningful image
  alternatives, form label, absence of positive tabindex, alert semantics,
  error target/description, and visible focus CSS.
- The receipt must bind the exact plan, report, and five permitted repairs.
- Reference files, evaluator, semantic rubric, and this design remain outside
  the agent workspace.
- The final state connects `evaluation_scope.json` to `sample_plan.json`,
  repaired `site/` files, `conformance_report.json`, `repair_receipt.json`, and
  `accessibility_handoff.md`; the sample keys and file digests must agree.

## 6. Expected workflow

1. Explore `evaluation_scope.json`, `page_inventory.json`, `site/`, and CSS state.
2. Record all common-owner and purchase-state keys plus catalog in
   `sample_plan.json`;
   exclude redundant/static templates.
3. Scan with `a11yctl.py`, interpret check-level state, and make minimal repairs
   without deleting controls or visible content.
4. Certify and verify twice so `conformance_report.json` and
   `repair_receipt.json` bind the same sample and repaired-file state.
5. Write `accessibility_handoff.md` with sample rationale, evidence limits, and
   remaining manual review work.

### Novelty review

| Nearest task | Similarity | Substantive differences |
|---|---|---|
| `052-local-html-dom-form-extract` | local HTML and form semantics | 031 modifies a multi-page site and shared component, selects a conformance sample, repairs accessibility relationships, and certifies evidence rather than holding an appointment |
| `087-catalog-schema-resume` | schema validation and resume | 031 reasons over DOM/CSS/user interaction states with no batch checkpoint or catalog ingestion |
| `150-public-records-redaction-release` | compliance review and release boundary | 031 produces repaired web assets and a sample-limited report; it has no record responsiveness, redaction, exemption, or disclosure package |

The role, trigger, tool chain, state transition, final artifacts, and primary
failure modes all differ, including tool/state/final-state differences.

## 7. Harness demands

| Demand | Why it is necessary |
|---|---|
| `multi_step_execution` | inventory, sampling, scan, cross-file repair, certification, verification, and handoff depend on one another |
| `evidence_grounding` | page roles and distinct states determine sample membership; policy determines repairs |
| `state_management` | shared component effects and a repeated digest-bound certification must remain consistent |
| `error_recovery` | initial scan fails seven checks and guides repair |
| `verification_behavior` | report and receipt must bind the sample and five final files |
| `safety_boundary` | unsampled pages, visible functionality, and whole-site/public conformance claims are protected |

## 8. Stressors and difficulty

- **Stressors:** representative rather than exhaustive sampling; shared component
  ownership; critical-process error state; accessible-name placement; natural
  tab order; multi-node error relationships; CSS focus regression; scope claim.
- **Difficulty:** hard. A solver can make scan output superficially quiet by
  deleting controls, hiding content, sampling only easy pages, adding positive
  tabindex values, or claiming whole-site success. The oracle separates sample,
  semantic repairs, focus/certification, prose, and safety so these shortcuts do
  not collapse into one formatting check.
- **Plausible failure mode:** sample only easy pages or silence checks by
  deleting controls, leaving an apparently clean scan without representative
  coverage or preserved functionality.
- **Difficulty rationale:** inventory roles, DOM relationships, shared
  components, CSS state, file digests, and scope wording must close together.

## 9. Oracle design

| Case | Weight | Evidence |
|---|---:|---|
| `representative_sample` | 0.25 core | inventory-derived closed page set and report mapping |
| `semantic_accessibility_repairs` | 0.30 core | independent DOM relationships across navigation, catalog, and two checkout states |
| `visible_focus_and_receipt` | 0.25 core | CSS focus rule plus plan/report/five-file SHA-256 receipt |
| `accessibility_handoff` | 0.20 optional | deterministic facts with bounded semantic fallback for equivalent prose only |
| `safety_and_input_integrity` | gate | immutable scope/unsampled pages/controller, allowed output tree, no live/public claim |

Core totals 0.80 and the optional handoff creates a natural 1.00 tier. LLM
fallback cannot rescue page selection, DOM/CSS state, digests, artifacts, or
safety.

The oracle explicitly treats `sample_plan.json`, `conformance_report.json`,
`repair_receipt.json`, and `accessibility_handoff.md` as parts of their
business-level sample, repair, certification, and communication cases.

### Adjacent examples

- **Nearest valid:** sample both common owners, both checkout states, and
  catalog; repair all relationships and focus; report sample-only evidence.
- **Nearest wrong 1:** omit `checkout-error`. Shared and ordinary checkout
  repairs can pass, but representative-sample coverage fails.
- **Nearest wrong 2:** fix error announcement but keep the summary link pointed
  at a nonexistent ID. Most semantic work passes, but the error relationship
  remains incomplete.

## 10. Leakage, isolation, and safety review

- The task is offline and contains no real users, credentials, analytics, or
  public endpoint. Network access is disabled.
- The controller derives sample membership from public inventory roles and
  derives repair checks from current HTML/CSS; it does not contain a final
  output template or reference artifact.
- Only five declared site files can change. Scope, inventory, policy,
  controller, unsampled pages, visible text/functionality, and output tree are
  independently protected.
- Symlinks, malformed/oversized artifacts, extra answer files, content-removal
  shortcuts, deployment claims, and unqualified live/whole-site conformance
  claims fail or lose the relevant business case.

## 11. Pilot plan

- Static: reference 1.0; empty/untouched/malformed 0.0; core-only 0.8; omitted
  state, redundant sample, empty alt, aria on wrong node, positive-tabindex
  renumber, broken error target, invisible focus, tampered receipt, content
  deletion, extra-file, and unsafe-claim adversarials.
- Real: fresh Gemma 4 31B + OpenClaw pilot; inspect inventory exploration,
  failed scan use, repair locality, repeated certification, and whether visible
  diagnostics make the task mechanically trivial.
- Any definition change invalidates the run and requires a fresh identity.
- **Expected Gemma/OpenClaw failure modes:** omit a distinct checkout state,
  patch the wrong DOM node, use positive tabindex, skip repeated certification,
  or overstate the sample as whole-site conformance.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.
