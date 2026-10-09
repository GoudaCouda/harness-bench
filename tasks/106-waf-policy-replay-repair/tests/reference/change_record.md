# INC-WAF-2408 local repair record

## Findings and changes

Revision 7 produced three independent regressions. First, `RCE-932100` treated
the pipe in the verified vendor release identity as command syntax. The rule
remains enabled. One local exclusion now applies only to `POST /hooks/vendor`,
`body.message`, and the cryptographically verified signer `vendor-prod`. A
signature-shaped string is insufficient. A retired signer, different path or
method, and `body.command` remain inspected, so a signed message cannot exempt
a dangerous command field.

Second, the download rule previously decoded once. The incident value exposed
`../` only after two bounded percent-decoding passes, so the local traversal
control now uses two passes on `/download/`. Safe nested download paths and
unrelated image paths remain allowed.

Third, login rate state now uses a 60-second sliding window keyed by
`client_ip`, with three requests allowed and attempt four blocked with 429.
Another address keeps an independent budget, and non-POST or non-login traffic
does not consume the window.

## Regression and handoff

The complete public replay passes. SQL injection remains blocked by
`SQLI-942100`; health and catalog requests preserve their baseline behavior.
The regression also proves the unsigned command webhook, wrong route, safe
download and window-expiry cases. The final report is bound to the exact policy
and protected corpus.

This package is staged offline for security review. There was no deployment,
vendor contact, webhook send, production mutation, or approval. Unseen attack
and legitimate replay remains a required independent promotion gate.
