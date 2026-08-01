"""Stage V3.4 bounded assisted-construction boundary tests."""

import asyncio
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from pydantic import Field

from claim_polygraph_ng.analysis.assisted_verification_construction import (
    ASSISTED_CONSTRUCTION_PROMPT_VERSION,
    AssistedConstructionEligibility,
    AssistedConstructionKind,
    AssistedConstructionProposal,
    AssistedConstructionRequest,
    AssistedEvidenceBinding,
    AssistedNumericalProviderProposal,
    AssistedScalarForm,
    AssistedScalarProviderProposal,
    AssistedTemporalEvidenceBinding,
    AssistedTemporalProviderProposal,
    canonicalize_assisted_proposal,
    classify_assisted_eligibility,
    validate_assisted_proposal,
)
from claim_polygraph_ng.analysis.bounded_assisted_construction import (
    AssistedConstructionBudgetExceeded,
    AssistedConstructionCancelled,
    BoundedAssistedConstructionService,
)
from claim_polygraph_ng.domain import (
    DatePrecision,
    Evidence,
    EvidenceStance,
    ModelCallUsage,
    ModelTask,
    NormalizedNumericValue,
    NumericComparator,
    NumericDimension,
    TemporalInstant,
    TemporalInterval,
    TemporalRelation,
)
from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.evaluation.v3_calibration import (
    select_v3_calibration_cases,
)
from claim_polygraph_ng.evaluation.v3_development import (
    select_v3_development_cases,
)
from claim_polygraph_ng.persistence.paid_operations import SQLitePaidOperationLedger
from claim_polygraph_ng.providers.idempotent import IdempotentStructuredModelProvider
from claim_polygraph_ng.providers.openai import (
    OpenAIStructuredModelProvider,
    _estimated_cost,
    _strict_openai_schema,
)
from claim_polygraph_ng.telemetry import TelemetryCollector


class AssistedFixtureProvider:
    provider_id = "openai:gpt-5.6-luna"
    model = "gpt-5.6-luna"

    def __init__(self, proposal: AssistedConstructionProposal) -> None:
        self.proposal = proposal
        self.calls = 0
        self._usage = None

    async def generate(self, *, task, response_model, inputs):
        del inputs
        self.calls += 1
        self._usage = ModelCallUsage(
            provider_id=self.provider_id,
            model=self.model,
            task=task,
            duration_seconds=0.1,
            input_tokens=200,
            cached_input_tokens=0,
            output_tokens=100,
            estimated_cost_usd=0.0008,
            pricing_version="fixture",
            output_valid=True,
        )
        payload = self.proposal.model_dump()
        return response_model.model_validate(
            {name: payload[name] for name in response_model.model_fields if name in payload}
        )

    def take_last_usage(self):
        usage = self._usage
        self._usage = None
        return usage


class _TinyAssistedOutput(DomainModel):
    value: str = Field(min_length=1)


def _boundary(tmp_path, *, cancelled=lambda: False):
    claim_id = uuid4()
    failed_id = uuid4()
    source_id = uuid4()
    passage = "District A recorded 62 percent; District B recorded 58 percent."
    evidence = Evidence(
        claim_id=claim_id,
        source_id=source_id,
        passage=passage,
        stance=EvidenceStance.CONTEXT,
        relevance_score=1,
    )
    quote = passage
    proposal = AssistedConstructionProposal(
        failed_construction_id=failed_id,
        claim_text_span=("District A recorded 62 percent, higher than District B at 58 percent"),
        left_subject="District A",
        right_subject="District B",
        comparator=NumericComparator.GREATER_THAN,
        dimension=NumericDimension.PERCENTAGE,
        left_value=NormalizedNumericValue(
            value=Decimal(62),
            unit="percent",
            dimension=NumericDimension.PERCENTAGE,
        ),
        right_value=NormalizedNumericValue(
            value=Decimal(58),
            unit="percent",
            dimension=NumericDimension.PERCENTAGE,
        ),
        evidence_bindings=(
            AssistedEvidenceBinding(
                evidence_id=evidence.evidence_id,
                start_char=0,
                end_char=len(quote),
                quoted_text=quote,
            ),
        ),
    )
    request = AssistedConstructionRequest(
        claim_id=claim_id,
        claim_text=("District A recorded 62 percent, higher than District B at 58 percent."),
        failed_construction_id=failed_id,
        approved_evidence_ids=(evidence.evidence_id,),
    )
    provider = AssistedFixtureProvider(proposal)
    ledger = SQLitePaidOperationLedger(tmp_path / "paid.db")
    wrapped = IdempotentStructuredModelProvider(
        provider=provider,
        ledger=ledger,
        investigation_id=claim_id,
        node_id=f"verification-construction:{claim_id}",
        worker_id="v3-test-worker",
    )
    service = BoundedAssistedConstructionService(
        provider=wrapped,
        ledger=ledger,
        investigation_id=claim_id,
        cancellation_requested=cancelled,
    )
    return claim_id, request, (evidence,), provider, ledger, service


