"""Build the fresh, AI-prefilled, zero-call V3.6e review workbook."""

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
OUTPUT = (
    ROOT
    / "benchmarks/"
    "verification_construction_v3_stage6e_fresh_calibration_workbook_v1.json"
)
PUBLIC_OUTPUT = ROOT / "dashboard/public/v3-stage6e-fresh-calibration.json"

# These are short passages from accessible official HTML pages. No PDF or
# restricted document is downloaded or stored.
CASES = (
    (
        "UNICEF-ESTABLISHED",
        "official:unicef",
        "UNICEF was established in 1946.",
        "temporal_instant",
        "established_in",
        "deterministic_constructible",
        "verified",
        "UNICEF history",
        "https://www.unicef.org/history",
        "The United Nations International Children’s Emergency Fund (UNICEF) was established in 1946, in the aftermath of World War II.",
        (),
    ),
    (
        "UNICEF-REACH",
        "official:unicef",
        "UNICEF works in more than 190 countries and territories.",
        "count",
        "greater_than",
        "deterministic_constructible",
        "verified",
        "Frequently Asked Questions",
        "https://www.unicef.org/about/frequently-asked-questions",
        "UNICEF works in more than 190 countries and territories and in the world’s toughest places to reach the children and young people in greatest need.",
        (),
    ),
    (
        "WTO-FOUNDED",
        "official:wto",
        "The World Trade Organization was founded on 1 January 1995.",
        "temporal_instant",
        "founded_on",
        "deterministic_constructible",
        "verified",
        "WTO accession has been a story of transformation",
        "https://www.wto.org/english/news_e/news20_e/ddgaw_14dec20_e.htm",
        "The Organization was founded on 1 January 1995 to serve the multilateral trade agreements negotiated by its 128 original Members.",
        (),
    ),
    (
        "WTO-MEMBERS",
        "official:wto",
        "Twenty-five years after its founding, the WTO accounted for 164 Members.",
        "count",
        "equal",
        "deterministic_constructible",
        "verified",
        "WTO accession has been a story of transformation",
        "https://www.wto.org/english/news_e/news20_e/ddgaw_14dec20_e.htm",
        "The Organization was founded on 1 January 1995 to serve the multilateral trade agreements negotiated by its 128 original Members. 25 years later, the Organization accounts for 164 Members, through a remarkable series of 36 accessions.",
        (),
    ),
    (
        "WMO-MEMBERS",
        "official:wmo",
        "The World Meteorological Organization has 193 Members.",
        "count",
        "equal",
        "deterministic_constructible",
        "verified",
        "WMO Members",
        "https://wmo.int/about/wmo-members",
        "WMO has 193 Members, including 187 Member States and 6 Territories, maintaining their own meteorological services.",
        (),
    ),
    (
        "WMO-TERRITORIES",
        "official:wmo",
        "The World Meteorological Organization includes 6 Territories.",
        "count",
        "equal",
        "deterministic_constructible",
        "verified",
        "WMO Members",
        "https://wmo.int/about/wmo-members",
        "WMO has 193 Members, including 187 Member States and 6 Territories, maintaining their own meteorological services.",
        (),
    ),
    (
        "ICAO-ESTABLISHED",
        "official:icao",
        "The International Civil Aviation Organization was established in 1944.",
        "temporal_instant",
        "established_in",
        "deterministic_constructible",
        "verified",
        "About ICAO",
        "https://www.icao.int/about-icao",
        "Since it was established in 1944, ICAO’s support and coordination has helped countries to diplomatically and technically realize a uniquely rapid and dependable network of global air mobility.",
        (),
    ),
    (
        "ICAO-COUNTRIES",
        "official:icao",
        "ICAO helps 193 countries cooperate and share their skies.",
        "count",
        "equal",
        "deterministic_constructible",
        "verified",
        "About ICAO",
        "https://www.icao.int/about-icao",
        "The International Civil Aviation Organization (ICAO) is a United Nations agency which helps 193 countries to cooperate together and share their skies to their mutual benefit.",
        (),
    ),
    (
        "INTERPOL-MEMBERS",
        "official:interpol",
        "INTERPOL has 196 member countries.",
        "count",
        "equal",
        "deterministic_constructible",
        "verified",
        "INTERPOL member countries",
        "https://www.interpol.int/en/Who-we-are/Member-countries",
        "INTERPOL has 196 member countries, making us the world’s largest police organization.",
        (),
    ),
    (
        "INTERPOL-EFFECTIVE",
        "official:interpol",
        "INTERPOL is the world’s most effective police organization.",
        "count",
        "qualitative_superlative",
        "not_applicable",
        None,
        "INTERPOL member countries",
        "https://www.interpol.int/en/Who-we-are/Member-countries",
        "INTERPOL has 196 member countries, making us the world’s largest police organization.",
        (
            "“Most effective” is a qualitative judgment, not an explicit numerical or temporal assertion.",
        ),
    ),
    (
        "IMO-ESTABLISHED",
        "official:imo",
        "The International Maritime Organization was established on 6 March 1948.",
        "temporal_instant",
        "established_on",
        "deterministic_constructible",
        "verified",
        "Frequently Asked Questions",
        "https://www.imo.org/en/about/pages/faqs.aspx",
        "It was established by means of a Convention adopted under the auspices of the United Nations in Geneva on 6 March 1948 and met for the first time in January 1959.",
        (),
    ),
    (
        "IMO-MEMBERS",
        "official:imo",
        "The International Maritime Organization has 176 Member States.",
        "count",
        "equal",
        "deterministic_constructible",
        "verified",
        "Frequently Asked Questions",
        "https://www.imo.org/en/about/pages/faqs.aspx",
        "IMO currently has 176 Member States.",
        (),
    ),
    (
        "ITU-ESTABLISHED",
        "official:itu",
        "The International Telecommunication Union was established in 1865.",
        "temporal_instant",
        "established_in",
        "deterministic_constructible",
        "verified",
        "About ITU",
        "https://www.itu.int/en/about/Pages/default.aspx",
        "Established in 1865 to manage the first international telegraph networks, ITU has worked ceaselessly since then to connect the world.",
        (),
    ),
    (
        "ITU-MEMBERS",
        "official:itu",
        "The International Telecommunication Union has 194 Member States.",
        "count",
        "equal",
        "deterministic_constructible",
        "verified",
        "About ITU",
        "https://www.itu.int/en/about/Pages/default.aspx",
        "The Organization is made up of a membership of 194 Member States and more than 1000 companies, universities and international and regional organizations.",
        (),
    ),
    (
        "UPU-ESTABLISHED",
        "official:upu",
        "The Universal Postal Union was established in 1874.",
        "temporal_instant",
        "established_in",
        "deterministic_constructible",
        "verified",
        "Factsheet: About the UPU",
        "https://www.upu.int/en/news/2018/10/factsheet-about-the-upu",
        "Established in 1874, with its headquarters in Berne, Switzerland, the Universal Postal Union is the world’s second oldest international organization.",
        (),
    ),
    (
        "UPU-MEMBERS",
        "official:upu",
        "The Universal Postal Union has 192 member countries.",
        "count",
        "equal",
        "deterministic_constructible",
        "verified",
        "Factsheet: About the UPU",
        "https://www.upu.int/en/news/2018/10/factsheet-about-the-upu",
        "With 192 member countries, the UPU is the primary forum for postal cooperation between governments, Posts, regulators and many other postal sector stakeholders.",
        (),
    ),
    (
        "FAO-MEMBERS",
        "official:fao",
        "The Food and Agriculture Organization has 194 members.",
        "count",
        "equal",
        "deterministic_constructible",
        "verified",
        "About FAO",
        "https://www.fao.org/about/about-fao/en/",
        "With 194 members - 193 countries and the European Union, FAO works in over 130 countries worldwide.",
        (),
    ),
    (
        "FAO-SUCCESSFUL",
        "official:fao",
        "FAO is the world’s most successful food-security organization.",
        "count",
        "qualitative_superlative",
        "not_applicable",
        None,
        "About FAO",
        "https://www.fao.org/about/about-fao/en/",
        "The Food and Agriculture Organization (FAO) is a specialized agency of the United Nations that leads international efforts to defeat hunger.",
        (
            "“Most successful” is an undefined qualitative judgment and has no typed numerical or temporal operands.",
        ),
    ),
    (
        "IAEA-BRAZIL",
        "official:iaea",
        "Brazil became an IAEA member on 29 July 1957.",
        "temporal_instant",
        "membership_started_on",
        "deterministic_constructible",
        "verified",
        "Brazil, Federative Republic of",
        "https://ola.iaea.org/Applications/FactSheets/Country/Detail?code=BR",
        "IAEA Membership 29 July 1957.",
        (),
    ),
    (
        "IAEA-EGYPT",
        "official:iaea",
        "Egypt became an IAEA member on 4 September 1957.",
        "temporal_instant",
        "membership_started_on",
        "deterministic_constructible",
        "verified",
        "Egypt, Arab Republic of",
        "https://ola.iaea.org/Applications/FactSheets/Country/Detail?code=EG",
        "IAEA Membership 4 September 1957.",
        (),
    ),
)


