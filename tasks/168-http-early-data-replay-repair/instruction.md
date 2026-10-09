# Repair HTTP early-data replay planning

An HTTP/3 edge planner treats every resumed connection as permission to send
0-RTT and retries `425 Too Early` in early data. Work only in
`/workspace/repo`.

Read `docs/early_data_contract.md`, inspect requests, session, policy, runner,
and public tests, then repair `src/early_data.py` as a general pure
implementation. Run public tests and `python bin/plan_early_data.py`; re-parse
both files in `out/`. Write `REPLAY_NOTES.md` covering safe methods,
application opt-in, replayable bodies, ticket age, remembered ALPN and complete
transport/application settings, anti-replay consistency, intermediary
`Early-Data` propagation (including malformed/multiple values), accepted and
rejected handshake state, application-state reset, 425 retry only after the
handshake, attempt limits, commands/results, and the offline/no-network
boundary.

Do not open sockets, mint or use tickets, contact an origin, or claim live QUIC,
TLS, proxy, or production validation.
