# Admission convergence handoff

The analyzer first matches operation and resource and then uses namespace
exclusions to exclude scoped requests. It does not treat the configured
webhook list order as semantic.
Applicable writes are collected before mutation: same-path, same-value writes
converge, while different values are a mutation conflict and reject the
request. Missing-field defaults preserve user values; enforced values are
applied only after the whole mutation set passes safety checks.

Mirror pods and immutable paths are rejected before mutation. An unavailable
webhook with failurePolicy Fail blocks, while Ignore removes that webhook from
the active set and still requires final validation. A dry-run accepts only
`None` or `NoneOnDryRun`; these side effects are checked before mutation, and
the stricter local policy requires `None` for every
request. Append is a non-idempotent mutation and is rejected because
reinvocation can duplicate it. These rules make the combined webhook set
idempotent and order independent, rather than trusting a convenient invocation
sequence.

Verification passed with `python -m unittest discover -s tests -v` and
`python bin/evaluate_admission.py`. I parsed all three JSON outputs: five
requests produced three admitted, one unchanged, and one blocked result. The
final objects preserve exclusions/defaults and do not include the blocked
side-effect mutation. This was an offline, no-cluster exercise. I did not call
Kubernetes, deploy or configure a webhook, mutate a live object, or claim any
decision was enforced.
