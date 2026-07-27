import json
from pathlib import Path

import pytest

from claim_polygraph_ng.domain import ModelCallUsage, ModelTask
from claim_polygraph_ng.evaluation.phase5_ambiguous_classifier import (
    AmbiguousDependencyClassification,
    AmbiguousDependencyLabel,
    audit_classifier_result,
    build_classifier_preflight,
)
from claim_polygraph_ng.evaluation.phase5_evidence_families import (
    EvidenceFamilyEvaluation,
)


def _baseline() -> EvidenceFamilyEvaluation:
    root = Path(__file__).parents[2]
    return EvidenceFamilyEvaluation.model_validate(
        json.loads(
            (root / "artifacts/evaluations/phase5-stage5.6-evidence-families.json").read_text(
                encoding="utf-8"
            )
        )
    )


def _classification(label=AmbiguousDependencyLabel.LIKELY_DEPENDENT):
    return AmbiguousDependencyClassification(
        label=label,
        confidence=0.9,
        shared_assertions=("minor surface cracking", "no structural damage"),
        dependency_evidence=("The passages express the same paired findings.",),
        independence_evidence=(),
        explanation=(
            "Both passages pair minor surface cracking with the absence of structural damage."
        ),
        human_review_required=False,
    )


def _usage(cost=0.0002):
    return ModelCallUsage(
        provider_id="openai:gpt-4o-mini",
        model="gpt-4o-mini",
        task=ModelTask.CLASSIFY_PROVENANCE_RELATIONSHIP,
        duration_seconds=1,
        input_tokens=200,
        output_tokens=80,
        estimated_cost_usd=cost,
        pricing_version="test",
        output_valid=True,
    )


def test_preflight_authorizes_exactly_one_unresolved_pair():
    result = build_classifier_preflight(_baseline())

    assert result.valid
    assert result.eligible_case_ids == ("PROV-012",)
    assert result.maximum_model_calls == 1
    assert result.mock_schema_valid
    assert not result.paid_call_authorized


def test_dependent_classification_closes_family_gates():
    result = audit_classifier_result(
        baseline=_baseline(),
        case_id="PROV-012",
        classification=_classification(),
        usage=_usage(),
        maximum_cost_usd=0.01,
        required_accuracy=0.9,
        maximum_false_independent_rate=0.05,
    )

    assert result.call_count == 1
    assert result.post_family_accuracy == 1
    assert result.post_false_independent_rate == 0
    assert result.valid
    assert result.retrieval_call_count == 0


def test_unknown_classification_does_not_close_false_independence_gate():
    result = audit_classifier_result(
        baseline=_baseline(),
        case_id="PROV-012",
        classification=_classification(AmbiguousDependencyLabel.UNKNOWN),
        usage=_usage(),
        maximum_cost_usd=0.01,
        required_accuracy=0.9,
        maximum_false_independent_rate=0.05,
    )

    assert not result.false_independence_gate_passed
    assert not result.valid


def test_cost_and_scope_are_hard_failures():
    with pytest.raises(ValueError, match="cost ceiling"):
        audit_classifier_result(
            baseline=_baseline(),
            case_id="PROV-012",
            classification=_classification(),
            usage=_usage(0.02),
            maximum_cost_usd=0.01,
            required_accuracy=0.9,
            maximum_false_independent_rate=0.05,
        )
    with pytest.raises(ValueError, match="unresolved"):
        audit_classifier_result(
            baseline=_baseline(),
            case_id="PROV-001",
            classification=_classification(),
            usage=_usage(),
            maximum_cost_usd=0.01,
            required_accuracy=0.9,
            maximum_false_independent_rate=0.05,
        )
