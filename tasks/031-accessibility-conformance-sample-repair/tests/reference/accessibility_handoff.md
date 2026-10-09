# PORTAL-2026-Q3 accessibility handoff

The offline WCAG 2.2 AA sample includes `home` and `account` because they own
the shared primary navigation and common form pattern. It includes `checkout`
and the distinct `checkout-error` state to cover the complete critical purchase
process. `catalog` supplies representative structured card and image content.
The duplicate product template and static about/legal pages add no distinct
state to this sample, so they remain outside it rather than inflating coverage.

The shared menu button now has one button-level accessible name while its glyph
remains hidden from assistive technology. Both catalog product images have
concise meaningful alt text. Checkout now uses a real label relationship for
the email field and relies on natural tab order instead of a positive tabindex.
In the error state, the summary is announced as an alert, its link targets the
actual email field, and that field references the specific `email-error`
description. The stylesheet replaces the removed outline with a high-contrast,
offset `:focus-visible` outline for links, buttons, and inputs.

The same plan was certified twice and verified after each run, so the receipt
binds an idempotent local repair state. This is evidence from a representative
offline sample, not a claim that the live site or complete portal conforms.
Broader automated coverage, keyboard/zoom checks, and manual assistive-
technology review are still required before any public conformance statement.
