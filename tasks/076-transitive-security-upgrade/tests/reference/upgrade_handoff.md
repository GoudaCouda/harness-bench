# Monorepo advisory handoff

The root paths for SYN-CJ-31, SYN-H2-09 and SYN-URL-22 are repaired by webstack 5.4.3 and auth-ui 3.2.1. The worker paths for SYN-PATH-14 and SYN-SIGN-08 are repaired by upload-agent 2.7.2, resolving archive-kit 1.8.2, pathmatch 4.0.3 and request-sign 1.3.2. SYN-RETRY-06 requires storage-sdk 4.1.1 and retry-core 1.2.2.

Both peer ranges remain satisfied and the selected versions retain session-v1, claims-v1, stream-v1 and storage-v1. Upload-agent 2.7.1 leaves pathmatch vulnerable; the 2.8.0/4.2.0 path changes worker and storage profiles. The webstack 5.5/auth-ui 3.3 pair changes application profiles, while the 6/4 pair requires Node 20. Root and worker manifests, recursive integrity records and workspace roots are coherent; parser tooling and lock metadata were preserved. `check_upgrade.py` returned PASS. Human release review remains required; nothing was published or deployed.
