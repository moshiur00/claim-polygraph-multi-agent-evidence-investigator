"""Build the AI-prefilled, zero-call V4.10 fresh held-out workbook."""

# ruff: noqa: E501 -- exact short official HTML passages remain intact.

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from claim_polygraph_ng.evaluation.v3_annotation import (
    V3AnnotationCase,
    V3ExactTextSpan,
    V3MachinePreparedProposal,
    V3ReviewEvidence,
    V4FreshHeldOutWorkbook,
)
from claim_polygraph_ng.evaluation.v3_manifest import (
    V3ConstructionGoldLabel,
    V3DatasetSplit,
    V3EvidenceSpan,
)

ROOT = Path(__file__).parents[1]
OUTPUT = ROOT / "benchmarks/verification_construction_v4_stage10_fresh_held_out_workbook_v1.json"
PUBLIC = ROOT / "dashboard/public/v4-stage10-fresh-held-out.json"

# family, claim, dimension, relation, label, state, title, URL, exact HTML passage
CASES = (
    ("official:nbs", "Národná banka Slovenska was established on January 1, 1993.", "temporal_instant", "established_on", "deterministic_constructible", "verified", "About the Bank", "https://nbs.sk/en/about-the-bank/", "Národná banka Slovenska was established on 1 January 1993."),
    ("official:nbs", "Slovakia became part of the Eurosystem on January 1, 2009.", "temporal_instant", "became_on", "deterministic_constructible", "verified", "About the Bank", "https://nbs.sk/en/about-the-bank/", "From 1 January 2009, Slovakia became part of the Eurosystem."),
    ("official:rbi", "The Reserve Bank of India commenced operations on April 1, 1935.", "temporal_instant", "started_on", "deterministic_constructible", "verified", "RBI History", "https://rbi.org.in/scripts/His_brief.aspx", "The Reserve Bank of India commenced operations on April 1, 1935."),
    ("official:rbi", "The Reserve Bank of India Act was enacted in 1934.", "temporal_instant", "enacted_in", "deterministic_constructible", "verified", "RBI History", "https://rbi.org.in/scripts/His_brief.aspx", "The Reserve Bank of India Act, 1934 provides the statutory basis of the functioning of the Bank."),
    ("official:bcb", "Banco Central do Brasil was established on December 31, 1964.", "temporal_instant", "established_on", "deterministic_constructible", "verified", "Historical composition", "https://www.bcb.gov.br/en/about/historicalcompositionboardgovernors", "Banco Central do Brasil was established on December 31, 1964."),
    ("official:bcb", "Banco Central do Brasil received statutory autonomy in February 2021.", "temporal_instant", "received_in", "deterministic_constructible", "verified", "Who We Are", "https://www.bcb.gov.br/en/publications/who_we_are_2021", "Its autonomy is enforced by the Complementary Law 179, of February 2021."),
    ("official:cbsl", "The Central Bank of Ceylon commenced operations on August 28, 1950.", "temporal_instant", "started_on", "deterministic_constructible", "verified", "Bank History", "https://www.cbsl.gov.lk/en/node/25", "The Central Bank of Ceylon commenced operations on August 28, 1950."),
    ("official:cbsl", "The Central Bank of Ceylon was renamed the Central Bank of Sri Lanka in 1985.", "temporal_instant", "renamed_in", "deterministic_constructible", "verified", "Bank History", "https://www.cbsl.gov.lk/en/node/25", "It was renamed the Central Bank of Sri Lanka in 1985."),
    ("official:sbp", "The State Bank of Pakistan opened on July 1, 1948.", "temporal_instant", "started_on", "deterministic_constructible", "verified", "State Bank history", "https://www.sbp.org.pk/about/history/history_1.htm", "The opening ceremony of the State Bank of Pakistan was held on July 1, 1948."),
    ("official:sbp", "The State Bank of Pakistan is more important than every other national institution.", "temporal_instant", "qualitative_superlative", "not_applicable", None, "About SBP", "https://www.sbp.org.pk/about-sbp", "The State Bank of Pakistan Order of May 12, 1948 became the precursor to more comprehensive legislation."),
    ("official:bot", "The Bank of Thailand Act was promulgated on April 16, 1942.", "temporal_instant", "promulgated_on", "deterministic_constructible", "verified", "History of the Bank of Thailand", "https://www.bot.or.th/en/about-us/history.html", "The Bank of Thailand Act was promulgated on 16 April 1942."),
    ("official:bot", "The Bank of Thailand's inauguration ceremony was held on December 10, 1942.", "temporal_instant", "inaugurated_on", "deterministic_constructible", "verified", "History of the Bank of Thailand", "https://www.bot.or.th/en/about-us/history.html", "The inauguration ceremonies were held on 10 December 1942."),
    ("official:bank-indonesia", "Bank Indonesia was officially established on July 1, 1953.", "temporal_instant", "established_on", "deterministic_constructible", "verified", "History of Bank Indonesia", "https://www.bi.go.id/en/tentang-bi/sejarah-bi/default.aspx", "On 1st July 1953, Bank Indonesia was officially established as the Central Bank of the Republic of Indonesia."),
    ("official:bank-indonesia", "Bank Indonesia's banking supervision function moved to OJK in 2011.", "temporal_instant", "moved_in", "deterministic_constructible", "verified", "History of Bank Indonesia", "https://www.bi.go.id/en/tentang-bi/sejarah-bi/default.aspx", "In 2011, banking regulation and surveillance was moved to OJK."),
    ("official:bank-korea", "The Bank of Korea was established on June 12, 1950.", "temporal_instant", "established_on", "deterministic_constructible", "verified", "History and Mission", "https://www.bok.or.kr/eng/main/contents.do?menuNo=400079", "The Bank of Korea was established on June 12, 1950."),
    ("official:bank-korea", "The Bank of Korea Act was passed on May 5, 1950.", "temporal_instant", "passed_on", "deterministic_constructible", "verified", "History and Mission", "https://www.bok.or.kr/eng/main/contents.do?menuNo=400079", "The Bank of Korea Act was passed on May 5, 1950."),
    ("official:cbuae", "The Central Bank of the UAE was established in 1980.", "temporal_instant", "established_in", "deterministic_constructible", "verified", "Our History", "https://www.centralbank.ae/en/about/about-cbuae/our-history/", "Union Law No. 10 of 1980 established the Central Bank of the UAE as a public institution."),
    ("official:cbuae", "The UAE Currency Board was established in 1973.", "temporal_instant", "established_in", "deterministic_constructible", "verified", "Our History", "https://www.centralbank.ae/en/about/about-cbuae/our-history/", "The Currency Board was established under Union Law No. 2 of 1973."),
    ("official:bnm", "Bank Negara Malaysia was established on January 26, 1959.", "temporal_instant", "established_on", "deterministic_constructible", "verified", "About Bank Negara Malaysia", "https://museum.bnm.gov.my/about/", "Bank Negara Malaysia was established on 26 January 1959 under the Central Bank of Malaya Act 1958."),
    ("official:bnm", "Bank Negara Malaysia has contributed more to nation building than every other statutory body.", "temporal_instant", "qualitative_superlative", "not_applicable", None, "About Bank Negara Malaysia", "https://museum.bnm.gov.my/about/", "The museum explains the role that the Central Bank plays in nation building."),
)


