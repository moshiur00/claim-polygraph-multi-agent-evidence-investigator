"""Tests for machine-checkable Phase 3 release gates."""

from datetime import UTC, datetime
from pathlib import Path

from claim_polygraph_ng.evaluation import (
    GateState,
    PageFetchCaseResult,
    PageFetchEvaluationResult,
    PageFetchEvaluationSummary,
    RetrievalCaseResult,
    RetrievalEvaluationSummary,
    RetrievalQueryStrategy,
    SemanticPassageEvaluationSummary,
    audit_phase3_gates,
    load_benchmark,
)

BENCHMARK = Path(__file__).parents[2] / "benchmarks" / "initial_claims_v1.json"
NOW = datetime(2026, 7, 27, tzinfo=UTC)


def test_phase3_audit_passes_human_and_retrieval_gates_and_keeps_runs_pending() -> None:
    audit = audit_phase3_gates(
        load_benchmark(BENCHMARK),
        _retrieval(),
        _pages(),
        baseline_semantic=_baseline(),
    )
    states = {gate.gate_id: gate.state for gate in audit.gates}

    assert states["live_query_completion"] is GateState.PASSED
    assert states["reviewed_passage_recall"] is GateState.PASSED
    assert states["first_ten_retrieval_regression"] is GateState.PASSED
    assert states["rights_compliance"] is GateState.PASSED
    assert states["human_reviewed_benchmark"] is GateState.PASSED
    assert states["complex_case_representation"] is GateState.PASSED
    assert states["declared_run_1_accuracy"] is GateState.PENDING
    assert states["exact_repeated_label_stability"] is GateState.PENDING
    assert audit.release_ready is False


def test_phase3_rights_gate_fails_when_a_pdf_was_fetched() -> None:
    pages = _pages()
    first_case = pages.results[0]
    fetched_pdf = first_case.pages[0].model_copy(
        update={
            "requested_url": "https://example.org/source.pdf",
            "final_url": "https://example.org/source.pdf",
            "fetched": True,
            "extracted": True,
            "content_type": "application/pdf",
        }
    )
    changed_case = first_case.model_copy(update={"pages": (fetched_pdf,)})
    pages = pages.model_copy(update={"results": (changed_case, *pages.results[1:])})

    audit = audit_phase3_gates(
        load_benchmark(BENCHMARK),
        _retrieval(),
        pages,
        baseline_semantic=_baseline(),
    )
    rights = next(gate for gate in audit.gates if gate.gate_id == "rights_compliance")

    assert rights.state is GateState.FAILED
    assert rights.observed == "1 fetched PDF candidates"


def _retrieval() -> RetrievalEvaluationSummary:
    result = RetrievalCaseResult(
        case_id="CPNG-001",
        queries=("calendar year length",),
        query_errors={},
        result_count=1,
        reference_count=1,
        exact_url_hit_count=0,
        reviewed_host_hit_count=1,
        lexical_hit_count=1,
        reciprocal_rank_exact_url=0.0,
        reciprocal_rank_reviewed_host=1.0,
        candidates=(),
        references=(),
        duration_seconds=0.1,
    )
    return RetrievalEvaluationSummary(
        dataset_id="initial_claims",
        dataset_version=5,
        provider_id="test-search",
        query_strategy=RetrievalQueryStrategy.GUARDED_FUSION,
        started_at=NOW,
        duration_seconds=1.0,
        case_count=20,
        completed_case_count=20,
        completion_rate=1.0,
        top_k=10,
        search_call_count=81,
        lexical_threshold=0.3,
        reference_count=47,
        exact_url_mrr=0.0,
        reviewed_host_mrr=1.0,
        case_success_at_k=1.0,
        mean_candidate_quality_score=0.5,
        low_quality_candidate_rate=0.0,
        unique_host_rate=1.0,
        component_query_enabled=True,
        material_component_count=21,
        component_query_completion_rate=1.0,
        component_candidate_rate=1.0,
        component_reviewed_evidence_rate=0.8,
        results=(result,),
        limitations=(),
    )


def _pages() -> PageFetchEvaluationSummary:
    results = tuple(
        PageFetchCaseResult(
            case_id=f"CPNG-{number:03d}",
            attempted_count=1,
            fetched_count=1,
            extracted_count=1,
            duplicate_count=0,
            reference_count=1,
            matched_reference_count=1,
            first_matching_candidate_rank=1,
            pages=(
                PageFetchEvaluationResult(
                    case_id=f"CPNG-{number:03d}",
                    candidate_rank=1,
                    requested_url=f"https://example.org/{number}",
                    final_url=f"https://example.org/{number}",
                    fetched=True,
                    extracted=True,
                    content_type="text/html",
                    byte_length=100,
                    readable_character_count=50,
                    chunk_count=1,
                    ranked_passage_count=1,
                    best_passage_score=1.0,
                    best_passage_text="Bounded evidence passage.",
                    best_reference_lexical_score=1.0,
                    matched_reference_ids=("E1",),
                ),
            ),
        )
        for number in range(1, 21)
    )
    return PageFetchEvaluationSummary(
        dataset_id="initial_claims",
        dataset_version=5,
        retrieval_input="retrieval.json",
        retrieval_strategy=RetrievalQueryStrategy.GUARDED_FUSION,
        fetcher_id="test-fetcher",
        started_at=NOW,
        duration_seconds=1.0,
        case_count=20,
        candidate_top_n=10,
        passage_top_k=5,
        passage_lexical_threshold=0.5,
        attempted_page_count=20,
        fetched_page_count=20,
        extracted_page_count=20,
        duplicate_page_count=0,
        fetch_success_rate=1.0,
        extraction_success_rate=1.0,
        duplicate_content_rate=0.0,
        reference_count=20,
        matched_reference_count=20,
        passage_lexical_recall=1.0,
        case_passage_success_rate=1.0,
        results=results,
        limitations=(),
    )


def _baseline() -> SemanticPassageEvaluationSummary:
    return SemanticPassageEvaluationSummary(
        dataset_id="initial_claims",
        dataset_version=4,
        page_evaluation_input="phase2-pages.json",
        provider_id="test-model",
        model="test-model",
        prompt_version="test-v1",
        started_at=NOW,
        duration_seconds=1.0,
        reference_count=23,
        lexical_match_count=17,
        semantic_candidate_count=6,
        evaluated_count=6,
        equivalent_count=2,
        partial_count=3,
        not_equivalent_count=1,
        combined_match_count=19,
        combined_passage_recall=19 / 23,
        metered_model_call_count=6,
        input_tokens=100,
        cached_input_tokens=0,
        output_tokens=50,
        estimated_model_cost_usd=0.01,
        results=(),
        limitations=(),
    )