def test_completed_assisted_proposal_replays_without_duplicate_charge(tmp_path) -> None:
    investigation_id, request, evidence, provider, ledger, service = _boundary(tmp_path)

    first = asyncio.run(service.propose(request=request, evidence=evidence))
    second = asyncio.run(service.propose(request=request, evidence=evidence))

    assert first == second
    assert provider.calls == 1
    assert ledger.cost_ledger(investigation_id).model_operation_count == 1
    assert ledger.cost_ledger(investigation_id).estimated_cost_usd == 0.0008


def test_cancellation_before_reservation_creates_no_receipt(tmp_path) -> None:
    investigation_id, request, evidence, provider, ledger, service = _boundary(
        tmp_path,
        cancelled=lambda: True,
    )

    with pytest.raises(AssistedConstructionCancelled):
        asyncio.run(service.propose(request=request, evidence=evidence))

    assert provider.calls == 0
    assert ledger.list_receipts(investigation_id) == ()


def test_changed_payload_for_same_case_is_blocked(tmp_path) -> None:
    _, request, evidence, provider, _, service = _boundary(tmp_path)
    asyncio.run(service.propose(request=request, evidence=evidence))
    changed = request.model_copy(update={"failed_construction_id": uuid4()})

    with pytest.raises(AssistedConstructionBudgetExceeded, match="different assisted"):
        asyncio.run(service.propose(request=changed, evidence=evidence))

    assert provider.calls == 1


def test_validator_rejects_subject_outside_claim_span(tmp_path) -> None:
    _, request, evidence, provider, _, _ = _boundary(tmp_path)
    proposal = provider.proposal.model_copy(update={"left_subject": "District C"})

    with pytest.raises(ValueError, match="left subject"):
        validate_assisted_proposal(
            request=request,
            proposal=proposal,
            evidence=evidence,
        )


def test_boundary_rejects_incomplete_approved_packet_before_provider_call(
    tmp_path,
) -> None:
    _, request, _, provider, _, service = _boundary(tmp_path)

    with pytest.raises(ValueError, match="packet is incomplete"):
        asyncio.run(service.propose(request=request, evidence=()))

    assert provider.calls == 0


def test_assisted_contract_cannot_set_judgment_or_publication() -> None:
    fields = AssistedConstructionProposal.model_fields

    assert "verdict" not in fields
    assert "verification_state" not in fields
    assert "readiness" not in fields
    assert "publication" not in fields
    assert ModelTask.ASSIST_VERIFICATION_CONSTRUCTION.value == ("assist_verification_construction")
    assert ASSISTED_CONSTRUCTION_PROMPT_VERSION == ("verification-construction-v4.9d-v8")


def test_temporal_proposal_requires_exact_claim_and_evidence_dates() -> None:
    claim_id = uuid4()
    evidence = Evidence(
        claim_id=claim_id,
        source_id=uuid4(),
        passage="The GDPR began applying on 25 May 2018.",
        stance=EvidenceStance.CONTEXT,
        relevance_score=1,
    )
    failed_id = uuid4()
    request = AssistedConstructionRequest(
        claim_id=claim_id,
        claim_text="The GDPR began applying on 25 May 2018.",
        failed_construction_id=failed_id,
        approved_evidence_ids=(evidence.evidence_id,),
        construction_kind=AssistedConstructionKind.TEMPORAL_STATUS,
    )
    instant = TemporalInstant(value=date(2018, 5, 25), precision=DatePrecision.DAY)
    proposal = AssistedConstructionProposal(
        kind=AssistedConstructionKind.TEMPORAL_STATUS,
        failed_construction_id=failed_id,
        claim_text_span=request.claim_text,
        temporal_relation=TemporalRelation.STARTED,
        reference_date=instant,
        temporal_bindings=(
            AssistedTemporalEvidenceBinding(
                evidence_id=evidence.evidence_id,
                start_char=0,
                end_char=len(evidence.passage),
                quoted_text=evidence.passage,
                effective_interval=TemporalInterval(start=instant, end=instant),
            ),
        ),
    )

    assert (
        validate_assisted_proposal(
            request=request,
            proposal=proposal,
            evidence=(evidence,),
        )
        == proposal
    )


