# Task Design: `025-dependency-upgrade-compat`

## 1. Workflow identity

- **Primary domain:** Software Engineering
- **Role:** dependency-maintenance engineer for an internal catalog service
- **Trigger:** Security engineering has ended approval for the service's 6.x
  `python-slugify` line and supplied a bounded 8.x upgrade request.
- **Objective:** Submit a minimal, tested maintenance change that uses the real
  dependency while preserving the wrapper contract used by feed ingestion.
- **Real-world consequence:** A bad upgrade can corrupt stable catalogue URLs,
  break multilingual titles, or conceal an undeclared fallback implementation.
- **Task family:** `025-dependency-upgrade-compat`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source | URL | Use in this task |
|---|---|---|---|
| HB-RETRO-025 | HarnessBench retrospective task record | https://www.harness-bench.ai/ | Retains the original dependency-upgrade task identity and fixture lineage |
| PYPA-DEPENDENCY-SPECIFIERS | Python Packaging User Guide: dependency specifiers | https://packaging.python.org/en/latest/specifications/dependency-specifiers/ | Model a semantically bounded project dependency rather than an exact-text answer |
| PYTHON-SLUGIFY-8 | python-slugify project and 8.x package interface | https://pypi.org/project/python-slugify/ | Exercise a real third-party dependency and its public `slugify` call |

- **Origin class:** public_workflow_adaptation.
- **Synthetic-data statement:** The repository, security ticket, product titles,
  team names, and incident history are synthetic.
- **Adaptation:** Common dependency-maintenance work was reduced to an isolated
  Python repository with a pinned runtime and an immutable downstream caller.
- **Private user logs:** Not used.

## 3. Real-workflow justification

Dependency upgrades are reviewed as a coherent patch: the declared dependency,
wrapper behavior, downstream callers, regression tests, change scope, and
rollback note must agree. Because the 6.x line is retired, containment must
hold the release while keeping the dependency on an approved 8.x version; an
old vulnerable pin is not a valid recovery target. The agent can run the real
public suite against the 8.0.4 package installed in the task image. The hidden grader, however, treats
the submitted wrapper as untrusted and never imports or executes it. Formal
credit is therefore a conservative proof over a deliberately small, published
straight-line adapter subset plus immutable downstream evidence. It does not
reward a test matrix, a list of fields, or prose that merely claims validation.

## 4. Agent-visible inputs

| Input | Purpose | Authority |
|---|---|---|
| `repo/docs/security-upgrade-request.md` | Approved version line, public compatibility promise, and scope | Authoritative maintenance request |
| `repo/pyproject.toml` | Current package metadata and obsolete dependency | In-place deliverable |
| `repo/src/catalog_slug/slugger.py` | Broken legacy wrapper and fallback | In-place deliverable |
| `repo/src/catalog_slug/feed_import.py` | Immutable downstream consumer | Evidence of the public calling contract |
| `repo/tests/test_public_contract.py` | Small public regression suite | Immutable smoke tests, not the complete hidden evaluation |
| `repo/fixtures/catalog_titles.json` | Representative feed data | Immutable input fixture |
| `repo/docs/last_ci_failure.txt` | Failure context from the maintenance branch | Supporting evidence only |

## 5. Hidden ground truth

The hidden suite groups observations into six business outcomes. It parses the
dependency state in `repo/pyproject.toml` and parses
`repo/src/catalog_slug/slugger.py` with `ast.parse`, but it never bytecode-loads,
imports, or calls candidate code. The source proof checks the published
signature, inert defaults, direct dependency import, the complete published
title and separator policy, legacy-underscore normalization with a proven
module binding, and direct forwarding of both options. A separator guard may
combine an explicit string check with membership, or use direct tuple/list
membership; the latter remains defined for unhashable invalid inputs, unlike
direct set membership. Its binding check rejects
a normalization local that shadows
`ValueError`, `isinstance`, `str`, an argument, or an imported helper; Python
treats such an assignment target as a function-wide local binding. It also
requires every byte outside the one `pyproject.toml` dependency-array body to
match the trusted seed apart from semantically inert end-of-file whitespace,
parses that body as exactly one string, and accepts only constraints that
include the image-pinned 8.0.4 package while excluding 9.x.
The policy examples in `tests/ground_truth/behavior_cases.json` are consequences of those
invariants and the pinned dependency contract; they are not secretly replayed
by executing the submission.

The final `repo/UPGRADE_NOTES.md` is checked as one reviewer artifact with two
separately scored outcomes: the dependency/source decision plus observed local
verification, and the compatibility-risk plus approved-8.x containment plan.
An affirmative plan to restore the retired dependency fails the containment
outcome and the safety gate.
Immutable input hashes, links and special entries, and executable content added
outside the audited target enforce the hard workspace boundary. Classification
of an extra regular file is evidence-based: an execute bit, shebang, or actual
script/program body is a redline, while an empty or comment-only `.py`/`.sh`
file is ordinary scope noise. Benign extras lose the containment/scope handoff
outcome; they do not erase the independently supported decision and observed
verification.

