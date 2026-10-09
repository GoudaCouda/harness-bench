# Station QC rules

The reporting window is 2026-01-01 through 2026-01-07 (seven calendar days).
A station qualifies with at least five usable days. Coverage is usable days
divided by seven, including calendar days with no reported row in the
denominator.

- Exclude `QFLAG=X`, raw sentinel `-9999`, and blank values.
- For duplicate station/day rows, a final row is authoritative over a
  preliminary (`source=prelim`) row. Do not fall back to a preliminary value
  when the corresponding final row exists but fails QC.
- An unflagged preliminary row is usable only when no final row exists for that
  station/day; retain that fact in the reason.
- Convert `tenths_C` by dividing by 10. Convert Fahrenheit with
  `(value - 32) * 5/9`. Values in `C` need no conversion.
- Compute means only from usable converted observations. Report means only for
  stations that qualify.