def test_v35a_eligibility_excludes_qualitative_and_missing_reference_status() -> None:
    assert (
        classify_assisted_eligibility("The GDPR began applying on 25 May 2018.")
        is AssistedConstructionEligibility.TEMPORAL
    )
    assert (
        classify_assisted_eligibility("WHO still classifies the event as an emergency.")
        is AssistedConstructionEligibility.MISSING_REFERENCE_DATE
    )
    assert (
        classify_assisted_eligibility("Mount Everest is the tallest mountain from base to summit.")
        is AssistedConstructionEligibility.EXCLUDED_QUALITATIVE
    )


def test_remediation_eligibility_supports_scalar_range_conversion_and_dates() -> None:
    assert (
        classify_assisted_eligibility("The network contains 120,000 stations.")
        is AssistedConstructionEligibility.NUMERICAL_SCALAR
    )
    assert (
        classify_assisted_eligibility("The rate was between 10 percent and 12 percent.")
        is AssistedConstructionEligibility.NUMERICAL_RANGE
    )
    assert (
        classify_assisted_eligibility("One euro equals 1.95583 Deutsche Mark.")
        is AssistedConstructionEligibility.NUMERICAL_CONVERSION
    )
    assert (
        classify_assisted_eligibility("Organization Z was founded in 1994.")
        is AssistedConstructionEligibility.TEMPORAL
    )


def test_scalar_provider_schema_enforces_form_cardinality() -> None:
    value = NormalizedNumericValue(
        value=Decimal(120_000),
        unit="stations",
        dimension=NumericDimension.COUNT,
    )
    proposal = AssistedScalarProviderProposal(
        failed_construction_id=uuid4(),
        claim_text_span="The network contains 120,000 stations.",
        form=AssistedScalarForm.SINGLE_VALUE,
        subject="The network",
        comparator=NumericComparator.EQUAL,
        operation="direct",
        dimension=NumericDimension.COUNT,
        values=(value,),
        evidence_bindings=(
            AssistedEvidenceBinding(
                evidence_id=uuid4(),
                start_char=0,
                end_char=37,
                quoted_text="The network contains 120,000 stations.",
            ),
        ),
    )

    assert proposal.to_proposal().kind is AssistedConstructionKind.NUMERICAL_SCALAR


def test_provider_schemas_are_structurally_branch_specific() -> None:
    assert "temporal_relation" not in AssistedNumericalProviderProposal.model_fields
    assert "left_value" not in AssistedTemporalProviderProposal.model_fields
    assert "verdict" not in AssistedTemporalProviderProposal.model_fields
    assert "verification_state" not in AssistedNumericalProviderProposal.model_fields
    assert "temporal_relation" not in AssistedScalarProviderProposal.model_fields


def test_stage5b_canary_source_does_not_load_benchmark_data() -> None:
    root = Path(__file__).parents[2]
    source = (root / "scripts/run_v3_stage5b_synthetic_canary.py").read_text(encoding="utf-8")

    assert "benchmarks/" not in source
    assert "select_v3_development_cases" not in source
    assert "CLAIM_TEXT =" in source
    assert "EVIDENCE_TEXT =" in source


def test_stage5c_canary_is_isolated_and_uses_a_fresh_identity() -> None:
    root = Path(__file__).parents[2]
    stage5b = (root / "scripts/run_v3_stage5b_synthetic_canary.py").read_text(encoding="utf-8")
    stage5c = (root / "scripts/run_v3_stage5c_synthetic_canary.py").read_text(encoding="utf-8")

    assert "benchmarks/" not in stage5c
    assert "select_v3_development_cases" not in stage5c
    assert 'CANARY_ID = "v3.5b-synthetic-temporal-canary-v1"' in stage5b
    assert 'CANARY_ID = "v3.5c-synthetic-temporal-canary-v1"' in stage5c
    assert "Regulation Y" in stage5c


