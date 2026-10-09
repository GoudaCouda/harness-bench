# Restore paging in an isolated Alertmanager control-plane rehearsal

You are the on-call platform engineer for incident `INC-482`. During a local
rehearsal, a critical payments root-cause alert went to a low-priority receiver
and was also covered by an unsafe service-wide silence. Repair both the checked-
in configuration and the stateful rehearsal, then leave a reviewer-ready
handoff.

Everything you may edit is under `$WORKSPACE`. Start with:

- `incident/INC-482.md`
- `repo/runbooks/alert-routing.md`
- `repo/alertmanager.yml`
- `repo/testdata/public_cases.json`
- `repo/tools/check_public_routes.py`

The trusted runtime publishes a pinned offline validator for the bounded
Alertmanager 0.32.1 configuration profile used by this rehearsal. It checks
YAML, UTF-8 matcher and RE2-compatible regex syntax, receiver references,
inhibition shapes, and routing behavior without network access. Its path is in
`$ALERTMANAGER_VALIDATOR`; the evaluator independently executes the protected,
content-addressed source for the same fixed profile.
The management endpoint is a stateful, isolated control-plane emulator for the
declared Alertmanager API subset; it is not an Alertmanager daemon and it is
never production. The trusted runtime has created `$ALERTMANAGER_ENV`; load it
to set the capability-scoped `ALERTMANAGER_URL` for this run. The portable
command below works in the task tool's default POSIX shell:

```bash
. "$ALERTMANAGER_ENV"
"$ALERTMANAGER_VALIDATOR" --version
```

That URL is the only authorized management endpoint. A successful reload binds
the rehearsal ledger to the SHA-256 of the current `repo/alertmanager.yml`;
the evaluator separately validates that same file with its protected validator.

## Deliverables

1. Modify `repo/alertmanager.yml` to implement the runbook with real
   Alertmanager semantics:

   - every critical alert routes only to `platform-page`;
   - payments warnings route only to `payments-low`;
   - other alerts inherit `operations-low`;
   - grouping uses `cluster`, `service`, and `alertname`;
   - a critical alert inhibits a warning only when those same three identity
     labels match; and
   - all receiver destinations remain loopback-only.

2. Repair the stateful rehearsal through the capability-scoped v2 API. Inspect the
   API state rather than assuming a silence ID. Expire only the active silence
   whose sole matcher is `service=payments`. Ensure exactly one active
   replacement matches both `service=payments` and `alertname=DeployNoise`,
   starts at execution time, lasts 90 minutes, and identifies `INC-482` plus the
   local rehearsal in its comment. Then request a reload of the current
   `repo/alertmanager.yml` and confirm readiness. For `/-/ready`, HTTP 200 is
   the readiness signal; a successful response may have an empty body.

   Exercise the workflow twice. It must be safe after full or partial
   completion: do not create a duplicate replacement or touch unrelated or
   expired silences. If reload returns a transient 5xx, retry only the reload
   after a short backoff: make at most three additional reload attempts, obtain
   a successful reload within 30 seconds of the first failure, and do not check
   readiness until reload succeeds. Do not repeat completed silence mutations
   merely because reload failed. You may keep a temporary helper under
   `/runtime`, but it is not a deliverable and must not be added to the
   repository.

3. Create `change_record.md` for the next on-call engineer. Record the root
   cause, configuration and silence changes, checks you actually observed,
   transient reload recovery, the duplicate-free second run, rollback, and the
   fact that no production endpoint or production action was involved.

## Stateful rehearsal verification

Use the published local configuration validator and the trusted stateful
endpoint, not a self-authored pass file. Load the environment first so the
validator path and capability URL are both unambiguous:

```bash
. "$ALERTMANAGER_ENV"
"$ALERTMANAGER_VALIDATOR" check-config repo/alertmanager.yml --utf8-strict
python repo/tools/check_public_routes.py repo/alertmanager.yml
# Inspect and repair the authorized API, then repeat your workflow once.
```

The second execution is the idempotence check. The permitted API surface is:

- `GET /api/v2/silences`
- `DELETE /api/v2/silence/{silenceID}`
- `POST /api/v2/silences`
- `POST /-/reload`
- `GET /-/ready`

Modify only `repo/alertmanager.yml` and `change_record.md`. In the handoff,
describe the endpoint accurately as an isolated control-plane rehearsal rather
than claiming that a real Alertmanager daemon or production system was changed.
Keep the incident, runbook, public cases, checker, and `repo/ops/.gitkeep`
unchanged. Do not add a helper or validation report to the repository, and do
not claim that prose proves an action: the evaluator uses its protected pinned
validator plus a controller-owned post-round API ledger whose successful reload hash
must match the final candidate configuration.
