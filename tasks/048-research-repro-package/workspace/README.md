# Trial analysis deposit

Environment: Python 3.11, standard library only.

Reproduce the main results:

```bash
python3 scripts/analyze_main.py \
  --input data/raw_trials.csv \
  --out /tmp/main_results.csv
```

Appendix D was described as using the same driver with `--subgroups` and output
`results/subgroup_ablation.csv`.

The deposited `results.csv` and `execution_log.txt` were produced during the
paper freeze. `deposit_manifest.json` records the snapshot identifiers that
should tie code, data, and results together. Reviewers should not overwrite the
shipped result table when testing the package.