def test_v35_selection_exposes_only_development_cases() -> None:
    root = Path(__file__).parents[2]
    cases, selection = select_v3_development_cases(
        root / "benchmarks/verification_construction_v3_approved_frozen_v2.json"
    )

    assert len(cases) == 20
    assert all(case.split.value == "development" for case in cases)
    assert len(selection.assisted_case_ids) == 9
    assert len(selection.control_case_ids) == 11
    assert set(selection.assisted_case_ids).isdisjoint(selection.control_case_ids)


def test_v36_selection_exposes_only_calibration_cases() -> None:
    root = Path(__file__).parents[2]
    cases, selection = select_v3_calibration_cases(
        root / "benchmarks/verification_construction_v3_approved_frozen_v2.json"
    )

    assert len(cases) == 20
    assert selection.case_count == 20
    assert all(case.split.value == "calibration" for case in cases)
    assert not {"V3-001", "V3-004"}.intersection(selection.case_ids)


def test_luna_uses_frozen_output_cap_and_current_cost_rates() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["model"] == "gpt-5.6-luna"
        assert payload["max_output_tokens"] == 1_200
        assert payload["store"] is False
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "usage": {"input_tokens": 1_000, "output_tokens": 500},
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps({"value": "bounded"}),
                            }
                        ],
                    }
                ],
            },
        )

    provider = OpenAIStructuredModelProvider(
        api_key="test-secret",
        model="gpt-5.6-luna",
        transport=httpx.MockTransport(handler),
    )
    result = asyncio.run(
        provider.generate(
            task=ModelTask.ASSIST_VERIFICATION_CONSTRUCTION,
            response_model=_TinyAssistedOutput,
            inputs={"fixture": True},
        )
    )
    usage = provider.take_last_usage()

    assert result.value == "bounded"
    assert usage is not None
    assert usage.estimated_cost_usd == pytest.approx(0.004)
    assert usage.pricing_version == "openai-list-prices-2026-07-30"
    assert _estimated_cost(
        "gpt-5.6-luna",
        input_tokens=1_000,
        cached_input_tokens=0,
        output_tokens=500,
    ) == pytest.approx(0.004)


def test_openai_schema_removes_unsupported_decimal_lookaround() -> None:
    schema = _strict_openai_schema(AssistedConstructionProposal.model_json_schema())

    def patterns(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "pattern":
                    yield child
                yield from patterns(child)
        elif isinstance(value, list):
            for child in value:
                yield from patterns(child)

    assert all(
        token not in pattern
        for pattern in patterns(schema)
        for token in ("(?=", "(?!", "(?<=", "(?<!")
    )


def test_openai_temporal_branch_schema_has_no_numerical_fields() -> None:
    failed_id = uuid4()
    evidence_id = uuid4()

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        schema = payload["text"]["format"]["schema"]
        assert "left_value" not in json.dumps(schema)
        output = {
            "failed_construction_id": str(failed_id),
            "claim_text_span": "The GDPR began applying on 25 May 2018.",
            "temporal_relation": "started",
            "reference_date": {"value": "2018-05-25", "precision": "day"},
            "claimed_interval": None,
            "requires_reference_date": False,
            "claimed_status": None,
            "temporal_bindings": [
                {
                    "evidence_id": str(evidence_id),
                    "start_char": 0,
                    "end_char": 41,
                    "quoted_text": "The GDPR began applying on 25 May 2018.",
                    "effective_interval": {
                        "start": {"value": "2018-05-25", "precision": "day"},
                        "end": {"value": "2018-05-25", "precision": "day"},
                        "start_inclusive": True,
                        "end_inclusive": True,
                    },
                    "observed_status": None,
                    "retrospective": False,
                }
            ],
        }
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "usage": {"input_tokens": 100, "output_tokens": 100},
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": json.dumps(output)}],
                    }
                ],
            },
        )

    provider = OpenAIStructuredModelProvider(
        api_key="test-secret",
        model="gpt-5.6-luna",
        transport=httpx.MockTransport(handler),
    )
    result = asyncio.run(
        provider.generate(
            task=ModelTask.ASSIST_VERIFICATION_CONSTRUCTION,
            response_model=AssistedTemporalProviderProposal,
            inputs={"fixture": True},
        )
    )

    assert result.temporal_relation is TemporalRelation.STARTED
    assert result.reference_date is not None
    assert result.to_proposal().reference_date == TemporalInstant(
        value=date(2018, 5, 25),
        precision=DatePrecision.DAY,
    )


