"""Build the AI-prefilled, zero-call V4.9e fresh calibration workbook."""

# ruff: noqa: E501 -- exact short official HTML passages remain intact.

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
OUTPUT = ROOT / "benchmarks/verification_construction_v4_stage9e_fresh_calibration_workbook_v1.json"
PUBLIC = ROOT / "dashboard/public/v4-stage9e-fresh-calibration.json"

# family, claim, dimension, relation, label, state, title, URL, exact HTML passage
CASES = (
    ("official:snb", "The Swiss National Bank commenced operations in 1907.", "temporal_instant", "started_in", "deterministic_constructible", "verified", "The history of the SNB", "https://www.snb.ch/en/the-snb/organisation/history", "Since the Swiss National Bank commenced operations in 1907, it has had a strong impact on economic policy in Switzerland."),
    ("official:snb", "The SNB head office in Berne was inaugurated on January 20, 1912.", "temporal_instant", "inaugurated_on", "deterministic_constructible", "verified", "The history of the SNB", "https://www.snb.ch/en/the-snb/organisation/history", "Inaugurated on 20 January 1912, the Swiss National Bank's head office on Bundesplatz 1 in Berne recently marked its 100th anniversary."),
    ("official:norges-bank", "Norges Bank was established on June 14, 1816.", "temporal_instant", "established_on", "deterministic_constructible", "verified", "History of Norges Bank", "https://www.norges-bank.no/en/topics/about/history/history-of-norges-bank/", "Norges Bank was established by Act of the Storting (the Norwegian parliament) of 14 June 1816."),
    ("official:norges-bank", "Norges Bank started operations in January 1817.", "temporal_instant", "started_in", "deterministic_constructible", "verified", "History of Norges Bank", "https://www.norges-bank.no/en/topics/about/history/history-of-norges-bank/", "The operation started up in small, leased premises in the Stiftsgaarden, Trondheim's old gubernatorial residence, in January 1817."),
    ("official:dnb", "De Nederlandsche Bank was founded in 1814.", "temporal_instant", "founded_in", "deterministic_constructible", "verified", "History", "https://www.dnb.nl/en/about-us/history/", "DNB was founded in 1814."),
    ("official:dnb", "DNB has faced more important challenges than every other central bank.", "temporal_instant", "qualitative_superlative", "not_applicable", None, "History", "https://www.dnb.nl/en/about-us/history/", "Discover the milestones and challenges of our history, spanning more than 200 years."),
    ("official:banque-france", "The Banque de France was founded on January 18, 1800.", "temporal_instant", "founded_on", "deterministic_constructible", "verified", "The history of the Banque de France", "https://www.banque-france.fr/en/banque-de-france/institution-rooted-history/founding-history-banque-de-france", "The Banque de France is founded on 18 January 1800 by a group of bankers at the instigation of the First Consul, Napoleon Bonaparte."),
    ("official:banque-france", "The Banque de France was nationalised on December 2, 1945.", "temporal_instant", "nationalised_on", "deterministic_constructible", "verified", "The history of the Banque de France", "https://www.banque-france.fr/en/banque-de-france/institution-rooted-history/founding-history-banque-de-france", "After the Liberation, the Banque de France is nationalised by the act of 2 December 1945."),
    ("official:banco-espana", "The Banco Nacional de San Carlos was founded on June 2, 1782.", "temporal_instant", "founded_on", "deterministic_constructible", "verified", "History", "https://www.bde.es/wbe/en/sobre-banco/mision/historia-del-banco/", "On 2 June, by means of a Royal Warrant signed by King Carlos III, the Banco Nacional de San Carlos was founded."),
    ("official:banco-espana", "Banco Español de San Fernando was renamed Banco de España on January 28, 1856.", "temporal_instant", "renamed_on", "deterministic_constructible", "verified", "History", "https://www.bde.es/wbe/en/sobre-banco/mision/historia-del-banco/", "The Law of 28 January 1856 renamed the new Banco Español de San Fernando as the Banco de España."),
    ("official:nbb", "The law establishing the National Bank of Belgium was signed on May 5, 1850.", "temporal_instant", "signed_on", "deterministic_constructible", "verified", "175 years of the National Bank of Belgium", "https://www.nbb.be/en/news-events/news/175-years-national-bank-belgium", "It was on 5 May 1850 that Leopold I signed the law establishing the National Bank."),
    ("official:nbb", "The National Bank of Belgium issued its first banknotes in 1851.", "temporal_instant", "issued_in", "deterministic_constructible", "verified", "175 years of the National Bank of Belgium", "https://www.nbb.be/en/news-events/news/175-years-national-bank-belgium", "In 1851, the National Bank issued its first banknotes."),
    ("official:oenb", "Austria's central bank started operating on June 1, 1816.", "temporal_instant", "started_on", "deterministic_constructible", "verified", "Foundation of the bank", "https://www.oenb.at/en/About-Us/History/1816-1818.html", "The privileged Austrian National Bank started operation on June 1, 1816."),
    ("official:oenb", "The Austrian central bank's permanent management was established on January 19, 1818.", "temporal_instant", "established_on", "deterministic_constructible", "verified", "The Privilegirte Oesterreichische National-Bank", "https://www.oenb.at/en/About-Us/History/1818-1878.html", "On January 19, 1818, the permanent bank management was set up."),
    ("official:cnb", "The Czech National Bank became the Czech Republic's central bank in 1993.", "temporal_instant", "became_in", "deterministic_constructible", "verified", "85 Years of the Central Bank", "https://www.cnb.cz/en/about_cnb/85-let/", "Under the Constitution, the Czech National Bank became the central bank of the newly formed Czech Republic in 1993."),
    ("official:cnb", "The Czech National Bank is more open than every other central bank.", "temporal_instant", "qualitative_superlative", "not_applicable", None, "85 Years of the Central Bank", "https://www.cnb.cz/en/about_cnb/85-let/", "The independent, competent and maximally open Czech National Bank works to ensure price stability."),
    ("official:nationalbanken", "Danmarks Nationalbank was established in 1818.", "temporal_instant", "established_in", "deterministic_constructible", "verified", "Historical banknotes", "https://www.nationalbanken.dk/en/what-we-do/notes-and-coins/historical-banknotes", "Since its establishment in 1818, Danmarks Nationalbank has been the only institution in Denmark that is allowed to issue banknotes."),
    ("official:nationalbanken", "Danmarks Nationalbank issued its first banknotes in 1819.", "temporal_instant", "issued_in", "deterministic_constructible", "verified", "Historical banknotes", "https://www.nationalbanken.dk/en/what-we-do/notes-and-coins/historical-banknotes", "Danmarks Nationalbank issued its first banknotes in 1819."),
    ("official:bank-finland", "The Bank of Finland traces its origin to 1811.", "temporal_instant", "originated_in", "deterministic_constructible", "verified", "History of the Bank of Finland", "https://www.suomenpankki.fi/en/bank-of-finland/art-and-history/", "It traces its origin back to 1811."),
    ("official:bank-finland", "The Bank of Finland moved to Helsinki in 1819.", "temporal_instant", "moved_in", "deterministic_constructible", "verified", "History of the Bank of Finland", "https://www.suomenpankki.fi/en/bank-of-finland/art-and-history/", "This pioneering bank later became the Bank of Finland, which was moved, with the relocation of the capital city, to Helsinki in 1819."),
)


