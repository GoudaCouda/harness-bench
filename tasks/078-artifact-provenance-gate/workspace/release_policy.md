# Production bundle provenance policy

The signed requested tag fixes the suite commit and component lock. Every component and bundle signature must bind its digest to the required CI identity. Bundle parent IDs, attestation parent digests, and complete SBOM parents must agree. The bundle must use an allowed base digest and have a passing scan.

Approval state is the latest chronological row for the same request and exact bundle digest. Revoked, stale-digest, or other-request approvals cannot be reused. A valid rebuilt bundle without active approval is selected as `pending_human_reapproval`, and a digest-bound approval request is prepared for the release board. Local tools never grant approval or promotion.
