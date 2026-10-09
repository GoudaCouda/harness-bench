# Reproducibility audit — RP-2026-17

### Claim CLAIM-1

The manuscript reports a 12.4 percentage-point conversion lift (`0.124`), and
the shipped `results.csv` contains that value for snapshot
`freeze-2026-04-18`. I ran `python3 scripts/analyze_main.py --input
data/raw_trials.csv --out /tmp/main_results.csv`; the command exited 0 on the
deposited 20 rows but produced `conversion_lift=0.200`. The runnable code and
current raw data therefore do not reproduce the paper value. Agreement between
the manuscript and a precomputed table is not an end-to-end reproduction.

### Claim CLAIM-2

The manuscript reports 3.8 percentage points (`0.038`). The shipped
`results.csv` instead records `0.031`, and the observed rerun records `0.100`
(10 percentage points). These three retention values disagree. The current
package does not reproduce CLAIM-2, and neither the shipped summary nor the
rerun resolves which freeze supported the manuscript value.

### Claim CLAIM-3

The documented main command is runnable: `analyze_main.py` parses, exits 0, and
writes two metrics from `data/raw_trials.csv`. That is only execution success.
`deposit_manifest.json` says the code/results use `freeze-2026-04-18`, while the
raw data is `freeze-2026-05-02`; it also expects 1681 main rows but deposits 20.
The observed 0.200/0.100 results differ from the shipped 0.124/0.031 values.
Consequently the headline results are not reproducible end-to-end from the
version-mixed deposit.

### Claim CLAIM-4

The paper and old `execution_log.txt` report a 6.1 percentage-point (`0.061`)
hesitant-shopper result in `results/subgroup_ablation.csv`. That artifact is
absent. Running the README interface with `--subgroups` fails because the
current `analyze_main.py` does not implement or recognize that flag. The old
log is provenance evidence, not a reproducible output, so CLAIM-4 is unsupported
and cannot be reproduced from this package.

## Package conclusion

The main command ran successfully, but no headline claim was reproduced from a
coherent deposited snapshot. The 20-row `freeze-2026-05-02` data conflicts with
the 1681-row `freeze-2026-04-18` code/results record, retention has three values,
and the subgroup interface and artifact are absent. Release requires a
content-matched freeze, reconciled claims/results, and a tested subgroup path.
