# Sigstore bundle verification handoff

The release gate first binds each bundle to the expected artifact digest and
payload type, then requires prior signature and certificate-chain verification.
Cryptographic validity is not authorization: certificate identity and issuer
must exactly match the release workflow policy. Unknown roots fail closed.

For short-lived certificates, verification uses trusted signing time evidence
rather than today's wall clock. A verified Rekor inclusion entry counts only
when its operator is trusted by the selected historical root. The tlog
threshold counts distinct operators, so repeated entries from one operator do
not increase assurance. Required RFC3161 timestamp evidence likewise needs a
verified, root-trusted timestamp operator. At least one required time from each
evidence class must fall inside both inclusive certificate and root validity
windows; endpoints are accepted. Retaining rotated roots allows old artifacts
to verify without treating expired certificates as currently valid.

Verification passed with `python -m unittest discover -s tests -v` and
`python bin/verify_bundles.py`. I parsed both JSON outputs: one of four
artifacts verifies; digest mismatch, identity mismatch, and insufficient tlog
operator diversity block the others. This was an offline, no-Sigstore policy
evaluation. I did not contact Fulcio, Rekor, a TSA, TUF, or a registry, perform
cryptography, publish an artifact, or claim a production release.
