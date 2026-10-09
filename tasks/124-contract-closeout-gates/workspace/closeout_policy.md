# Contract closeout controller policy — revision CC-8

The review is as of the `as_of_date` stored in `closeout.db`. Process evidence
by numeric `event_sequence`, never by CSV row position. For acceptance, legal,
invoice, and funds gates, only the matching signed authority is controlling:
`acceptance_signed`, `legal_signed`, and `finance_signed`. A draft is retained
as history but cannot override signed evidence. Among signed events of one
contract and evidence type, the greatest event sequence is current. Evidence
for another contract or another gate never cures a blocker.

Apply this primary-blocker precedence:

1. `physical_complete` is false or latest signed acceptance is not `complete`:
   disposition `hold`, owner `program`, next action `complete_acceptance`;
2. latest signed legal evidence is absent or not `clear`: disposition `hold`,
   owner `legal`, next action `resolve_legal_hold`;
3. `option_end` is later than the review as-of date: disposition `hold`, owner
   `contracts`, next action `await_option_expiry`;
4. latest signed invoice evidence is absent or not `complete`: disposition
   `hold`, owner `finance`, next action `obtain_final_invoice`;
5. latest signed funds evidence is absent or not `complete`: disposition
   `hold`, owner `finance`, next action `complete_deobligation`.

When every gate is complete, use disposition `ready_for_controller`, owner
`controller`, and next action `approve_closeout_package`.

A recovery plan cites exactly `contracts.csv#<contract_id>`, every historical
event for that contract as `evidence_events.csv#<event_id>`, and
`closeout_policy.md#gate-precedence`. Duplicate, fabricated, unrelated,
absolute, parent, generated-output, hidden-file, and URL locators are not
evidence.

`ready_for_controller` is an internal proposal. This offline exercise must
never record a contract as closed, pay or release funds, notify a party, or
execute any external controller action. The local verification and stage
receipts are recovery evidence only, not external-action receipts.
