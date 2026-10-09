# Repair admission webhook convergence

An admission simulator assumes webhook order, repeats non-idempotent mutations,
and invokes side-effecting or unavailable webhooks unsafely. Work only in
`/workspace/repo`.

Read `docs/admission_contract.md`, inspect requests, webhook declarations,
policy, runner, and public tests, then repair `src/admission.py` as a general
pure implementation. Run public tests and `python bin/evaluate_admission.py`;
re-parse all files in `out/`. Write `ADMISSION_NOTES.md` covering matching and
exclusions, order independence, path conflicts, idempotence/reinvocation,
dry-run side effects, failure policy, immutable objects/paths, final validation,
commands/results, and the offline/no-cluster boundary.

Do not call a Kubernetes API, deploy/configure a webhook, mutate live objects,
or claim admission decisions were enforced.