def main() -> None:
    cases = []
    for index, item in enumerate(CASES, start=361):
        family, claim, dimension, relation, label, state, title, url, passage = item
        evidence_id = f"V3-{index}:E1"
        constructible = label != "not_applicable"
        cases.append(V3AnnotationCase(
            case_id=f"V3-{index}", source_candidate_id=f"V4-STAGE10-{index}", split=V3DatasetSplit.HELD_OUT,
            origin_family_id=family, claim_text=claim,
            evidence=(V3ReviewEvidence(evidence_id=evidence_id, title=title, url=url, source_class="official_html", passage=passage),),
            proposal=V3MachinePreparedProposal(
                dimension_bucket=dimension, comparator_or_relation=relation,
                claim_span=V3ExactTextSpan(start_char=0, end_char=len(claim), quoted_text=claim),
                evidence_spans=(V3EvidenceSpan(evidence_id=evidence_id, start_char=0, end_char=len(passage), quoted_text=passage),) if constructible else (),
                suggested_gold_label=V3ConstructionGoldLabel(label), suggested_verification_state=state,
                machine_notes=("Prefilled review proposal; human confirmation is required.", "Accessible official HTML; no PDF or restricted document was stored."), model_calls=0,
            ),
        ))
    workbook = V4FreshHeldOutWorkbook(cases=tuple(cases))
    payload = json.dumps(workbook.model_dump(mode="json"), indent=2) + "\n"
    OUTPUT.write_text(payload, encoding="utf-8")
    PUBLIC.write_text(payload, encoding="utf-8")
    print(f"{OUTPUT.relative_to(ROOT)} cases=20 families=10 sha256={hashlib.sha256(payload.encode()).hexdigest()} model_calls=0")


if __name__ == "__main__":
    main()
