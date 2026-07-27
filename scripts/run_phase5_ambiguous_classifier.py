"""Run exactly one authorized OpenAI call for the Stage 5.7 unresolved pair."""

import argparse
import asyncio
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from claim_polygraph_ng.domain import ModelTask
from claim_polygraph_ng.evaluation.phase5_ambiguous_classifier import (
    AmbiguousDependencyClassification,
    audit_classifier_result,
    build_classifier_preflight,
    export_ambiguous_classifier_artifact,
)
from claim_polygraph_ng.evaluation.phase5_evidence_families import (
    EvidenceFamilyEvaluation,
)
from claim_polygraph_ng.evaluation.phase5_manifest import (
    load_phase5_manifest,
    load_provenance_benchmark,
)
from claim_polygraph_ng.providers import OpenAIStructuredModelProvider

ROOT = Path(__file__).parents[1]
MAXIMUM_COST_USD = 0.01


class _Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    openai_api_key: SecretStr
    openai_fast_model: str = "gpt-4o-mini"
    openai_timeout_seconds: float = 60


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorize-paid", action="store_true")
    args = parser.parse_args()
    if not args.authorize_paid:
        raise SystemExit("Stage 5.7 requires --authorize-paid")
    baseline = EvidenceFamilyEvaluation.model_validate_json(
        (ROOT / "artifacts/evaluations/phase5-stage5.6-evidence-families.json").read_text(
            encoding="utf-8"
        )
    )
    preflight = build_classifier_preflight(baseline, maximum_cost_usd=MAXIMUM_COST_USD)
    if not preflight.valid or preflight.eligible_pair_count != 1:
        raise SystemExit("Stage 5.7 preflight is invalid")
    benchmark = load_provenance_benchmark(ROOT / "benchmarks/phase5_provenance_fixtures_v1.json")
    case = next(item for item in benchmark.cases if item.case_id == "PROV-012")
    settings = _Settings()
    provider = OpenAIStructuredModelProvider(
        api_key=settings.openai_api_key.get_secret_value(),
        model=settings.openai_fast_model,
        fast_model=settings.openai_fast_model,
        timeout_seconds=settings.openai_timeout_seconds,
    )
    classification = await provider.generate(
        task=ModelTask.CLASSIFY_PROVENANCE_RELATIONSHIP,
        response_model=AmbiguousDependencyClassification,
        inputs={
            "case_id": case.case_id,
            "component_claim": case.component_claim,
            "left": case.sources[0].model_dump(mode="json"),
            "right": case.sources[1].model_dump(mode="json"),
            "deterministic_status": "unknown",
            "instruction": (
                "Classify dependency only. Do not decide claim truth. Similar meaning supports "
                "dependency only when wording, details, or attribution suggest one origin."
            ),
        },
    )
    usage = provider.take_last_usage()
    if usage is None:
        raise SystemExit("OpenAI usage telemetry is missing")
    manifest = load_phase5_manifest(
        ROOT / "artifacts/evaluations/phase5-source-intelligence-manifest-v1.json"
    )
    result = audit_classifier_result(
        baseline=baseline,
        case_id=case.case_id,
        classification=classification,
        usage=usage,
        maximum_cost_usd=MAXIMUM_COST_USD,
        required_accuracy=manifest.thresholds.family_accuracy,
        maximum_false_independent_rate=manifest.thresholds.maximum_false_independent_rate,
    )
    output = export_ambiguous_classifier_artifact(
        result, ROOT / "artifacts/evaluations/phase5-stage5.7-classifier.json"
    )
    print(f"Label: {result.classification.label}")
    print(f"Confidence: {result.classification.confidence}")
    print(f"Cost: ${result.estimated_cost_usd:.8f}")
    print(f"Post accuracy: {result.post_family_accuracy:.2%}")
    print(f"Post false-independent rate: {result.post_false_independent_rate:.2%}")
    print(f"Valid: {result.valid}")
    print(f"Artifact: {output}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
