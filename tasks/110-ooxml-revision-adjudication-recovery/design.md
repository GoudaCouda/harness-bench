# Task Design: `110-ooxml-revision-adjudication-recovery`

## 1. Workflow identity

- **Primary domain:** office publication systems and controlled document
  operations.
- **Role:** publication-systems editor recovering an interrupted internal
  bulletin revision.
- **Trigger:** one contact decision committed to an append-only SQLite journal
  before the worker crashed, the DOCX checkpoint is missing, and a later signed
  legal correction arrived with dependent and lower-authority revisions.
- **Objective:** adjudicate the current revision graph, resolve a real tracked
  WordprocessingML document, reconcile the durable prefix exactly once, and
  stage a hash-bound internal-approval package.
- **Real-world consequence:** replaying the committed contact decision can
  duplicate history; accepting stale, dependency-invalid, retention-deleting,
  or publication language can put an incorrect or unauthorized bulletin into
  review.
- **Task family:** `office-ooxml-revision-recovery`.
- **Variant:** interrupted journal plus late signed correction.

## 2. Idea provenance

| Source ID | Official source | Accessed | Adapted mechanic |
|---|---|---|---|
| OP-01 | https://help.libreoffice.org/latest/en-GB/text/shared/guide/redlining_accept.html | 2026-08-19 | Reviewers accept/reject individual tracked changes, retain a decision history, and confirm that no hidden unresolved revisions remain. |
| OOXML-TRACKED-REVISIONS | https://learn.microsoft.com/en-us/office/open-xml/word/how-to-accept-all-revisions-in-a-word-processing-document | 2026-08-19 | Word revisions are represented as actual insertion/deletion elements that must be resolved in package content rather than copied into a report. |
| OOXML-OPC | https://ecma-international.org/publications-and-standards/standards/ecma-376/ | 2026-08-19 | A DOCX is an Open Packaging Conventions ZIP with content types, relationships, document parts, styles, headers, footers, and comments that must remain coherent. |
| SQLITE-TRANSACTIONS | https://www.sqlite.org/lang_transaction.html | 2026-08-19 | A durable transaction/journal can survive a process interruption even when a later materialized-file checkpoint is missing. |

- **Origin class:** public-workflow adaptation of the retained tracked-change
  adjudication idea.
- **Adaptation:** the old Markdown/CSV answer package is replaced by an actual
  OOXML revision graph, a SQLite durable journal, a missing checkpoint,
  plan-driven preview/apply/verify operations, a late signed supersession, and
  idempotent replay.
- **Synthetic-data statement:** all document text, revisions, identities,
  credentials, timestamps, transactions, and organizations are synthetic.
- **Private user logs:** not used.

## 3. Real-workflow justification

Controlled publication work is not finished when an editor writes a decision
table. The authoritative revision must be selected, its credential and scope
must be checked, rejected parents must invalidate dependent changes, and the
decision must be materialized in the actual document package without damaging
unaffected Office parts. Here the recovery operator must also reconcile a
durable journal entry that is newer than the document checkpoint. A naive
replay creates duplicate history, while a naive DOCX rewrite can discard
styles, bookmarks, comments, relationships, header, or footer. The terminal
workflow therefore joins document-package manipulation, transactional state,
diagnostic feedback, verification, and a publication safety boundary.

## 4. Agent-visible inputs

| Input | Authority and purpose |
|---|---|
| `authority_policy.md` | Event selection, authority roles, dependency ordering, append-only recovery, package preservation, and internal-only boundary. |
| `revision_manifest.json` | Out-of-order current and stale events, proposal classes, credentials, target bookmarks, OOXML revision IDs, and old/new text. |
| `revision_dependencies.csv` | Required accepted-parent edges for the revision graph. |
| `signature_registry.json` | Frozen verification and role state for legal, directory-owner, and release-coordinator credentials. |
| `bulletin_working.docx` | Real tracked-change Office Open XML source with ten revision pairs and preserved package parts. |
| `review_state.db` | Mutable interrupted workflow state, one durable CH-05 journal row, and the prior TX-04 transaction. |
| `bulletinctl.py` | Protected inspect, preview, apply, and verify interface. |

No file declares the final action map. The manifest supplies competing events
and proposal evidence; policy, credentials, dependencies, durable state, and
the actual OOXML package jointly determine the plan.

## 5. Hidden ground truth

The evaluator never imports or executes `bulletinctl.py`. It independently
parses the manifest, credential registry, and dependency CSV; selects the
highest-sequence current event; applies published role and dependency rules;
and derives the deterministic topological order. It opens both DOCX ZIPs,
parses `word/document.xml`, independently renders the accepted or rejected text
for every bookmarked revision, requires no remaining `w:ins`, `w:del`, or move
markup, and compares every non-document package part byte for byte.

