# Diagnose a mixed CI run without wasting retries

You are the CI reliability maintainer taking over a run that mixes valid
successes, deterministic code failures, transient runner loss, an exhausted
runner retry, a stale artifact, and a fail-fast cancellation. The handoff must
preserve completed work and distinguish jobs that are recovered from jobs that
still block the run.

Use only the local evidence in `$WORKSPACE`:

- `policy.md`
- `attempt1.json`
- `retry_update.json`
- `patch_evidence.json`
- `package_update.json`

Create these deliverables in `$WORKSPACE`:

- `job_ledger.csv`, with columns
  `job,classification,action,final_attempt,final_status,evidence` in that order
  and one row per required job;
- `run_state.json`, containing `head_sha`, a per-job `retry_budget_used` object,
  `preserved_jobs`, `pending_jobs`, `artifact_digest`, and final `status`;
- `diagnosis.md`, explaining each recovery class, remaining blocker, evidence,
  retry accounting, and verification.

Apply `policy.md` before interpreting updates. A code failure may reach a later
attempt only when matching patch evidence exists. A runner loss may consume at
most one retry. A fail-fast-cancelled job waits for upstream blockers rather
than consuming runner budget. The old-SHA package pass is not reusable; use
only a current-head artifact. `final_attempt` and `final_status` describe the
latest evidenced state, including unresolved failures.

Derive aggregate state from the completed ledger and re-parse every CSV/JSON
artifact before finishing. Do not modify source evidence, use the network, or
claim that a CI rerun, patch, upload, or external production action was
actually executed beyond what the supplied snapshots record.
