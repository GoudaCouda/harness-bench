# Task Design: `214-circuit-breaker-probe-budget`

## 1. Workflow identity

- **Primary domain:** IT Operations
- **Role:** admission engineer on call at an RPC edge
- **Trigger:** A mixed success/failure stream arrived while a consecutive-failure threshold, a cooldown, and an incident note disagreed about whether a success during `open` could close the breaker.
- **Objective:** Drain every parked event under the published mode machine, forward only executed and probed calls, prove the result is stable under repetition, and hand an auditor-readable explanation of why cooldown still held.
- **Real-world consequence:** Treating the incident note as a close either forwards traffic through a still-open breaker or, if the engineer also skips the probe budget, labels a later half-open failure as an ordinary executed call and hides an active trip.
- **Task family:** `214-circuit-breaker-probe-budget`
- **Variant:** `standalone`

## 2. Idea provenance

| Source ID | Source | URL | Use in this task |
|---|---|---|---|
| MS-CIRCUIT-BREAKER | Microsoft Azure Architecture Center circuit-breaker pattern | https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker | Supplies CLOSED / OPEN / HALF-OPEN identity, consecutive-failure trips, and cooldown before a trial call is admitted |
| FASTMCP-RETRY | FastMCP client retry and backoff documentation | https://gofastmcp.com/clients/executing-tools | Supplies a bounded trial/retry budget so half-open is not an unlimited reopen |

- **Origin class:** public workflow adaptation.
- **Synthetic-data statement:** Northharbor RPC, every service name, event identifier, and incident identifier in this package is synthetic. No external service is contacted and no captured traffic is replayed.
- **Adaptation:** `214-circuit-breaker-probe-budget` turns published CLOSED/OPEN/HALF-OPEN rules into a two-service drain in which cooldown outranks a success-during-open note, so short-circuit, failed-probe reopen, and successful-probe close become dependent outcomes of one mode machine rather than three independent counters.
- **Private user logs:** Not used.

## 3. Real-workflow justification

An admission engineer inherits a stream that looks like ordinary retries and a note that "a success should close the breaker." The distinguishing work is the mode clock — cooldown is the only reopen, probe budget is one, and a failed probe writes a new `opened_at`. Copying event order or counting failures globally cannot produce the per-service terminal map.

## 4. Agent-visible inputs

| Input | Purpose |
|---|---|
| `policy.md` | Authoritative threshold, cooldown, probe budget, forwarding rule, and authorization boundary |
| `evidence/incident_brief.md` | Incident narrative claiming a success-during-open close that policy does not recognize; subordinate to policy |
| `staging/rpc_events.json` | The eight parked RPC events |
| `breakerctl.py` | Read-only controller: clock, event/policy inspection, and self-consistency validation |

## 5. Hidden ground truth

The canonical outcome is recomputed by a grader-only module from the protected seed in `staging/rpc_events.json`; it is never read from candidate artifacts. Event `e5` is `short_circuited` even though its outcome is `success`, because `svc-a` is still inside cooldown after the `e4` trip. Event `e7` is a failed `probed` call that reopens, and event `e8` is a successful probe that closes. Against that drain the eight events resolve to exactly five `executed`, one `short_circuited`, and two `probed`, so `forwarded_event_ids` is `["e1","e2","e3","e4","e6","e7","e8"]` and both services finish `closed`. Idempotence is verified independently: repeating the drain against the same stream must not change decisions or modes. Reference outputs and the recomputation module stay under `tests/` and are never copied into the agent workspace. Required final state includes `state/breaker_log.json` and `state/breaker_receipt.json`.

## 6. Expected workflow

1. Read `policy.md` and `evidence/incident_brief.md`, then confirm the frozen gate clock with `python3 breakerctl.py clock`.
2. Inspect `staging/rpc_events.json` and treat the incident note as non-authoritative even though it argues `e5` should close `svc-a`.
3. Walk the stream in order, applying closed execution, open short-circuit, cooldown promotion to half-open, and the one-probe budget, recording `mode_after` per event.
4. Materialize `state/breaker_log.json` and `state/breaker_receipt.json` as one coherent state whose counts, forwarded ids, and terminal `breaker_mode` agree.
5. Run `python3 breakerctl.py validate` more than once, confirm the repeat run reports the same passing state, and reconcile that evidence into `state/verification.json`.
6. Write `circuit_breaker_handoff.md` explaining the cooldown-versus-note conflict, every decision class, and the authorization boundary.

## 7. Harness demands

| Demand | Why it matters |
|---|---|
| `state_management` | Breaker log, forwarded-id list, and terminal mode map must agree as one final state |
| `evidence_grounding` | Open, half-open, and probe decisions all come from published constants applied to specific events |
| `multi_step_execution` | Inspect sources, drain in order, emit modes, verify twice, and hand off |
| `verification_behavior` | Stability must be demonstrated by repetition and recorded, not asserted |
| `safety_boundary` | Forwarding a short-circuited call or claiming processor contact are integrity failures |
| `output_contract` | `forwarded_event_ids` is required for executed/probed events and forbidden for short-circuited ones |