It opens candidate SQLite read-only, verifies the exact seed journal and
transaction prefixes, one decision per change, append order, proposal hashes,
one recovery transaction, counts, phase, document/plan hashes, and the
non-publication state. Receipt, source-bundle, database logical-state, prefix,
DOCX, normalized-plan, and handoff hashes are recomputed independently.
Equivalent JSON key order, action order, evidence order, whitespace, and ZIP
serialization are accepted when the normalized semantics and package
invariants match.

The concrete required final workspace state is a semantically correct
`adjudication_plan.json`, a revision-free `approved_bulletin.docx`, a recovered
and internally staged `review_state.db`, a matching
`verification_receipt.json`, and an `editorial_handoff.md` that preserves the
publication boundary.

## 6. Expected workflow

1. Read authority, dependency, credential, and revision evidence; run
   `inspect` to observe the ten tracked pairs and the interrupted TX-04 state.
2. Select one current event per change and construct the deterministic
   dependency order without treating row order as authority.
3. Write an evidenced action plan, including the already durable CH-05
   decision and the internal-approval boundary.
4. Run `preview`; use event, authority, dependency, evidence, or package
   diagnostics to repair the plan without mutating state.
5. Run `apply`; inspect the clean DOCX and SQLite state. The controller resolves
   OOXML, reconciles CH-05, appends nine decisions, and records one TX-05.
6. Write the editorial handoff, verify twice, then reapply the same normalized
   plan and confirm byte-stable idempotence.

The controller validates a candidate-authored plan. It deliberately has no
command that generates the action map or chooses revisions for the agent.

## 7. Harness demands

| Demand | Why it matters |
|---|---|
| `multi_step_execution` | Inspection, plan authoring, preview feedback, transactional apply, document inspection, handoff, verify, and replay depend on prior observations. |
| `evidence_grounding` | Current event, authority class, credential role, dependency outcome, and prior durable decision come from different sources. |
| `state_management` | Revision 4 plus an incomplete TX-04 checkpoint becomes one revision-5 internal stage with preserved append-only history. |
| `error_recovery` | The package starts between durable journal commit and document checkpoint; recovery must reconcile instead of duplicate. |
| `verification_behavior` | XML, OPC parts, SQLite invariants, hashes, receipt, and second-run stability all close independently. |
| `safety_boundary` | Public export is a rejected revision and external publication/approval remains prohibited. |

## 8. Stressors and difficulty

- **Stressors:** out-of-order events, two current signed events plus a later
  correction, stale credentials, authority classes, a dependency DAG, a
  journal/document mismatch, append-only recovery, real OOXML XML/ZIP state,
  non-document part preservation, and normalized-plan idempotence.
- **Coupled burdens:** the selected event changes the document text; parent
  disposition changes child state; a prior journal entry changes append
  behavior; document bytes bind the database transaction and receipt.
- **Adjacent wrong solution 1:** choose older signed EV-107 instead of later
  EV-114. The plan, final text, journal event, plan digest, and receipt cannot
  all close.
- **Adjacent wrong solution 2:** reject CH-03 but independently accept/reject
  CH-04 instead of dependency-invalidating it. The graph semantics, final
  document, journal, counts, and receipt diverge.
- **Other plausible failures:** append CH-05 again, edit SQLite or XML directly,
  discard a comment/header/style, keep unresolved revisions, trust a stale
  directory credential, or accept public-portal language.
- **Plausible failure mode:** the agent selects the right text but replays
  CH-05, or closes the journal correctly while flattening the DOCX and losing
  package parts; either incomplete half cannot satisfy the coupled state.
- **Difficulty rationale:** difficulty comes from causal state and real package
  operations rather than input volume, installation, or hidden wording.
- **Spec feasibility:** complete deterministic path using Python standard
  library, SQLite, ZIP/XML, and local files; no network, credentials, Docker,
  or specialist Office installation is required.

### Nearest-task novelty review

| Dimension | 110 OOXML recovery | 004 office DOCX | 017 revision plan | 020/065 late evidence | retired 111 idea |
|---|---|---|---|---|---|
| workflow identity | recover interrupted controlled-document transaction | generate finance memo | revise Markdown under legal comments | repair JSON launch/rollout state | merge late Markdown correction |
| primary object | tracked DOCX plus SQLite journal | template DOCX plus rollup | Markdown draft | queue/plan JSON | Markdown clean copy |
| initial fault | durable journal newer than document checkpoint | dirty close inputs | unsupported language | stale scoped evidence | late correction |
| tool chain | inspect → plan → preview → OOXML apply → verify/replay | calculate and author document | edit files | controller verify | no tool |
| state transition | interrupted revision 4 → staged revision 5 | inputs → report | draft → review draft | stale state → repaired state | v1 file → v2 file |
| final artifacts | real resolved OOXML, mutated DB, receipt | generated DOCX/CSV | Markdown/handoff | operational JSON/handoff | CSV/JSON/Markdown |
| defining failure | duplicate durable decision or corrupt OPC package | wrong financial treatment | legal regression | wrong scope/queue propagation | authority precedence only |

