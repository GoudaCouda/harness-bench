# Build and repair a representative accessibility conformance sample

You are the accessibility specialist reviewing an offline portal snapshot for
WCAG 2.2 AA evidence. The job is not to scan every duplicate page or claim
whole-site compliance: define a representative sample, repair the exposed
cross-page and critical-process failures, and leave an auditable local report.

Work only in `$WORKSPACE`.

1. Read `evaluation_scope.json`, `page_inventory.json`, and
   `remediation_policy.md`. Inspect the HTML, shared navigation component, and
   theme CSS. Run `python3 a11yctl.py inventory`.
2. Create `sample_plan.json` with `scope_id` and a unique `page_ids` array.
   Include the common component owners, every page/state in the critical
   purchase process, and one representative structured-content page. Exclude
   redundant catalog/static templates that add no distinct state.
3. Run `python3 a11yctl.py scan sample_plan.json`. Use its check-level feedback
   and the policy to make the smallest repairs. You may modify only:

   - `site/components/nav.html`
   - `site/catalog.html`
   - `site/checkout.html`
   - `site/checkout-error.html`
   - `site/styles/theme.css`

   Preserve visible wording, product facts, links, form names/actions, and
   overall structure. Do not hide content, remove interactive controls, or use
   blanket ARIA to silence diagnostics.
4. When scan passes, run `python3 a11yctl.py certify sample_plan.json`. It creates
   `conformance_report.json` and `repair_receipt.json`; do not hand-author them.
   Run `python3 a11yctl.py verify sample_plan.json`, certify the same plan again,
   and verify once more.
5. Write `accessibility_handoff.md`. Explain why each sampled page represents
   the scope, the shared navigation, catalog image, checkout label/tab order,
   error announcement/focus target, and visible-focus repairs, plus the local
   sample boundary and remaining need for broader/manual review.

Do not edit the scope, inventory, policy, unsampled pages, or controller. Do not
claim that a live site or the complete portal conforms, and do not claim an
external publication or deployment.
