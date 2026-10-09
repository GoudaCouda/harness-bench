# Shipment claim recovery handoff

CRR-20260819-01 was recovered locally. CL-A2 shares RoadStar tracking RS-9001
with older CL-A1, so CL-A1 is the duplicate survivor; EV-A2-SUP was routed to
that survivor. Events were de-duplicated by event ID and then interpreted by
carrier sequence: the repeated EV-B-SUP and EV-E-ACK deliveries were ignored,
the unknown-case delivery was ignored, and EV-G-SUP could not reopen CL-G1.
Although the denial arrived first in the delivery file, EV-F-SUP sequence 14
precedes EV-F-DEN sequence 15.

Evidence hashes and shipment identity were checked per line. CL-A1's shortage
has a signed BOL and matching invoice; its merged damage line has photos and a
matching invoice but no packaging, so only the 60 percent policy amount applies.
CL-B1 likewise receives the 60 percent damage amount. CL-C1 has a matching
invoice and signed BOL for the full shortage amount. CL-D1 remains held because
BL-D1-I names SHIP-WRONG rather than SHIP-D; its signed BOL cannot cure invoice
identity. Amounts and claim lines reconcile exactly once through the survivor.

CL-F1 is first in packet order because its denial response deadline is
2026-08-24. CL-E1's carrier acknowledgment preserves its existing submission
timestamp and does not resubmit. CL-G1 remains closed and paid with its closed
timestamp and paid amount unchanged.

The interrupted CL-B1 journal entry was restored before the atomic recovery
commit. Verification binds the source checkpoint and normalized semantic plan
to the claim projection and event receipts. The local claim packet bundle and
packet manifest hashes close to the recovery receipt; semantic replay was a
byte-stable no-op.

The packet remains local and not submitted. No claim or denial response was
submitted, no carrier was contacted, and no payment or refund was executed.
