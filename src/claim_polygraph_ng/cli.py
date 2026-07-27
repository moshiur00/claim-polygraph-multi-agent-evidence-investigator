"""Command-line interface for local Claim Polygraph NG investigations."""

import argparse
import asyncio
import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from claim_polygraph_ng.application import ComplexInvestigationService, InvestigationService
from claim_polygraph_ng.domain import ArtifactType, ClaimDecomposition, InvestigationStatus
from claim_polygraph_ng.evaluation import (
    BenchmarkEvidenceSearchProvider,
    RecordingSearchProvider,
    RetrievalCandidateSearchProvider,
    RetrievalQueryStrategy,
    SnapshotReplaySearchProvider,
    audit_phase3_gates,
    build_retrieval_snapshot,
    compare_complex_evaluations,
    export_benchmark,
    export_complex_evaluation,
    export_complex_stability,
    export_evaluation,
    export_page_fetch_evaluation,
    export_phase3_gate_audit,
    export_retrieval_evaluation,
    export_retrieval_snapshot,
    export_semantic_passage_evaluation,
    load_benchmark,
    load_complex_evaluation,
    load_page_fetch_evaluation,
    load_phase4_manifest,
    load_retrieval_evaluation,
    load_retrieval_snapshot,
    load_semantic_passage_evaluation,
    merge_complex_evaluations,
    review_benchmark_cases,
    run_complex_evaluation,
    run_evaluation,
    run_page_fetch_evaluation,
    run_retrieval_evaluation,
    run_semantic_passage_evaluation,
    validate_initial_benchmark,
    verify_phase4_manifest,
)
from claim_polygraph_ng.persistence import SQLiteInvestigationRepository
from claim_polygraph_ng.providers import (
    DeterministicModelProvider,
    DeterministicSearchProvider,
    OllamaStructuredModelProvider,
    OpenAIStructuredModelProvider,
    SearXNGSearchProvider,
    SerpAPISearchProvider,
    StructuredModelProvider,
)
from claim_polygraph_ng.reporting import (
    export_complex_report,
    export_report,
    load_complex_report,
    load_report,
    render_complex_markdown,
    render_markdown,
)
from claim_polygraph_ng.retrieval import SafeHttpFetcher, UrlSafetyPolicy

DEFAULT_DATABASE = Path("data") / "claim_polygraph_ng.sqlite3"
DEFAULT_ARTIFACTS = Path("artifacts")
DEFAULT_BENCHMARK = Path("benchmarks") / "initial_claims_v1.json"
DEFAULT_EVALUATION_OUTPUT = DEFAULT_ARTIFACTS / "evaluations" / "deterministic-baseline.json"
DEFAULT_COMPLEX_STABILITY_OUTPUT = (
    DEFAULT_ARTIFACTS / "evaluations" / "phase3-complex-stability.json"
)
DEFAULT_PHASE3_GATE_OUTPUT = DEFAULT_ARTIFACTS / "evaluations" / "phase3-gate-audit.json"
DEFAULT_RETRIEVAL_OUTPUT = DEFAULT_ARTIFACTS / "evaluations" / "searxng-retrieval.json"
DEFAULT_PAGE_EVALUATION_OUTPUT = DEFAULT_ARTIFACTS / "evaluations" / "page-fetch-evaluation.json"
DEFAULT_SEMANTIC_PASSAGE_OUTPUT = (
    DEFAULT_ARTIFACTS / "evaluations" / "semantic-passage-evaluation.json"
)
DEFAULT_REVIEW_CASES = tuple(f"CPNG-{number:03d}" for number in range(1, 6))
DEFAULT_AI_REVIEW_CASES = tuple(f"CPNG-{number:03d}" for number in range(6, 11))


