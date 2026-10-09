# Admit an offline patchset through checks, CODEOWNERS, and rebase

You are the on-call merge engineer at Westline Platform. An offline patchset is
parked in front of the merge gate. Required checks, CODEOWNERS, and the current
base SHA disagree with an incident note that `team-core` may approve docs.
Those sources do not agree.

Platform needs a decision an auditor can read, and a docs path must not be
admitted on a core-team approval alone.

Work only in `$WORKSPACE`. Start by inspecting the local evidence; useful inputs
include:
- `policy.md`
- `evidence/incident_brief.md`
- `policy/merge_policy.json`
- `staging/patchset.json`
- `mergectl.py`

## Deliverables

- `state/merge_log.json`: One decision per patch, the decision counts, and the
  admitted ids.
- `state/merge_receipt.json`: The same counts and admitted ids.
- `state/verification.json`: Record the controller command you ran, the result
  of each attempt, and whether re-running it left the state unchanged.
- `patchset_merge_handoff.md`: Explain the owner-versus-note conflict, why each
  class of patch resolved the way it did, the verification you performed, and
  the authorization boundary.

These files are a handoff to another practitioner, so choose clear prose and
stable local identifiers. The named business fields are required where stated,
but prose layout, explanation style, and additional useful context are up to you.

## Working rules

1. Read `policy.md` before recording decisions; it is authoritative over
   `evidence/incident_brief.md` where they disagree.
2. Apply the published precedence in order. CODEOWNERS outrank a human note.
3. Use `python3 mergectl.py validate` for feedback, and run it more than once so
   your verification record reflects repeat behavior rather than a single pass.
4. Create only the four declared handoff artifacts. Do not modify policy,
   evidence, the patchset, or the controller.

Keep all source evidence byte-for-byte unchanged except for a path explicitly
named as an in-place deliverable. Work offline. Do not execute or claim an
external, production, payment, filing, deletion, message-send, booking, or
account action. Before finishing, re-open the final JSON files and reconcile
their keys and totals across the handoff.
