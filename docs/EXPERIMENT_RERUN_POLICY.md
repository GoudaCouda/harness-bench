# Formal Evaluation Rerun Policy

This policy separates unusable infrastructure runs from otherwise complete runs
whose reasoning controls or replay semantics need later normalization. It applies
to evaluated configurations on the 274 general and 26 multimodal tasks. Coverage
is recorded separately for each model and modality.

## Priority 1: rerun now

A run is Priority 1 only when its result cannot be treated as a usable model and
harness attempt. Examples include:

- HTTP 401 or another authentication failure;
- a hard provider disconnect that leaves no complete response or usable trajectory;
- a verified infrastructure failure, such as a failed container setup or an
  unavailable model endpoint;
- a trace that is absent, truncated before a meaningful attempt, or structurally
  unusable for grading and audit.

Priority 1 runs are quarantined from the clean result set and rerun. A successful
replacement may supersede the contaminated attempt, while the original evidence
remains archived for diagnosis. Retries must not erase genuine model failures.

## Priority 2: record and defer

A run is Priority 2 when the attempt is complete and auditable, but the requested
reasoning configuration was not fully observed or its reasoning state was not
replayed across turns. Examples include:

- requested `high` or adaptive thinking differs from the provider-observed mode;
- reasoning content or encrypted reasoning state is not carried into a later turn;
- the trajectory, workspace, grader output, and model/tool exchanges are complete,
  but reasoning metadata is missing or inconsistent.

Priority 2 runs remain in the current result set with an explicit experiment
caveat. They are not rerun during the current recovery pass. A later controlled
rerun may be scheduled when the release policy changes or the required budget is
approved.

## Do not classify as infrastructure reruns

The following remain valid benchmark outcomes and stay in the denominator:

- a model or harness reaches a normal failure terminal;
- the agent works until the task time budget expires;
- the model produces an incorrect, incomplete, or low-scoring solution;
- a safety or protocol terminal is reached as designed.

Provider request timeouts that occur before a usable attempt are infrastructure
failures. Task-level timeouts after sustained agent work are benchmark outcomes.

## Current operating rule

Only Priority 1 recovery is active. Priority 2 cases are inventoried separately
and must not trigger bulk reruns. Every status update must report totals as:
model task units, usable completed units, Priority 1 reruns, and deferred Priority
2 units.
