"""Run the zero-cost Stage 8.11 durable-job backend gate."""

import argparse
import json
import tempfile
from pathlib import Path

from claim_polygraph_ng.evaluation.job_backend import run_job_backend_gate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="cpng-stage8-11-") as directory:
        result = run_job_backend_gate(directory)
    rendered = json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
