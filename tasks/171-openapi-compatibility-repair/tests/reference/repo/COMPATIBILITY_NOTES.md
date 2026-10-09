# Directional API compatibility handoff

The repaired analyzer evaluates deployed-client compatibility separately for
requests and responses. In request direction, a new required input, type
change, enum narrowing, or nullable narrowing can reject payloads that old
clients already send. In response direction, removal or loss of requiredness,
type change, enum widening for closed consumers, or nullable widening can
produce payloads old clients cannot safely consume. Enum null is treated as an
unconstrained universal set, so subset direction is not reversed at that edge.

OpenAPI readOnly and writeOnly are usage annotations. A readOnly property is
inactive in request comparison and a writeOnly property is inactive in
response comparison. When an annotation change activates or deactivates a
field, the analyzer uses addition/removal rules for that direction. Request
property removal follows the reject-unknown policy; response additions remain
compatible except for separately modeled closed discriminator variants.

Property precedence is addition/removal, type, requiredness, enum, then
nullability, producing one auditable finding per changed active field.
Discriminators are hints and do not replace schema validation, but their
contract still matters: property changes, missing required discriminator
properties, and mapping removal break. A new response mapping also breaks when
closed response variants are enabled; request mapping expansion is compatible.

Verification used `python -m unittest discover -s tests -p test_public.py` and
`python bin/check_compatibility.py`. Public tests passed and both generated
JSON files were parsed. The visible comparison produced four breaking findings
across two schemas, so release status is blocked.

This was offline deterministic analysis only. No API, schema registry, client,
deployment, rollout, or production compatibility decision was executed or
claimed.