class _EnvironmentSettings(BaseSettings):
    """Secret-safe optional hosted-provider settings."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: SecretStr | None = None
    openai_model: str | None = None
    openai_fast_model: str | None = None
    openai_timeout_seconds: float = 60.0
    serpapi_api_key: SecretStr | None = None
    serpapi_engine: str | None = None
    serpapi_language: str = "en"
    serpapi_country: str = "us"
    serpapi_timeout_seconds: float = 15.0


@dataclass(frozen=True)
class _SerpAPIOptions:
    """Secret-safe CLI configuration for the optional hosted search provider."""

    api_key: SecretStr | None
    engine: str | None
    language: str
    country: str
    timeout_seconds: float

    @property
    def enabled(self) -> bool:
        return self.engine is not None


def build_parser() -> argparse.ArgumentParser:
    """Build the public command hierarchy."""
    environment = _EnvironmentSettings()
    parser = argparse.ArgumentParser(
        prog="claim-polygraph",
        description="Run and inspect local evidence investigations.",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE,
        help=f"SQLite database path (default: {DEFAULT_DATABASE}).",
    )
    parser.add_argument(
        "--artifacts",
        type=Path,
        default=DEFAULT_ARTIFACTS,
        help=f"Report output directory (default: {DEFAULT_ARTIFACTS}).",
    )
    parser.add_argument(
        "--searxng-url",
        default=os.getenv("SEARXNG_BASE_URL"),
        help=(
            "Opt into real search through this trusted SearXNG base URL. "
            "Can also be set with SEARXNG_BASE_URL."
        ),
    )
    parser.add_argument(
        "--searxng-engines",
        default=os.getenv("SEARXNG_ENGINES"),
        help=(
            "Optional comma-separated SearXNG engines, for example bing,mojeek. "
            "Can also be set with SEARXNG_ENGINES."
        ),
    )
    parser.add_argument(
        "--serpapi-engine",
        choices=("google", "duckduckgo"),
        default=environment.serpapi_engine,
        help=(
            "Opt into hosted SerpAPI search with Google or DuckDuckGo. "
            "Requires SERPAPI_API_KEY; can also be set with SERPAPI_ENGINE."
        ),
    )
    parser.add_argument(
        "--serpapi-language",
        default=environment.serpapi_language,
        help="Two-letter SerpAPI result language (default: en).",
    )
    parser.add_argument(
        "--serpapi-country",
        default=environment.serpapi_country,
        help="Two-letter SerpAPI result country (default: us).",
    )
    parser.add_argument(
        "--serpapi-timeout",
        type=float,
        default=environment.serpapi_timeout_seconds,
        help="Per-search SerpAPI timeout in seconds (default: 15).",
    )
    parser.add_argument(
        "--ollama-url",
        default=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        help="Trusted local Ollama base URL (default: http://localhost:11434).",
    )
    parser.add_argument(
        "--ollama-model",
        default=os.getenv("OLLAMA_MODEL"),
        help=(
            "Opt into real structured reasoning with this installed Ollama model. "
            "Can also be set with OLLAMA_MODEL."
        ),
    )
    parser.add_argument(
        "--ollama-timeout",
        type=float,
        default=os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"),
        help="Per-task Ollama timeout in seconds (default: 120).",
    )
    parser.add_argument(
        "--openai-model",
        default=environment.openai_model,
        help=(
            "Opt into paid hosted reasoning with this OpenAI model. "
            "Requires OPENAI_API_KEY; can also be set with OPENAI_MODEL."
        ),
    )
    parser.add_argument(
        "--openai-fast-model",
        default=environment.openai_fast_model,
        help=(
            "Optional cheaper OpenAI model for normalization, evidence classification, "
            "and citation auditing. Can also be set with OPENAI_FAST_MODEL."
        ),
    )
    parser.add_argument(
        "--openai-timeout",
        type=float,
        default=environment.openai_timeout_seconds,
        help="Per-task OpenAI timeout in seconds (default: 60).",
    )
    parser.add_argument(
        "--no-hosted-model",
        action="store_true",
        help=(
            "Ignore OPENAI_MODEL defaults for this command and use Ollama or the "
            "deterministic development provider."
        ),
    )
    parser.add_argument(
        "--allow-pdf-host",
        action="append",
        default=[],
        metavar="HOST",
        help=(
            "Explicitly approve downloading PDFs from this exact host after checking rights. "
            "Repeat for multiple hosts; PDFs are blocked by default."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    investigate = subparsers.add_parser(
        "investigate",
        help="Run a local investigation.",
    )
    investigate.add_argument("claim", help="Factual claim to investigate.")
    investigate.add_argument(
        "--complex",
        action="store_true",
        help="Selectively decompose the claim and produce a component-coverage report.",
    )
    resume_complex = subparsers.add_parser(
        "resume-complex",
        help="Resume a checkpointed complex investigation.",
    )
    resume_complex.add_argument("investigation_id", help="Root investigation UUID.")

    subparsers.add_parser("list", help="List stored investigations.")

    show = subparsers.add_parser(
        "show",
        help="Render a stored investigation.",
    )
    show.add_argument("investigation_id", help="Investigation UUID.")

    evaluate = subparsers.add_parser(
        "evaluate",
        help="Run a versioned claim benchmark.",
    )
    evaluate.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_BENCHMARK,
        help=f"Benchmark JSON path (default: {DEFAULT_BENCHMARK}).",
    )
    evaluate.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_EVALUATION_OUTPUT,
        help=f"Evaluation JSON path (default: {DEFAULT_EVALUATION_OUTPUT}).",
    )
    evaluate.add_argument(
        "--limit",
        type=int,
        help="Run only the first N cases for a smoke test.",
    )
    evaluate.add_argument(
        "--cases",
        nargs="+",
        help="Run only these benchmark case IDs; cannot be combined with --limit.",
    )
    evaluate.add_argument(
        "--benchmark-evidence",
        action="store_true",
        help="Use each case's curated evidence packet instead of search.",
    )
    evaluate.add_argument(
        "--complex",
        action="store_true",
        help="Evaluate only cases with 2+ expected material components.",
    )
    evaluate.add_argument(
        "--retrieval-candidates",
        type=Path,
        help=(
            "Use frozen ranked search candidates, then fetch their live pages. "
            "Cannot be combined with --benchmark-evidence or a live search provider."
        ),
    )
    compare_complex = subparsers.add_parser(
        "compare-complex-runs",
        help="Compare two declared complex evaluation results for exact stability.",
    )
    compare_complex.add_argument("--first", type=Path, required=True)
    compare_complex.add_argument("--second", type=Path, required=True)
    compare_complex.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_COMPLEX_STABILITY_OUTPUT,
        help=(f"Complex stability JSON path (default: {DEFAULT_COMPLEX_STABILITY_OUTPUT})."),
    )
    merge_complex = subparsers.add_parser(
        "merge-complex-runs",
        help="Replace selected cases in a base complex run and recompute all metrics.",
    )
    merge_complex.add_argument("--dataset", type=Path, default=DEFAULT_BENCHMARK)
    merge_complex.add_argument("--base", type=Path, required=True)
    merge_complex.add_argument("--patch", type=Path, nargs="*", default=())
    merge_complex.add_argument("--output", type=Path, required=True)
    audit_phase3 = subparsers.add_parser(
        "audit-phase3",
        help="Audit declared Phase 3 release artifacts against every numerical gate.",
    )
    audit_phase3.add_argument("--dataset", type=Path, default=DEFAULT_BENCHMARK)
    audit_phase3.add_argument("--retrieval", type=Path, required=True)
    audit_phase3.add_argument("--pages", type=Path, required=True)
    audit_phase3.add_argument("--phase2-baseline", type=Path, required=True)
    audit_phase3.add_argument("--semantic", type=Path)
    audit_phase3.add_argument("--first-run", type=Path)
    audit_phase3.add_argument("--second-run", type=Path)
    audit_phase3.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_PHASE3_GATE_OUTPUT,
    )
    verify_phase4 = subparsers.add_parser(
        "verify-phase4-manifest",
        help="Verify the frozen Phase 4 baseline without network or model calls.",
    )
    verify_phase4.add_argument("--manifest", type=Path, required=True)
    verify_phase4.add_argument(
        "--project-root",
        type=Path,
        default=Path("."),
        help="Root used to resolve manifest artifact paths (default: current directory).",
    )
    evaluate_retrieval = subparsers.add_parser(
        "evaluate-retrieval",
        help="Measure claim-only SearXNG candidates against reviewed evidence.",
    )
    evaluate_retrieval.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_BENCHMARK,
        help=f"Benchmark JSON path (default: {DEFAULT_BENCHMARK}).",
    )
    evaluate_retrieval.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_RETRIEVAL_OUTPUT,
        help=f"Retrieval summary path (default: {DEFAULT_RETRIEVAL_OUTPUT}).",
    )
    evaluate_retrieval.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Run only the first N cases (default: 5).",
    )
    evaluate_retrieval.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Number of SearXNG candidates per claim (default: 10).",
    )
    evaluate_retrieval.add_argument(
        "--lexical-threshold",
        type=float,
        default=0.3,
        help="Jaccard threshold for the snippet lexical proxy (default: 0.3).",
    )
    evaluate_retrieval.add_argument(
        "--query-strategy",
        choices=tuple(strategy.value for strategy in RetrievalQueryStrategy),
        default=RetrievalQueryStrategy.CLAIM_ONLY.value,
        help="Non-oracle query strategy (default: claim_only).",
    )
    evaluate_retrieval.add_argument(
        "--snapshot-output",
        type=Path,
        help="Record every raw normalized query response to this snapshot.",
    )
    evaluate_retrieval.add_argument(
        "--snapshot-input",
        type=Path,
        help="Replay query responses from this snapshot without using a live search provider.",
    )
    evaluate_retrieval.add_argument(
        "--empty-result-retries",
        type=int,
        default=2,
        help="Retries for unexpectedly empty live searches (default: 2).",
    )
    evaluate_retrieval.add_argument(
        "--search-delay",
        type=float,
        default=1.0,
        help="Seconds between live search calls (default: 1).",
    )
    evaluate_retrieval.add_argument(
        "--component-queries",
        action="store_true",
        help=(
            "Also query every declared material component and report component-level "
            "candidate coverage."
        ),
    )
    evaluate_pages = subparsers.add_parser(
        "evaluate-pages",
        help="Fetch and rank passages from a retrieval evaluation's top candidates.",
    )
    evaluate_pages.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_BENCHMARK,
        help=f"Benchmark JSON path (default: {DEFAULT_BENCHMARK}).",
    )
    evaluate_pages.add_argument(
        "--retrieval",
        type=Path,
        required=True,
        help="Retrieval evaluation JSON whose ranked candidates will be fetched.",
    )
    evaluate_pages.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_PAGE_EVALUATION_OUTPUT,
        help=f"Page evaluation JSON path (default: {DEFAULT_PAGE_EVALUATION_OUTPUT}).",
    )
    evaluate_pages.add_argument(
        "--top-n",
        type=int,
        default=3,
        help="Candidates fetched per claim (default: 3).",
    )
    evaluate_pages.add_argument(
        "--passage-top-k",
        type=int,
        default=3,
        help="Ranked passages retained per fetched page (default: 3).",
    )
    evaluate_pages.add_argument(
        "--passage-lexical-threshold",
        type=float,
        default=0.5,
        help="Reviewed-passage token-coverage threshold (default: 0.5).",
    )
    evaluate_semantic = subparsers.add_parser(
        "evaluate-semantic-passages",
        help="Semantically compare borderline passages with reviewed evidence.",
    )
    evaluate_semantic.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_BENCHMARK,
        help=f"Benchmark JSON path (default: {DEFAULT_BENCHMARK}).",
    )
    evaluate_semantic.add_argument(
        "--pages",
        type=Path,
        required=True,
        help="Page-fetch evaluation JSON containing per-reference passages.",
    )
    evaluate_semantic.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_SEMANTIC_PASSAGE_OUTPUT,
        help=f"Semantic evaluation JSON path (default: {DEFAULT_SEMANTIC_PASSAGE_OUTPUT}).",
    )
    evaluate_semantic.add_argument(
        "--lower-lexical-threshold",
        type=float,
        default=0.2,
        help="Minimum token coverage sent for semantic comparison (default: 0.2).",
    )
    review_status = subparsers.add_parser(
        "review-status",
        help="Show human-review readiness for benchmark cases.",
    )
    review_status.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_BENCHMARK,
        help=f"Benchmark JSON path (default: {DEFAULT_BENCHMARK}).",
    )
    review_status.add_argument(
        "--cases",
        nargs="+",
        default=DEFAULT_REVIEW_CASES,
        help="Case IDs to inspect (default: CPNG-001 through CPNG-005).",
    )
    ai_review = subparsers.add_parser(
        "ai-review",
        help="Run transparent, non-human annotator and critic passes.",
    )
    ai_review.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_BENCHMARK,
        help=f"Benchmark JSON path to update (default: {DEFAULT_BENCHMARK}).",
    )
    ai_review.add_argument(
        "--cases",
        nargs="+",
        default=DEFAULT_AI_REVIEW_CASES,
        help="Case IDs to review (default: CPNG-006 through CPNG-010).",
    )
    ai_review.add_argument(
        "--annotator-model",
        default=environment.openai_model,
        help="OpenAI annotator model (default: OPENAI_MODEL).",
    )
    ai_review.add_argument(
        "--critic-model",
        default=environment.openai_fast_model,
        help="OpenAI critic model (default: OPENAI_FAST_MODEL).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run a CLI command and return a process exit code."""
    args = build_parser().parse_args(argv)
    if args.no_hosted_model:
        args.openai_model = None
        args.openai_fast_model = None
    environment = _EnvironmentSettings()
    serpapi = _SerpAPIOptions(
        api_key=environment.serpapi_api_key,
        engine=args.serpapi_engine,
        language=args.serpapi_language,
        country=args.serpapi_country,
        timeout_seconds=args.serpapi_timeout,
    )

    try:
        if args.command == "review-status":
            return _review_status(args.dataset, args.cases)
        if args.command == "ai-review":
            return _ai_review(
                args.dataset,
                tuple(args.cases),
                args.annotator_model,
                args.critic_model,
                args.openai_timeout,
            )
        if args.command == "compare-complex-runs":
            return _compare_complex_runs(args.first, args.second, args.output)
        if args.command == "merge-complex-runs":
            return _merge_complex_runs(
                args.dataset,
                args.base,
                tuple(args.patch),
                args.output,
            )
        if args.command == "audit-phase3":
            return _audit_phase3(
                args.dataset,
                args.retrieval,
                args.pages,
                args.phase2_baseline,
                args.semantic,
                args.first_run,
                args.second_run,
                args.output,
            )
        if args.command == "verify-phase4-manifest":
            return _verify_phase4_manifest(args.manifest, args.project_root)
        if args.command == "evaluate-retrieval":
            return _evaluate_retrieval(
                args.dataset,
                args.output,
                args.limit,
                args.top_k,
                args.lexical_threshold,
                args.query_strategy,
                args.snapshot_output,
                args.snapshot_input,
                args.searxng_url,
                args.searxng_engines,
                serpapi,
                args.empty_result_retries,
                args.search_delay,
                args.component_queries,
            )
        if args.command == "evaluate-pages":
            return _evaluate_pages(
                args.dataset,
                args.retrieval,
                args.output,
                args.top_n,
                args.passage_top_k,
                args.passage_lexical_threshold,
                tuple(args.allow_pdf_host),
            )
        if args.command == "evaluate-semantic-passages":
            return _evaluate_semantic_passages(
                args.dataset,
                args.pages,
                args.output,
                args.lower_lexical_threshold,
                args.ollama_url,
                args.ollama_model,
                args.ollama_timeout,
                args.openai_model,
                args.openai_fast_model,
                args.openai_timeout,
            )
        repository = _repository(args.database)
        if args.command == "investigate":
            return _investigate(
                repository,
                args.artifacts,
                args.claim,
                args.searxng_url,
                args.searxng_engines,
                serpapi,
                args.ollama_url,
                args.ollama_model,
                args.ollama_timeout,
                args.openai_model,
                args.openai_fast_model,
                args.openai_timeout,
                tuple(args.allow_pdf_host),
                args.complex,
            )
        if args.command == "resume-complex":
            return _resume_complex(
                repository,
                args.artifacts,
                args.investigation_id,
                args.searxng_url,
                args.searxng_engines,
                serpapi,
                args.ollama_url,
                args.ollama_model,
                args.ollama_timeout,
                args.openai_model,
                args.openai_fast_model,
                args.openai_timeout,
                tuple(args.allow_pdf_host),
            )
        if args.command == "list":
            return _list(repository)
        if args.command == "show":
            return _show(repository, args.artifacts, args.investigation_id)
        if args.command == "evaluate":
            return _evaluate(
                repository,
                args.dataset,
                args.output,
                args.limit,
                tuple(args.cases) if args.cases else (),
                args.benchmark_evidence,
                args.complex,
                args.retrieval_candidates,
                args.searxng_url,
                args.searxng_engines,
                serpapi,
                args.ollama_url,
                args.ollama_model,
                args.ollama_timeout,
                args.openai_model,
                args.openai_fast_model,
                args.openai_timeout,
                tuple(args.allow_pdf_host),
            )
    except (LookupError, OSError, RuntimeError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    raise RuntimeError(f"unsupported command: {args.command}")


def _repository(database: Path) -> SQLiteInvestigationRepository:
    database.parent.mkdir(parents=True, exist_ok=True)
    repository = SQLiteInvestigationRepository(database)
    repository.initialize()
    return repository


def _investigate(
    repository: SQLiteInvestigationRepository,
    artifacts: Path,
    claim: str,
    searxng_url: str | None,
    searxng_engines: str | None,
    serpapi: _SerpAPIOptions,
    ollama_url: str,
    ollama_model: str | None,
    ollama_timeout: float,
    openai_model: str | None,
    openai_fast_model: str | None,
    openai_timeout: float,
    allowed_pdf_hosts: tuple[str, ...],
    complex_mode: bool,
) -> int:
    if searxng_url or serpapi.enabled:
        search_provider = _configured_search_provider(
            searxng_url,
            searxng_engines,
            serpapi,
        )
        content_fetcher = _safe_fetcher(allowed_pdf_hosts)
        retrieval_message = (
            f"Retrieval: {search_provider.provider_id} search and safe public-page fetching."
        )
    else:
        search_provider = DeterministicSearchProvider()
        content_fetcher = None
        retrieval_message = "Retrieval: deterministic synthetic search content."

    model_provider, model_message = _configured_model_provider(
        ollama_model,
        ollama_url,
        ollama_timeout,
        openai_model,
        openai_fast_model,
        openai_timeout,
    )

    if complex_mode:
        complex_service = ComplexInvestigationService(
            repository=repository,
            model_provider=model_provider,
            search_provider=search_provider,
            content_fetcher=content_fetcher,
        )
        complex_report = asyncio.run(complex_service.investigate(claim))
        events = repository.list_events(complex_report.investigation.investigation_id)
        exported = export_complex_report(complex_report, events, artifacts)
        print(f"Investigation ID: {complex_report.investigation.investigation_id}")
        print(f"Status: {complex_report.investigation.status.value}")
        print(f"Verdict: {complex_report.verdict.label.value}")
        print(f"Components: {len(complex_report.component_reports)}")
        print(f"Coverage: {complex_report.coverage.material_coverage_rate:.2%}")
        print(f"Report: {exported.report_markdown}")
        print(f"{retrieval_message} {model_message}")
        return 0

    service = InvestigationService(
        repository=repository,
        model_provider=model_provider,
        search_provider=search_provider,
        content_fetcher=content_fetcher,
    )
    report = asyncio.run(service.investigate(claim))
    events = repository.list_events(report.investigation.investigation_id)
    exported = export_report(report, events, artifacts)

    print(f"Investigation ID: {report.investigation.investigation_id}")
    print(f"Status: {report.investigation.status.value}")
    print(f"Verdict: {report.verdict.label.value}")
    print(f"Report: {exported.report_markdown}")
    print(f"{retrieval_message} {model_message}")
    return 0


def _resume_complex(
    repository: SQLiteInvestigationRepository,
    artifacts: Path,
    raw_investigation_id: str,
    searxng_url: str | None,
    searxng_engines: str | None,
    serpapi: _SerpAPIOptions,
    ollama_url: str,
    ollama_model: str | None,
    ollama_timeout: float,
    openai_model: str | None,
    openai_fast_model: str | None,
    openai_timeout: float,
    allowed_pdf_hosts: tuple[str, ...],
) -> int:
    investigation_id = UUID(raw_investigation_id)
    if searxng_url or serpapi.enabled:
        search_provider = _configured_search_provider(
            searxng_url,
            searxng_engines,
            serpapi,
        )
        content_fetcher = _safe_fetcher(allowed_pdf_hosts)
    else:
        search_provider = DeterministicSearchProvider()
        content_fetcher = None
    model_provider, _ = _configured_model_provider(
        ollama_model,
        ollama_url,
        ollama_timeout,
        openai_model,
        openai_fast_model,
        openai_timeout,
    )
    service = ComplexInvestigationService(
        repository=repository,
        model_provider=model_provider,
        search_provider=search_provider,
        content_fetcher=content_fetcher,
    )
    report = asyncio.run(service.resume(investigation_id))
    events = repository.list_events(investigation_id)
    exported = export_complex_report(report, events, artifacts)
    print(f"Investigation ID: {investigation_id}")
    print(f"Status: {report.investigation.status.value}")
    print(f"Verdict: {report.verdict.label.value}")
    print(f"Components: {len(report.component_reports)}")
    print(f"Coverage: {report.coverage.material_coverage_rate:.2%}")
    print(f"Report: {exported.report_markdown}")
    return 0


def _list(repository: SQLiteInvestigationRepository) -> int:
    investigations = repository.list_investigations()
    if not investigations:
        print("No investigations found.")
        return 0

    print("ID                                   STATUS      STAGE             CLAIM")
    for investigation in investigations:
        claim = investigation.input_claim.replace("\n", " ")
        if len(claim) > 60:
            claim = claim[:57] + "..."
        print(
            f"{investigation.investigation_id} "
            f"{investigation.status.value:<11} "
            f"{investigation.stage.value:<17} "
            f"{claim}"
        )
    return 0


def _evaluate(
    repository: SQLiteInvestigationRepository,
    dataset_path: Path,
    output_path: Path,
    limit: int | None,
    case_ids: tuple[str, ...],
    benchmark_evidence: bool,
    complex_mode: bool,
    retrieval_candidates_path: Path | None,
    searxng_url: str | None,
    searxng_engines: str | None,
    serpapi: _SerpAPIOptions,
    ollama_url: str,
    ollama_model: str | None,
    ollama_timeout: float,
    openai_model: str | None,
    openai_fast_model: str | None,
    openai_timeout: float,
    allowed_pdf_hosts: tuple[str, ...],
) -> int:
    dataset = load_benchmark(dataset_path)
    if dataset.dataset_id == "initial_claims":
        validate_initial_benchmark(dataset)
    if limit is not None and case_ids:
        raise ValueError("--limit and --cases cannot be combined")
    if case_ids:
        cases_by_id = {case.case_id: case for case in dataset.cases}
        missing = tuple(case_id for case_id in case_ids if case_id not in cases_by_id)
        if missing:
            raise LookupError(f"benchmark cases not found: {', '.join(missing)}")
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("--cases values must be unique")
        dataset = dataset.model_copy(
            update={"cases": tuple(cases_by_id[case_id] for case_id in case_ids)}
        )

    selected_retrieval_modes = sum(
        (
            benchmark_evidence,
            retrieval_candidates_path is not None,
            searxng_url is not None,
            serpapi.enabled,
        )
    )
    if selected_retrieval_modes > 1:
        raise ValueError(
            "--benchmark-evidence, --retrieval-candidates, --searxng-url, and "
            "--serpapi-engine are mutually exclusive"
        )

    search_provider = None
    retrieval_candidates = None
    if benchmark_evidence:
        content_fetcher = None
        retrieval_mode = "benchmark_evidence"
    elif retrieval_candidates_path is not None:
        retrieval_candidates = load_retrieval_evaluation(retrieval_candidates_path)
        if (
            retrieval_candidates.dataset_id != dataset.dataset_id
            or retrieval_candidates.dataset_version != dataset.version
        ):
            raise ValueError("retrieval candidates do not match the benchmark dataset")
        content_fetcher = _safe_fetcher(allowed_pdf_hosts)
        retrieval_mode = "frozen_candidates_live_pages"
    elif searxng_url:
        search_provider = _searxng_provider(searxng_url, searxng_engines)
        content_fetcher = _safe_fetcher(allowed_pdf_hosts)
        retrieval_mode = "real_retrieval"
    elif serpapi.enabled:
        search_provider = _serpapi_provider(serpapi)
        content_fetcher = _safe_fetcher(allowed_pdf_hosts)
        retrieval_mode = "serpapi_retrieval"
    else:
        search_provider = DeterministicSearchProvider()
        content_fetcher = None
        retrieval_mode = "deterministic_retrieval"

    model_provider, _ = _configured_model_provider(
        ollama_model,
        ollama_url,
        ollama_timeout,
        openai_model,
        openai_fast_model,
        openai_timeout,
    )
    if openai_model:
        reasoning_mode = f"openai:{openai_model}"
    elif ollama_model:
        reasoning_mode = f"ollama:{ollama_model}"
    else:
        reasoning_mode = "deterministic_reasoning"
    provider_mode = f"{retrieval_mode}+{reasoning_mode}"

    def case_search_provider(case):
        if benchmark_evidence:
            return BenchmarkEvidenceSearchProvider(case)
        if retrieval_candidates is not None:
            retrieval_case = next(
                (
                    result
                    for result in retrieval_candidates.results
                    if result.case_id == case.case_id
                ),
                None,
            )
            if retrieval_case is None:
                raise RuntimeError(f"retrieval candidates are missing case {case.case_id}")
            return RetrievalCandidateSearchProvider(
                retrieval_case,
                retrieval_candidates.provider_id,
            )
        if search_provider is None:
            raise RuntimeError("evaluation search provider is not configured")
        return search_provider

    def service_factory(case) -> InvestigationService:
        return InvestigationService(
            repository=repository,
            model_provider=model_provider,
            search_provider=case_search_provider(case),
            content_fetcher=content_fetcher,
        )

    if complex_mode:

        def complex_service_factory(case) -> ComplexInvestigationService:
            shared_search_provider = case_search_provider(case)
            return ComplexInvestigationService(
                repository=repository,
                model_provider=model_provider,
                search_provider=shared_search_provider,
                component_search_provider_factory=(
                    (
                        lambda component: BenchmarkEvidenceSearchProvider.for_component(
                            case,
                            component.text,
                        )
                    )
                    if benchmark_evidence
                    else None
                ),
                content_fetcher=content_fetcher,
            )

        complex_summary = asyncio.run(
            run_complex_evaluation(
                dataset,
                complex_service_factory,
                provider_mode=provider_mode,
                limit=limit,
            )
        )
        exported = export_complex_evaluation(complex_summary, output_path)
        print(f"Dataset: {complex_summary.dataset_id} v{complex_summary.dataset_version}")
        print(f"Mode: {complex_summary.provider_mode}")
        print(
            f"Complex cases: {complex_summary.completed_case_count}/"
            f"{complex_summary.case_count} completed"
        )
        print(f"Completion rate: {complex_summary.completion_rate:.2%}")
        print(f"Component recall: {complex_summary.mean_component_recall:.2%}")
        print(f"Parent linkage: {complex_summary.parent_linkage_valid_rate:.2%}")
        print(f"Context validity: {complex_summary.context_contract_valid_rate:.2%}")
        print(f"Material coverage: {complex_summary.material_component_coverage_rate:.2%}")
        print(
            "Parent citation full rate: "
            + (
                f"{complex_summary.parent_citation_full_rate:.2%}"
                if complex_summary.parent_citation_full_rate is not None
                else "not available"
            )
        )
        print(
            "Verdict accuracy: "
            + (
                f"{complex_summary.verdict_accuracy:.2%}"
                if complex_summary.verdict_accuracy is not None
                else "not available (no human-reviewed complex gold labels)"
            )
        )
        print(
            "Estimated cost per completed component: "
            f"${complex_summary.mean_estimated_model_cost_per_completed_component_usd:.6f}"
        )
        print(f"Summary: {exported}")
        return 0

    summary = asyncio.run(
        run_evaluation(
            dataset,
            service_factory,
            provider_mode=provider_mode,
            limit=limit,
        )
    )
    exported = export_evaluation(summary, output_path)

    print(f"Dataset: {summary.dataset_id} v{summary.dataset_version}")
    print(f"Mode: {summary.provider_mode}")
    print(f"Cases: {summary.completed_case_count}/{summary.case_count} completed")
    print(f"Completion rate: {summary.completion_rate:.2%}")
    print(f"Metered model calls: {summary.metered_model_call_count}")
    print(f"Input tokens: {summary.input_tokens} ({summary.cached_input_tokens} cached)")
    print(f"Output tokens: {summary.output_tokens}")
    print(f"Estimated model cost: ${summary.estimated_model_cost_usd:.6f}")
    print(
        "Verdict accuracy: "
        + (
            f"{summary.verdict_accuracy:.2%}"
            if summary.verdict_accuracy is not None
            else "not available (no human-reviewed gold labels)"
        )
    )
    print(
        "AI-provisional agreement: "
        + (
            f"{summary.ai_provisional_agreement_rate:.2%} "
            f"({summary.ai_provisional_comparison_count} compared; diagnostic only)"
            if summary.ai_provisional_agreement_rate is not None
            else "not available"
        )
    )
    print(f"Summary: {exported}")
    return 0


def _evaluate_retrieval(
    dataset_path: Path,
    output_path: Path,
    limit: int,
    top_k: int,
    lexical_threshold: float,
    query_strategy: str,
    snapshot_output: Path | None,
    snapshot_input: Path | None,
    searxng_url: str | None,
    searxng_engines: str | None,
    serpapi: _SerpAPIOptions,
    empty_result_retries: int,
    search_delay: float,
    component_queries: bool,
) -> int:
    if snapshot_output is not None and snapshot_input is not None:
        raise ValueError("--snapshot-output cannot be combined with --snapshot-input")
    if searxng_url and serpapi.enabled:
        raise ValueError("--searxng-url and --serpapi-engine are mutually exclusive")
    if snapshot_input is None and not searxng_url and not serpapi.enabled:
        raise ValueError(
            "retrieval evaluation requires --searxng-url, --serpapi-engine, or a snapshot input"
        )
    dataset = load_benchmark(dataset_path)
    if dataset.dataset_id == "initial_claims":
        validate_initial_benchmark(dataset)

    recording_provider = None
    if snapshot_input is not None:
        snapshot = load_retrieval_snapshot(snapshot_input)
        if snapshot.dataset_id != dataset.dataset_id or snapshot.dataset_version != dataset.version:
            raise ValueError(
                "retrieval snapshot dataset identity/version does not match the benchmark"
            )
        provider = SnapshotReplaySearchProvider(snapshot)
    else:
        live_provider = _configured_search_provider(
            searxng_url,
            searxng_engines,
            serpapi,
        )
        if snapshot_output is not None:
            recording_provider = RecordingSearchProvider(live_provider)
            provider = recording_provider
        else:
            provider = live_provider

    summary = asyncio.run(
        run_retrieval_evaluation(
            dataset,
            provider,
            limit=limit,
            top_k=top_k,
            lexical_threshold=lexical_threshold,
            query_strategy=query_strategy,
            empty_result_retries=(0 if snapshot_input is not None else empty_result_retries),
            retry_delay_seconds=0.0 if snapshot_input is not None else search_delay,
            include_component_queries=component_queries,
        )
    )
    exported_snapshot = None
    if recording_provider is not None and snapshot_output is not None:
        snapshot = build_retrieval_snapshot(
            dataset,
            recording_provider,
            top_k=top_k,
            require_nonempty=True,
        )
        exported_snapshot = export_retrieval_snapshot(snapshot, snapshot_output)
    exported = export_retrieval_evaluation(summary, output_path)

    print(f"Dataset: {summary.dataset_id} v{summary.dataset_version}")
    print(f"Provider: {summary.provider_id}")
    print(f"Query strategy: {summary.query_strategy.value}")
    print(f"Search calls: {summary.search_call_count}")
    print(f"Cases: {summary.completed_case_count}/{summary.case_count} searched")
    print(f"Top K: {summary.top_k}")
    print(f"Reviewed references: {summary.reference_count}")
    print(
        "Exact URL recall@K: "
        + (
            f"{summary.exact_url_recall_at_k:.2%}"
            if summary.exact_url_recall_at_k is not None
            else "not available"
        )
    )
    print(
        "Reviewed host recall@K: "
        + (
            f"{summary.reviewed_host_recall_at_k:.2%}"
            if summary.reviewed_host_recall_at_k is not None
            else "not available"
        )
    )
    print(f"Reviewed host MRR: {summary.reviewed_host_mrr:.4f}")
    print(f"Case success@K: {summary.case_success_at_k:.2%}")
    print(
        "Lexical snippet proxy recall@K: "
        + (
            f"{summary.lexical_proxy_recall_at_k:.2%}"
            if summary.lexical_proxy_recall_at_k is not None
            else "not available"
        )
    )
    print(f"Mean candidate quality: {summary.mean_candidate_quality_score:.4f}")
    print(f"Low-quality candidate rate: {summary.low_quality_candidate_rate:.2%}")
    print(f"Unique-host rate: {summary.unique_host_rate:.2%}")
    if summary.component_query_enabled:
        print(f"Component query completion: {summary.component_query_completion_rate or 0.0:.2%}")
        print(f"Components with a candidate: {summary.component_candidate_rate or 0.0:.2%}")
        print(
            "Components recovering reviewed evidence: "
            f"{summary.component_reviewed_evidence_rate or 0.0:.2%}"
        )
    print(f"Summary: {exported}")
    if exported_snapshot is not None:
        print(f"Snapshot: {exported_snapshot}")
    return 0


def _compare_complex_runs(
    first_path: Path,
    second_path: Path,
    output_path: Path,
) -> int:
    first = load_complex_evaluation(first_path)
    second = load_complex_evaluation(second_path)
    summary = compare_complex_evaluations(first, second)
    exported = export_complex_stability(summary, output_path)

    print(f"Dataset: {summary.dataset_id} v{summary.dataset_version}")
    print(f"Cases: {summary.case_count}")
    print(f"Completion stability: {summary.completion_stability_rate:.2%}")
    print(
        "Exact verdict stability: "
        + (
            f"{summary.exact_verdict_stability_rate:.2%} "
            f"({summary.verdict_comparison_count} compared)"
            if summary.exact_verdict_stability_rate is not None
            else "not available"
        )
    )
    print(
        "Exact component-set stability: "
        + (
            f"{summary.exact_component_set_stability_rate:.2%}"
            if summary.exact_component_set_stability_rate is not None
            else "not available"
        )
    )
    print(f"Summary: {exported}")
    return 0


def _merge_complex_runs(
    dataset_path: Path,
    base_path: Path,
    patch_paths: tuple[Path, ...],
    output_path: Path,
) -> int:
    summary = merge_complex_evaluations(
        load_benchmark(dataset_path),
        load_complex_evaluation(base_path),
        tuple(load_complex_evaluation(path) for path in patch_paths),
    )
    exported = export_complex_evaluation(summary, output_path)
    print(f"Dataset: {summary.dataset_id} v{summary.dataset_version}")
    print(f"Cases: {summary.completed_case_count}/{summary.case_count} completed")
    print(f"Component recall: {summary.mean_component_recall:.2%}")
    print(
        "Parent citation full rate: "
        + (
            f"{summary.parent_citation_full_rate:.2%}"
            if summary.parent_citation_full_rate is not None
            else "not available"
        )
    )
    print(
        "Verdict accuracy: "
        + (
            f"{summary.verdict_accuracy:.2%}"
            if summary.verdict_accuracy is not None
            else "not available"
        )
    )
    print(f"Summary: {exported}")
    return 0


def _audit_phase3(
    dataset_path: Path,
    retrieval_path: Path,
    pages_path: Path,
    phase2_baseline_path: Path,
    semantic_path: Path | None,
    first_run_path: Path | None,
    second_run_path: Path | None,
    output_path: Path,
) -> int:
    dataset = load_benchmark(dataset_path)
    audit = audit_phase3_gates(
        dataset,
        load_retrieval_evaluation(retrieval_path),
        load_page_fetch_evaluation(pages_path),
        baseline_semantic=load_semantic_passage_evaluation(phase2_baseline_path),
        semantic=(load_semantic_passage_evaluation(semantic_path) if semantic_path else None),
        first_run=(load_complex_evaluation(first_run_path) if first_run_path else None),
        second_run=(load_complex_evaluation(second_run_path) if second_run_path else None),
    )
    exported = export_phase3_gate_audit(audit, output_path)

    print(f"Dataset: {audit.dataset_id} v{audit.dataset_version}")
    for gate in audit.gates:
        print(f"{gate.state.value.upper():<7} {gate.gate_id:<38} {gate.observed}")
    print(
        f"Gates: {audit.passed_count} passed, {audit.failed_count} failed, "
        f"{audit.pending_count} pending"
    )
    print(f"Release ready: {'yes' if audit.release_ready else 'no'}")
    print(f"Audit: {exported}")
    return 0 if audit.release_ready else 1


def _verify_phase4_manifest(manifest_path: Path, project_root: Path) -> int:
    manifest = load_phase4_manifest(manifest_path)
    result = verify_phase4_manifest(manifest, project_root)
    print(f"Manifest: {result.manifest_id}")
    print(f"Artifacts checked: {result.checked_artifact_count}")
    if result.errors:
        for error in result.errors:
            print(f"FAILED  {error}")
    print(f"Valid: {'yes' if result.valid else 'no'}")
    return 0 if result.valid else 1


def _evaluate_pages(
    dataset_path: Path,
    retrieval_path: Path,
    output_path: Path,
    top_n: int,
    passage_top_k: int,
    passage_lexical_threshold: float,
    allowed_pdf_hosts: tuple[str, ...],
) -> int:
    dataset = load_benchmark(dataset_path)
    if dataset.dataset_id == "initial_claims":
        validate_initial_benchmark(dataset)
    retrieval = load_retrieval_evaluation(retrieval_path)
    summary = asyncio.run(
        run_page_fetch_evaluation(
            dataset,
            retrieval,
            _safe_fetcher(allowed_pdf_hosts),
            retrieval_input=str(retrieval_path),
            candidate_top_n=top_n,
            passage_top_k=passage_top_k,
            passage_lexical_threshold=passage_lexical_threshold,
        )
    )
    exported = export_page_fetch_evaluation(summary, output_path)

    print(f"Dataset: {summary.dataset_id} v{summary.dataset_version}")
    print(f"Retrieval strategy: {summary.retrieval_strategy.value}")
    print(f"Attempted pages: {summary.attempted_page_count}")
    print(f"Fetch success: {summary.fetch_success_rate:.2%}")
    print(f"Extraction success: {summary.extraction_success_rate:.2%}")
    print(f"Duplicate content: {summary.duplicate_content_rate:.2%}")
    print(
        "Passage lexical recall: "
        + (
            f"{summary.passage_lexical_recall:.2%}"
            if summary.passage_lexical_recall is not None
            else "not available"
        )
    )
    print(f"Case passage success: {summary.case_passage_success_rate:.2%}")
    print(f"Summary: {exported}")
    return 0


def _safe_fetcher(allowed_pdf_hosts: tuple[str, ...]) -> SafeHttpFetcher:
    return SafeHttpFetcher(policy=UrlSafetyPolicy(allowed_pdf_hosts=frozenset(allowed_pdf_hosts)))


def _searxng_provider(
    base_url: str,
    configured_engines: str | None,
) -> SearXNGSearchProvider:
    engines = tuple(
        value.strip() for value in (configured_engines or "").split(",") if value.strip()
    )
    return SearXNGSearchProvider(base_url, engines=engines)


def _serpapi_provider(options: _SerpAPIOptions) -> SerpAPISearchProvider:
    if options.api_key is None:
        raise ValueError("--serpapi-engine requires SERPAPI_API_KEY")
    if options.engine is None:
        raise ValueError("SerpAPI engine is not configured")
    return SerpAPISearchProvider(
        api_key=options.api_key.get_secret_value(),
        engine=options.engine,
        language=options.language,
        country=options.country,
        timeout_seconds=options.timeout_seconds,
    )


def _configured_search_provider(
    searxng_url: str | None,
    searxng_engines: str | None,
    serpapi: _SerpAPIOptions,
) -> SearXNGSearchProvider | SerpAPISearchProvider:
    if searxng_url and serpapi.enabled:
        raise ValueError("--searxng-url and --serpapi-engine are mutually exclusive")
    if searxng_url:
        return _searxng_provider(searxng_url, searxng_engines)
    if serpapi.enabled:
        return _serpapi_provider(serpapi)
    raise ValueError("a live search provider is not configured")


def _evaluate_semantic_passages(
    dataset_path: Path,
    pages_path: Path,
    output_path: Path,
    lower_lexical_threshold: float,
    ollama_url: str,
    ollama_model: str | None,
    ollama_timeout: float,
    openai_model: str | None,
    openai_fast_model: str | None,
    openai_timeout: float,
) -> int:
    if not openai_model and not ollama_model:
        raise ValueError("semantic passage evaluation requires --openai-model or --ollama-model")
    dataset = load_benchmark(dataset_path)
    if dataset.dataset_id == "initial_claims":
        validate_initial_benchmark(dataset)
    pages = load_page_fetch_evaluation(pages_path)
    provider, _ = _configured_model_provider(
        ollama_model,
        ollama_url,
        ollama_timeout,
        openai_model,
        openai_fast_model,
        openai_timeout,
    )
    summary = asyncio.run(
        run_semantic_passage_evaluation(
            dataset,
            pages,
            provider,
            page_evaluation_input=str(pages_path),
            lower_lexical_threshold=lower_lexical_threshold,
        )
    )
    exported = export_semantic_passage_evaluation(summary, output_path)

    print(f"Dataset: {summary.dataset_id} v{summary.dataset_version}")
    print(f"Provider: {summary.provider_id}")
    print(f"Model: {summary.model}")
    print(f"Lexical matches: {summary.lexical_match_count}/{summary.reference_count}")
    print(f"Semantic candidates: {summary.semantic_candidate_count}")
    print(f"Equivalent: {summary.equivalent_count}")
    print(f"Partial: {summary.partial_count}")
    print(f"Not equivalent: {summary.not_equivalent_count}")
    print(
        "Combined passage recall: "
        + (
            f"{summary.combined_passage_recall:.2%}"
            if summary.combined_passage_recall is not None
            else "not available"
        )
    )
    print(f"Model calls: {summary.metered_model_call_count}")
    print(f"Estimated model cost: ${summary.estimated_model_cost_usd:.6f}")
    print(f"Summary: {exported}")
    return 0


def _review_status(dataset_path: Path, case_ids: Sequence[str]) -> int:
    dataset = load_benchmark(dataset_path)
    cases_by_id = {case.case_id: case for case in dataset.cases}
    missing = [case_id for case_id in case_ids if case_id not in cases_by_id]
    if missing:
        raise LookupError(f"benchmark cases not found: {', '.join(missing)}")

    print(
        "CASE      STATUS    PROPOSED          EXPECTED          "
        "EVIDENCE  ANNOTATOR            APPROVER"
    )
    for case_id in case_ids:
        case = cases_by_id[case_id]
        print(
            f"{case.case_id:<9} "
            f"{case.annotation_status.value:<9} "
            f"{case.proposed_verdict.value if case.proposed_verdict else '-':<17} "
            f"{case.expected_verdict.value if case.expected_verdict else '-':<17} "
            f"{len(case.candidate_evidence):<9} "
            f"{case.annotated_by or '-':<20} "
            f"{case.approved_by or '-'}"
        )

    reviewed = sum(
        cases_by_id[case_id].annotation_status.value == "reviewed" for case_id in case_ids
    )
    print(f"Reviewed: {reviewed}/{len(case_ids)}")
    return 0


def _ai_review(
    dataset_path: Path,
    case_ids: tuple[str, ...],
    annotator_model: str | None,
    critic_model: str | None,
    timeout_seconds: float,
) -> int:
    if not annotator_model or not critic_model:
        raise ValueError(
            "AI review requires OPENAI_MODEL and OPENAI_FAST_MODEL "
            "or explicit annotator and critic models"
        )
    api_key = _EnvironmentSettings().openai_api_key
    if api_key is None:
        raise ValueError("OPENAI_API_KEY is required for AI review")

    provider = OpenAIStructuredModelProvider(
        api_key=api_key.get_secret_value(),
        model=annotator_model,
        fast_model=critic_model,
        timeout_seconds=timeout_seconds,
    )
    reviewed = asyncio.run(
        review_benchmark_cases(
            load_benchmark(dataset_path),
            provider,
            case_ids,
        )
    )
    export_benchmark(reviewed, dataset_path)

    cases_by_id = {case.case_id: case for case in reviewed.cases}
    total_cost = 0.0
    print("CASE      STATUS       PROVISIONAL       ANNOTATOR        CRITIC")
    for case_id in case_ids:
        case = cases_by_id[case_id]
        if case.ai_review is None:
            continue
        total_cost += sum(item.estimated_cost_usd or 0.0 for item in case.ai_review.usage)
        print(
            f"{case.case_id:<9} "
            f"{case.annotation_status.value:<12} "
            f"{case.ai_review.provisional_verdict.value:<17} "
            f"{case.ai_review.annotator_model:<16} "
            f"{case.ai_review.critic_model}"
        )
    print(f"Estimated review cost: ${total_cost:.6f}")
    print("Human-grounded accuracy remains unchanged; expected_verdict was not set.")
    return 0


def _configured_model_provider(
    ollama_model: str | None,
    ollama_url: str,
    ollama_timeout: float,
    openai_model: str | None,
    openai_fast_model: str | None,
    openai_timeout: float,
) -> tuple[StructuredModelProvider, str]:
    if openai_fast_model and not openai_model:
        raise ValueError("--openai-fast-model requires --openai-model or OPENAI_MODEL")
    if ollama_model and (openai_model or openai_fast_model):
        raise ValueError("choose either --ollama-model or --openai-model, not both")
    if openai_model:
        api_key = _EnvironmentSettings().openai_api_key
        if api_key is None:
            raise ValueError(
                "OPENAI_API_KEY is required when --openai-model or OPENAI_MODEL is set"
            )
        return (
            OpenAIStructuredModelProvider(
                api_key=api_key.get_secret_value(),
                model=openai_model,
                fast_model=openai_fast_model,
                timeout_seconds=openai_timeout,
            ),
            (
                (
                    f"Reasoning: routed OpenAI models "
                    f"{openai_fast_model} (focused tasks) and {openai_model} "
                    "(planning/verdict)"
                    if openai_fast_model
                    else f"Reasoning: paid hosted OpenAI model {openai_model}"
                )
                + "; no silent fallback. "
                "Results remain provisional and require benchmark evaluation."
            ),
        )
    if ollama_model:
        return (
            OllamaStructuredModelProvider(
                model=ollama_model,
                base_url=ollama_url,
                timeout_seconds=ollama_timeout,
            ),
            (
                f"Reasoning: local Ollama model {ollama_model}; results remain "
                "provisional and require benchmark evaluation."
            ),
        )
    return (
        DeterministicModelProvider(),
        "Reasoning: deterministic development provider, not factual analysis.",
    )


def _show(
    repository: SQLiteInvestigationRepository,
    artifacts: Path,
    raw_investigation_id: str,
) -> int:
    investigation_id = UUID(raw_investigation_id)
    investigation = repository.get_investigation(investigation_id)
    if investigation is None:
        raise LookupError(f"investigation not found: {investigation_id}")

    events = repository.list_events(investigation_id)
    if investigation.status is InvestigationStatus.COMPLETED:
        decompositions = repository.list_artifacts(
            investigation_id,
            ArtifactType.DECOMPOSITION,
            ClaimDecomposition,
        )
        if decompositions:
            complex_report = load_complex_report(repository, investigation_id)
            export_complex_report(complex_report, events, artifacts)
            print(render_complex_markdown(complex_report), end="")
            return 0
        report = load_report(repository, investigation_id)
        export_report(report, events, artifacts)
        print(render_markdown(report, events), end="")
        return 0

    print(f"Investigation ID: {investigation.investigation_id}")
    print(f"Status: {investigation.status.value}")
    print(f"Stage: {investigation.stage.value}")
    if investigation.failure_reason:
        print(f"Failure: {investigation.failure_reason}")
    print(f"Trace events: {len(events)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
