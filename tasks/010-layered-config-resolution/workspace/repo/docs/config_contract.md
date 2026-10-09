# Configuration resolver contract

The function returns `{"values": ..., "sources": ...}` and does not mutate its
arguments. Every schema key must resolve. Precedence is CLI, environment, file,
then defaults; dictionary membership means supplied, including explicit null.
An invalid value in the highest supplied layer raises `ValueError` and never
falls back.

Reject unknown file or CLI keys and unknown environment names beginning
`EDGE_`; ignore unrelated environment names. Environment values must be
strings. The case-insensitive environment literal `null` is explicit null;
other layers use JSON null. Null is accepted only when `nullable` is true.

Supported types are:

- `int`: a non-boolean integer or environment decimal digits, within inclusive
  `min` and `max`;
- `bool`: a boolean or environment `true`/`false`, case-insensitive;
- `enum`: an exact string in `choices`;
- `string`: a string, with empty controlled by `allow_empty`.

Each schema record has exactly `type`, `nullable`, `sensitive`, `env`, plus the
type-specific keys shown in `schema.json`. Environment names must be unique.
Schema defects also raise `ValueError`.

The pure function returns actual values. Only the generated diagnostic artifact
redacts every schema key whose `sensitive` value is true as `<redacted>`.
