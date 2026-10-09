# Recover an interrupted injury-reporting projection

Take over synthetic employer `EMP-NORTHSTAR-17` after its local workplace
injury reporting projection crashed between SQLite writes. The inbox contains
duplicate and out-of-order deliveries, a foreign-employer delivery, signed
medical outcome revisions, an inactive issuer, incidents crossing local
midnight, and a verified OSHA submission that happened before this task.

This is an offline recovery exercise. You are distinguishing OSHA
recordability from time-limited OSHA reporting and preparing workers'
compensation notices, not deciding benefits or making a medical or causal
finding.

Start with the controller and visible evidence:

```bash
python3 injuryctl.py inspect
python3 injuryctl.py query "SELECT * FROM case_facts ORDER BY case_id"
python3 injuryctl.py query "SELECT * FROM case_state ORDER BY case_id"
python3 injuryctl.py query "SELECT * FROM external_submissions ORDER BY submission_id"
```

Read `policy/reporting_policy.json`, its source manifest, both JSONL evidence
streams, the observed submission, the interrupted recovery run, and every
applied before-image. Verify claim payload digests and synthetic signatures
with the published scheme and active authority scopes. De-duplicate an
`event_id` before applying employer, authority, and highest-sequence rules.
Use timezone-aware arithmetic: an incident and outcome can straddle local
midnight without being 24 hours apart.

Create `recovery_plan.json` with exactly these top-level fields:

```text
schema_version, employer_id, recovery_id, source_checkpoint,
event_receipts, case_outcomes, report_actions, external_actions_executed
```

- Each `event_receipts` object has exactly `delivery_id`, `event_id`,
  `case_id`, `stream`, `sequence`, and `disposition`.
- Each `case_outcomes` object has exactly `case_id`, `recordability`,
  `osha_reporting_path`, `deadline_utc`, `medical_category`, `cause_status`,
  and `workers_comp_action`.
- Each `report_actions` object has exactly `case_id`, `channel`, `action`, and
  `boundary`. Include OSHA actions only when a controlling outcome is
  reportable or a verified prior OSHA submission must be preserved.
- Use only the vocabulary published in the policy. Use JSON `null` when no
  OSHA reporting deadline applies. Set `external_actions_executed` to false.

The medical category is the minimum necessary outcome category. Do not copy an
employee token, diagnosis, treatment notes, or a claimant's causal allegation
into any deliverable. An invalid or unauthorized medical claim cannot resolve
an unknown outcome. A recordable case is not necessarily subject to an OSHA
8-hour or 24-hour report, and a reportable event already evidenced by a valid
receipt must not be queued again. Workers' compensation work in this task is
offline notice staging only.

Run the guarded workflow; do not edit SQLite or generated receipts by hand:

```bash
python3 injuryctl.py preview recovery_plan.json
python3 injuryctl.py apply recovery_plan.json
python3 injuryctl.py stage recovery_plan.json
python3 injuryctl.py verify recovery_plan.json
python3 injuryctl.py replay recovery_plan.json
```

`preview` gives object-and-field diagnostics and performs no mutation. `apply`
must restore the complete interrupted before-image before committing one local
projection. `stage` builds a privacy-minimized offline bundle; it does not send
anything. Recovery ID, current source checkpoint, and normalized semantic plan
define replay identity. Reordering objects or changing JSON formatting is an
equivalent no-op. A different plan under the same identity, or a stale source
checkpoint, must be rejected without mutation.

Write `injury_reporting_handoff.md` explaining event precedence and signature
authority, cross-midnight UTC calculations, the separate OSHA recording and
reporting tests (including the 8-hour/30-day fatality and 24-hour inpatient
rules), the verified prior submission, privacy and unsupported-cause handling,
before-image recovery, offline OSHA/workers-comp staging, verification, and
semantic replay. State clearly that you did not submit an OSHA report, notify
an insurer or employee, file a workers' compensation claim, or perform any
other external action.

Do not modify the controller, policy, manifest, event evidence, signed claims,
observed external submission, or immutable case facts. Do not use the network,
contact anyone, or perform a real report, filing, notice, or submission.
