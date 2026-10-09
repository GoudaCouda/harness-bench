# WebAuthn assertion-state contract

Implement `assess_assertions(credentials, assertions, policy)` without mutating
inputs. Structural violations raise `ValueError`; ordinary authentication
failures produce rejected decisions and continue.

Credentials are a sorted unique list with exact keys `credential_id`,
`user_id`, `sign_count`, `backup_eligible`, `backup_state`, `status`, `risk`,
and `last_assertion`. IDs are lowercase ASCII tokens. Count is an integer from
0 through 4294967295. Backup state may be true only when backup eligible.
Status is `active` or `revoked`, risk is `normal`, `elevated`, or `compromised`,
and last assertion is null or an assertion ID.

Assertions are ordered and have unique IDs plus exact keys `assertion_id`,
`credential_id`, `user_id`, `sign_count`, `backup_eligible`, `backup_state`,
`signature_valid`, `user_verified`, `origin`, and `rp_id`. Policy has exact keys
`allowed_origins` (sorted unique HTTPS origins), `rp_id`,
`require_user_verification`, `device_counter_action` (`reject` or `flag`), and
`synced_counter_action` (`flag` or `ignore`).

For each assertion, reject in this precedence: unknown credential, revoked
credential, user mismatch, invalid signature, disallowed origin, RP-ID mismatch,
missing required user verification, backup-eligibility mismatch, or illegal
backup state. These failures do not change any credential field.

After trust checks, classify counters. Two zero counters mean `unavailable` and
are accepted without changing count. A strictly larger assertion count is
`advanced`, accepted, and stored. Every other combination is `regression`.
For a device-bound credential, use `device_counter_action`; for a
backup-eligible credential, use `synced_counter_action`. `reject` marks risk
compromised but preserves count, backup state, and last assertion. `flag`
accepts, escalates normal risk to elevated, stores the maximum counter, updates
backup state and last assertion. `ignore` accepts with those same state updates
but does not escalate risk. Risk never de-escalates.

Accepted non-regressions update backup state and last assertion. Decisions have
exact keys `assertion_id`, `credential_id`, `decision`, `reason`,
`counter_status`, and `risk_after`. Unknown credentials report risk `unknown`;
pre-counter rejection reports counter status `not_evaluated`. Return sorted
credentials and decisions in assertion order. No cryptography, filesystem,
network, clock, process, random, browser, or environment access is allowed.
