import json
from pathlib import Path

import pytest

from claim_polygraph_ng.analysis import FamilySourceRecord
from claim_polygraph_ng.reporting.provenance import (
    ProvenanceInspectionReport,
    ProvenanceSourceSummary,
    build_component_provenance_report,
    export_provenance_report,
    render_provenance_markdown,
)


def _record(source_id: str, text: str, url: str):
    return FamilySourceRecord(source_id=source_id, text=text, url=url)


def _summary(source_id: str, url: str):
    return ProvenanceSourceSummary(
        source_id=source_id,
        title=f"Source {source_id}",
        publisher="Fixture Publisher",
        canonical_url=url,
    )


def test_unresolved_pair_is_visible_in_json_and_markdown(tmp_path: Path):
    component = build_component_provenance_report(
        component_id="PROV-012",
        component_claim="The inspection found surface cracks.",
        source_records=(
            _record("A", "Inspectors observed shallow surface cracks.", "https://a.test"),
            _record("B", "An examination found minor cracking.", "https://b.test"),
        ),
        source_summaries=(
            _summary("A", "https://a.test"),
            _summary("B", "https://b.test"),
        ),
        required_independent_families=2,
    )
    report = ProvenanceInspectionReport(
        dataset_id="test",
        dataset_version=1,
        components=(component,),
        limitations=("A test limitation.",),
    )

    markdown = render_provenance_markdown(report)
    paths = export_provenance_report(report, tmp_path)
    payload = json.loads(paths.report_json.read_text(encoding="utf-8"))

    assert "Confirmed/possible independent families: [1, 2]" in markdown
    assert "Unresolved dependency pairs: 1" in markdown
    assert "insufficient_dependency_signals" in markdown
    assert "**uncertain**" in markdown
    assert payload["components"][0]["independence"]["confidence_score"] is None
    assert paths.report_markdown.read_text(encoding="utf-8") == markdown


def test_source_record_and_summary_ids_must_match():
    with pytest.raises(ValueError, match="same source IDs"):
        build_component_provenance_report(
            component_id="case",
            component_claim="A claim.",
            source_records=(_record("A", "Some source text.", "https://a.test"),),
            source_summaries=(_summary("B", "https://b.test"),),
            required_independent_families=1,
        )
