"""Build the fresh, prefilled, zero-provider-call V4.8 calibration workbook."""

# ruff: noqa: E501 -- exact public-source passages remain visually intact.

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from claim_polygraph_ng.evaluation.v3_annotation import (
    V3AnnotationCase,
    V3ExactTextSpan,
    V3MachinePreparedProposal,
    V3ReplacementCalibrationWorkbook,
    V3ReviewEvidence,
)
from claim_polygraph_ng.evaluation.v3_manifest import (
    V3ConstructionGoldLabel,
    V3DatasetSplit,
    V3EvidenceSpan,
)

ROOT = Path(__file__).parents[1]
OUTPUT = ROOT / "benchmarks/verification_construction_v4_stage8_fresh_calibration_workbook_v1.json"
PUBLIC_OUTPUT = ROOT / "dashboard/public/v4-stage8-fresh-calibration.json"

# Short passages from accessible official HTML pages. No PDF, private content,
# paywalled content, or restricted document is downloaded or stored.
CASES = (
    (
        "NATO-MEMBERS",
        "official:nato",
        "NATO has 32 member countries.",
        "count",
        "equal",
        "deterministic_constructible",
        "verified",
        "NATO member countries",
        "https://www.nato.int/en/about-us/organization/nato-member-countries",
        "At present, NATO has 32 member countries.",
    ),
    (
        "NATO-SUCCESS",
        "official:nato",
        "NATO is the world's most successful military alliance.",
        "count",
        "qualitative_superlative",
        "not_applicable",
        None,
        "What is NATO?",
        "https://www.nato.int/content/what-is-nato/en.html",
        "There are currently 32 members.",
    ),
    (
        "FTC-CREATED",
        "official:ftc",
        "The Federal Trade Commission was created on September 26, 1914.",
        "temporal_instant",
        "created_on",
        "deterministic_constructible",
        "verified",
        "Our History",
        "https://www.ftc.gov/about-ftc/history",
        "The Federal Trade Commission was created on September 26, 1914, when President Woodrow Wilson signed the Federal Trade Commission Act into law.",
    ),
    (
        "FTC-TERM",
        "official:ftc",
        "Federal Trade Commissioners serve seven-year terms.",
        "duration",
        "equal",
        "deterministic_constructible",
        "verified",
        "Commissioners",
        "https://www.ftc.gov/about-ftc/commissioners-staff/commissioners",
        "The Commission is headed by five Commissioners, nominated by the President and confirmed by the Senate, each serving a seven-year term.",
    ),
    (
        "OECD-FORCE",
        "official:oecd",
        "The OECD Convention entered into force on 30 September 1961.",
        "temporal_instant",
        "entered_into_force_on",
        "deterministic_constructible",
        "verified",
        "Our history",
        "https://www.oecd.org/en/about/history.html",
        "The Convention transforming the OEEC into the OECD was signed at the Chateau de la Muette in Paris on 14 December 1960 and entered into force on 30 September 1961.",
    ),
    (
        "OECD-MEMBERS",
        "official:oecd",
        "The OECD has 38 Members.",
        "count",
        "equal",
        "deterministic_constructible",
        "verified",
        "Partnerships in OECD Bodies",
        "https://www.oecd.org/en/about/legal/partnerships-in-oecd-bodies.html",
        "Alongside the Organisation's 38 Members, other countries and economies may be invited to participate in any of its committees and other bodies.",
    ),
    (
        "ISO-MEMBERS",
        "official:iso",
        "ISO has 176 members.",
        "count",
        "equal",
        "deterministic_constructible",
        "verified",
        "ISO Members",
        "https://www.iso.org/about/members",
        "The International Organization for Standardization is a network of 176 national standards bodies.",
    ),
    (
        "ISO-BEST",
        "official:iso",
        "ISO is the world's best standards organization.",
        "count",
        "qualitative_superlative",
        "not_applicable",
        None,
        "About ISO",
        "https://www.iso.org/about",
        "ISO brings global experts together to agree on the best way of doing things.",
    ),
    (
        "BOE-FOUNDED",
        "official:bank-of-england",
        "The Bank of England was founded on 27 July 1694.",
        "temporal_instant",
        "founded_on",
        "deterministic_constructible",
        "verified",
        "History",
        "https://www.bankofengland.co.uk/about/history",
        "The Bank of England opened for business on 1 August 1694, after it was founded on 27 July 1694.",
    ),
    (
        "BOE-RELIABLE",
        "official:bank-of-england",
        "The Bank of England is the world's most reliable central bank.",
        "count",
        "qualitative_superlative",
        "not_applicable",
        None,
        "What does the Bank of England do?",
        "https://www.bankofengland.co.uk/about",
        "The Bank of England is the central bank of the United Kingdom.",
    ),
    (
        "STATCAN-MANDATE",
        "official:statistics-canada",
        "Statistics Canada has been mandated since 1918.",
        "temporal_interval_or_status",
        "active_since",
        "deterministic_constructible",
        "verified",
        "A glimpse into history",
        "https://www.statcan.gc.ca/en/about/history",
        "Canada's central statistical agency, which we know today as Statistics Canada, has been mandated since 1918 to provide statistical information to the people of Canada and to the world.",
    ),
    (
        "STATCAN-SURVEYS",
        "official:statistics-canada",
        "Statistics Canada conducts more than 450 active surveys.",
        "count",
        "greater_than",
        "deterministic_constructible",
        "verified",
        "About Statistics Canada",
        "https://www.statcan.gc.ca/en/about",
        "Statistics Canada has more than 450 active surveys on virtually all aspects of life in Canada.",
    ),
    (
        "RBA-OPERATIONS",
        "official:reserve-bank-australia",
        "The Reserve Bank of Australia commenced operations on 14 January 1960.",
        "temporal_instant",
        "started_on",
        "deterministic_constructible",
        "verified",
        "Fifty Years of the Reserve Bank",
        "https://www.rba.gov.au/about-rba/history/anniversary/",
        "The Reserve Bank of Australia commenced operations as Australia's central bank on 14 January 1960.",
    ),
    (
        "RBA-STAFF",
        "official:reserve-bank-australia",
        "The Reserve Bank opened for business with 1,800 staff.",
        "count",
        "equal",
        "deterministic_constructible",
        "verified",
        "Fifty Years of the Reserve Bank",
        "https://www.rba.gov.au/about-rba/history/anniversary/",
        "On 14 January 1960, when the Reserve Bank opened for business it had 1,800 staff from the Commonwealth Bank.",
    ),
    (
        "FAA-ACT",
        "official:faa",
        "The Federal Aviation Act was signed on August 23, 1958.",
        "temporal_instant",
        "signed_on",
        "deterministic_constructible",
        "verified",
        "A Brief History of the FAA",
        "https://www.faa.gov/about/history/brief_history",
        "On August 23, 1958, the President signed the Federal Aviation Act.",
    ),
    (
        "FAA-OPERATIONS",
        "official:faa",
        "The Federal Aviation Agency began operations on December 31, 1958.",
        "temporal_instant",
        "started_on",
        "deterministic_constructible",
        "verified",
        "A Brief History of the FAA",
        "https://www.faa.gov/about/history/brief_history",
        "Sixty days later, on December 31, the Federal Aviation Agency began operations.",
    ),
    (
        "SSA-CREATED",
        "official:ssa",
        "The Social Security Board was created on August 14, 1935 at 3:30 p.m.",
        "temporal_instant",
        "created_on",
        "deterministic_constructible",
        "verified",
        "Organizational History",
        "https://www.ssa.gov/history/orghist.html",
        "The SSB was created at the moment President Roosevelt inked his signature on the Social Security Act (August 14, 1935 at 3:30 p.m.).",
    ),
    (
        "SSA-INDEPENDENT",
        "official:ssa",
        "SSA returned to independent agency status on March 31, 1995.",
        "temporal_instant",
        "status_changed_on",
        "deterministic_constructible",
        "verified",
        "Organizational History",
        "https://www.ssa.gov/history/orghist.html",
        "On March 31, 1995 at a ceremony at SSA Headquarters in Baltimore, SSA once again became an independent agency.",
    ),
    (
        "USPTO-FIRST",
        "official:uspto",
        "The first U.S. patent was granted on July 31, 1790.",
        "temporal_instant",
        "granted_on",
        "deterministic_constructible",
        "verified",
        "America's innovative history",
        "https://www.uspto.gov/about-us/history/freedom250/americas-innovative-history",
        "On July 31, 1790, the first patent was granted to Samuel Hopkins for improvements in the making of pot ash and pearl ash.",
    ),
    (
        "USPTO-INNOVATIVE",
        "official:uspto",
        "The USPTO is the most innovative federal agency.",
        "count",
        "qualitative_superlative",
        "not_applicable",
        None,
        "About Us",
        "https://www.uspto.gov/about-us",
        "The USPTO is the federal agency that grants patents, registers trademarks, and advises the Administration on intellectual property policy.",
    ),
)


