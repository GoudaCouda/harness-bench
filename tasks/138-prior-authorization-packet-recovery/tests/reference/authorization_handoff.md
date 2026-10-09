# Prior-authorization recovery handoff

For synthetic case PA-502, the recovered packet preserves patient PAT-4102, member MEM-8731, payer SYN-PAYER-A, service code 72148, diagnosis M54.16, service dates 2026-09-15 through 2026-09-30, and authorization window 2026-09-15 through 2026-10-14. Eligibility EV-ELIG-12 and order EV-ORD-05 are current after sequence ordering; older events were superseded, duplicate deliveries were ignored, and the wrong-member eligibility event was rejected.

The minimum-necessary packet contains DOC-ORD-77, DOC-CLN-22, and DOC-PT-09. DOC-CLN-OLD was stale, DOC-PSYCH-4 was a sensitive psychotherapy note, DOC-WRONG-MEMBER had the wrong member, DOC-UNSIGNED-PT was unsigned, and DOC-LAB-EXTRA was unnecessary, so each was excluded.

The interrupted SQLite journal restored the before-images for ATT-PART-502 and Q-PART-502 before one atomic local projection created Q-PA-502. ATT-SUB-401 remains submitted with its payer reference, and ATT-DEN-402 remains denied with its denial timestamp; neither irreversible boundary was reopened. Hash verification closes the source checkpoint, semantic plan, state, packet, manifest, and receipt. Equivalent replay was an idempotent no-op.

Everything remains an offline local staging artifact. No payer transmission, clinical or coverage decision, patient notification, appointment scheduling, or external contact occurred.
