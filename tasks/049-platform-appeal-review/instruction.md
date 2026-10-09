# Review a batch of platform moderation appeals

You are the platform governance appeals reviewer. A daily appeal batch spans policy amendments, advisory automation conflicts, counterspeech, and privacy-sensitive reporter fields.

Your job is to recover the interrupted local appeal queue, apply the policy
version in force, explain each disposition, and stage a privacy-safe handoff for
governance review. This is local review state only: do not enact production
moderation or contact a reporter.

Work only in `$WORKSPACE`. Begin with:

```bash
python3 appealctl.py inspect
python3 appealctl.py query A-01 --json
```

`inspect` publishes the exact protected-source checkpoint, its calculation
contract, all controlled decision/action/confidence values, policy clause IDs,
the redaction-locator grammar, and current SQLite queue/journal state. `query`
returns a privacy-minimized case view plus its stable sensitive source paths;
query every case before deciding it. Then inspect the local evidence:
- `case_files/case_1.json`
- `case_files/case_2.json`
- `case_files/case_3.json`
- `case_files/case_4.json`
- `case_files/case_5.json`
- `case_files/case_6.json`
- `case_files/case_7.json`
- `moderation_policy.md`
- `policy_amendments.md`
- `state/appeals.db`

## Deliverables

- `appeal_decisions.csv`: Use columns case_id, decision, final_action, policy_basis, confidence; one row per case.
- `explanations.md`: Create one clearly labelled section per case and explain why the selected outcome is preferable to the main alternative.
- `redaction_audit.csv`: Use columns case_id, redacted_field, redaction_reason and name each sensitive source path separately with the published `case_files/case_<n>.json#/<reporter_field>` locator.

These files are a handoff to another practitioner, so choose clear prose and stable local identifiers. The named business fields are required where stated, but prose layout, explanation style, and additional useful context are up to you.

## Working rules

1. Read the base policy, amendments, and every case file. Apply effective dates from the appeal filing date rather than file order.
2. Use uphold, overturn, or downgrade; cite every clause that materially governs the outcome and calibrate confidence to evidentiary ambiguity.
3. Treat automation as advisory evidence, not the decision authority, and address material facts in the explanation.
4. Do not reproduce reporter identifiers or contact details in any deliverable.

For a stable downstream handoff, `final_action` must name the resulting
operational state: an overturned content removal is `restore`, not the generic
phrase `no action`. Use `high` confidence only for a clear base-policy outcome
with no competing evidence. Use `medium` when the decision depends on an
amendment/effective-date boundary, account-compromise evidence, a borderline
rule, or overriding an automation label with source context; reserve `low` for
an unresolved material evidence gap.

After drafting all three handoff files, use the guarded queue workflow:

```bash
python3 appealctl.py preview
python3 appealctl.py apply
python3 appealctl.py verify
python3 appealctl.py stage
python3 appealctl.py replay
```

`preview` is candidate-first: it writes `.appeal_preview.json` with only
per-case field, explanation, and redaction-category booleans; it never returns
correct values and never mutates SQLite. Repair every false category before
applying. `apply` restores the interrupted A-01 journal before committing the
seven local adjudications in one transaction. `verify` records independently
inspectable state, `stage` creates only a local pending-governance-review
receipt, and `replay` must be a byte-stable semantic no-op. Reordering decision
rows, clause-ID sets, or redaction rows does not change package identity;
changing a decision under the same recovery identity is a conflict.

Keep all source evidence, policies, cases, and `appealctl.py` byte-for-byte
unchanged. The only mutable supplied file is `state/appeals.db`. Work offline.
Do not execute or claim an external production moderation, reporter contact,
payment, filing, deletion, message-send, booking, or account action. Before
finishing, re-open the final CSV/JSON files and reconcile their keys, checkpoint,
revision, semantic digest, and totals across the handoff.