def main() -> None:
    cases: list[V3AnnotationCase] = []
    for index, record in enumerate(CASES, start=241):
        (
            candidate_id,
            family,
            claim,
            dimension,
            relation,
            label,
            expected_state,
            title,
            url,
            passage,
            notes,
        ) = record
        evidence_id = f"V3-{index}:E1"
        constructible = label in {
            "deterministic_constructible",
            "fallback_eligible",
        }
        cases.append(
            V3AnnotationCase(
                case_id=f"V3-{index}",
                source_candidate_id=candidate_id,
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
                        start_char=0,
                        end_char=len(claim),
                        quoted_text=claim,
                    ),
                    evidence_spans=(
                        V3EvidenceSpan(
                            evidence_id=evidence_id,
                            start_char=0,
                            end_char=len(passage),
                            quoted_text=passage,
                        ),
                    ),
                    suggested_gold_label=V3ConstructionGoldLabel(label),
                    suggested_verification_state=expected_state,
                    machine_notes=(
                        "AI-prepared review suggestion; requires human acceptance.",
                        "Accessible public HTML; no PDF or restricted document.",
                        *notes,
                    ),
                    model_calls=0,
                ),
            )
        )
        if not constructible and expected_state is not None:
            raise ValueError("non-constructible suggestion cannot define a state")
    workbook = V3ReplacementCalibrationWorkbook(
        workbook_id=(
            "verification-construction-v3-stage6e-fresh-calibration-workbook-v1"
        ),
        cases=tuple(cases),
    )
    serialized = json.dumps(workbook.model_dump(mode="json"), indent=2) + "\n"
    OUTPUT.write_text(serialized, encoding="utf-8")
    PUBLIC_OUTPUT.write_text(serialized, encoding="utf-8")
    print(
        f"{OUTPUT.relative_to(ROOT)} cases={len(cases)} "
        f"families={len({item.origin_family_id for item in cases})} "
        f"sha256={hashlib.sha256(serialized.encode()).hexdigest()} model_calls=0"
    )


if __name__ == "__main__":
    main()
