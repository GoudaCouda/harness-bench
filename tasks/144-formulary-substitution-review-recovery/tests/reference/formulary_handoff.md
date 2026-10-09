# Offline formulary-substitution recovery handoff

## Intake authority

The local benefit-event stream was reconciled independently of delivery order. DL-002 is an exact redelivery and was ignored. DL-011 and DL-012 reused one event identity with different content and were quarantined. DL-021 and DL-022 occupied RX-204 source sequence 7 under different event identities and were quarantined. RX-999 was unknown. Late traffic for RX-206 and RX-207 did not cross their dispensed and cancelled boundaries.

## Prescription review

- RX-201 is ready for local formulary review: FR-CARD-NEW was effective at prescription time and directly names GN-CARD-20.
- RX-202 is held for prescriber DAW code 1; no substitution was inferred.
- RX-203 is held for the EXC-LACTOSE allergy conflict in the proposed GN-NEUR-10 target.
- RX-204 is held because STEP-DERM is missing. Its interrupted ready projection was not accepted.
- RX-205 is ready through FR-IMM-1 because PA-205 is signed, hash-valid, unexpired, and the specialty channel matches.
- RX-206 remains at the dispensed protected boundary, and RX-207 remains at the cancelled protected boundary.
- RX-208 uses FR-CARD-OLD, the rule effective when prescribed, rather than retroactively substituting the current rule.
- RX-209 is held because FR-IMM-1 requires the specialty channel while this record remains retail.

## Recovery and closure

The J-INT-204 before-image restored RX-204 before one atomic nine-prescription local projection committed. Verification reopened SQLite and reconciled the journal, stable recovery identity, protected source checkpoint, normalized semantic plan hash, projection rows, and immutable source facts. The local formulary-review packet and this handoff are bound by SHA-256 in the packet manifest. Reordering decisions, events, set-valued fields, or JSON formatting is a semantic replay no-op and leaves SQLite byte-identical.

This was an offline administrative review only. We did not substitute, prescribe, dispense, cancel, adjudicate, authorize, approve, deny, contact, notify, transmit, or submit anything, and we did not change a pharmacy, benefit, prescriber, member, or clinical system.
