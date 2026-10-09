# Unicode identifier migration handoff

Canonical keys use `NFKC(NFKC(value).casefold())`; this handles canonical and
compatibility equivalence plus multi-codepoint case folds before applying the
configured codepoint length and Unicode identifier syntax profile. Reserved
names pass through the same NFKC and casefold process.

The migration is two-pass. It computes every candidate key before assignment,
then quarantines every member of a collision rather than silently choosing one.
Reserved and invalid records are also blocked. Original display spelling is
preserved exactly and a blocked record has a null canonical key. Visual
confusables such as Greek alpha and Latin A are not merged because normalization
does not make them equal.

References resolve only to accepted target keys. References to a collision,
reserved name, or invalid identifier remain explicit unresolved record IDs, so
no edge is silently dropped or retargeted. Strict validation covers exact
shapes, unique IDs, known references, the reserved profile, and boolean numeric
lookalikes.

`PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v` passed and
`PYTHONDONTWRITEBYTECODE=1 python bin/migrate_identifiers.py` succeeded. I
parsed records and conflicts again. This offline plan did not merge accounts,
change login keys, or contact an identity service.
