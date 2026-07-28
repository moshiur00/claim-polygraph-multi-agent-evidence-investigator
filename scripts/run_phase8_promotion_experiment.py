"""Run the locked zero-cost Stage 8.13 promotion experiment."""

import argparse
import asyncio
import json
import tempfile
from pathlib import Path

from claim_polygraph_ng.evaluation.phase8_promotion import (
    evaluate_stage8_13_promotion,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="cpng-stage8-13-") as directory:
        result = asyncio.run(evaluate_stage8_13_promotion(directory))
    rendered = json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    # A safe non-promotion is a successful experiment, not a runner failure.
    return 0 if not result.failed_gates or not result.multi_agent_research_promoted else 1


if __name__ == "__main__":
    raise SystemExit(main())
