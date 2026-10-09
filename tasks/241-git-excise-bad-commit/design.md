# Task Design: `241-git-excise-bad-commit`

## 1. Workflow identity

- **Domain:** Software Engineering
- **Role:** release engineer removing a leaked middle commit
- **Trigger:** a cutover branch still contains a credential-shaped commit between two legitimate changes
- **Objective:** rebuild main so later docs remain and the leaked commit is not reachable
- **Irreversible boundary:** no secret-store rotation ticket, no host notification, and no force-push to an external network

## 2. Idea provenance

| Source ID | Source | URL | Accessed | Adaptation |
|---|---|---|---|---|
| GIT-DIFF | Git diff documentation | https://git-scm.com/docs/git-diff | 2026-09-11 | Grounds inspecting per-commit patches rather than the final tree |
| GITHUB-STATUS-CHECKS | GitHub required status checks | https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/about-status-checks | 2026-09-11 | Motivates a local history-aware check that must pass before delivery |

All names, identifiers, and fixture values are synthetic.
- **Private user logs:** None were used.
- **Synthetic-data statement:** Every file, commit, SQL statement, and JSON record in this package was authored for the benchmark; no production dump was copied.
- **Adaptation:** An isolated Git remote holds a three-commit cutover branch whose middle commit is prohibited.

## 3. Real-workflow justification

Operators often delete a leaked file on HEAD and merge. The later legitimate commit makes cherry-pick or rebase-onto the real repair, unlike rewriting an entire unsafe PR tip.

## 4. Agent-visible inputs

Runtime hooks materialize the Git workspace. `HISTORY_POLICY.md`, `tools/hist_check.py`, and `README.md` are protected. Branch `work/cutover` is checked out.

## 5. Hidden ground truth

The hidden oracle inspects worktree and `origin/main` independently of `hist_check.py`. Required markers are `HELIX_APP_READY` and `HELIX_RUNBOOK_OK`. The synthetic token must not appear in any patch reachable from main. The leaked filename must be absent from the main tree.

The required final workspace state is `review.txt`.
The durable record keeps a stable key for each decision in `review.txt`.

## 6. Expected workflow

1. Read the policy and inspect `git log -p`.
2. Identify the middle leaked commit versus the later runbook commit.
3. Rebuild main by cherry-picking or rebasing onto main while skipping the leaked commit.
4. Push origin/main and rerun the history check.
5. Write review.txt with the rewrite evidence and residual risk.

### Novelty review

| Nearest task | Similarity | Substantive differences |
|---|---|---|
| `003-git-pr-merge` | unsafe Git history with a credential-shaped commit | 003 rebuilds from a PR whose HEAD tree is already clean; 241 must keep a later commit after dropping the middle leak |
| `005-repository-regression-bisect-repair` | Git history surgery | 005 bisects a regression; 241 excises one known bad commit |

1. Read the protected inputs and record their state before editing `review.txt`.
2. Apply the published rule to the key fields that determine `review.txt`.
3. Write `review.txt` and verify the resulting state against the visible contract.

## 7. Harness demands

The task requires Git inspection, history rewrite, remote delivery, a written review, and an offline safety boundary.

## 8. Stressors and difficulty

- **Stressors:** history versus final tree, a later good commit after a leak, remote main sync
- **Difficulty:** hard; deleting secrets.env on HEAD still fails the history check
- **Plausible failure mode:** merge the branch tip, reset away the runbook, or forget to push origin/main

- **Difficulty rationale:** a file-order or partial reading produces a different durable state than the published rule.

## 9. Oracle design

`clean_tree_and_history` (0.50 core) checks markers, absent secrets, and token-free main history. `remote_delivery` (0.30 core) requires origin/main to match local main. `review_handoff` (0.20 optional) checks review.txt. The gate requires protected policy files.

### Adjacent examples

- **Nearest valid:** cherry-pick the app commit and the runbook commit onto main, skip the leak, push.
- **Nearest wrong 1:** `git rm secrets.env` on the branch tip; history still contains the token.
- **Nearest wrong 2:** reset to the app commit and drop the runbook.

`review.txt` is a required final artifact checked by the hidden evaluator.

## 10. Leakage, isolation, and safety review

The synthetic token exists only in Git objects created at runtime. Hidden expected markers are not printed in the prompt. The evaluator does not import the public checker.

## 11. Pilot plan

Require reference `1.0` and empty/untouched/malformed `0.0`. Pilot Qwen + OpenClaw. Expect resets that drop the runbook or tree-only secret deletion.

- **Expected Gemma/OpenClaw failure modes:** follow file order, skip a conflicting record, or stop before the required final state is written.

## 12. Human validation status

- **Status:** `pending`.
- **Canonical registry:** `docs/task_reviews/review_registry.csv`.
- **Domain sign-off:** not complete.
- **Task sign-off:** not complete.
- **Oracle sign-off:** not complete.
- **Approval claim:** this maintainer pass does not claim human approval.
