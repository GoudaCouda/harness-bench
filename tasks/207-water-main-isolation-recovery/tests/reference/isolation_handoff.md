# Offline water-main isolation recovery handoff

## Authority and telemetry intake

Distribution control used only the protected network database, the source manifest, the local telemetry delivery file, and the published isolation policy. Delivery order was not treated as business order. D-002 and D-004 are exact redeliveries and were ignored. D-051 and D-052 were both quarantined because EV-COLLIDE-04 reused one event identity with conflicting bodies. D-061 and D-062 were both quarantined because different identities occupied V-06 source sequence 8. D-091 names unknown V-99 and was ignored. D-011 is not newer than V-01's high-water mark, so it was ignored as stale. D-071 could not alter maintenance-locked V-05. Current accepted observations leave V-03 operable and establish V-02 as stuck open.

## Boundary adjudication

- B-A affects 120 connections and no critical service, but it is inadmissible because required V-02 is stuck open.
- B-B affects 145 connections across Z-EAST and Z-NORTH, has no critical-service outage, and both V-03 and V-04 are operable and unlocked. It is admissible.
- B-C would affect 80 connections but crosses the maintenance lock on V-05, so it is inadmissible.
- B-D would affect only 60 connections, but it would interrupt the Z-HOSPITAL critical feed through V-07, so it is inadmissible.

B-B is therefore the admissible minimum-impact boundary. The local projection stages V-03 and V-04 as desired closed while preserving their physical positions. V-02 remains open and unavailable pending field assessment; V-05 remains under its maintenance lock; V-07 remains an open critical feed; and V-01 and V-06 remain open outside the selected boundary.

## Recovery and closure

The open J-INT-V04 journal restored V-04's before-image and removed the interrupted projection before one atomic seven-valve projection committed. Verification reopened SQLite and reconciled the recovery identity, protected source checkpoint, normalized plan hash, journal closure, seven projections, and unchanged physical valve positions. The staged isolation-review packet and this handoff are bound by SHA-256 values in the packet manifest. Reordering valve rows, delivery rows, set-valued fields, or JSON formatting is a semantic replay no-op and leaves the database byte-identical.

This is an offline synthetic planning exercise only. No physical valve was operated, no water service was interrupted, and no crew, customer, hospital, regulator, approval workflow, notification channel, or external system was contacted, dispatched, submitted to, or changed.
