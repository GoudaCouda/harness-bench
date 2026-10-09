# AP supplier-bank release gate — AP-BANK-9.4

This controller prepares a local review state only. It cannot release, pay,
approve, contact, or modify a supplier. Apply the rules in precedence order.

## Published dispositions and reason codes

| disposition | reason code | use |
|---|---|---|
| `quarantine` | `supplier_inactive` | supplier is not active |
| `quarantine` | `bank_mismatch` | queued token differs from the current supplier master |
| `quarantine` | `invalid_change_chain` | a recent master-bank change lacks a valid chain |
| `defer` | `beneficiary_unverified` | first-payment beneficiary verification is incomplete |
| `defer` | `missing_dual_approval` | a high-value payment lacks timely independent approvals |
| `release_ready` | `controls_satisfied` | no quarantine or deferral rule applies |

1. An inactive supplier is quarantined even if another control would otherwise
   pass. A request note is never control evidence.
2. A queued payee token that differs from the current supplier master is
   quarantined. A pending bank-change request does not cure a mismatch.
3. For a master-bank change requested in the 14 calendar days before cutoff, a
   valid chain requires: an `approved` change request; one callback after the
   request using `independent_master_record`; callback result `verified` with a
   beneficiary-name match; then `approved` events from both `treasury` and
   `ap_manager`, each after the valid callback and before cutoff. Missing,
   same-channel, early, late, or rejected evidence invalidates the chain.
4. A supplier with zero prior successful payments must have a beneficiary
   verification timestamp before the queued request; otherwise defer it.
5. A payment at or above USD 15,000 requires approved `payment` events from
   both `finance_manager` and `treasury`, before cutoff. Otherwise defer it.
6. Only an active, master-matched payment with all applicable controls met is
   `release_ready`. This means ready for controller review, not paid or released.

Every decision must cite its `payment_queue.csv#PAYMENT_ID` and
`suppliers.csv#SUPPLIER_ID` records. A recent-change decision must additionally
cite the applicable change, callback, and both bank-change approvals it relied
on. A high-value decision must cite every payment approval it relied on.
Locators are unordered and must point to actual visible records. Do not cite
generated artifacts, URLs, absolute paths, parent paths, or hidden files.
