"""Run the zero-cost Stage 7.1 LangGraph fixture."""

import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from claim_polygraph_ng.application import FixtureLangGraphWorkflow
from claim_polygraph_ng.domain import FixtureGraphRequest, VerdictLabel

ROOT = Path(__file__).parents[1]
OUTPUT = ROOT / "artifacts/evaluations/phase7-stage7.1-fixture-graph-v1.json"


def main() -> int:
    request = FixtureGraphRequest(
        graph_run_id=uuid5(NAMESPACE_URL, "claim-polygraph/phase7/stage7.1"),
        claim_text="The Great Wall is visible from the Moon with the unaided eye.",
        approved_evidence_ids=tuple(
            uuid5(NAMESPACE_URL, f"claim-polygraph/CPNG-005/evidence/{index}")
            for index in range(1, 4)
        ),
        authoritative_verdict=VerdictLabel.CONTRADICTED,
        review_required=True,
        review_reason=(
            "The absolute visibility statement and its orbital photography "
            "qualification require explicit human confirmation."
        ),
    )
    result = FixtureLangGraphWorkflow(enabled=True).invoke(request)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(result.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Graph run: {result.graph_run_id}")
    print(f"Status: {result.status}")
    print(f"Route: {result.route_decision.route}")
    print(f"Nodes completed: {len(result.completed_nodes)}")
    print(f"Verdict preserved: {result.authoritative_verdict is request.authoritative_verdict}")
    print(
        "Evidence contained: "
        f"{result.consumed_evidence_ids == result.approved_evidence_ids}"
    )
    print(
        f"Provider usage: models={result.model_calls}, searches={result.search_calls}, "
        f"cost=${result.estimated_cost_usd:.4f}"
    )
    print(f"Artifact: {OUTPUT.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
