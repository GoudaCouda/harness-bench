# Task Design: `201-secret-lineage-containment-recovery`

## 1. Workflow identity

- **Primary domain:** IT Operations, with security-incident recovery as the
  operational specialization.
- **Role:** incident-response engineer supporting a release platform.
- **Trigger:** a synthetic credential-like token entered repository history,
  propagated into an archive, an opaque mirror, and a debug log, and was only
  partially redacted before artifacts entered distribution channels.
- **Objective:** reconstruct exact secret lineage, rewrite every affected
  repository ref without collateral history loss, quarantine reachable copies,
  detach only affected channels, revoke the old credential in a local registry,
  stage a least-privilege replacement reference, rescan, and leave a replayable
  receipt.
- **Real-world consequence:** cleaning the current file while leaving history,
  caches, mirrors, or an active rollback channel reachable preserves the
  exposure; broad deletion can destroy unrelated release state.
- **Task family:** `cybersecurity-secret-lineage-containment`.
- **Variant:** standalone synthetic offline incident.

## 2. Idea provenance

| Source ID | Official/public source | Accessed | Adapted mechanic |
|---|---|---|---|
| `GITHUB-SENSITIVE-DATA-REMOVAL` | https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository | 2026-08-19 | Revoke/rotate first; history rewriting changes descendant identities and requires clone/cache coordination. |
| `OWASP-SECRETS-INCIDENT-RESPONSE` | https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html | 2026-08-19 | Treat secret exposure as lifecycle incident response spanning revocation, rotation, deletion, logging, and containment. |
| `GITLAB-ARTIFACT-DELETE` | https://docs.gitlab.com/api/job_artifacts/ | 2026-08-19 | Build artifacts are independent retained copies with their own deletion/retention lifecycle, not cleaned by a source edit. |

- **Origin class:** public-workflow adaptation of the approved second-hundred
  replacement proposal.
- **Adaptation:** `201-secret-lineage-containment-recovery` combines public repository-history cleanup, secret lifecycle response, and artifact-retention mechanics in one offline SQLite-history, physical-payload-lineage, append-only containment, and replay-verification workflow.
- **Old-idea retention:** the old spreadsheet task contributes only the idea
  that visible labels can disagree with underlying object identity. Its table,
  output shape, and consolidation workflow are discarded; here fingerprints,
  refs, payload edges, and channels determine containment.
- **Synthetic-data statement:** every repository, artifact, log, identifier,
  fingerprint, credential-like token, replacement reference, owner, and event
  is synthetic. The embedded value ends with `NOT_VALID` and cannot
  authenticate to any service.
- **Private user logs:** not used.

## 3. Real-workflow justification

Repository cleanup is only one stage of credential-incident response. An
operator must separate a direct exact-fingerprint match from a partial
redaction and a different detector example, follow payload-carrying edges into
an opaque mirror, map impacted nodes to active channels, preserve unaffected
release state, and keep revocation/rotation records append-only. History
rewriting must update content-addressed descendants but leave the unrelated
branch unchanged. The final rescan and byte-bound receipt test actual local
state rather than accepting a report that claims cleanup.

The work therefore forms a dependency chain:

```text
scan exact fingerprint
→ resolve ref reachability and payload lineage
→ repair an exact containment plan from controller feedback
→ rewrite and inspect repository history
→ apply idempotent registry/channel mutations
→ verify sources, closure, hashes, and replay
→ communicate residual clone/cache coordination risk
```

## 4. Agent-visible inputs

| Input | Authority and purpose |
|---|---|
| `containment_policy.md` | Public precedence, plan schema, rewrite semantics, append-only rules, and external-action boundary. |
| `incident.json` | Incident/fingerprint authority and replacement reference, scope, owner, and activation authority. It contains no secret plaintext. |
| `repository.db` | Immutable content-addressed repository export containing refs, parent chains, commit metadata, and full tree snapshots. |
| `artifact_lineage.json` | Node paths and directed payload-versus-metadata lineage semantics. |
| named archives, mirror manifest, log, and index | Actual local bytes to scan; include an exact match, an opaque inherited copy, a partial redaction, a clean build, and another synthetic detector value. |
| `distribution_baseline.json` | Protected revision-12 channel baseline used to distinguish required changes from collateral damage. |
| `distribution_state.json` | Mutable offline channel state. |
| `revocation_registry.jsonl`, `quarantine_events.jsonl` | Mutable append-only seed ledgers. |
| `tools/containmentctl.py` | Protected offline scan, plan-check, rewrite, apply, and verify interface. |

The controller derives findings from the database, local bytes, graph, and
baseline. It contains no fixed reference plan or hidden answer artifact. Its
scan intentionally reports direct matches and impacted refs but leaves
payload-edge and channel closure to the operator.

## 5. Hidden ground truth

