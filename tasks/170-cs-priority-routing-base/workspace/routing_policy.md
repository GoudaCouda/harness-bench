# Service desk priority and routing policy — version 4.1

Use the exact decision codes. Apply rules in order.

1. An acknowledged case never pages again: `hold`, reason
   `already_acknowledged`, owner `current_owner`, action `monitor_ack`.
2. A duplicate alert fingerprint: `hold`, reason `duplicate_alert`, owner
   `queue_control`, action `link_alert`.
3. Safety impact or multi-region outage: `p1`, reason `critical_impact`, owner
   `incident_response`, action `page_primary`.
4. More than 20 customer accounts affected with a deadline under four hours:
   `p2`, reason `broad_urgent`, owner `specialist_queue`, action
   `assign_specialist`.
5. All remaining single-account cases: `p3`, reason `limited_impact`, owner
   `general_queue`, action `assign_general`.
