"""Project-authored fixture evaluation for the Stage 6.2 numerical verifier."""

import json
from decimal import Decimal
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field, model_validator

from claim_polygraph_ng.analysis.numerical_verification import (
    NumericalEvidenceOperand,
    NumericalVerificationRequest,
    RankOrder,
    verify_numerical_assertion,
)
from claim_polygraph_ng.domain import (
    AssertionVerificationState,
    NormalizedNumericValue,
    NumericComparator,
    NumericDimension,
    NumericOperation,
)
from claim_polygraph_ng.domain.base import DomainModel


class NumericalFixtureValue(DomainModel):
    value: Decimal
    unit: str | None = None
    dimension: NumericDimension = NumericDimension.DIMENSIONLESS
    scale: Decimal = Decimal(1)
    tolerance: Decimal | None = None

    def normalized(self) -> NormalizedNumericValue:
        return NormalizedNumericValue(**self.model_dump())


class NumericalOperationFixture(DomainModel):
    case_id: str = Field(pattern=r"^NUM-[0-9]{3}$")
    description: str
    operation: NumericOperation
    comparator: NumericComparator = NumericComparator.EQUAL
    expected_values: tuple[NumericalFixtureValue, ...] = Field(min_length=1, max_length=2)
    operands: tuple[NumericalFixtureValue, ...]
    expected_state: AssertionVerificationState
    expected_result: Decimal | None = None
    decimal_places: int | None = Field(default=None, ge=0, le=18)
    target_operand_index: int | None = None
    rank_order: RankOrder = RankOrder.DESCENDING
    ranking_complete: bool = False


class NumericalOperationBenchmark(DomainModel):
    dataset_id: str = "phase6_numerical_operations"
    version: int = 1
    rights_basis: str = Field(pattern=r"^synthetic_project_authored$")
    cases: tuple[NumericalOperationFixture, ...] = Field(min_length=10)

    @model_validator(mode="after")
    def unique_cases(self) -> "NumericalOperationBenchmark":
        if len({case.case_id for case in self.cases}) != len(self.cases):
            raise ValueError("numerical fixture case IDs must be unique")
        return self


class NumericalOperationCaseResult(DomainModel):
    case_id: str
    observed_state: AssertionVerificationState
    expected_state: AssertionVerificationState
    observed_result: Decimal | None = None
    expected_result: Decimal | None = None
    passed: bool
    issues: tuple[str, ...] = ()


class NumericalOperationEvaluation(DomainModel):
    evaluation_id: str = "phase6-stage6.2-numerical-v1"
    dataset_id: str
    dataset_version: int
    case_count: int = Field(ge=0)
    passed_count: int = Field(ge=0)
    accuracy: float = Field(ge=0, le=1)
    false_resolved_incomplete_count: int = Field(ge=0)
    out_of_packet_reference_count: int = Field(ge=0)
    results: tuple[NumericalOperationCaseResult, ...]
    gate_passed: bool
    model_calls: int = 0
    network_calls: int = 0
    pdf_downloads: int = 0


def load_numerical_benchmark(path: str | Path) -> NumericalOperationBenchmark:
    return NumericalOperationBenchmark.model_validate_json(Path(path).read_text(encoding="utf-8"))


def evaluate_numerical_benchmark(
    benchmark: NumericalOperationBenchmark,
) -> NumericalOperationEvaluation:
    results = []
    false_resolved = 0
    out_of_packet = 0
    for fixture in benchmark.cases:
        claim_id = uuid5(NAMESPACE_URL, f"{benchmark.dataset_id}/{fixture.case_id}/claim")
        operands = tuple(
            NumericalEvidenceOperand(
                evidence_id=uuid5(
                    NAMESPACE_URL,
                    f"{benchmark.dataset_id}/{fixture.case_id}/evidence/{index}",
                ),
                value=value.normalized(),
            )
            for index, value in enumerate(fixture.operands)
        )
        request = NumericalVerificationRequest(
            claim_id=claim_id,
            claim_text_span=fixture.description,
            comparator=fixture.comparator,
            operation=fixture.operation,
            expected_values=tuple(item.normalized() for item in fixture.expected_values),
            operands=operands,
            decimal_places=fixture.decimal_places,
            target_operand_index=fixture.target_operand_index,
            rank_order=fixture.rank_order,
            ranking_complete=fixture.ranking_complete,
        )
        observed = verify_numerical_assertion(request)
        observed_result = (
            observed.normalized_result.value if observed.normalized_result is not None else None
        )
        passed = (
            observed.state is fixture.expected_state
            and observed_result == fixture.expected_result
        )
        incomplete_expected = fixture.expected_state in {
            AssertionVerificationState.INSUFFICIENT,
            AssertionVerificationState.ERROR,
        }
        if incomplete_expected and observed.state in {
            AssertionVerificationState.VERIFIED,
            AssertionVerificationState.CONTRADICTED,
            AssertionVerificationState.QUALIFIED,
        }:
            false_resolved += 1
        allowed = {operand.evidence_id for operand in operands}
        out_of_packet += len(set(observed.evidence_ids) - allowed)
        results.append(
            NumericalOperationCaseResult(
                case_id=fixture.case_id,
                observed_state=observed.state,
                expected_state=fixture.expected_state,
                observed_result=observed_result,
                expected_result=fixture.expected_result,
                passed=passed,
                issues=observed.issues,
            )
        )
    passed_count = sum(item.passed for item in results)
    accuracy = passed_count / len(results)
    return NumericalOperationEvaluation(
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


def export_numerical_evaluation(
    evaluation: NumericalOperationEvaluation,
    path: str | Path,
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(evaluation.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
    return target