def main() -> None:
    cases = []
    for index, record in enumerate(CASES, start=301):
        candidate, family, claim, dimension, relation, label, state, title, url, passage = record
        evidence_id = f"V3-{index}:E1"
        constructible = label in {"deterministic_constructible", "fallback_eligible"}
        cases.append(
            V3AnnotationCase(
                case_id=f"V3-{index}",
                source_candidate_id=f"V4-{candidate}",
                split=V3DatasetSplit.CALIBRATION,
                origin_family_id=family,
                claim_text=claim,
                evidence=(
                    V3ReviewEvidence(
                        evidence_id=evidence_id,
                        title=title,
                        url=url,
                        source_class="official_html",
                        passage=passage,
                    ),
                ),
                proposal=V3MachinePreparedProposal(
                    dimension_bucket=dimension,
                    comparator_or_relation=relation,
                    claim_span=V3ExactTextSpan(
                        start_char=0, end_char=len(claim), quoted_text=claim
                    ),
                    evidence_spans=(
                        V3EvidenceSpan(
                            evidence_id=evidence_id,
                            start_char=0,
                            end_char=len(passage),
                            quoted_text=passage,
                        ),
                    )
                    if constructible
                    else (),
                    suggested_gold_label=V3ConstructionGoldLabel(label),
                    suggested_verification_state=state,
                    machine_notes=(
                        "Prefilled review proposal; human confirmation is required.",
                        "Accessible official HTML; no PDF or restricted document was stored.",
                    ),
                    model_calls=0,
                ),
            )
        )
    workbook = V3ReplacementCalibrationWorkbook(
        workbook_id="verification-construction-v4-stage8-fresh-calibration-workbook-v1",
        cases=tuple(cases),
    )
    serialized = json.dumps(workbook.model_dump(mode="json"), indent=2) + "\n"
    OUTPUT.write_text(serialized, encoding="utf-8")
    PUBLIC_OUTPUT.write_text(serialized, encoding="utf-8")
    print(
        f"{OUTPUT.relative_to(ROOT)} cases={len(cases)} "
        f"families={len({case.origin_family_id for case in cases})} "
        f"sha256={hashlib.sha256(serialized.encode()).hexdigest()} model_calls=0"
    )


if __name__ == "__main__":
    main()