This task absorbs the useful late-signed-correction mechanic from 111 instead
of retaining a second static document-merging task.

## 9. Oracle design

| Case | Weight | Tier | Observable outcome |
|---|---:|---|---|
| `authoritative_revision_and_dependency_state` | 0.27 | core | Current-event selection, credentialed authority, deterministic order, and dependency dispositions are independently correct. |
| `ooxml_resolution_and_package_integrity` | 0.27 | core | The final WordprocessingML text and revision closure are correct while bookmarks, styles, comments, header/footer, relationships, and other OPC parts remain intact. |
| `transaction_recovery_and_idempotence` | 0.26 | core | The exact durable prefix remains, CH-05 is not duplicated, one TX-05 closes every action, and the core receipt binds final plan/document/database state. |
| `plan_and_evidence_quality` | 0.06 | enhancement | Every action has sufficient safe local evidence and normalized portable structure. |
| `editorial_handoff` | 0.06 | bounded semantic enhancement | Authority, recovery, package, replay, verification, and internal-only handoff are coherent; structured errors cannot be compensated. |
| `durable_stage_closure` | 0.08 | enhancement | The exact source bundle, normalized plan, document, database, prefix, checks, and handoff are bound by a stable receipt. |
| `source_controller_and_publication_safety` | 0.00 | redline | Protected source/controller mutation, unsafe required artifacts/evidence, publication state/text, or affirmative external-action claim forces zero. |

The three core cases total exactly 0.80. Positive weights total 1.00. The
handoff fallback is bounded to 0.06 and cannot rescue any structured core. The
shared `required_artifact_contract` still enforces declared regular artifacts;
task-local safety additionally rejects symlinked required files and protected
mutation.

Artifact ownership is non-overlapping where practical: the first core owns
`adjudication_plan.json`; the second owns `approved_bulletin.docx`; the third
owns `review_state.db` and core receipt hashes; evidence quality owns plan
locators; narrative owns `editorial_handoff.md`; closure owns full receipt
binding in `verification_receipt.json`. Contract tests cover reference 1,
empty 0, untouched 0, malformed 0,
source/controller tamper, replay stability, alternative serialization, both
adjacent wrong solutions, failed preview non-mutation, stale receipt, and a
duplicate recovery transaction.

## 10. Leakage, isolation, and safety review

- Hidden evaluator, generator, reference artifacts, and semantic rubric remain
  under `tests/` and are not copied into the agent workspace.
- The visible controller derives validation from public rules and candidate
  actions; `inspect` does not print an expected action map and there is no
  auto-plan command.
- `preview` transforms only in memory. `apply` accepts bounded JSON, executes no
  candidate code, writes a separate DOCX through a temporary file, and uses
  parameterized SQLite updates.
- The evaluator uses its own XML, ZIP, graph, credential, database, digest, and
  plan-normalization implementation; it never imports or calls the controller.
- The source DOCX, policy, manifest, dependencies, registry, and controller are
  protected. Only `review_state.db` may be modified.
- The output must remain a macro-free local DOCX with the public-portal proposal
  rejected and `external_published = 0`.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** choose EV-107, treat current as
  automatically accepted, miss a credential role, adjudicate an invalidated
  child independently, duplicate CH-05, stop after preview, hand-edit outputs,
  omit replay, or conflate internal staging with publication.
- Require deterministic reference 1.00, empty/untouched/malformed 0.00, both
  protected-source gates, two neighboring incorrect plans below threshold,
  alternate serialization 1.00, stale receipt 0.92, and byte-stable replay.
- Run Ruff, 12-section design validation, public-leakage validation, targeted
  contract tests, task-suite validation, oracle-quality cases, permission
  normalization, and a frozen package digest before pilot identity creation.
- After task-only static approval, run real Gemma 4 31B plus OpenClaw against a
  frozen package and model-service identity. Audit actual inspect/preview/apply,
  OOXML/SQLite observations, diagnostic recovery, replay, receipt, safety, and
  score attribution.
- Any package repair after the trajectory receives a new package and run
  identity. Candidate outcome never controls task-only selection.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.
