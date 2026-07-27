"""Build the locked Stage 5.9 JSON and Markdown inspection report."""

from datetime import date
from pathlib import Path

from claim_polygraph_ng.analysis import (
    FamilySourceRecord,
    SourceQualityMetadata,
    assess_source_quality,
)
from claim_polygraph_ng.domain import SourceType
from claim_polygraph_ng.evaluation import load_provenance_benchmark
from claim_polygraph_ng.reporting.provenance import (
    ProvenanceInspectionReport,
    ProvenanceSourceSummary,
    SourceQualityReportEntry,
    build_component_provenance_report,
    export_provenance_report,
)

ROOT = Path(__file__).parents[1]


def main() -> int:
    benchmark = load_provenance_benchmark(ROOT / "benchmarks/phase5_provenance_fixtures_v1.json")
    components = []
    for case in benchmark.cases:
        records = tuple(
            FamilySourceRecord(
                source_id=source.source_id,
                url=source.url,
                text=source.excerpt,
                published_at=date.fromisoformat(source.published_at),
            )
            for source in case.sources
        )
        summaries = tuple(
            ProvenanceSourceSummary(
                source_id=source.source_id,
                title=source.title,
                publisher=source.publisher,
                canonical_url=source.url,
            )
            for source in case.sources
        )
        qualities = tuple(
            SourceQualityReportEntry(
                source_id=source.source_id,
                assessment=assess_source_quality(
                    SourceQualityMetadata(
                        source_type=SourceType.OTHER,
                        publisher_identified=bool(source.publisher),
                        author_identified=False,
                        publication_date=date.fromisoformat(source.published_at),
                    )
                ),
            )
            for source in case.sources
        )
        components.append(
            build_component_provenance_report(
                component_id=case.case_id,
                component_claim=case.component_claim,
                source_records=records,
                source_summaries=summaries,
                required_independent_families=2,
                quality_assessments=qualities,
            )
        )
    report = ProvenanceInspectionReport(
        dataset_id=benchmark.dataset_id,
        dataset_version=benchmark.version,
        components=tuple(components),
        limitations=(
            "Synthetic fixture metadata leaves many quality dimensions unknown.",
            "Independence intervals are evidence features, not verdict confidence.",
            "The failed Stage 5.7 classifier output is not included.",
        ),
    )
    paths = export_provenance_report(report, ROOT / "artifacts/evaluations/phase5-stage5.9-report")
    print(f"Components: {len(report.components)}")
    print(f"JSON: {paths.report_json}")
    print(f"Markdown: {paths.report_markdown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
