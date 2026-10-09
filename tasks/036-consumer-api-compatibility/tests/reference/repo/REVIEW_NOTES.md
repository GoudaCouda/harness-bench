# Compatibility review notes

The repair treats compatibility as directional: consumers produce requests and
read responses. A required request addition is unsafe unless that version always
sends it, while a new response field is safe for tolerant readers but unsafe for
an explicitly strict reader. Missing and nullable remain distinct; adding null
to a consumed response field is breaking only for a null-intolerant consumer.

Enum narrowing is checked against values a consumer actually sends. Response
enum widening is checked only for exhaustive consumers. Every decision is scoped
to subscribed operations and versioned consumer evidence, so changes on unused
operations do not create noise. Verification used
`PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v`; all tests
passed successfully. Integration risk: consumer declarations can become stale,
so the real gate must version and audit those snapshots. No API deployment or
consumer notification was performed.
