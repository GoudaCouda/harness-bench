from __future__ import annotations

import argparse
import csv
from pathlib import Path


def rate(rows: list[dict[str, str]], field: str) -> float:
    return sum(int(row[field]) for row in rows) / len(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    with open(args.input, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    control = [row for row in rows if row["arm"] == "control"]
    treatment = [row for row in rows if row["arm"] == "treatment"]
    if not control or not treatment:
        raise ValueError("both trial arms are required")

    metrics = [
        ("conversion_lift", rate(treatment, "converted") - rate(control, "converted")),
        ("retention_lift", rate(treatment, "retained_30d") - rate(control, "retained_30d")),
    ]
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "value", "n_control", "n_treatment"])
        for metric, value in metrics:
            writer.writerow([metric, f"{value:.3f}", len(control), len(treatment)])


if __name__ == "__main__":
    main()
