# Reconcile CODEOWNER coverage after a cross-cutting refactor

You are the repository review coordinator preparing a protected-branch handoff.
The pull request moves payment code across generated, infrastructure, docs,
secrets, release, shared, and workflow paths. Ownership rules overlap, several
reviews are path-scoped, and some reviews target an old SHA or were dismissed.

Use only these local inputs in `$WORKSPACE`:

- `policy.md`
- `codeowners.csv`
- `changes.json`
- `reviews.json`

Create these deliverables in `$WORKSPACE`:

- `path_coverage.csv`, with columns `path,owner,approval,reviewer,reason` in that
  order and one row for every changed path;
- `review_state.json`, containing `head_sha`, `satisfied`, `missing`, `blocked`,
  and `decision`;
- `review_request.md`, explaining ownership precedence, path scoping, stale or
  dismissed reviews, current blockers, exact follow-up, and verification.

Apply the last-matching CODEOWNER rule. A review qualifies only when it is an
approval from the resolved current team, targets the current SHA, and covers
the path under the review's optional `paths` scope. A current-team
`changes_requested` review is blocking. Old-SHA and dismissed reviews do not
satisfy ownership and are missing rather than current blockers.

In `review_state.json`, represent all three buckets consistently: either use
integer counts for all three or exact path arrays for all three. Derive them
from the final ledger and re-parse all deliverables before finishing. Do not
modify source evidence, use the network, request reviews externally, or claim a
merge/production action was executed.
