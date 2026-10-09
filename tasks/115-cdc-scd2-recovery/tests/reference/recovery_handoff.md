# CDC-42 recovery handoff

The local batch was recovered and staged pending publish approval. No external publish, notification, deployment, or remote warehouse action occurred.

## Adjudication

EV-401 advances C001 from version 3 to version 4 and changes only the segment to enterprise. Its second delivery is byte-equivalent, so it is deduplicated by event ID and applied once. EV-402 arrived before EV-403, but sorting by entity version shows that EV-403 supplies C002 version 2 and EV-402 supplies version 3; together they close the complete 1→2→3 chain. EV-407 is an ordinary C001 version-2 event below the existing version 3 and is recorded as stale without rewinding history.

EV-408 is the verified CORR-88 steward correction for C001 version 3. It changes region to central. EV-401 does not explicitly change region, so version 4 inherits central; the correction does not disturb its enterprise segment. EV-404 is quarantined because C003 has active HOLD-77, and C003 remains at version 2 without a tombstone. EV-405 is quarantined because a new customer lacks consent provenance. EV-409 is quarantined because source schema 3 is unsupported. EV-406 is a valid schema-2 insert for C005 and consumes the durable prepared journal record without a duplicate application.

## Transaction and verification

The recovery committed one nine-action batch transaction. The event ledger has one final disposition per unique event, the prepare journal is committed, history intervals close at the next effective timestamp, and current projections match the final history rows. The controller verification passed for projections, history, ledger, quarantines, transaction count, and journal state. Re-running apply returned idempotent; re-running stage preserved the same digest-bound receipt. The package remains an offline local stage pending an independent publish approval.
