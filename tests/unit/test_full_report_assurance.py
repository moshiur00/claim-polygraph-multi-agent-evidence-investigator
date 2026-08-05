"""Stage 8.8 full-report assurance and publication-gate tests."""

import asyncio
from uuid import uuid4

import pytest

from claim_polygraph_ng.analysis import assure_full_report, reassess_full_report_assurance
from claim_polygraph_ng.application import InvestigationService
from claim_polygraph_ng.domain import (
    Evidence,
    EvidenceStance,
    EvidentiaryUse,
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


def test_unbounded_raw_source_passage_cannot_become_a_report_finding() -> None:
    claim_id = uuid4()
    evidence = _evidence(
        claim_id,
        EvidenceStance.CONTRADICTS,
        "<!DOCTYPE html><html><body>" + ("relevant source text " * 900) + "</body></html>",
    )
    verdict = _verdict(
        claim_id,
        VerdictLabel.CONTRADICTED,
        evidence.evidence_id,
        "The submitted claim is contradicted by the reviewed record.",
    )

    assurance = assure_full_report(
        claim_id=claim_id,
        verdict=verdict,
        evidence=(evidence,),
        approved_evidence_ids=(evidence.evidence_id,),
    )

    evidence_findings = tuple(
        item
        for item in assurance.original_assertions
        if item.section.value == "evidence_finding"
    )
    assert evidence_findings == ()
    assert assurance.publication_status is PublicationGateStatus.BLOCKED


def test_contaminated_decisive_passage_cannot_satisfy_report_support() -> None:
    claim_id = uuid4()
    evidence = _evidence(
        claim_id,
        EvidenceStance.SUPPORTS,
        (
            "Skip to main content User account menu Log in Subscribe Product directory. "
            "The programme reduced emissions. Privacy policy All rights reserved."
        ),
    )
    verdict = _verdict(
        claim_id,
        VerdictLabel.SUPPORTED,
        evidence.evidence_id,
        "The programme reduced emissions.",
    )

    assurance = assure_full_report(
        claim_id=claim_id,
        verdict=verdict,
        evidence=(evidence,),
        approved_evidence_ids=(evidence.evidence_id,),
        claim_text="The programme reduced emissions.",
    )

    assert assurance.final_audit.approved_evidence_ids == ()
    assert assurance.final_audit.supported_count == 0
    assert assurance.publication_status is PublicationGateStatus.BLOCKED
    assert not any(
        item.section.value == "evidence_finding"
        for item in assurance.final_assertions
    )


def test_contrastive_sentence_is_audited_as_separate_stance_specific_clauses() -> None:
    claim_id = uuid4()
    supporting = _evidence(
        claim_id,
        EvidenceStance.SUPPORTS,
        "Water expands when it freezes because its crystal structure occupies more volume.",
    )
    qualifying = _evidence(
        claim_id,
        EvidenceStance.QUALIFIES,
        "Most liquids shrink when freezing, but exceptions exist under specific conditions.",
    )
    verdict = Verdict(
        claim_id=claim_id,
        label=VerdictLabel.MIXED,
        concise_explanation=(
            "Water expands when it freezes, although exceptions mean the broader rule "
            "does not apply universally."
        ),
        detailed_reasoning="Water expands when it freezes under the reviewed conditions.",
        decisive_evidence_ids=(supporting.evidence_id, qualifying.evidence_id),
    )

    assurance = assure_full_report(
        claim_id=claim_id,
        verdict=verdict,
        evidence=(supporting, qualifying),
        approved_evidence_ids=(supporting.evidence_id, qualifying.evidence_id),
        maximum_revision_attempts=0,
    )

    summary = tuple(
        item
        for item in assurance.original_assertions
        if item.section.value == "verdict_summary"
    )
    assert len(summary) == 2
    assert summary[0].asserted_stance is EvidenceStance.SUPPORTS
    assert summary[1].asserted_stance is EvidenceStance.QUALIFIES
    assert all(item.section.value != "evidence_finding" for item in assurance.original_assertions)


def test_effective_reassessment_splits_legacy_compound_assertion() -> None:
    claim_id = uuid4()
    supporting = _evidence(
        claim_id,
        EvidenceStance.SUPPORTS,
        "Water expands when it freezes because ice occupies more volume.",
    )
    qualifying = _evidence(
        claim_id,
        EvidenceStance.QUALIFIES,
        "Most liquids contract on freezing, although exceptions exist.",
    )
    verdict = Verdict(
        claim_id=claim_id,
        label=VerdictLabel.MIXED,
        concise_explanation=(
            "Water expands when it freezes, although the rule for other liquids has exceptions."
        ),
        detailed_reasoning="Water expands when it freezes under the reviewed conditions.",
        decisive_evidence_ids=(supporting.evidence_id, qualifying.evidence_id),
    )
    historical = assure_full_report(
        claim_id=claim_id,
        verdict=verdict,
        evidence=(supporting, qualifying),
        approved_evidence_ids=(supporting.evidence_id, qualifying.evidence_id),
        maximum_revision_attempts=0,
    )
    legacy_summary = (
        *(
            item
            for item in historical.final_assertions
            if item.section.value != "verdict_summary"
        ),
        historical.final_assertions[0].model_copy(
            update={
                "sentence": verdict.concise_explanation,
                "asserted_stance": EvidenceStance.QUALIFIES,
            }
        ),
    )
    legacy = historical.model_copy(update={"final_assertions": legacy_summary})

    effective = reassess_full_report_assurance(
        historical=legacy,
        evidence=(supporting, qualifying),
        approved_evidence_ids=(),
    )

    summary = tuple(
        item
        for item in effective.final_assertions
        if item.section.value == "verdict_summary"
    )
    assert len(summary) == 2
    assert summary[0].asserted_stance is EvidenceStance.SUPPORTS
    assert summary[1].asserted_stance is EvidenceStance.QUALIFIES
    assert effective.final_audit.out_of_packet_count == len(effective.final_assertions)


def test_clause_splitter_preserves_dependent_because_while_construction() -> None:
    claim_id = uuid4()
    qualifying = _evidence(
        claim_id,
        EvidenceStance.QUALIFIES,
        "Most liquids contract on freezing, but exceptions exist.",
    )
    explanation = (
        "The broad wording is misleading because, while most liquids contract, "
        "exceptions exist under specific conditions."
    )
    verdict = _verdict(
        claim_id,
        VerdictLabel.MISLEADING,
        qualifying.evidence_id,
        explanation,
    )

    assurance = assure_full_report(
        claim_id=claim_id,
        verdict=verdict,
        evidence=(qualifying,),
        approved_evidence_ids=(qualifying.evidence_id,),
        maximum_revision_attempts=0,
    )

    summary = tuple(
        item
        for item in assurance.final_assertions
        if item.section.value == "verdict_summary"
    )
    assert len(summary) == 1
    assert summary[0].sentence == explanation


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
    assert "Effective full-report citation assurance" in markdown
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
        evidentiary_use=EvidentiaryUse.DECISIVE,
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
