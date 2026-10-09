# Offline mailbox DSN recovery handoff

The Maildir identity graph was reconciled by original `Message-ID`, not filename or copy order. The delivered invoice DSN closed its stale retry draft; the hard bounce was linked to the signed approval and produced one corrected-recipient draft pending human review. The delayed shipment remains under monitoring, while the renewal remains pending because its recipient-mismatched DSN was quarantined.

The duplicate delivered DSN was deduplicated. The orphan and mismatched DSNs were quarantined, and the retired-key approval was ignored. The prepared SQLite journal was rolled back before the new transaction committed. Verification passed, and an equivalent replay left the database and staged receipt byte-stable.

No message was sent, resent, forwarded, deleted from the source Maildir, or otherwise executed externally. The replacement remains a local draft for human review.
