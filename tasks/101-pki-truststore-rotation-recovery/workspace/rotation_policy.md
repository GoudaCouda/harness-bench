# Internal mTLS rotation policy

- Build a presented chain from the service leaf to one intermediate. The intermediate issuer identifies the required trust root.
- A service truststore must contain the root for its presented chain.
- `billing-api` is the only service in this recovery scope and must present the leaf named by `expected_leaf`.
- `event-worker` still depends on `root-2024`; the old root remains in overlap trust everywhere it is already present until the worker rotation closes.
- Services outside rotation scope must remain byte-for-byte equivalent at the state-object level.
- Applying the same plan twice is idempotent: one state revision and one audit event.
- This controller changes only the offline state file. It does not issue, revoke, deploy, or contact a network service.
