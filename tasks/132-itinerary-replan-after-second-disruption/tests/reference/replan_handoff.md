# Local itinerary recovery handoff

## Authority and event recovery

The valid signed inventory snapshot `INV-20261014T221000Z` (ETag
`inventory-v37`) was checked against the local trust material and remained valid
at the policy as-of time; its signature was verified. Delivery order was
normalized by sequence. `EVT-501`, `EVT-502`, and `EVT-503` were applied once;
repeated delivery `DLV-02` of `EVT-501` was ignored as a duplicate. The earlier
interrupted journal was recovered before this recovery was committed atomically.

## Option decision

O-F is the selected proposal. It preserves reviewed LEG-1 and replaces only the
cancelled LEG-2, meets the 75-minute connection rule, arrives at 16:05 PDT before
the curfew, supports WCHR and a through-checked bag, stays within US/Canada
transit authority, connects to accessible shuttle SH-1700, and leaves the hotel
and event windows intact. O-D misses the minimum connection. O-E arrives after
curfew and misses the dependent timing windows. O-G requires unauthorized GB
transit, a checked-bag recheck, and arrives the next day. O-I has no accessible
shuttle connection. O-H is feasible and CAD 180 versus O-F's CAD 260, but it
replaces both reviewed air legs and is cheaper; the published minimum-change
objective therefore dominates cost and correctly retains O-F.

## Minimal object delta and local stage

AIR-1, the inactive RAIL fallback, HOTEL H-VAN-22, CAR not-needed state, and
EVENT EV-VAN-0915 were preserved. AIR-2 is a local proposal hold for OF-2,
SHUTTLE is a local proposal hold for accessible SH-1700, and REFUND is only a
staged local request for cancelled LEG-2. The receipt contains two local hold
tokens and one local request token. The RFC 5545 itinerary is TENTATIVE.

Verification closed the source checkpoint, semantic plan, exact SQLite object
projection, event deduplication, objective, revision, and recovered journal.
Semantic replay left the database, receipt, and calendar byte-stable with one
committed recovery identity.

No booking, cancellation, refund submission, purchase, payment, or message was
executed. All holds, requests, and calendar entries remain offline proposals for
human review.
