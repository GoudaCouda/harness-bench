# Seven-day station QC handoff

For duplicate days, the unflagged final row won over the preliminary row at
ST-A and ST-C. At ST-D on January 3, the final row carried `QFLAG=X`; policy
therefore excluded the day without falling back to the cleaner preliminary
reading. The `-9999` sentinels, the other X-flagged readings, and ST-B's blank
value were also excluded.

ST-A's tenths-C values and ST-C's Fahrenheit values were converted to Celsius
before aggregation. With a five-of-seven threshold, ST-A and ST-C each have
6/7 usable days and qualify; ST-B has 4/7 and ST-D 2/7, so they do not. The
qualified means are 13.583333 C for ST-A and 14.166667 C for ST-C.

Verification recomputed valid-day counts, coverage, qualification, and means
from the 24 canonical station-day rows. No external or production system was
updated.