def test_temporal_wire_accepts_exact_written_source_date() -> None:
    payload = {
        "failed_construction_id": str(uuid4()),
        "claim_text_span": "Regulation X began applying on 25 May 2018.",
        "temporal_relation": "started",
        "reference_date": {"value": "25 May 2018", "precision": "day"},
        "claimed_interval": None,
        "requires_reference_date": False,
        "claimed_status": None,
        "temporal_bindings": [
            {
                "evidence_id": str(uuid4()),
                "start_char": 0,
                "end_char": 47,
                "quoted_text": "Regulation X began applying on 25 May 2018.",
                "effective_interval": {
                    "start": {"value": "25 May 2018", "precision": "day"},
                    "end": {"value": "25 May 2018", "precision": "day"},
                    "start_inclusive": True,
                    "end_inclusive": True,
                },
                "observed_status": None,
                "retrospective": False,
            }
        ],
    }

    proposal = AssistedTemporalProviderProposal.model_validate(payload).to_proposal()

    assert proposal.reference_date is not None
    assert proposal.reference_date.value == date(2018, 5, 25)


def test_v36b_normalizes_grouped_and_scientific_decimal_text() -> None:
    grouped = NormalizedNumericValue(
        value="12,345,678",
        unit="people",
        dimension=NumericDimension.COUNT,
    )
    scientific = NormalizedNumericValue(
        value="2.75 x 10^6",
        unit="joules",
        dimension=NumericDimension.ENERGY,
    )

    assert grouped.value == Decimal("12345678")
    assert scientific.value == Decimal("2750000")


def test_v47b_normalizes_string_null_for_optional_tolerance() -> None:
    value = NormalizedNumericValue(
        value="12.3",
        unit="psi",
        dimension=NumericDimension.PRESSURE,
        tolerance="null",
    )

    assert value.tolerance is None


def test_v46a_does_not_expand_an_unmatched_quote_to_the_whole_passage() -> None:
    evidence = Evidence(
        claim_id=uuid4(),
        source_id=uuid4(),
        passage="Synthetic reservoir capacity is 72 million liters.",
        stance=EvidenceStance.CONTEXT,
        relevance_score=1,
    )
    proposal = AssistedConstructionProposal(
        kind=AssistedConstructionKind.NUMERICAL_SCALAR,
        failed_construction_id=uuid4(),
        claim_text_span="The reservoir holds 72 million liters.",
        scalar_form=AssistedScalarForm.SINGLE_VALUE,
        scalar_subject="reservoir capacity",
        comparator=NumericComparator.EQUAL,
        numeric_operation="direct",
        dimension=NumericDimension.VOLUME,
        expected_values=(
            NormalizedNumericValue(
                value=72,
                unit="million liters",
                dimension=NumericDimension.VOLUME,
            ),
        ),
        evidence_bindings=(
            AssistedEvidenceBinding(
                evidence_id=evidence.evidence_id,
                start_char=99,
                end_char=105,
                quoted_text="not an exact source quote",
            ),
        ),
    )

    normalized = canonicalize_assisted_proposal(
        proposal=proposal,
        evidence=(evidence,),
    )

    assert normalized.scalar_subject == "The reservoir"
    assert normalized.evidence_bindings[0].start_char == 99
    assert normalized.evidence_bindings[0].end_char == 105
    assert normalized.evidence_bindings[0].quoted_text == "not an exact source quote"


