"""Offline project-authored evaluation for the Stage 6.3 temporal verifier."""

import json
from datetime import date
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field, model_validator

from claim_polygraph_ng.analysis.temporal_verification import (
    TemporalEvidenceFact,
    TemporalFactStatus,
    TemporalVerificationRequest,
    verify_temporal_assertion,
)
from claim_polygraph_ng.domain import (
    AssertionVerificationState,
    DatePrecision,
    TemporalInstant,
    TemporalInterval,
    TemporalRelation,
)
from claim_polygraph_ng.domain.base import DomainModel


class TemporalFactFixture(DomainModel):
    start: date | None = None
    end: date | None = None
    precision: DatePrecision = DatePrecision.DAY
    publication_date: date | None = None
    status: TemporalFactStatus = TemporalFactStatus.UNKNOWN
    retrospective: bool = False


class TemporalRelationFixture(DomainModel):
    case_id: str = Field(pattern=r"^TMP-[0-9]{3}$")
    description: str
    relation: TemporalRelation
    reference_date: date | None = None
    reference_precision: DatePrecision = DatePrecision.DAY
    claimed_start: date | None = None
    claimed_end: date | None = None
    requires_reference_date: bool = False
    facts: tuple[TemporalFactFixture, ...]
    expected_state: AssertionVerificationState


class TemporalRelationBenchmark(DomainModel):
    dataset_id: str = "phase6_temporal_relations"
    version: int = 1
    rights_basis: str = Field(pattern=r"^synthetic_project_authored$")
    cases: tuple[TemporalRelationFixture, ...] = Field(min_length=10)

    @model_validator(mode="after")
    def unique_cases(self) -> "TemporalRelationBenchmark":
        if len({case.case_id for case in self.cases}) != len(self.cases):
            raise ValueError("temporal fixture case IDs must be unique")
        return self


class TemporalRelationCaseResult(DomainModel):
    case_id: str
    observed_state: AssertionVerificationState
    expected_state: AssertionVerificationState
    passed: bool


class TemporalRelationEvaluation(DomainModel):
    evaluation_id: str = "phase6-stage6.3-temporal-v1"
    dataset_id: str
    dataset_version: int
    case_count: int
    passed_count: int
    accuracy: float = Field(ge=0, le=1)
    false_resolved_incomplete_count: int
    out_of_packet_reference_count: int
    results: tuple[TemporalRelationCaseResult, ...]
    gate_passed: bool
    model_calls: int = 0
    network_calls: int = 0
    pdf_downloads: int = 0


def load_temporal_benchmark(path: str | Path) -> TemporalRelationBenchmark:
    return TemporalRelationBenchmark.model_validate_json(Path(path).read_text(encoding="utf-8"))


def evaluate_temporal_benchmark(
    benchmark: TemporalRelationBenchmark,
) -> TemporalRelationEvaluation:
    results = []
    false_resolved = 0
    out_of_packet = 0
    for fixture in benchmark.cases:
        claim_id = uuid5(NAMESPACE_URL, f"{benchmark.dataset_id}/{fixture.case_id}/claim")
        facts = tuple(
            TemporalEvidenceFact(
                evidence_id=uuid5(
                    NAMESPACE_URL, f"{benchmark.dataset_id}/{fixture.case_id}/evidence/{index}"
                ),
                publication_date=_instant(item.publication_date, DatePrecision.DAY),
                effective_interval=_interval(item.start, item.end, item.precision),
                status=item.status,
                retrospective=item.retrospective,
            )
            for index, item in enumerate(fixture.facts)
        )
        observed = verify_temporal_assertion(
            TemporalVerificationRequest(
                claim_id=claim_id,
                claim_text_span=fixture.description,
                relation=fixture.relation,
                reference_date=_instant(
                    fixture.reference_date, fixture.reference_precision
                ),
                claimed_interval=_interval(
                    fixture.claimed_start, fixture.claimed_end, DatePrecision.DAY
                ),
                requires_reference_date=fixture.requires_reference_date,
                facts=facts,
            )
        )
        passed = observed.state is fixture.expected_state
        if fixture.expected_state is AssertionVerificationState.INSUFFICIENT and observed.state in {
            AssertionVerificationState.VERIFIED,
            AssertionVerificationState.CONTRADICTED,
        }:
            false_resolved += 1
        allowed = {fact.evidence_id for fact in facts}
        out_of_packet += len(
            {item.evidence_id for item in observed.observations} - allowed
        )
        results.append(
            TemporalRelationCaseResult(
                case_id=fixture.case_id,
                observed_state=observed.state,
                expected_state=fixture.expected_state,
                passed=passed,
            )
        )
    passed_count = sum(item.passed for item in results)
    accuracy = passed_count / len(results)
    return TemporalRelationEvaluation(
        dataset_id=benchmark.dataset_id,
        dataset_version=benchmark.version,
        case_count=len(results),
        passed_count=passed_count,
        accuracy=accuracy,
        false_resolved_incomplete_count=false_resolved,
        out_of_packet_reference_count=out_of_packet,
        results=tuple(results),
        gate_passed=accuracy >= 0.95 and false_resolved == 0 and out_of_packet == 0,
    )


def export_temporal_evaluation(
    evaluation: TemporalRelationEvaluation, path: str | Path
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(evaluation.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
    return target


def _instant(value: date | None, precision: DatePrecision) -> TemporalInstant | None:
    return TemporalInstant(value=value, precision=precision) if value else None


def _interval(
    start: date | None, end: date | None, precision: DatePrecision
) -> TemporalInterval | None:
    if start is None and end is None:
        return None
    return TemporalInterval(
        start=_instant(start, precision),
        end=_instant(end, precision),
    )
