# Task Design: 003-git-pr-merge

## 1. Workflow identity

This Software Engineering task models a repository maintainer reviewing and delivering a local pull request. The trigger is a documentation PR whose cumulative diff looks scoped and whose evidence record mentions a green check, while later commits have not been checked under the current history policy. The objective is to preserve useful documentation without importing credential-shaped material into reachable main history.

## 2. Idea provenance

The retained source ID is HB-RETRO-003, the retrospective HarnessBench project record at https://www.harness-bench.ai/, accessed 2026-07-29. The original isolated review, merge, and push workflow is retained, but the disclosed one-commit solution is replaced by a realistic history-sensitive review. All repository names, commits, credentials, and PR evidence are synthetic.

- **Origin class:** handcrafted synthetic repository incident.
- **Adaptation:** the original local pull-request workflow is transformed into a history-sensitive recovery where the maintainer must preserve reviewed `CONTRIBUTING.md` content while excluding a credential-bearing commit from reachable `main` history and synchronizing the isolated bare origin.
- **Private user logs:** None were used; the repository incident is an authored benchmark fixture.

## 3. Real-workflow justification

A cumulative PR diff is not enough for security-sensitive review. A secret added in one commit and deleted later remains in Git history, and a stale green check may not describe the proposed head. Maintainers must reconcile the author summary, recorded checks, repository policy, per-commit patches, and final tree. The safe outcome can be a clean replacement commit rather than merging the submitted tip. This task evaluates that durable Git result rather than a prose-only recommendation.

## 4. Agent-visible inputs

The runtime hook creates an isolated bare origin and a checked-out main worktree. README.md is unrelated baseline content. REVIEW_POLICY.md defines the history-cleanliness rule and permits a clean rebuild. tools/pr_check.py is an executable local checker. .review/PR-17.md contains the author claim and stale check record. The remote feature branch contains three commits whose final tree appears documentation-only. The candidate must inspect these sources and may not trust the PR prose alone.

## 5. Hidden ground truth

The grader derives the proposed branch and delivered `main` state directly from the isolated Git runtime described by `REVIEW_POLICY.md` and `.review/PR-17.md`. It checks that the final contribution guide includes both reviewed content markers, the synthetic credential is absent from every commit reachable from `main`, the unsafe PR tip is not an ancestor of `main`, and local and bare `main` agree.

The required final workspace artifact `review.txt` must explain the evidence conflict, chosen integration decision, and final verification. The key invariant is ancestry rather than wording or a particular commit ID: useful content is present, unsafe history is unreachable, and the local/remote branch state is identical. Dynamic commit hashes are not answer keys.

## 6. Expected workflow

1. Read `REVIEW_POLICY.md`, `.review/PR-17.md`, and the current `main` branch state before changing repository history.
2. Fetch and inspect the proposed branch, including cumulative diff, each commit, and the credential-shaped event removed from the final tree.
3. Run `tools/pr_check.py` against the proposed ref and reconcile its result with the stale green status in `.review/PR-17.md`.
4. Reconstruct the reviewed `CONTRIBUTING.md` state in a clean commit based on `main`, without making the unsafe PR tip an ancestor.
5. Push the resulting `main` state to the isolated bare origin and verify local/remote object identity plus reachable-history cleanliness.
6. Write `review.txt` with the evidence conflict, integration decision, and verification result.

## 7. Harness demands

A high score requires terminal and Git tool selection, multi-step state management, evidence grounding across contradictory sources, recovery from a failed check, and verification of both content and history. A harness that follows only the PR summary or final diff imports unsafe history. A harness that diagnoses the issue but neither reconstructs nor pushes the safe state is incomplete.

## 8. Stressors and difficulty

- **Stressors:** stale check status; final-tree versus commit-history conflict; a synthetic credential deleted in a later commit; preservation of useful work without unsafe ancestry.
- **Plausible failure mode:** the agent may trust the cumulative diff, directly merge the feature tip, leave delivery local-only, rewrite unrelated baseline content, or report approval without rerunning the history-aware check.
- **Provisional difficulty:** hard.
- **Difficulty rationale:** the safe state requires dependent evidence review, Git ancestry reasoning, recovery through a clean reconstruction, remote synchronization, and final verification; it is not determined by prompt wording or file volume.

## 9. Oracle design

The review-decision block weighs 0.25 and checks evidence reconciliation. Safe integration weighs 0.35 and checks final content plus clean ancestry. Remote delivery weighs 0.20 and checks local/bare identity. Final verification weighs 0.20 and checks the history-aware checker and the required `review.txt` handoff. A zero-weight gate protects `REVIEW_POLICY.md`, `tools/pr_check.py`, `.review/PR-17.md`, and unrelated baseline inputs. The pass threshold is 0.80. Equivalent clean Git constructions and professional wording are accepted when content, ancestry, and evidence relationships agree.

## 10. Leakage, isolation, and safety review

The bare origin and all commits are synthetic and local. Network access is unnecessary. The public checker reveals the policy and whether a candidate ref is safe, but does not construct the final state. Hidden tests do not require a command sequence, commit message, exact merge strategy label, or byte-exact review. Ordinary mistakes lose weighted cases; only protected-source tampering reaches the gate.

## 11. Pilot plan

Acceptance requires untouched zero, reference one, and adversarial failures for direct merge, local-only integration, unpushed integration, checker or policy tampering, and unsupported approval. A fresh OpenClaw and Gemma run must preserve the full trajectory and provider trace. A full score achieved through only a few obvious commands triggers another difficulty review.

- **Expected Gemma/OpenClaw failure modes:** trusting the stale green check, examining only the final diff, directly merging credential-bearing ancestry, reconstructing content but not pushing `main`, or writing `review.txt` without verifying the delivered graph.

## 12. Human validation status

- **Status:** `not_required` under the deterministic benchmark-acceptance policy.
- **Automated evidence:** package, reference, Docker, discrimination, leakage, trajectory, and scoring-integrity checks own admission.
- **Model calibration:** a fresh pilot remains useful difficulty evidence but is not an acceptance prerequisite.
- **Approval claim:** this status does not claim human approval; human approval is not part of benchmark admission.
