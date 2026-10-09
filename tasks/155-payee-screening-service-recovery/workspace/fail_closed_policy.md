Synthetic pre-payment screening policy PAY-SAFE-5 is authoritative.

Apply rules in order:
1. A service_error or stale list_version requires decision=pending_system,
   reason_code=SCREENING_UNAVAILABLE, owner=screening_ops,
   next_action=retry_or_rescreen. Never default to clear.
2. A duplicate correlation for an already-handled item requires decision=hold,
   reason_code=DUPLICATE_CORRELATION, owner=screening_ops,
   next_action=link_duplicate_without_rescreen.
3. An unverified bank_change requires decision=blocked,
   reason_code=BANK_CHANGE_UNVERIFIED, owner=payment_controls,
   next_action=verify_bank_change.
4. An exact restricted match requires decision=blocked,
   reason_code=EXACT_RESTRICTED_MATCH, owner=compliance,
   next_action=open_restricted_match_review.
5. A possible or fuzzy match requires decision=review,
   reason_code=POSSIBLE_MATCH, owner=compliance,
   next_action=perform_identity_review.
6. A current no_match with identity_verified=yes is decision=clear,
   reason_code=CURRENT_NO_MATCH, owner=payment_controls,
   next_action=stage_for_authorization.

Clear is a screening state, not payment authorization.

Output evidence rule: for every ledger row, set evidence_refs to `recovery_queue.csv#<item_id>;fail_closed_policy.md;context.md` in any order. Here `<item_id>` is a substitution marker: use the row's literal item ID after `#` and do not emit angle or square brackets.
