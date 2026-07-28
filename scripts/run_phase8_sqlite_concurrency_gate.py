"""Run the Stage 8.10 local persistence gate and emit its JSON result."""

import argparse
import json
import tempfile
from pathlib import Path

from claim_polygraph_ng.evaluation.sqlite_concurrency import (
    run_sqlite_concurrency_gate,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="cpng-stage8-10-") as directory:
        result = run_sqlite_concurrency_gate(directory)
    payload = result.model_dump(mode="json")
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
