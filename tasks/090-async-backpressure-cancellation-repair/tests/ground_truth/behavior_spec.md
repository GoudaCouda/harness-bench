# Hidden behavior cohorts

The evaluator executes synthetic coroutine cohorts for bounded concurrency,
input-order output, ordinary exception isolation, deadline cancellation,
caller cancellation propagation, validation-before-work, and absence of
surviving pool tasks. Concrete hidden timings and inputs are intentionally kept
out of the agent workspace; no additional business rule is defined here.