def test_v46a_safely_expands_date_quote_to_include_unique_status() -> None:
    claim_id = uuid4()
    evidence = Evidence(
        claim_id=claim_id,
        source_id=uuid4(),
        passage=(
            "The fictional permit register states that Permit Z became "
            "effective on 17 February 2022."
        ),
        stance=EvidenceStance.CONTEXT,
        relevance_score=1,
    )
    failure_id = uuid4()
    request = AssistedConstructionRequest(
        claim_id=claim_id,
        claim_text="Permit Z became effective on 17 February 2022.",
        failed_construction_id=failure_id,
        approved_evidence_ids=(evidence.evidence_id,),
        construction_kind=AssistedConstructionKind.TEMPORAL_STATUS,
    )
    wire = AssistedTemporalProviderProposal.model_validate(
        {
            "failed_construction_id": str(failure_id),
            "claim_text_span": request.claim_text,
            "temporal_relation": "active",
            "reference_date": None,
            "claimed_interval": None,
            "requires_reference_date": False,
            "claimed_status": "effective",
            "temporal_bindings": [
                {
                    "evidence_id": str(evidence.evidence_id),
                    "start_char": 37,
                    "end_char": 61,
                    "quoted_text": "17 February 2022",
                    "effective_interval": None,
                    "observed_status": None,
                    "retrospective": False,
                }
            ],
        }
    )

    normalized = canonicalize_assisted_proposal(
        proposal=wire.to_proposal(),
        evidence=(evidence,),
    )
    binding = normalized.temporal_bindings[0]

    assert binding.quoted_text == "effective on 17 February 2022"
    assert binding.observed_status == "effective"
    assert evidence.passage[binding.start_char : binding.end_char] == binding.quoted_text
    assert (
        validate_assisted_proposal(
            request=request,
            proposal=normalized,
            evidence=(evidence,),
        )
        == normalized
    )


@pytest.mark.parametrize(
    "passage",
    [
        "Permit Z was effective. The recorded date was 17 February 2022.",
        ("Permit Z was effective and remained effective on 17 February 2022."),
    ],
)
def test_v46a_refuses_unsafe_status_quote_expansion(passage: str) -> None:
    claim_id = uuid4()
    evidence = Evidence(
        claim_id=claim_id,
        source_id=uuid4(),
        passage=passage,
        stance=EvidenceStance.CONTEXT,
        relevance_score=1,
    )
    failure_id = uuid4()
    request = AssistedConstructionRequest(
        claim_id=claim_id,
        claim_text="Permit Z was effective on 17 February 2022.",
        failed_construction_id=failure_id,
        approved_evidence_ids=(evidence.evidence_id,),
        construction_kind=AssistedConstructionKind.TEMPORAL_STATUS,
    )
    date_start = passage.index("17 February 2022")
    proposal = AssistedConstructionProposal(
        kind=AssistedConstructionKind.TEMPORAL_STATUS,
        failed_construction_id=failure_id,
        claim_text_span=request.claim_text,
        temporal_relation=TemporalRelation.ACTIVE,
        claimed_status="effective",
        temporal_bindings=(
            AssistedTemporalEvidenceBinding(
                evidence_id=evidence.evidence_id,
                start_char=date_start,
                end_char=date_start + len("17 February 2022"),
                quoted_text="17 February 2022",
                observed_status="effective",
            ),
        ),
    )

    normalized = canonicalize_assisted_proposal(
        proposal=proposal,
        evidence=(evidence,),
    )

    assert normalized.temporal_bindings[0].quoted_text == "17 February 2022"
    with pytest.raises(ValueError, match="observed status is not explicit"):
        validate_assisted_proposal(
            request=request,
            proposal=normalized,
            evidence=(evidence,),
        )


def test_v36b_temporal_binding_inherits_explicit_reference_date() -> None:
    payload = {
        "failed_construction_id": str(uuid4()),
        "claim_text_span": "Synthetic rule Q took effect on 14 February 2022.",
        "temporal_relation": "started",
        "reference_date": {"value": "14 February 2022", "precision": "day"},
        "claimed_interval": None,
        "requires_reference_date": False,
        "claimed_status": None,
        "temporal_bindings": [
            {
                "evidence_id": str(uuid4()),
                "start_char": 0,
                "end_char": 50,
                "quoted_text": "Synthetic rule Q took effect on 14 February 2022.",
                "effective_interval": None,
                "observed_status": None,
                "retrospective": False,
            }
        ],
    }

    proposal = AssistedTemporalProviderProposal.model_validate(payload).to_proposal()

    assert proposal.temporal_bindings[0].effective_interval is not None
    assert proposal.temporal_bindings[0].effective_interval.start == TemporalInstant(
        value=date(2022, 2, 14),
        precision=DatePrecision.DAY,
    )


