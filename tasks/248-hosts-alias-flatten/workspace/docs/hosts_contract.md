# Hosts contract

1. `target` values that start with a digit are IPv4 literals.
2. Other targets are names that must themselves be resolved.
3. Follow a name until an IPv4 literal is reached.
4. If a walk repeats a name, the start name is a loop: list it in `loops`
   (sorted) and do not emit a record for it.
5. `records` maps each non-loop `name` to its IPv4 literal.

Use the `name` strings from the input. Do not invent hosts.