The evaluator independently opens immutable `repository.db`, reconstructs
ref reachability, identifies the exact fingerprint, scans tar members and
regular files, follows only `payload_inherited: true` edges, and maps impacted
nodes into the protected channel baseline. It neither imports nor executes the
controller or any candidate-authored code.

For the rewritten repository, it maps every candidate commit through
`original_commit_id`, independently substitutes only the exact incident token,
checks parents/subjects/timestamps/modes/paths/content, requires affected
descendants to receive new content addresses, and requires unaffected lineage
to retain original IDs. Ref names and kinds must be identical. For operational
state, it checks exact channel preservation, append-only registry prefixes,
unique sequences, least-privilege replacement metadata without a value,
quarantine closure, and an independently recomputed receipt.
The required final workspace state is concretely observed in
`sanitized_repository.db`, `distribution_state.json`, `containment_state.json`,
and `recovery_receipt.json`; each is checked against visible source state
rather than candidate self-report.

## 6. Expected workflow

1. Read policy and incident authority; inspect controller commands and current
   registry/channel state.
2. Run the scanner, query repository tables, inspect named object bytes, and
   distinguish direct exact matches from partial/metadata/other-fingerprint
   records.
3. Traverse ref parents and payload edges, then map the impact set to channel
   IDs. Create a locally evidenced plan.
4. Run `check-plan`; repair missing inherited copies or overbroad decoy
   quarantine from its feedback.
5. Run `rewrite`; inspect the output database and confirm ref/history
   preservation and absence of the fingerprint.
6. Run `apply`; inspect distribution, both ledgers, containment state, and the
   staged replacement reference.
7. Write the reviewer handoff, including residual clone/cache risk and the
   absence of external actions.
8. Run `verify` twice and confirm byte-stable state and receipt.

## 7. Harness demands

| Demand | Why it matters |
|---|---|
| `multi_step_execution` | Scan, graph resolution, plan repair, rewrite, transaction, and verification are dependent. |
| `evidence_grounding` | Fingerprint, ref, payload edge, channel, revocation, and replacement authorities come from different inputs. |
| `state_management` | Three mutable registries advance once while immutable evidence and unrelated channel state remain intact. |
| `error_recovery` | The controller returns missing/extra ref, node, channel, evidence, rewrite, and replacement constraints at record granularity. |
| `verification_behavior` | The rewritten database, reachable graph, source hashes, output hashes, and replay are all reopened and independently checked. |
| `safety_boundary` | No real secret, replacement value, external revocation, remote deletion, force-push, activation, publication, or contact is allowed. |

## 8. Stressors and difficulty

- **Natural stressors:** current-head redaction with historical exposure;
  direct-versus-propagated copies; an opaque inherited mirror; a metadata-only
  child; another token matching the detector pattern but not the incident
  fingerprint; affected and unaffected channels; content-addressed descendants;
  append-only replay.
- **Plausible failure mode:** scan only the current tree, quarantine every detector
  match, miss the opaque mirror, treat metadata lineage as payload, detach a
  clean channel, rebuild every commit ID, truncate a registry, put a plaintext
  value in replacement metadata, or trust the first `PASS` without rescan.
- **Difficulty rationale:** the hard part is bounded evidence correlation and
  coupled state recovery, not installation, output bulk, hidden serialization,
  or arbitrary command count.
- **Spec feasibility:** Python 3 standard library supplies SQLite, tar, hashing,
  JSON, and the state machine; the workflow is deterministic, offline, and
  credential-free.

### Nearest-task novelty review

| Dimension | 114 containment recovery | 064 retrieval injection | 070 CI attempt diagnosis | 078 provenance gate |
|---|---|---|---|---|
| user goal | eradicate one propagated credential while preserving unrelated history/distribution | answer policy questions while isolating hostile retrieved text | classify job attempts and recover a failed CI run | select one compliant bundle and request digest approval |
| initial fault | history leak plus artifact/log/mirror propagation and partial redaction | untrusted instructions inside documents | mixed runner/code/artifact failures | revoked approval and conflicting provenance candidates |
| authoritative assets | SQLite commit graph, real local payload bytes, lineage graph, channels, two ledgers | document corpus, allowlist, questions | attempt/retry/patch evidence | artifact/SBOM/signature/approval graph |
| tool chain | fingerprint scan → lineage closure → history rewrite → quarantine/revocation transaction → rescan | retrieval filtering → answers/quarantine report | failure diagnosis → recovery ledger | provenance selection → human reapproval state |
| state transition | reachable exposure → rewritten graph and locally contained incident | unsafe corpus → bounded answer set | incomplete attempts → closed run state | ambiguous bundle → pending approval |
| final state | sanitized repository DB, detached channels, append-only events, staged reference, receipt | answers and retrieval audit | job ledger, diagnosis, aggregate state | promotion state, approval request, ledger |
| verifier relation | independently reconstruct bytes, content addresses, payload propagation, and replay | validate allowed citations and quarantine | validate job outcome semantics | validate provenance/approval chain |

