# Caveats

ARR is a non-comparable trend because the new definition deducts refunds and credits; its decline is an expected definition change, not evidence of weaker recurring revenue performance. Activation rate is also non-comparable because the denominator changed from all signups to eligible signups, so its increase is not a like-for-like trend.

Retention is an unexpected regression for a different reason: the after-dashboard formula still uses `old_cohort_users`, while the migration policy and new definition require `new_cohort_users`. Its value delta cannot be accepted as a definition-driven change until that bad field is corrected and the export is rerun.
