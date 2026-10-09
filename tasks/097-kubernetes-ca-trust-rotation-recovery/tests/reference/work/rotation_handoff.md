# Northstar HA CA-rotation recovery handoff

The interrupted synthetic rotation is now `new_ca_only_verified`. The initial failure was not a reason to roll back the two API servers already signed by `NEW-CA`. Kube-controller-manager correctly needed `pki/ca-bundle.crt` as the overlap `root_ca_file`, but its `client_ca_file` and `cluster_signing_cert_file` incorrectly pointed at that bundle. Those single-CA roles were repaired to `pki/new-ca.crt` with the matching `pki/new-ca.key`, restoring the controller to healthy while dual root distribution was still active.

`metrics-adapter` was the only client left at `old_only` trust after the partial in-cluster restart. It was refreshed to `dual`. `kube-apiserver/cp-3` was the only required endpoint still signed by `OLD-CA`; its leaf moved forward to `NEW-CA`. The already-new cp-1 and cp-2 signers were preserved and never rolled backward.

Before retirement, `cactl` evaluated every one of the 12 required client/server pairs from the component inventory. `work/dual_probe.json` records complete dual-trust coverage with no TLS compatibility failure. Only after the controller roles, client trust, server signers, original history prefix, and complete dual probe all closed did the protected controller accept old-anchor retirement.

Retirement changed root distribution and all required clients from dual to `new_only`, without changing any server back to the old signer. Final `work/verification.json` contains the same 12 required pairs, all using `new_only` client trust against `NEW-CA` server leaves, plus input, state, event-log, and verification fingerprints. A second new-only verification was byte-stable and appended no duplicate event.

A momentary reconnect is expected as in-cluster clients re-establish TLS sessions after a serving restart, but no TLS errors remain in this deterministic probe graph. The rollback boundary remains forward-only: before retirement, stop on a failed prerequisite and repair overlap state; after retirement, recover with the new CA rather than restoring old-only trust. Continue monitoring control-plane, kubelet, kube-proxy, aggregated API, webhook, and in-cluster client TLS logs and alert on any unknown-authority failure.

This was an offline synthetic recovery. No production cluster was changed, no certificate was distributed externally, and no external action or communication occurred.