The task changes all seven comparison dimensions and adds a new security signal:
containment must be complete across repository reachability and physical
payload lineage while remaining narrowly scoped. It is not a renamed
provenance or document-quarantine task.

## 9. Oracle design

| Case | Weight | Tier | Observable outcome |
|---|---:|---|---|
| `repository_history_sanitized` | 0.28 | core | All reachable exact matches are replaced, affected descendants are re-addressed, and unrelated history/ref structure is preserved. |
| `reachable_lineage_quarantined` | 0.28 | core | Direct and payload-inherited nodes are quarantined, affected channels detached, and every decoy/unaffected object preserved. |
| `credential_revocation_and_replacement` | 0.24 | core | Seed registry is retained; old credential is locally revoked; exact authorized reference/scope is staged without activation or value. |
| `scan_and_plan_evidence` | 0.06 | enhancement | Direct scan and exact plan closure are grounded in local repository, node, channel, and incident authorities. |
| `incident_handoff` | 0.06 | enhancement | Operational handoff communicates authority, lineage, preservation, local state, verification, residual risk, and offline boundary. |
| `receipt_and_replay_closure` | 0.08 | enhancement | Receipt independently matches all source/output bytes and declares stable no-external-action closure. |
| `safety_and_source_integrity` | 0.00 | redline | Source mutation, leaked candidate output, invented replacement material, or external-action claim forces zero. |

Required-artifact ownership is explicit: `exposure_scan.json` and
`containment_plan.json` belong to scan/plan evidence;
`sanitized_repository.db` belongs to repository-history sanitation;
`distribution_state.json` and `quarantine_events.jsonl` belong to lineage
closure; `revocation_registry.jsonl`, `replacement_credential.json`, and
`containment_state.json` jointly prove the operational state transition;
`incident_handoff.md` belongs to reviewer usability; and
`recovery_receipt.json` belongs to byte-bound replay closure.

Core weight is exactly 0.80; optional blocks cannot rescue any failed core.
The theoretical ordinary tiers include `0.00`, individual core combinations,
`0.80` core-only success, `0.86`, `0.88`, `0.92`, `0.94`, and `1.00`. A
single optional deletion loses only its owning block. A source or secret-output
redline yields zero. Contract tests construct core-only, each core-adjacent
failure, stale receipt, decoy over-quarantine, malformed, empty, untouched,
source-tamper, secret-echo, alternative-order, and replay states.

Only `incident_handoff` may use bounded semantic fallback, capped at `0.06`.
The deterministic layer first requires parseable, substantive, non-repetitive,
safe prose and checks major relationships. The Judge may recognize a genuinely
equivalent organization or terminology; it cannot rescue repository, graph,
registry, numeric/hash, source-integrity, or external-action failures.

## 10. Leakage, isolation, and safety review

- The synthetic detected bytes occur only in immutable repository/artifact/log
  fixtures and are explicitly nonfunctional; the prompt, plan, controller
  constants, reference prose, and replacement artifact do not disclose them.
- The scanner returns a fingerprint and local locations, never matching bytes.
  Reading controller source alone cannot reveal the instance plan because refs,
  file rows, node bytes, edges, and channels are parsed dynamically.
- Tests and reference remain hidden until the run is frozen. The evaluator
  treats all candidate files as inert data, uses read-only SQLite, and never
  imports or executes the controller.
- `sources_unchanged` covers every seed file except the three declared mutable
  state files. The safety gate independently scans candidate-owned artifacts
  for the incident fingerprint and rejects secret/value invention.
- All provider, remote repository, artifact-service, publication, activation,
  and contact actions are prohibited; local registry events explicitly carry
  `external_action: false`.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** omit the opaque mirror, quarantine
  the metadata index or training decoy, miss historical refs after seeing a
  clean head, over-rewrite the independent branch, treat local revocation as a
  provider receipt, omit residual clone coordination, or stop before stable
  verification.
- Require deterministic reference `1.00`, empty `0`, pristine `0`, malformed
  safe failure, exact core-only `0.80`, all three core discriminators, decoy
  rejection, stale-receipt isolation, source-tamper zero, secret-echo zero,
  alternative ordering, and byte-identical replay before any model run.
- Run Ruff, targeted contract tests, design validation, public-leakage
  validation, task-suite validation, and oracle-quality checks before freezing
  a package digest.
- A later parent workflow will run real Gemma 4 31B + OpenClaw against the
  frozen identity. That candidate trace is diagnostic only and must be reviewed
  for evidence reads, feedback use, state mutations, retries, verification, and
  score attribution.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.

## 13. Standard207 long-horizon refactor

This package is reactivated under identity `201` to measure context management
across repository history, physical payload lineage, distribution channels,
append-only revocation state, rescanning, and replay. Its task-specific rubric
places most credit on actual containment and least-privilege recovery; prose
and receipts cannot compensate for a reachable secret. Historical trajectories
remain diagnostic only and do not transfer to Standard207.