def main() -> None:
    cases = []
    for index, item in enumerate(CASES, start=341):
        family, claim, dimension, relation, label, state, title, url, passage = item
        evidence_id = f"V3-{index}:E1"
        constructible = label != "not_applicable"
        cases.append(
            V3AnnotationCase(
                case_id=f"V3-{index}",
                source_candidate_id=f"V4-STAGE9E-{index}",
                split=V3DatasetSplit.CALIBRATION,
                origin_family_id=family,
                claim_text=claim,
                evidence=(V3ReviewEvidence(evidence_id=evidence_id, title=title, url=url, source_class="official_html", passage=passage),),
                proposal=V3MachinePreparedProposal(
                    dimension_bucket=dimension,
                    comparator_or_relation=relation,
                    claim_span=V3ExactTextSpan(start_char=0, end_char=len(claim), quoted_text=claim),
                    evidence_spans=(V3EvidenceSpan(evidence_id=evidence_id, start_char=0, end_char=len(passage), quoted_text=passage),) if constructible else (),
                    suggested_gold_label=V3ConstructionGoldLabel(label),
                    suggested_verification_state=state,
                    machine_notes=("Prefilled review proposal; human confirmation is required.", "Accessible official HTML; no PDF or restricted document was stored."),
                    model_calls=0,
                ),
            )
        )
    workbook = V3ReplacementCalibrationWorkbook(
        workbook_id="verification-construction-v4-stage9e-fresh-calibration-workbook-v1",
        cases=tuple(cases),
    )
    payload = json.dumps(workbook.model_dump(mode="json"), indent=2) + "\n"
    OUTPUT.write_text(payload, encoding="utf-8")
    PUBLIC.write_text(payload, encoding="utf-8")
    print(f"{OUTPUT.relative_to(ROOT)} cases=20 families=10 sha256={hashlib.sha256(payload.encode()).hexdigest()} model_calls=0")


if __name__ == "__main__":
    main()