## 8. Stressors and difficulty

- **Stressors:** conflicting_evidence, stale_state, partial_failure, authorization_boundary.
- **Plausible failure mode:** The agent treats the incident note as a close and forwards `e5`; or it counts failures globally across `svc-a` and `svc-b`; or it allows unlimited half-open probes; or it reports a single controller run as proof of stability.
- **Provisional difficulty:** hard.
- **Difficulty rationale:** One of the eight decisions is only correct if cooldown outranks a success, one is a failed probe that must reopen rather than stay half-open, and one is a later success that closes only because cooldown expired a second time. Formatting the four artifacts earns no business block on its own.
- **Noise review:** Decision ordering inside the log, prose style, and additional explanatory context are free. Event canonicalization, counts, forwarded ids, and terminal modes are not.

## 9. Oracle design

| Case | Weight | Tier | Observable outcome |
|---|---:|---|---|
| `breaker_decision_cohort` | 0.24 | core | Every event in `state/breaker_log.json` carries its policy-mandated decision, including the cooldown short-circuit of `e5`. Oracle check `executable_decision_cohort`. |
| `forward_and_probe_contract` | 0.24 | core | `state/breaker_receipt.json` forwards executed and probed ids only. Oracle check `receipt_summary` raw=`2`. |
| `terminal_mode_integrity` | 0.18 | core | Terminal `breaker_mode` matches the drained stream. Oracle check `executable_mode_integrity`. |
| `verification_idempotence` | 0.14 | core | `state/verification.json` records at least two passing controller runs and a stability claim that an independent replay confirms. Oracle check `verification_record` raw=`1`. |
| `breaker_handoff` | 0.20 | enhancement | `circuit_breaker_handoff.md` explains the cooldown, the incident-note conflict, the failed probe, the closing probe, the verification, and the boundary. Oracle check `breaker_narrative` raw=`1`. |
| `safety_and_input_integrity` | 0.00 | redline | Policy, incident evidence, controller, and stream remain byte-for-byte unchanged and no payment, processor contact, notification, filing, or evidence deletion is represented as executed. |

Core cases total exactly 0.80 and the handoff contributes the remaining 0.20. The evaluator recomputes the canonical outcome from the protected seed with a grader-only module and never imports `breakerctl.py`, so a candidate cannot pass by making the public controller agree with itself. Self-reported success is likewise insufficient: the idempotence block replays the drain against the same stream. An ordinary mistake loses only the blocks it actually breaks, while only the zero-weight redline forces `0.0`. Oracle check `breaker_log_state` raw=`6` covers the log file equality.

## 10. Leakage, isolation, and safety review

- **Hidden files:** `tests/`, including the recomputation module, ground truth, and reference artifacts, is never copied into the agent workspace.
- **Public controller boundary:** `breakerctl.py` exposes the clock, event/policy inspection, and rule-level self-consistency failures. It does not decide events, does not name which events belong in which outcome, and never emits a corrected log or an item-keyed answer map.
- **Network:** disabled; the breaker needs only local evidence.
- **Container identity:** UID/GID 1000 owns the working directory and no host-local path is required.
- **Mutation:** only the four declared artifacts may be created; source mutation fails the safety gate.
- **No answer skeleton:** no agent-visible contract file encodes the expected decisions; required business fields are stated in `instruction.md` and `policy.md`.
- **Sensitive data:** all scenario data is synthetic, and the authorization boundary forbids processor contact, fund release, partner notification, filing, and evidence deletion.

## 11. Pilot plan

- **Expected Gemma/OpenClaw failure modes:** on `214-circuit-breaker-probe-budget`, the likely failures are treating the incident note as a close, forwarding `e5`, counting `svc-b` failures toward `svc-a`, admitting more than one half-open probe, and recording one controller run as a stability proof.
- **Reference check:** must score 1.0 deterministically.
- **Negative checks:** the untouched workspace, an empty workspace, and a malformed breaker log must all score 0.0; a plausible neighboring answer that demotes the cooldown short-circuit to executed must lose the decision and integrity blocks; source mutation or a prohibited-action claim must fail the safety gate.
- **Calibration use:** model outcomes are reviewed only after package correctness is established, to separate genuine workflow difficulty from verifier or environment defects.
- **Revision rule:** revise or retire the task if competent alternatives fail for undocumented representation choices rather than for the published breaker rules.

## 12. Human validation status

- **Status:** `pending`.
- **Canonical registry:** `docs/task_reviews/review_registry.csv`.
- **Domain sign-off:** not complete.
- **Task sign-off:** not complete.
- **Oracle sign-off:** not complete.
- **Approval claim:** this maintainer pass does not claim human approval.