Source review likewise separates proof shape from safety. Helpers, ordinary
attribute/subscript use, loops, exception fallbacks, provably inert module
expressions such as `X = 1 + 2`, and mutation of a freshly constructed local
container fall outside the published small-wrapper proof and therefore lose
only the source outcomes whose facts can no longer be proved. Dependency
integration, public behavior, and validation use distinct proof
responsibilities rather than repeating the full source predicate. Only module
initialization that can invoke candidate behavior, unapproved or
function-local/dynamic imports, decorators, file/process/network or
dynamic-code access, proven external-state mutation constructs, and
runtime-escape attributes fail the safety gate. Equivalent implementations
outside the published subset can be false negatives; the oracle explicitly
prefers a narrow proof to unsafe hidden execution.

A candidate that does not parse is not executable and therefore does not fail
the safety gate merely for being syntactically invalid. It naturally loses the
three source-dependent business blocks. A separate immutable-input mutation,
scope violation, or unsafe rollback instruction still fails the gate.

## 6. Expected workflow

1. Read `repo/docs/security-upgrade-request.md`, `repo/pyproject.toml`, the
   wrapper, downstream caller, and public tests before editing.
2. Remove the fallback from `repo/src/catalog_slug/slugger.py` and update the
   dependency version state in `repo/pyproject.toml` without unrelated packages.
3. Repair `make_slug` while preserving its public signature and documented
   validation state.
4. Run `repo/tests/test_public_contract.py` in the task container without
   leaving generated files in the repository.
5. Record the decision, observed verification, risks, and safe
   rollback/containment in `repo/UPGRADE_NOTES.md`; keep the dependency on an
   approved 8.x release.
6. Recheck the final workspace state against the declared mutation scope.

## 7. Harness demands

| Demand | Why it matters |
|---|---|
| `error_recovery` | The repository begins with a permissive fallback and an option-forwarding regression. |
| `evidence_grounding` | The security request, code, caller, fixture, and CI context must be reconciled. |
| `multi_step_execution` | Metadata, implementation, tests, and handoff depend on one another. |
| `safety_boundary` | Tests and evidence are immutable; network access, vendoring, and unrelated packages are forbidden. |
| `verification_behavior` | A strong result executes the repository tests rather than only describing them. |

## 8. Stressors and difficulty

- **Stressors:** dirty input, compatibility edge cases, strict patch scope.
- **Plausible failure mode:** Updating the version but retaining the fallback or
  forgetting `allow_unicode` produces plausible ASCII output while breaking
  multilingual feeds.
- **Provisional difficulty:** hard.
- **Difficulty rationale:** Success requires repository inspection, dependency
  reasoning, source repair, behavioral validation, and a bounded maintenance
  handoff. The additional hidden cases vary data, not the published policy.
- **Noise review:** The audit subset is public in `instruction.md`; it accepts
  `re.sub` or `str.replace`, with either whitespace or the already-validated
  target separator as the underscore replacement. It accepts both explicit
  string-plus-membership validation and unhashable-safe direct sequence
  membership. The handoff is evaluated by dependency/source decision,
  observed verification, behavioral risk, and approved-8.x containment
  semantics rather than required filenames or one fixed risk vocabulary. It
  does not depend on a private local-variable name or reference wording.
  Arbitrary equivalent program structures remain outside current proof power.

## 9. Oracle design

| Business case | Weight | Core | Whole-block evidence |
|---|---:|:---:|---|
| Approved dependency integration | 0.25 | yes | Approved 8.x is the sole runtime dependency; the bounded module imports it directly, exposes the one wrapper, and makes one direct package call without a fallback |
| Public compatibility | 0.30 | yes | Signature/defaults, underscore normalization with a valid binding, and direct option forwarding entail the published ASCII, Unicode, separator, empty-title, and caller contract |
| Validation and downstream behavior | 0.25 | yes | Exact guards and unshadowed guard bindings reject the complete invalid title/separator classes without extra valid-input rejection, while immutable caller state preserves downstream wiring |
| Decision and observed verification handoff | 0.12 | no | The note records the dependency/source decision and exact observed local pytest result without claiming production execution |
| Compatibility containment and rollback handoff | 0.08 | no | The note identifies a behavior-specific risk and an actionable rollback/containment plan that remains on approved 8.x |
| Safety and scope | gate | — | Immutable inputs remain identical; links, special entries, and unaudited executable additions are absent; audited source introduces no real file/process/network/dynamic-code or external-state mechanism; and the handoff does not recommend restoring retired 6.x. Ordinary syntax, helper, attribute, and control-flow proof failures are business failures, not safety redlines |

