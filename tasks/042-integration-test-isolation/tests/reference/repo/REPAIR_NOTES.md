# Isolation repair notes

Every test now receives a recursively isolated copy of the fixture, so nested
lists and objects cannot leak state into a later test. Each random stream is
seeded from the global seed plus stable test ID using the specified FNV and LCG
steps; changing suite order therefore cannot change a test's sample.

Quarantine remains bounded evidence rather than a skip mechanism. The runner
always executes assertions, labels an actual failure `quarantined_failed` only
through the inclusive expiry day, and exposes it as a regular failure afterward.
A quarantined test that passes is reported passed, preserving both recovery and
real regression signals. Verification used
`PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v`; all public
tests passed successfully. Integration risk: the descriptor runner cannot model
external service contamination, so production CI still needs process/container
isolation for those fixtures. No external CI or quarantine record was changed.
