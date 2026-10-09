import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from import_migrator import migrate_batch


def main():
    records = json.loads((ROOT / "imports.json").read_text(encoding="utf-8"))
    defaults = json.loads((ROOT / "defaults.json").read_text(encoding="utf-8"))
    result = migrate_batch(records, defaults)
    output = ROOT / "out"
    output.mkdir(exist_ok=True)
    (output / "migrated.json").write_text(
        json.dumps(result["migrated"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "rejected.json").write_text(
        json.dumps(result["rejected"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
