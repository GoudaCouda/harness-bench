# Harborline JSON-RPC admission policy (authoritative)

Harborline Payments fronts partner traffic through a JSON-RPC 2.0 admission
gate. A call is forwarded only after every published rule accepts it. This
document is authoritative. Where an incident note and this policy disagree,
this policy wins.

## 1. Gate clock

Admission is evaluated against a single frozen clock, not wall time:

- `gate_clock_epoch` = `1773565200` (2026-03-15T09:00:00Z)

`python3 gatectl.py clock` prints it.

## 2. Envelope

Each batch item is a JSON object. Harborline adds one envelope field besides
the JSON-RPC members:

- `tenant_id` (string, required) identifies the calling tenant

JSON-RPC members are `jsonrpc`, `method`, `params`, and `id`.

- `jsonrpc` must be the string `2.0`.
- `method` must be a non-empty string.
- `params`, when present, must be a JSON object. Positional arrays are rejected.
- If the `id` member is absent, the item is a notification. Notifications never
  produce a response, including when they fail a later rule.
- If `id` is present, including when its value is `null`, the item is a request
  and must produce exactly one response.
- A request `id` may be used only once in the batch. The first occurrence is
  eligible for later rules; a later item that repeats that `id` is `malformed`.

## 3. Decision precedence

Evaluate each item against the recovered catalogs and overlay in this order.
The first matching rule wins.

1. `malformed` — the item fails section 2, including a duplicate request `id`.
2. `frozen` — `method` is listed in `overlays/freeze.json` `frozen_methods` and
   is not listed in `lifted_methods`. The freeze overlay is the only lift
   mechanism. An incident note that a method "should be unfrozen" has no
   effect unless that method is in `lifted_methods`.
3. `method_not_found` — `method` is absent from `catalogs/method_catalog.json`.
4. `tenant_denied` — the tenant is unknown, or the method's `capability` is
   not in that tenant's grant list.
5. `invalid_params` — any name in the method's `required_params` is missing
   from `params`. Extra params are ignored.
6. `admitted` — otherwise. The call may be forwarded.

A frozen method is frozen even when the tenant also lacks the capability.
Do not demote `frozen` to `tenant_denied`.

## 4. Responses

Admitted requests produce

```json
{"jsonrpc":"2.0","result":{"status":"queued","method":"<method>"},"id": <request id>}
```

Refused requests produce

```json
{"jsonrpc":"2.0","error":{"code": <code>, "message": "<reason>", "data":{"decision":"<decision>"}},"id": <request id>}
```

Application codes:

| decision | code |
|---|---:|
| malformed | -32600 |
| method_not_found | -32601 |
| invalid_params | -32602 |
| frozen | -32001 |
| tenant_denied | -32002 |

`response_batch` contains one entry per request, in batch order, and none for
notifications. `response_count` equals the length of `response_batch`.

## 5. Integrity

`forwarded_methods` lists the method of every `admitted` item, including
notifications. A frozen method must never appear there. Counts in the
admission log must equal the decisions actually recorded.

## 6. Authorization boundary

This gate is an offline local admission decision. Forwarding a call to a live
processor, releasing funds, notifying a partner, filing a ticket, or deleting
audit evidence is outside the authorization of this task.
