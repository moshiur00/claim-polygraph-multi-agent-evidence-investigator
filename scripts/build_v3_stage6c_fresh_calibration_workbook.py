"""Build the fresh, zero-call V3.6c annotation workbook."""

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
    V3DatasetSplit,
    V3EvidenceSpan,
)

ROOT = Path(__file__).parents[1]
OUTPUT = (
    ROOT
    / "benchmarks/"
    "verification_construction_v3_stage6c_fresh_calibration_workbook_v1.json"
)
PUBLIC_OUTPUT = ROOT / "dashboard/public/v3-stage6c-fresh-calibration.json"

CASES = (
    (
        "NOAA-DEPTH",
        "official:noaa",
        "The average depth of the ocean is approximately 3,682 meters.",
        "distance",
        "approximately_equal",
        "How deep is the ocean?",
        "https://oceanexplorer.noaa.gov/ocean-fact/ocean-depth/",
        "The average depth of the ocean is 3,682 meters, or 12,080 feet.",
    ),
    (
        "NOAA-COVERAGE",
        "official:noaa",
        "The ocean covers approximately 70 percent of Earth's surface.",
        "percentage",
        "approximately_equal",
        "How much of the ocean has been explored?",
        "https://oceanexplorer.noaa.gov/ocean-fact/explored/",
        "The ocean covers approximately 70% of Earth's surface.",
    ),
    (
        "BLS-BASE-VALUE",
        "official:bls",
        "The current CPI base-period index is 100.",
        "count",
        "equal",
        "CPI - All Urban Consumers - Field Definitions",
        "https://www.bls.gov/help/def/cu.htm",
        "The current base year is 1982-84=100 or more recent.",
    ),
    (
        "BLS-BASE-RANGE",
        "official:bls",
        "The standard current CPI base period runs from 1982 through 1984.",
        "date_range",
        "range",
        "CPI - All Urban Consumers - Field Definitions",
        "https://www.bls.gov/help/def/cu.htm",
        "The current base year is 1982-84=100 or more recent.",
    ),
    (
        "SEC-CREATED",
        "official:sec",
        "The Securities Exchange Act of 1934 created the SEC.",
        "temporal_status",
        "created_in",
        "Opening Remarks Before the SEC's 90th Anniversary Event",
        "https://www.sec.gov/newsroom/speeches-statements/gensler-remarks-90thsec-060624",
        "President Roosevelt worked with Congress to enact the Securities "
        "Exchange Act of 1934—creating the SEC and making June 6 our official birthday.",
    ),
    (
        "SEC-ANNIVERSARY",
        "official:sec",
        "The SEC celebrated its 90th anniversary on 6 June 2024.",
        "date",
        "on",
        "Opening Remarks Before the SEC's 90th Anniversary Event",
        "https://www.sec.gov/newsroom/speeches-statements/gensler-remarks-90thsec-060624",
        "Opening Remarks Before the SEC's 90th Anniversary Event. June 6, 2024. "
        "We celebrate the 90th anniversary of a milestone in American history.",
    ),
    (
        "FED-CREATED",
        "official:federal-reserve",
        "The Federal Reserve System was created on 23 December 1913.",
        "date",
        "created_on",
        "About the Federal Reserve System",
        "https://www.federalreserve.gov/publications/2017-ar-overview.htm",
        "The Federal Reserve System, which serves as the nation's central bank, "
        "was created by an act of Congress on December 23, 1913.",
    ),
    (
        "FED-BANKS",
        "official:federal-reserve",
        "The Federal Reserve System has 12 regional Reserve Banks.",
        "count",
        "equal",
        "About the Federal Reserve System",
        "https://www.federalreserve.gov/publications/2017-ar-overview.htm",
        "The System consists of a seven-member Board of Governors with headquarters "
        "in Washington, D.C., and the 12 Reserve Banks located in major cities "
        "throughout the United States.",
    ),
    (
        "NHGRI-BASES",
        "official:nhgri",
        "The human genome contains about 3 billion bases.",
        "count",
        "approximately_equal",
        "Deoxyribonucleic Acid (DNA) Fact Sheet",
        "https://www.genome.gov/about-genomics/fact-sheets/Deoxyribonucleic-Acid-Fact-Sheet",
        "The complete DNA instruction book, or genome, for a human contains "
        "about 3 billion bases and about 20,000 genes on 23 pairs of chromosomes.",
    ),
    (
        "NHGRI-CHROMOSOMES",
        "official:nhgri",
        "A typical human cell has 46 chromosomes.",
        "count",
        "equal",
        "Chromosome Abnormalities Fact Sheet",
        "https://www.genome.gov/about-genomics/fact-sheets/Chromosome-Abnormalities-Fact-Sheet",
        "The typical number of chromosomes in a human cell is 46: 23 pairs, "
        "holding an estimated total of 20,000 to 25,000 genes.",
    ),
    (
        "LOC-FOUNDED",
        "official:library-of-congress",
        "The Library of Congress was established on 24 April 1800.",
        "date",
        "established_on",
        "Bicentennial of the Library of Congress",
        "https://www.loc.gov/loc/lcib/0005/proclaim.html",
        "The Library of Congress was established in the District of Columbia "
        "on April 24, 1800.",
    ),
    (
        "LOC-DAILY-ADDITIONS",
        "official:library-of-congress",
        "The Library of Congress adds more than 10,000 items each working day.",
        "count",
        "greater_than",
        "Fascinating Facts",
        "https://www.loc.gov/about/fascinating-facts",
        "Each working day the Library receives some 15,000 items and adds more "
        "than 10,000 items to its collections.",
    ),
    (
        "UN-START",
        "official:un",
        "The United Nations officially began on 24 October 1945.",
        "date",
        "started_on",
        "History of the United Nations",
        "https://www.un.org/en/about-us/history-of-the-un",
        "The United Nations officially began, on 24 October 1945, when it came "
        "into existence after its Charter had been ratified.",
    ),
    (
        "UN-MEMBERS",
        "official:un",
        "The United Nations currently has 193 Member States.",
        "count",
        "equal",
        "About Us",
        "https://www.un.org/en/about-us/",
        "The United Nations is an international organization founded in 1945. "
        "Currently made up of 193 Member States.",
    ),
    (
        "ILO-CREATED",
        "official:ilo",
        "The International Labour Organization was created in 1919.",
        "temporal_status",
        "created_in",
        "About the ILO",
        "https://www.ilo.org/about-ilo",
        "The ILO was created in 1919, as part of the Treaty of Versailles that "
        "ended World War I.",
    ),
    (
        "ILO-MEMBERS",
        "official:ilo",
        "The International Labour Organization has 187 Member States.",
        "count",
        "equal",
        "ILO Member States",
        "https://www.ilo.org/about-ilo/ilo-member-states",
        "The ILO has 187 Member States.",
    ),
    (
        "CERN-RING",
        "official:cern",
        "The Large Hadron Collider has a 27-kilometre ring.",
        "distance",
        "equal",
        "The Large Hadron Collider",
        "https://home.cern/science/accelerators/large-hadron-collider/",
        "The LHC consists of a 27-kilometre ring of superconducting magnets.",
    ),
    (
        "CERN-START",
        "official:cern",
        "The Large Hadron Collider first started up on 10 September 2008.",
        "date",
        "started_on",
        "The Large Hadron Collider",
        "https://home.cern/science/accelerators/large-hadron-collider/",
        "It first started up on 10 September 2008, and remains the latest "
        "addition to CERN's accelerator complex.",
    ),
    (
        "SMITHSONIAN-FOUNDED",
        "official:smithsonian",
        "The Smithsonian Institution was established on 10 August 1846.",
        "date",
        "established_on",
        "Our History",
        "https://www.si.edu/about/history",
        "On August 10, 1846, the U.S. Senate passed the act organizing the "
        "Smithsonian Institution, which was signed into law by President James K. Polk.",
    ),
    (
        "SMITHSONIAN-MUSEUMS",
        "official:smithsonian",
        "The Smithsonian complex includes 21 museums.",
        "count",
        "equal",
        "About the Smithsonian",
        "https://www.si.edu/about/",
        "The Smithsonian Institution is the world's largest museum, education, "
        "and research complex, with 21 museums, 14 education and research "
        "centers, and the National Zoo.",
    ),
)


def main() -> None:
    cases = []
    for index, record in enumerate(CASES, start=201):
        (
            candidate_id,
            family,
            claim,
            dimension,
            relation,
            title,
            url,
            passage,
        ) = record
        evidence_id = f"V3-{index}:E1"
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
                    machine_notes=(
                        "Navigation-only proposal; requires human annotation.",
                        "Accessible public HTML; no document download.",
                    ),
                    model_calls=0,
                ),
            )
        )
    workbook = V3ReplacementCalibrationWorkbook(
        workbook_id=(
            "verification-construction-v3-stage6c-fresh-calibration-workbook-v1"
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
