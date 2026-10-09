# Offline accessibility remediation policy

The evaluation scope is WCAG 2.2 level AA. Sampling must include common owners,
all critical process states, and a representative structured-content page;
duplicate/static templates do not add value by themselves.

Repairs must preserve visible text, form names/actions, links, product data, and
page structure. Give the menu button one accessible name at the button level.
Use a real label relationship for the checkout email. Remove positive tabindex
rather than renumbering it. The error summary must be announced, link to the
invalid field, and the field must reference its specific error message. Product
images need concise meaningful alt text. Keyboard focus must remain visibly
styled; do not replace `outline: none` with another invisible treatment.

This snapshot supports only local evaluation. A passing sample is evidence for
review, not a claim that the live site or every page conforms.
