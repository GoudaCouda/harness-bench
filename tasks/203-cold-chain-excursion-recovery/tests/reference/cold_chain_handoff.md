# Cold-chain recovery handoff

The protected source checkpoint was verified before mutation. Logger wall times
were normalized with each explicit UTC offset, so the repeated 01:00 hour across
the America/New_York DST fold remained ordered. Identical P-C1 duplicate sequence
4 was deduplicated; no conflicting duplicate was accepted.

LOT-AURORA's P-A1 gap from 05:30 through 06:00 UTC was closed only by S-A1.
Assignment ASN-SA covers the whole gap, calibration CAL-SA-2026 was in force,
and signed range RANGE-A-50-53 bound the exact logger checksum. After its -0.1 C
offset, three consecutive readings exceeded the inclusive 8.0 C ceiling from
05:40 through 06:00 UTC, meeting the 20-minute excursion rule. The lot is retained locally
in do-not-use quarantine. Door event DOOR-17 explains context but grants no waiver.

LOT-BIRCH remains on an evidence-gap hold. Its primary gap has apparent S-B1
readings, but CAL-SB-OLD expired before the gap and therefore cannot authorize
them. MOVE-22 grants no waiver. LOT-CEDAR has complete authoritative P-C1 data,
stays within 2.0--8.0 C, and remains available without a mutation.

Apply restored the interrupted LOT-AURORA before-image before atomically writing
the new assessments and holds. Verify closed the exact inventory, journal,
and recovery identity; staging produced only a local QA packet, and semantic
replay was an idempotent byte-stable no-op.

No stock was destroyed or released, no vaccine was administered or shipped, we
did not notify any recipient or regulator, and no external action was executed.