def test_v46b_reconstructs_unique_date_before_domain_conversion() -> None:
    claim_id = uuid4()
    evidence = Evidence(
        claim_id=claim_id,
        source_id=uuid4(),
        passage=(
            "The fictional registry records that Charter R entered into force on 9 March 2021."
        ),
        stance=EvidenceStance.CONTEXT,
        relevance_score=1,
    )
    failure_id = uuid4()
    request = AssistedConstructionRequest(
        claim_id=claim_id,
        claim_text="Charter R entered into force on 9 March 2021.",
        failed_construction_id=failure_id,
        approved_evidence_ids=(evidence.evidence_id,),
        construction_kind=AssistedConstructionKind.TEMPORAL_STATUS,
    )
    wire = AssistedTemporalProviderProposal.model_validate(
        {
            "failed_construction_id": str(failure_id),
            "claim_text_span": request.claim_text,
            "temporal_relation": "on",
            "reference_date": None,
            "claimed_interval": None,
            "requires_reference_date": False,
            "claimed_status": None,
            "temporal_bindings": [
                {
                    "evidence_id": str(evidence.evidence_id),
                    "start_char": 39,
                    "end_char": 56,
                    "quoted_text": "9 March 2021",
                    "effective_interval": None,
                    "observed_status": None,
                    "retrospective": False,
                }
            ],
        }
    )

    proposal = canonicalize_assisted_proposal(
        proposal=wire.to_proposal(),
        evidence=(evidence,),
    )

    assert proposal.reference_date == TemporalInstant(
        value=date(2021, 3, 9),
        precision=DatePrecision.DAY,
    )
    assert proposal.temporal_bindings[0].effective_interval is not None
    assert proposal.temporal_bindings[0].effective_interval.start == (proposal.reference_date)
    assert (
        validate_assisted_proposal(
            request=request,
            proposal=proposal,
            evidence=(evidence,),
        )
        == proposal
    )


@pytest.mark.parametrize(
    ("claim_span", "quote"),
    [
        (
            "Charter R changed between 9 March 2021 and 10 March 2021.",
            "9 March 2021 and 10 March 2021",
        ),
        ("Charter R changed on an unknown date.", "unknown date"),
        ("Charter R changed on 31 February 2021.", "31 February 2021"),
    ],
)
def test_v46b_rejects_missing_ambiguous_or_invalid_reconstruction(
    claim_span: str,
    quote: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="typed or uniquely reconstructible claim fact",
    ):
        AssistedTemporalProviderProposal.model_validate(
            {
                "failed_construction_id": str(uuid4()),
                "claim_text_span": claim_span,
                "temporal_relation": "on",
                "reference_date": None,
                "claimed_interval": None,
                "requires_reference_date": False,
                "claimed_status": None,
                "temporal_bindings": [
                    {
                        "evidence_id": str(uuid4()),
                        "start_char": 0,
                        "end_char": len(quote),
                        "quoted_text": quote,
                        "effective_interval": None,
                        "observed_status": None,
                        "retrospective": False,
                    }
                ],
            }
        )


@pytest.mark.parametrize(
    ("written", "expected", "precision"),
    [
        ("2021-03-09", date(2021, 3, 9), DatePrecision.DAY),
        ("March 2021", date(2021, 3, 1), DatePrecision.MONTH),
        ("2021-03", date(2021, 3, 1), DatePrecision.MONTH),
        ("2021", date(2021, 1, 1), DatePrecision.YEAR),
    ],
)
def test_v46b_preserves_reconstructed_date_precision(
    written: str,
    expected: date,
    precision: DatePrecision,
) -> None:
    proposal = AssistedTemporalProviderProposal.model_validate(
        {
            "failed_construction_id": str(uuid4()),
            "claim_text_span": f"Charter R changed on {written}.",
            "temporal_relation": "on",
            "reference_date": None,
            "claimed_interval": None,
            "requires_reference_date": False,
            "claimed_status": None,
            "temporal_bindings": [
                {
                    "evidence_id": str(uuid4()),
                    "start_char": 0,
                    "end_char": len(written),
                    "quoted_text": written,
                    "effective_interval": None,
                    "observed_status": None,
                    "retrospective": False,
                }
            ],
        }
    ).to_proposal()

    assert proposal.reference_date == TemporalInstant(
        value=expected,
        precision=precision,
    )


def test_v36b_eligibility_handles_qualified_units_and_ratio_words() -> None:
    assert (
        classify_assisted_eligibility("A synthetic orbital cycle lasts 412 local days.")
        is AssistedConstructionEligibility.NUMERICAL_SCALAR
    )
    assert (
        classify_assisted_eligibility("The chamber pressure is 875 hectopascals.")
        is AssistedConstructionEligibility.NUMERICAL_SCALAR
    )
    assert (
        classify_assisted_eligibility("The revised process is twice as fast.")
        is AssistedConstructionEligibility.NUMERICAL_SCALAR
    )


