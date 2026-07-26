"""Unit tests for readable report rendering."""

import asyncio

from claim_polygraph_ng.application import InvestigationService
from claim_polygraph_ng.persistence import SQLiteInvestigationRepository
from claim_polygraph_ng.providers import (
    DeterministicModelProvider,
    DeterministicSearchProvider,
)
from claim_polygraph_ng.reporting import export_report, load_report, render_markdown


def test_report_round_trip_and_exports(tmp_path) -> None:
    repository = SQLiteInvestigationRepository(tmp_path / "report.sqlite3")
    service = InvestigationService(
        repository=repository,
        model_provider=DeterministicModelProvider(),
        search_provider=DeterministicSearchProvider(),
    )
    report = asyncio.run(service.investigate("The example programme reduced waste by ten percent."))
    investigation_id = report.investigation.investigation_id
    events = repository.list_events(investigation_id)

    loaded = load_report(repository, investigation_id)
    exported = export_report(loaded, events, tmp_path / "artifacts")
    markdown = render_markdown(loaded, events)

    assert loaded == report
    assert exported.report_json.is_file()
    assert exported.report_markdown.is_file()
    assert exported.trace_json.is_file()
    assert "# Claim Polygraph NG Investigation" in markdown
    assert "## Supporting evidence" in markdown
    assert "## Contradictory evidence" in markdown
    assert "## Citation audit" in markdown
    assert "deterministic-model" in markdown
    assert '"status": "completed"' in exported.report_json.read_text(encoding="utf-8")
