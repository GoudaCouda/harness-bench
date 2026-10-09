# Repair notes

## Decision

The planner invalidates direct owners for source, generated, and global inputs,
then closes over reverse dependencies. It rejects an invalid graph before
planning and orders affected packages by dependency depth with lexical ties.
Documentation-only paths do not create build work.

## Verification

I ran `PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` from
`repo`; both public tests passed.

## Remaining risk

The repository export does not exercise the production build tool's own target
discovery, so an integration test should compare planner package names with the
real workspace inventory before rollout. No CI run, cache purge, merge, or
deployment was performed.
