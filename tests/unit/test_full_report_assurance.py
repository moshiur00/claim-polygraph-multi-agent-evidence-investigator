"""Stage 8.8 full-report assurance and publication-gate tests."""

import asyncio
from uuid import uuid4

import pytest

from claim_polygraph_ng.analysis import assure_full_report
from claim_polygraph_ng.application import InvestigationService
from claim_polygraph_ng.domain import (
    Evidence,
    EvidenceStance,
    PublicationGateStatus,
    Verdict,
    VerdictLabel,
)
from claim_polygraph_ng.persistence import SQLiteInvestigationRepository
from claim_polygraph_ng.providers import (
    DeterministicModelProvider,
    DeterministicSearchProvider,
)
from claim_polygraph_ng.reporting import (
    PublicationBlockedError,
    export_report,
    render_publishable_markdown,
)


def test_bounded_revision_is_reaudited_and_reaches_publication_ready() -> None:
    claim_id = uuid4()
    evidence = _evidence(
        claim_id,
        EvidenceStance.SUPPORTS,
        "The official record reports that the programme reduced emissions.",
    )
    verdict = _verdict(
        claim_id,
        VerdictLabel.SUPPORTED,
        evidence.evidence_id,
        "The submitted claim is supported by the reviewed record.",
    )

    assurance = assure_full_report(
        claim_id=claim_id,
        verdict=verdict,
        evidence=(evidence,),
        approved_evidence_ids=(evidence.evidence_id,),
    )

    assert assurance.initial_audit.full_support_rate < 1
    assert assurance.final_audit.full_support_rate == 1
    assert assurance.publication_status is PublicationGateStatus.READY
    assert assurance.critical_failure_count == 0
    assert assurance.material_sentence_count == assurance.audited_material_sentence_count
    assert assurance.revisions
    assert all(not item.verdict_label_changed for item in assurance.revisions)
    final_by_id = {item.assertion_id: item for item in assurance.final_audit.findings}
    assert all(
        final_by_id[item.assertion_id].sentence == item.revised_sentence
        for item in assurance.revisions
    )


def test_unsupported_critical_sentence_blocks_after_bounded_attempts() -> None:
    claim_id = uuid4()
    evidence = _evidence(
        claim_id,
        EvidenceStance.SUPPORTS,
        "The supplied record discusses a related programme.",
    )
    verdict = _verdict(
        claim_id,
        VerdictLabel.UNVERIFIABLE,
        None,
        "The available material cannot verify the submitted claim.",
    )

    assurance = assure_full_report(
        claim_id=claim_id,
        verdict=verdict,
        evidence=(evidence,),
        approved_evidence_ids=(evidence.evidence_id,),
    )

    assert assurance.publication_status is PublicationGateStatus.BLOCKED
    assert assurance.critical_failure_count == 1
    assert assurance.blocking_reasons
    assert len(assurance.revisions) <= assurance.maximum_revision_attempts * len(
        assurance.original_assertions
    )


def test_export_and_markdown_endpoint_boundary_fail_before_writing(tmp_path) -> None:
    repository = SQLiteInvestigationRepository(tmp_path / "investigations.db")
    report = asyncio.run(
        InvestigationService(
            repository=repository,
            model_provider=DeterministicModelProvider(),
            search_provider=DeterministicSearchProvider(),
        ).investigate("The programme reduced emissions.")
    )
    assert report.full_report_assurance is not None
    assert report.full_report_assurance.publication_status is PublicationGateStatus.READY
    markdown = render_publishable_markdown(report, ())
    assert "Full-report citation assurance" in markdown
    assert "Publication status:** ready" in markdown

    blocked_verdict = _verdict(
        report.claim.claim_id,
        VerdictLabel.UNVERIFIABLE,
        None,
        "The available material cannot verify the submitted claim.",
    )
    blocked = assure_full_report(
        claim_id=report.claim.claim_id,
        verdict=blocked_verdict,
        evidence=report.evidence,
        approved_evidence_ids=tuple(item.evidence_id for item in report.evidence),
    )
    blocked_report = report.model_copy(
        update={"verdict": blocked_verdict, "full_report_assurance": blocked}
    )
    output = tmp_path / "blocked-output"

    with pytest.raises(PublicationBlockedError):
        export_report(blocked_report, (), output)
    assert not output.exists()


def _evidence(claim_id, stance, passage):
    return Evidence(
        claim_id=claim_id,
        source_id=uuid4(),
        passage=passage,
        stance=stance,
        relevance_score=1,
    )


def _verdict(claim_id, label, evidence_id, explanation):
    return Verdict(
        claim_id=claim_id,
        label=label,
        concise_explanation=explanation,
        detailed_reasoning=(
            "The detailed assessment applies the declared evidence policy to the approved packet."
        ),
        decisive_evidence_ids=(evidence_id,) if evidence_id else (),
    )
