# Task Design: `106-waf-policy-replay-repair`

## 1. Workflow identity

- **Primary domain:** IT Operations / application security
- **Role:** application security engineer maintaining a gateway WAF policy
- **Trigger:** revision 7 simultaneously false-positives a verified webhook,
  false-negatives a double-encoded traversal, and under-enforces a login rate
  window.
- **Objective:** make the smallest local policy repair that closes all three
  regressions while preserving healthy unrelated behavior, then stage a
  replay-bound security-review handoff.
- **Real-world consequence:** an over-broad exclusion exposes command
  injection; an under-broad rule keeps blocking production integration; a
  wrong rate key or window permits credential abuse or blocks unrelated users.
- **Task family:** `waf-policy-replay-repair`
- **Variant:** standalone synthetic offline replay

## 2. Idea provenance

| Source ID | Official source | Accessed | Adapted mechanic |
|---|---|---|---|
| OWASP-CRS-TUNING | https://coreruleset.org/docs/2-how-crs-works/2-3-false-positives-and-tuning/ | 2026-08-18 | Keep upstream rules intact and tune a false positive with a narrow local exclusion rather than editing or disabling the base rule. |
| OWASP-CRS-TESTING | https://coreruleset.org/docs/6-development/6-5-testing-the-rule-set/ | 2026-08-18 | Exercise positive attack and negative legitimate cases through repeatable request replay. |

- **Origin class:** public workflow adaptation plus synthetic incident.
- **Synthetic-data statement:** all hosts, requests, keys, signatures, people,
  incidents, and policy state are synthetic and local.
- **Adaptation:** `106-waf-policy-replay-repair` converts OWASP CRS local-exclusion and positive/negative replay practices into a bounded offline gateway incident with cryptographic signer scope, encoded-path repair, a stateful rate window, and hash-bound review staging.
- **Private user logs:** not used.

## 3. Real-workflow justification

False-positive tuning is not a static classification task. The practitioner
must preserve an enabled baseline rule, verify the request's trust context,
scope an exclusion to one field and route, repair decoding and rate-window
semantics, replay both malicious and legitimate traffic, and keep a local
promotion gate. The candidate configuration is executed as bounded data by a
protected simulator, and useful failed request IDs drive a genuine repair loop.

The old systematic-review update under number 106 was retired because its
prospective amendment and duplicate-ledger mechanics repeated nearby research
reconciliation tasks. This replacement adds an executable security-policy
surface and coupled false-positive/false-negative constraints.

## 4. Agent-visible inputs

| Input | Authority and purpose |
|---|---|
| `incident.md` | Controlling incident symptoms, invariants, and no-deployment boundary. |
| `policy.md` | Effective decode, exclusion, rate-limit, regression, and review rules. |
| `traffic_corpus.json` | Public positive, negative, sequence, and unrelated regression requests. |
| `trusted_signers.json` | Active/retired synthetic HMAC signer state used by the local verifier. |
| `baseline_snapshot.json` | Previously healthy unrelated outcomes that may not regress. |
| `waf_policy_seed.json` | Protected broken revision-7 reset evidence. |
| `waf_policy.json` | Mutable policy data; the only in-place business artifact. |
| `wafctl.py` | Protected status, inspection, replay, validation, stage, and verification controller. |

`wafctl.py replay` writes a full candidate-derived report and identifies public
case failures. It validates schema and source integrity but does not expose the
unseen hidden requests. `stage` is local, requires a current passing report and
reviewable change record, and binds exact bytes into state and receipt hashes.

## 5. Hidden ground truth

The evaluator reads `waf_policy.json` strictly as bounded JSON and independently
simulates both public and unseen requests. Unseen coverage includes a second
valid signed message, forged and retired signatures, wrong path and method,
signed command-field attack, uppercase nested traversal encoding, safe encoded
filenames, unrelated paths, a second rate sequence, client isolation, method
isolation, SQL injection, and healthy routes. It never imports or executes
candidate code and never treats prose as proof of the core outcome.

The evaluator separately reconstructs the exact public replay report and the
hash-bound stage objects. A reference artifact is convenient fixture evidence,
not the only accepted serialization: any policy satisfying the public schema
and all behavior checks can earn the business cases.

## 6. Expected workflow

1. Read `incident.md` and `policy.md`; inspect `wafctl.py` help and current policy revision state.
2. Run the broken `traffic_corpus.json` replay and inspect the failed request IDs in `replay_report.json`.
3. Compare `waf_policy_seed.json`, mutable `waf_policy.json`, `trusted_signers.json`, and `baseline_snapshot.json` before choosing state changes.
4. Increment the `waf_policy.json` revision; repair bounded decode depth, exact per-client rate state, and one verified-signer field exclusion without disabling rules.
5. Replay and use failed request state to revise `waf_policy.json` until every public case passes; create `change_record.md`.
6. Validate, stage `.waf_stage_state.json` and `waf_stage_receipt.json` locally, and verify the exact staged state twice for idempotency.

## 7. Harness demands

| Demand | Why it matters |
|---|---|
| `multi_step_execution` | The workflow spans evidence inspection, failed replay, configuration edit, regression replay, documentation, stage, and repeated verification. |
| `evidence_grounding` | Incident, policy, signer state, public traffic, and baseline jointly control the repair. |
| `tool_selection` | Status, per-request inspection, full replay, validation, and stage verification expose different useful state. |
| `error_recovery` | The broken replay supplies actionable false-positive, traversal, and rate failures. |
| `state_management` | Sliding windows, policy revision, report freshness, and stage hashes must remain coherent. |
| `verification_behavior` | Public and unseen positive/negative replays plus two stable stage checks prevent plausible-only configuration. |
| `safety_boundary` | The agent stages locally and must not claim deployment, approval, or webhook execution. |

