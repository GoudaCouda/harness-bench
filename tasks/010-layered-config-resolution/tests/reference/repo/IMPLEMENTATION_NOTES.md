# Implementation notes

## Decision

Resolution uses CLI, environment, file, then default precedence. Membership is
distinct from truthiness, so CLI false and explicit nullable null win. Invalid
values in the winning layer fail closed instead of falling back. Values are
typed from schema rules and sensitive diagnostic values are redacted.

## Verification

I ran `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` from
`repo`; both public tests passed.

## Remaining risk

The pure resolver does not prove the service launcher passes an exact CLI
presence map rather than parser defaults. That adapter needs an integration
test before rollout. No service start, secret-store access, or deployment was
performed.
