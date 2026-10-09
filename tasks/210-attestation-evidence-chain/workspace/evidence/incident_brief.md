# Incident SS-2026-0316-04: inbound attestation bundle parked

A supplier bundle arrived after a root-key rotation. The verification cache
still holds some `accepted` rows from generation 1. Operations asked whether
those cache hits can be trusted so the lots can ship today.

They cannot, unless the cache matches the current key generation. The keyring
in `keyring/keys.json` is the authority for generation, validity, and
revocation. The cache is a hint, not a grant.

Verify every artifact in `staging/artifacts.json`. Do not contact the
supplier or the notary.
