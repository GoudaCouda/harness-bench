import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.confirm_policy import decide_run


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("apply", "plan"), default="apply")
    parser.add_argument("--target-count", type=int, required=True)
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--no-input", action="store_true")
    args = parser.parse_args()
    stdin_is_tty = sys.stdin.isatty()
    stdin_text = "" if stdin_is_tty else sys.stdin.read()
    result = decide_run(
        {
            "mode": args.mode,
            "target_count": args.target_count,
            "yes": args.yes,
            "no_input": args.no_input,
            "stdin_is_tty": stdin_is_tty,
        },
        stdin_text,
    )
    print(json.dumps(result, sort_keys=True))
    code = result["exit_code"]
    return 0 if code is None else int(code)


if __name__ == "__main__":
    raise SystemExit(main())