@pytest.mark.parametrize(
    ("claim", "expected"),
    (
        (
            "The Federal Reserve System has 12 regional Reserve Banks.",
            AssistedConstructionEligibility.NUMERICAL_SCALAR,
        ),
        (
            "A typical human cell has 46 chromosomes.",
            AssistedConstructionEligibility.NUMERICAL_SCALAR,
        ),
        (
            "The Library of Congress adds more than 10,000 items each working day.",
            AssistedConstructionEligibility.NUMERICAL_SCALAR,
        ),
        (
            "The United Nations currently has 193 Member States.",
            AssistedConstructionEligibility.NUMERICAL_SCALAR,
        ),
        (
            "The Large Hadron Collider has a 27-kilometre ring.",
            AssistedConstructionEligibility.NUMERICAL_SCALAR,
        ),
        (
            "The Smithsonian complex includes 21 museums.",
            AssistedConstructionEligibility.NUMERICAL_SCALAR,
        ),
        (
            "The Securities Exchange Act of 1934 created the SEC.",
            AssistedConstructionEligibility.TEMPORAL,
        ),
        (
            "The Library of Congress was established on 24 April 1800.",
            AssistedConstructionEligibility.TEMPORAL,
        ),
        (
            "The standard current CPI base period runs from 1982 through 1984.",
            AssistedConstructionEligibility.TEMPORAL,
        ),
    ),
)
def test_v36d_routes_exposed_calibration_patterns_without_broad_qualitative_expansion(
    claim: str,
    expected: AssistedConstructionEligibility,
) -> None:
    assert classify_assisted_eligibility(claim) is expected


def test_v36d_keeps_dimensionless_and_qualitative_claims_ineligible() -> None:
    assert (
        classify_assisted_eligibility("The current CPI base-period index is 100.")
        is AssistedConstructionEligibility.EXCLUDED_QUALITATIVE
    )
    assert (
        classify_assisted_eligibility("The proposed institutional design is elegant.")
        is AssistedConstructionEligibility.EXCLUDED_QUALITATIVE
    )
    assert (
        classify_assisted_eligibility("The committee currently considers the proposal active.")
        is AssistedConstructionEligibility.MISSING_REFERENCE_DATE
    )


@pytest.mark.parametrize(
    ("written", "expected"),
    (
        ("June 6, 2024", date(2024, 6, 6)),
        ("December 23, 1913", date(1913, 12, 23)),
        ("24 April 1800", date(1800, 4, 24)),
    ),
)
def test_v36d_accepts_explicit_historical_and_month_first_day_dates(
    written: str,
    expected: date,
) -> None:
    payload = {
        "failed_construction_id": str(uuid4()),
        "claim_text_span": f"The event occurred on {written}.",
        "temporal_relation": "on",
        "reference_date": {"value": written, "precision": "day"},
        "claimed_interval": None,
        "requires_reference_date": False,
        "claimed_status": None,
        "temporal_bindings": [
            {
                "evidence_id": str(uuid4()),
                "start_char": 0,
                "end_char": len(f"The event occurred on {written}."),
                "quoted_text": f"The event occurred on {written}.",
                "effective_interval": None,
                "observed_status": None,
                "retrospective": False,
            }
        ],
    }

    proposal = AssistedTemporalProviderProposal.model_validate(payload).to_proposal()

    assert proposal.reference_date == TemporalInstant(
        value=expected,
        precision=DatePrecision.DAY,
    )


def test_assisted_boundary_emits_bounded_provider_telemetry(tmp_path) -> None:
    investigation_id, request, evidence, _, ledger, service = _boundary(tmp_path)
    telemetry = TelemetryCollector(tmp_path / "telemetry.db")
    telemetry.initialize()
    service = BoundedAssistedConstructionService(
        provider=service._provider,
        ledger=ledger,
        investigation_id=investigation_id,
        telemetry=telemetry,
    )

    asyncio.run(service.propose(request=request, evidence=evidence))
    snapshot = telemetry.snapshot()

    assert snapshot.spans == 1
    assert snapshot.traces == 1
    assert len(snapshot.metrics) == 2
    assert sum(metric.count for metric in snapshot.metrics) == 3
