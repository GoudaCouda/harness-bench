# Consumer compatibility contract

`assess_compatibility(baseline, candidate, consumers)` returns
`{"compatible": bool, "issues": [...]}`. Documents map `operation_id` to
`request` and `response` object schemas. Object schemas contain `properties`
and `required`; each property has a nonempty `type` list and optional `enum`.

Consumers have `consumer_id`, `operations`, `always_sends`, `request_values`,
`response_fields`, `accepts_null`, `exhaustive_enums`, and
`reject_unknown_response`. The five maps/lists are scoped by operation.

For each subscribed operation present in both documents:

- A newly required request property breaks consumers that do not always send it.
- Removing a baseline request type narrows what the consumer may send and breaks
  only if its declared sent values include that type. Removing an enum value
  breaks only if the consumer declares sending that value.
- Removing a response field declared in `response_fields` breaks that consumer.
  Adding `null` to a consumed response property's types breaks unless the field
  is listed in `accepts_null`. Removing `null` is safe to readers.
- Adding response enum values breaks only when that field is listed in
  `exhaustive_enums`. Removing response enum values is safe to readers.
- A new response property breaks only a consumer with
  `reject_unknown_response: true` for that operation.
- Removing a subscribed operation is `operation_removed`. A new operation is safe.

Each issue is `{consumer_id, operation_id, direction, field, code}`. Use field
`"*"` for operation removal. Sort by those five values; `compatible` means the
issue list is empty. Reject malformed/duplicate data, unknown subscribed
operations, or unsupported schema keywords with `ValueError`. Inputs are immutable.