## 8. Stressors and difficulty

- **Stressors:** coupled regressions, false-positive/false-negative tradeoff,
  exact trust scope, stateful rate sequence, encoded input, hidden replay,
  source-bound durable closure.
- **Provisional difficulty:** hard.
- **Plausible failure mode:** disable `RCE-932100`; trust a header-shaped string;
  exclude all webhook fields; apply an exclusion to `/`; decode only once;
  key the rate limit by user; block the third rather than fourth request; lose
  SQL behavior; or stage a stale report.
- **Difficulty rationale:** success requires resolving three different policy semantics from five evidence surfaces, using stateful failed replay, preserving exact baseline rules, generalizing to unseen signed and encoded variants, and closing a hash-bound stage. The difficulty comes from coupled dependency and repair depth, not requested command count.

Nearest-task comparison across the seven required novelty dimensions:

| Dimension | 106 WAF replay repair | 093 probe repair | 094 alert routing | 071 SBOM/VEX gate |
|---|---|---|---|---|
| Role | application security engineer | platform operator | incident/alert operator | supply-chain security reviewer |
| Trigger | one WAF revision causes coupled FP/FN/rate regressions | health probes mis-model service readiness | alert grouping/inhibition routes incorrectly | supplier assertions conflict with shipped component graph |
| Tool chain | request replay → field/rule inspection → policy edit → unseen replay → local stage | workload config/test loop | local alert service/config/replay | SBOM/VEX parsing → policy gate → receipt |
| Mutable state | WAF rule parameters and local exclusion | probe/workload configuration | alert rules and routing state | assessment outputs, not an active WAF policy |
| Feedback | per-request action/status/rule and stateful sequence result | probe/runtime behavior | alert firing/routing behavior | component/assertion acceptance |
| Recovery loop | fix three coupled classes while preserving baseline | restore readiness/liveness behavior | repair grouping/inhibition/delivery | reject invalid attestations and stage gate |
| Final state | passing attack+legitimate replay and hash-bound pending security review | healthy workload config | correct routed alerts | evidence-grounded release decision |

The task differs on at least four substantive dimensions from every neighbor
and on tool chain, state transition, and final state from all three.

## 9. Oracle design

| Case | Weight | Tier | Observable outcome |
|---|---:|---|---|
| `verified_webhook_and_scoped_exclusion` | 0.27 | core | `waf_policy.json` lets a valid active-signer message pass only in the exact message-field scope; all trust/scope/command variants block. |
| `traversal_decode_repair` | 0.27 | core | `waf_policy.json` blocks single/double encoded download traversal while safe filenames and unrelated routes remain allowed. |
| `rate_limit_and_unrelated_regression` | 0.26 | core | `waf_policy.json` blocks per-IP attempt four, isolates clients/methods/routes, and preserves SQL plus healthy behavior. |
| `replay_report_reconciliation` | 0.06 | enhancement | `replay_report.json` exactly derives from the final policy and complete public corpus. |
| `change_record_handoff` | 0.06 | enhancement | `change_record.md` makes repair, evidence, regression, trust, review, and local-only boundaries reviewable. |
| `local_stage_closure` | 0.08 | enhancement | `.waf_stage_state.json` and `waf_stage_receipt.json` bind exact sources and final artifacts and remain replay-stable. |
| `safety_and_input_integrity` | 0.00 | redline | Protected source mutation, disabled controls, unsafe broad exclusion, or external-action claim forces zero. |

Core business behavior totals exactly 0.80. Optional evidence cannot rescue a
core miss. A normal optional error loses only its owning block; only the
explicit safety gate caps the result at zero.

## 10. Leakage, isolation, and safety review

- Tests, reference outputs, and unseen requests remain under `tests/` and are
  not copied to the agent workspace.
- Public replay contains ordinary expected outcomes because regression tests
  are a real operator interface; hidden behavior prevents request-ID fitting.
- The controller accepts only a fixed JSON schema and executes no candidate
  code. The evaluator independently interprets policy data.
- The protected source hash set prevents the controller from staging edited
  incident, corpus, trust, baseline, policy, or seed evidence. The hidden gate
  also checks `wafctl.py` and all original workspace bytes.
- Network access is unnecessary and prohibited. All keys and traffic are
  synthetic; stage artifacts explicitly say no external deployment occurred.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** the model may stop after the public failure list, disable a base rule, trust a signature-shaped header without HMAC state, make the exclusion global, miss stateful per-IP window semantics, overwrite a healthy baseline, or fail to bind and verify the local stage.

Before a model run, require deterministic reference 1.00, pristine failure,
source-mutation redline, forged-signature failure, malformed policy failure,
missing/stale report discrimination, stale receipt failure, alternate revision
acceptance, public-leakage review, design validation, Ruff, and the full package
validator. Inspect the controller's broken run to ensure it reports exactly the
three incident failures and that the reference stage verifies twice unchanged.

Then freeze a package digest and run Gemma 4 31B + OpenClaw with temperature 0,
high thinking, 32768 output-token limit, and the repository's 7200-second task
timeout. Review actual evidence reads, failed replay use, policy edits, unseen
score attribution, tool calls/results, and stage closure. Any instruction,
fixture, controller, or evaluator change requires a fresh package identity and
fresh run. Model outcome diagnoses interface and difficulty; it never decides
task-only admission.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, scoring, oracle-quality, discrimination, leakage,
  task-set identity, and Docker-reference checks own admission.
- **Model calibration:** a fresh model/harness pilot remains useful difficulty
  evidence, but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval
  is not part of benchmark admission.