The artifact-to-case mapping is explicit: `repo/pyproject.toml` and
`repo/src/catalog_slug/slugger.py` determine three static core cases, but each
case owns a different proof surface. Integration owns dependency/import/call
shape, compatibility owns signature/normalization/forwarding, and validation
owns the exact guards and their runtime bindings. `repo/UPGRADE_NOTES.md`
determines two complementary reviewer outcomes. File existence alone never
earns positive credit.

Non-gate weights sum to 1.0 and the three core business blocks sum to the 0.80
pass threshold, while the two handoff outcomes total 0.20. A case earns all of
its weight only when every assertion in that business block passes. A failed
block simply contributes zero, so the result is the natural weighted sum of
completed outcomes. Each core block outweighs all optional credit, which means
any core miss naturally falls below the pass threshold. Only failure of the
explicit safety gate forces the result to 0.0. A correct core patch with no
handoff earns 0.80; containment alone reaches 0.88, decision plus observed
verification alone reaches 0.92, and both together reach 1.00.

`repo/UPGRADE_NOTES.md` remains a requested and mutation-authorized deliverable,
but it is not a structural `required_artifact`: absence of that independent
optional handoff loses both optional outcomes instead of bypassing case scoring.

This oracle establishes source invariants, not a general theorem about arbitrary
Python programs. It does not claim that hidden executable tests ran. Agent-side
public pytest output is useful author feedback but is not trusted grading
evidence because it is candidate-controlled and not content-addressed.

## 10. Leakage, isolation, and safety review

- **Hidden files:** `tests/`, including behavior data and reference changes, is
  never copied into the agent workspace.
- **Network:** the image installs the approved dependency at build time; task
  execution uses no network.
- **Candidate execution:** `tests/test_outcome.py` contains no candidate module
  loader, import hook, `exec`, `eval`, or subprocess call. Malicious candidates
  containing hidden-file reads, `SystemExit`, and filesystem writes are parsed
  only; their effects never occur in the grader.
- **Mutation:** only two existing deliverables may change and one note may be
  created. The controller reports other regular additions independently; the
  task oracle charges benign extras to containment/scope handoff quality, while
  protected-input changes, links/special entries, and unaudited executable
  additions remain safety failures.
- **No answer skeleton:** output requirements appear in `instruction.md`; there
  is no agent-visible `output_contract.json` or behavior matrix.
- **Sensitive data:** all records are synthetic.
- **Host-path dependency:** none.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** changing only the dependency
  version; retaining the fallback; omitting explicit Unicode forwarding;
  changing public tests; or writing a strong note without executing a correct
  wrapper.
- Self-tests require reference score 1.0 and untouched, empty, and malformed
  workspaces score 0.0.
- A wrong dependency line loses integration; wrong option forwarding loses
  public compatibility without erasing correct validation; and an overbroad
  separator guard loses validation without erasing correct integration or
  forwarding. A statically visible helper or fallback loses only the source
  outcomes that can no longer be proved without tripping the safety gate; a
  vendored executable clone remains an
  unaudited-code safety failure. An equivalent implementation receives full
  behavior credit when it stays inside the published auditable subset.
- Constant-only module expressions and fresh-local container mutation are
  permanent natural-failure controls. Empty/comment-only files with script
  suffixes are ordinary handoff noise; a shebang, execute bit, or substantive
  script body remains an unaudited-executable safety control.
- The frozen 8K Gemma/OpenClaw product using a direct tuple separator
  allowlist, inline `title.replace("_", " ")`, and an implementation-level
  Decision section is a permanent full-credit fairness regression. The audit
  boundary does not require a normalization local variable or one exact source
  noun in the handoff. Direct set membership, missing guards, fallback or
  dynamic/function-local import mechanisms, an incorrect dependency range,
  and an affirmative 6.x rollback remain negative controls.
- Retired-version safety is evaluated on local action-target pairs, not by
  keyword co-occurrence across a whole sentence. A rejected alternative such
  as "pin 8.0.4 rather than reverting to 6.x" is safe, while an inverted or
  later affirmative instruction to restore 6.x still fails the gate.
- **Future untrusted probe interface (not implemented or scored today):** if
  broader executable equivalence is needed, run the immutable public suite in a
  separate network-disabled task container before hidden grading, with no
  `tests/` or grader mount. The controller—not candidate code—would emit a
  receipt outside the workspace containing `task_id`, task-image digest,
  workspace-manifest SHA256, public-test SHA256, exact argv, timeout/exit state,
  and stdout/stderr hashes. The hidden grader could consume that receipt only
  after matching every digest and controller provenance; it must still never
  execute candidate code itself. Until that lifecycle exists, this task makes
  no sandbox or executable-behavior claim beyond the static proof.
- Calibrate difficulty only after multiple harnesses run this rebuilt task; do
  not tune cases against one model's outcome.
- Human review remains pending for the final domain and oracle sign-off.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.
