# OIDC trust handoff

Authorization is fail closed in exact precedence: ID-token write permission, issuer, audience, stable owner and repository IDs, immutable-subject policy, reconstructed subject, event context, and reusable-workflow pin. Repository names may change while IDs remain stable, but every redundant claim must agree with the subject; matching substrings are never sufficient.

Environment context takes subject precedence over ref and encodes colon as `%3A`. Ref and environment allowlists are exact. Pull requests require explicit global permission. A required `job_workflow_ref` matches the complete path and 40-character commit SHA, not a branch or tag, preventing mutable reusable-workflow trust.

Verification ran `python -m unittest discover -s tests -p 'test_*.py'`, `python bin/evaluate_trust.py`, and JSON parsing of decisions and summary; all passed. Inputs are decoded facts only: no JWT cryptography or token request occurred, and no GitHub API, cloud provider, role assumption, trust policy, or production identity state was contacted or changed.
