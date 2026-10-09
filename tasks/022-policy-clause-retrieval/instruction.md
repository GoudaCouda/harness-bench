Task: Policy Clause Retrieval and Case Rulings

Inputs:
- `$WORKSPACE/policy_manual.md`
- `$WORKSPACE/cases.json`
- `$WORKSPACE/policy_amendment.md`
- `$WORKSPACE/reason_codes.json`

Use the policy manual, amendment, and canonical reason-code registry to rule on every case, and write `$WORKSPACE/case_rulings.json`.
The amendment supersedes the base manual where it is more specific. Mixed packets must be ruled at both line-item and case levels.

Output format:
- The top level must be a JSON array.
- Each element must contain: `case_id`, `applicable_clause`, `decision`, `reason_code`, `quote_or_signal`, `secondary_clauses`, `blocking_condition`, and `missing_information`.
- `applicable_clause` must name the most specific clause that directly controls
  the ruling. A more-specific amendment such as `AM-1` or `AM-3` takes
  precedence over its base clause; an exception such as `EX-1` may be
  controlling when it changes the decision.
- `secondary_clauses` must be an array containing every other base,
  amendment, or exception clause that materially affects the ruling. Do not
  repeat `applicable_clause`; otherwise use an empty array.
- `decision` must be one of `approve`, `deny`, or `needs_review`.
- `reason_code` must be a short machine-readable code, such as `domestic_with_receipt`.
- Use the canonical reason codes; do not invent synonymous codes.
- `quote_or_signal` may quote the controlling policy language, identify the
  decisive case evidence, or combine both. It need not repeat an amount when
  the policy quotation otherwise supports the ruling.
- `blocking_condition` must explain the key condition causing a `deny` or
  `needs_review` decision in ordinary language; no fixed wording is required.
  For `approve`, it may be an empty string.
- `missing_information` must be an array. If the ruling depends on missing or conflicting approval, receipt, attendee-list, or business-purpose information, list the missing items; otherwise use an empty array.
- For cases with `line_items`, include `line_item_rulings`, an array where each item has `line_id`, `applicable_clause`, `decision`, `reason_code`, `quote_or_signal`, `secondary_clauses`, `blocking_condition`, and `missing_information`.
- For mixed packets, the case-level decision must follow AM-2 aggregation, while each line item must preserve its own applicable clause and reason code.

Also write `$WORKSPACE/ruling_summary.csv` with header:
`case_id,case_decision,denied_lines,review_lines,approved_lines,controlling_clause,summary_reason`

The summary must include every case, including single-line cases. For every
case without an explicit `line_items` array, `denied_lines`, `review_lines`,
and `approved_lines` must all be `0`; these columns count explicit line items,
not the case-level decision.

Forbidden: do not use the internet; do not modify fixtures; do not ignore exception clauses.
