"""Unit tests for readable report rendering."""

import asyncio
from datetime import UTC, datetime

from claim_polygraph_ng.application import InvestigationService
from claim_polygraph_ng.domain import (
    ArgumentLedger,
    ArtifactType,
    DistributionMedium,
    EvidentiaryUse,
    InvestigationProvenance,
    InvestigationReport,
    JudgmentPolicyTrace,
    JudgmentReadiness,
    SocialAccountIdentity,
    SocialAccountType,
    SocialAuthenticityEvidence,
    SocialAuthenticityEvidenceType,
    SocialAuthenticityStatus,
    SocialCaptureMethod,
    SocialContentOriginStatus,
    SocialPostType,
    SocialSourceContext,
    Source,
    VerificationPacketV2,
    evaluate_social_evidence_eligibility,
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
    assert "**Comparative construction attempts:**" in markdown
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


def test_markdown_exposes_social_identity_origin_use_and_limitations(tmp_path) -> None:
    repository = SQLiteInvestigationRepository(tmp_path / "social-report.sqlite3")
    service = InvestigationService(
        repository=repository,
        model_provider=DeterministicModelProvider(),
        search_provider=DeterministicSearchProvider(),
    )
    report = asyncio.run(service.investigate("The example programme reduced waste."))
    original_source = report.sources[0]
    context = SocialSourceContext(
        account=SocialAccountIdentity(
            platform="x",
            handle="agency",
            account_type=SocialAccountType.GOVERNMENT,
            authority_scope="Statements about the agency's own programme.",
            authenticity_status=SocialAuthenticityStatus.AUTHENTICATED,
            authenticity_evidence=(
                SocialAuthenticityEvidence(
                    evidence_type=(
                        SocialAuthenticityEvidenceType.OFFICIAL_WEBSITE_LINK
                    ),
                    reference_url="https://agency.example/social",
                    observed_at=datetime.now(UTC),
                    description="The official website links to this account.",
                ),
            ),
        ),
        post_type=SocialPostType.ORIGINAL,
        capture_method=SocialCaptureMethod.DIRECT_PUBLIC_PAGE,
        content_origin_status=SocialContentOriginStatus.ORIGINAL_ACCESSIBLE,
    )
    social_source = Source.model_validate(
        {
            **original_source.model_dump(),
            "distribution_medium": DistributionMedium.SOCIAL_PLATFORM,
            "social_context": context,
            "social_eligibility": evaluate_social_evidence_eligibility(context),
        }
    )
    evidence = (
        report.evidence[0].model_copy(
            update={"evidentiary_use": EvidentiaryUse.ATTRIBUTED_STATEMENT}
        ),
        *report.evidence[1:],
    )
    social_report = report.model_copy(
        update={"sources": (social_source, *report.sources[1:]), "evidence": evidence}
    )

    markdown = render_markdown(social_report, ())

    assert "## Social-evidence trace" in markdown
    assert "**Platform/account:** x / @agency" in markdown
    assert "**Authenticity:** authenticated" in markdown
    assert "**Assigned use:** attributed_statement" in markdown
    assert "**Corroboration required:** no" in markdown
    assert "Authenticity records attribution" in markdown
