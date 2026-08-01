"""V4.7b offline remediation gates from exposed development categories."""

from pathlib import Path
from uuid import uuid4

from claim_polygraph_ng.analysis import (
    construct_linked_assertions,
    extract_verification_candidates,
    route_construction_eligibility,
)
from claim_polygraph_ng.analysis.assisted_verification_construction import (
    AssistedConstructionEligibility,
    AssistedConstructionKind,
    AssistedConstructionProposal,
    AssistedConstructionRequest,
    AssistedEvidenceBinding,
    AssistedScalarForm,
    AssistedTemporalProviderProposal,
    canonicalize_assisted_proposal,
    resolve_assisted_eligibility,
    validate_assisted_proposal,
)
from claim_polygraph_ng.domain import (
    Evidence,
    EvidenceStance,
    NormalizedNumericValue,
    NumericComparator,
    NumericDimension,
    NumericOperation,
)
from claim_polygraph_ng.evaluation.v3_development import select_v3_development_cases
from claim_polygraph_ng.evaluation.v3_manifest import V3ConstructionGoldLabel


def test_authoritative_eligibility_has_complete_exposed_development_recall() -> None:
    root = Path(__file__).parents[2]
    cases, _ = select_v3_development_cases(
        root / "benchmarks/verification_construction_v3_approved_frozen_v2.json"
    )
    positive_labels = {
        V3ConstructionGoldLabel.DETERMINISTIC_CONSTRUCTIBLE,
        V3ConstructionGoldLabel.FALLBACK_ELIGIBLE,
    }
    false_exclusions = []
    unsafe_inclusions = []
    for case in cases:
        extraction = extract_verification_candidates(case.claim_text)
        constructions = construct_linked_assertions(case.claim_text, extraction)
        routing = route_construction_eligibility(case.claim_text, extraction, constructions)
        resolved = resolve_assisted_eligibility(
            claim_text=case.claim_text,
            extraction=extraction,
            routing=routing,
        )
        positive = case.annotation.gold_label in positive_labels
        available = resolved is not AssistedConstructionEligibility.EXCLUDED_QUALITATIVE or any(
            decision.route.value == "deterministic" for decision in routing.decisions
        )
        if positive and not available:
            false_exclusions.append(case.case_id)
        if not positive and available:
            unsafe_inclusions.append(case.case_id)

    assert false_exclusions == []
    assert unsafe_inclusions == []


def test_unique_fact_sentence_repairs_provider_offsets_without_inventing_quote() -> None:
    claim_id = uuid4()
    evidence = Evidence(
        claim_id=claim_id,
        source_id=uuid4(),
        passage="Background only. The chamber pressure is exactly 875 hectopascals.",
        stance=EvidenceStance.CONTEXT,
        relevance_score=1,
    )
    failure_id = uuid4()
    proposal = AssistedConstructionProposal(
        kind=AssistedConstructionKind.NUMERICAL_SCALAR,
        failed_construction_id=failure_id,
        claim_text_span="The chamber pressure is 875 hectopascals.",
        scalar_form=AssistedScalarForm.SINGLE_VALUE,
        scalar_subject="chamber pressure",
        comparator=NumericComparator.EQUAL,
        numeric_operation=NumericOperation.DIRECT,
        dimension=NumericDimension.PRESSURE,
        expected_values=(
            NormalizedNumericValue(
                value=875,
                unit="hectopascals",
                dimension=NumericDimension.PRESSURE,
            ),
        ),
        evidence_bindings=(
            AssistedEvidenceBinding(
                evidence_id=evidence.evidence_id,
                start_char=0,
                end_char=5,
                quoted_text="wrong",
            ),
        ),
    )
    normalized = canonicalize_assisted_proposal(proposal=proposal, evidence=(evidence,))

    assert normalized.evidence_bindings[0].quoted_text == (
        "The chamber pressure is exactly 875 hectopascals."
    )
    assert (
        evidence.passage[
            normalized.evidence_bindings[0].start_char : normalized.evidence_bindings[0].end_char
        ]
        == normalized.evidence_bindings[0].quoted_text
    )
    request = AssistedConstructionRequest(
        claim_id=claim_id,
        claim_text=proposal.claim_text_span,
        failed_construction_id=failure_id,
        approved_evidence_ids=(evidence.evidence_id,),
        construction_kind=AssistedConstructionKind.NUMERICAL_SCALAR,
    )
    assert (
        validate_assisted_proposal(
            request=request,
            proposal=normalized,
            evidence=(evidence,),
        )
        == normalized
    )


def test_conversion_allows_implicit_unity_only_when_its_unit_is_bound() -> None:
    claim_id = uuid4()
    evidence = Evidence(
        claim_id=claim_id,
        source_id=uuid4(),
        passage="The fixed rate is 1.95583 Deutsche Mark per euro.",
        stance=EvidenceStance.CONTEXT,
        relevance_score=1,
    )
    failure_id = uuid4()
    proposal = AssistedConstructionProposal(
        kind=AssistedConstructionKind.NUMERICAL_SCALAR,
        failed_construction_id=failure_id,
        claim_text_span="One euro equals 1.95583 Deutsche Mark.",
        scalar_form=AssistedScalarForm.CONVERSION,
        scalar_subject="One euro",
        comparator=NumericComparator.EQUAL,
        numeric_operation=NumericOperation.DIRECT,
        dimension=NumericDimension.CURRENCY,
        expected_values=(
            NormalizedNumericValue(
                value=1,
                unit="euro",
                dimension=NumericDimension.CURRENCY,
            ),
            NormalizedNumericValue(
                value="1.95583",
                unit="Deutsche Mark",
                dimension=NumericDimension.CURRENCY,
            ),
        ),
        evidence_bindings=(
            AssistedEvidenceBinding(
                evidence_id=evidence.evidence_id,
                start_char=0,
                end_char=len(evidence.passage),
                quoted_text=evidence.passage,
            ),
        ),
    )
    request = AssistedConstructionRequest(
        claim_id=claim_id,
        claim_text=proposal.claim_text_span,
        failed_construction_id=failure_id,
        approved_evidence_ids=(evidence.evidence_id,),
        construction_kind=AssistedConstructionKind.NUMERICAL_SCALAR,
    )

    assert (
        validate_assisted_proposal(
            request=request,
            proposal=proposal,
            evidence=(evidence,),
        )
        == proposal
    )


def test_temporal_wire_infers_one_exact_status_phrase() -> None:
    claim_id = uuid4()
    evidence = Evidence(
        claim_id=claim_id,
        source_id=uuid4(),
        passage="The regulation began applying on 25 May 2018.",
        stance=EvidenceStance.CONTEXT,
        relevance_score=1,
    )
    failure_id = uuid4()
    wire = AssistedTemporalProviderProposal.model_validate(
        {
            "failed_construction_id": str(failure_id),
            "claim_text_span": "The regulation began applying on 25 May 2018.",
            "temporal_relation": "changed_status",
            "reference_date": {"value": "25 May 2018", "precision": "day"},
            "claimed_interval": None,
            "requires_reference_date": False,
            "claimed_status": None,
            "temporal_bindings": [
                {
                    "evidence_id": str(evidence.evidence_id),
                    "start_char": 0,
                    "end_char": len(evidence.passage),
                    "quoted_text": evidence.passage,
                    "effective_interval": None,
                    "observed_status": "began applying",
                    "retrospective": False,
                }
            ],
        }
    )
    proposal = wire.to_proposal()

    assert proposal.claimed_status == "began applying"
