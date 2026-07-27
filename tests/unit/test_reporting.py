"""Unit tests for readable report rendering."""

import asyncio

from claim_polygraph_ng.application import InvestigationService
from claim_polygraph_ng.domain import (
    ArgumentLedger,
    ArtifactType,
    InvestigationProvenance,
    InvestigationReport,
    JudgmentPolicyTrace,
    JudgmentReadiness,
    VerificationPacketV2,
)
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
    loaded_again = load_report(repository, investigation_id)
    exported = export_report(loaded, events, tmp_path / "artifacts")
    markdown = render_markdown(loaded, events)

    assert loaded == report
    assert loaded_again == loaded
    assert loaded.provenance is not None
    assert loaded.verification_packet is not None
    assert loaded.argument_ledger is not None
    assert loaded.judgment_policy is not None
    assert loaded.readiness is not None
    assert loaded.provenance.claim_id == loaded.claim.claim_id
    assert len(
        repository.list_artifacts(
            investigation_id,
            ArtifactType.PROVENANCE,
            InvestigationProvenance,
        )
    ) == 1
    for artifact_type, model in (
        (ArtifactType.VERIFICATION_PACKET, VerificationPacketV2),
        (ArtifactType.ARGUMENT_LEDGER, ArgumentLedger),
        (ArtifactType.JUDGMENT_POLICY, JudgmentPolicyTrace),
        (ArtifactType.READINESS, JudgmentReadiness),
    ):
        assert len(repository.list_artifacts(investigation_id, artifact_type, model)) == 1
    assert exported.report_json.is_file()
    assert exported.report_markdown.is_file()
    assert exported.trace_json.is_file()
    assert "# Claim Polygraph NG Investigation" in markdown
    assert "## Supporting evidence" in markdown
    assert "## Contradictory evidence" in markdown
    assert "## Citation audit" in markdown
    assert "## Provenance inspection" in markdown
    assert "## Assertion-level verification" in markdown
    assert "## Argument ledger" in markdown
    assert "## Judgment policy" in markdown
    assert "## Judgment readiness" in markdown
    assert "deterministic-model" in markdown
    assert '"status": "completed"' in exported.report_json.read_text(encoding="utf-8")
    assert '"provenance_version": "investigation-provenance-v1"' in (
        exported.report_json.read_text(encoding="utf-8")
    )


def test_old_report_payload_without_provenance_remains_valid(tmp_path) -> None:
    repository = SQLiteInvestigationRepository(tmp_path / "old-report.sqlite3")
    service = InvestigationService(
        repository=repository,
        model_provider=DeterministicModelProvider(),
        search_provider=DeterministicSearchProvider(),
    )
    report = asyncio.run(service.investigate("The example programme reduced waste by ten percent."))
    old_payload = report.model_dump()
    for field in (
        "provenance",
        "verification_packet",
        "argument_ledger",
        "judgment_policy",
        "readiness",
    ):
        old_payload.pop(field)

    restored = InvestigationReport.model_validate(old_payload)

    assert restored.provenance is None
    assert restored.verification_packet is None
    assert restored.argument_ledger is None
    assert restored.judgment_policy is None
    assert restored.readiness is None
