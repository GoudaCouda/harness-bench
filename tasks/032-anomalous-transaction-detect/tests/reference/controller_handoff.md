# AP-RG-2026-08-19-15 controller handoff

This is a **review_only** local package. The recovered review has 9 payments:
3 `release_ready`, 4 `quarantine`, and 2 `defer`. The interrupted apply had two
prepared records and zero committed records; the controller rolled that attempt
back and atomically applied the complete source-bound plan.

- P-3201 is release-ready on the active supplier's unchanged master token.
- P-3202 is quarantined because the queued token does not match the current
  master. Keep it out of the release file and complete an independent callback
  before any master update is separately approved.
- P-3203 is release-ready: its recent change has an independent callback and
  both post-callback approvals before cutoff.
- P-3204 is quarantined because the callback reused the vendor email channel.
  Obtain a new independent callback and then collect new downstream approvals.
- P-3205 is deferred pending the missing treasury half of dual approval.
- P-3206 is deferred until AP onboarding records beneficiary verification.
- P-3207 is quarantined while the supplier is inactive; the owner must complete
  supplier reactivation under the separate master-data process.
- P-3208 is quarantined because both approvals predate its callback. Repeat the
  approval chain after valid callback evidence exists.
- P-3209 is release-ready with both timely high-value approvals.

No external payment, release, callback, contact, supplier update, bank change,
or approval was executed. Staging only makes the local proposal available for
human controller review.
