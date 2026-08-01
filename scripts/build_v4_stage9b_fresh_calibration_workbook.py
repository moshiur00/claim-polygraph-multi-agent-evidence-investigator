"""Build the AI-prefilled, zero-call V4.9b fresh calibration workbook."""

# ruff: noqa: E501, RUF001 -- exact official HTML passages remain intact.

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
OUTPUT = ROOT / "benchmarks/verification_construction_v4_stage9b_fresh_calibration_workbook_v1.json"
PUBLIC = ROOT / "dashboard/public/v4-stage9b-fresh-calibration.json"

# family, claim, dimension, relation, label, state, title, URL, exact HTML passage
CASES = (
    (
        "official:bis",
        "The BIS was established in 1930.",
        "temporal_instant",
        "established_in",
        "deterministic_constructible",
        "verified",
        "History - overview",
        "https://www.bis.org/about/history.htm",
        "Established in 1930, the Bank for International Settlements is the oldest international financial institution.",
    ),
    (
        "official:bis",
        "The BIS is owned by 63 central banks.",
        "count",
        "equal",
        "deterministic_constructible",
        "verified",
        "About BIS",
        "https://www.bis.org/about/index.htm",
        "Established in 1930, the BIS is owned by 63 central banks, representing countries from around the world that together account for about 95% of world GDP.",
    ),
    (
        "official:gao",
        "GAO was created in 1921.",
        "temporal_instant",
        "created_in",
        "deterministic_constructible",
        "verified",
        "History",
        "https://www.gao.gov/about/what-gao-does/history",
        "The Budget and Accounting Act created GAO in 1921 when Congress realized the need to control growing government expenditures and debt after World War I.",
    ),
    (
        "official:gao",
        "GAO handles Congress's toughest audit assignments better than every other agency.",
        "count",
        "qualitative_superlative",
        "not_applicable",
        None,
        "History",
        "https://www.gao.gov/about/what-gao-does/history",
        "Today, our agency that once checked millions of government vouchers has become a multidisciplinary organization equipped to handle Congress’s toughest audit and evaluation assignments.",
    ),
    (
        "official:doj",
        "The Department of Justice was created on July 1, 1870.",
        "temporal_instant",
        "created_on",
        "deterministic_constructible",
        "verified",
        "DOJ history",
        "https://www.justice.gov/history/timeline/150-years-department-justice",
        "Creation of the U.S. Department of Justice and Civil Rights Enforcement, 1870-1872 — July 1, 1870",
    ),
    (
        "official:doj",
        "The Department of Justice keeps the country safer than every other department.",
        "count",
        "qualitative_superlative",
        "not_applicable",
        None,
        "About DOJ",
        "https://www.justice.gov/about",
        "The mission of the Department of Justice is to uphold the rule of law, to keep our country safe, and to protect civil rights.",
    ),
    (
        "official:cisa",
        "The CISA Act was signed into law on November 16, 2018.",
        "temporal_instant",
        "signed_on",
        "deterministic_constructible",
        "verified",
        "CISA established",
        "https://www.cisa.gov/news-events/alerts/2018/11/19/cybersecurity-and-infrastructure-security-agency",
        "On November 16, 2018, the President signed into law the Cybersecurity and Infrastructure Security Agency Act of 2018.",
    ),
    (
        "official:cisa",
        "CISA was established in November 2018.",
        "temporal_instant",
        "established_in",
        "deterministic_constructible",
        "verified",
        "CISA established",
        "https://www.cisa.gov/news-events/alerts/2018/11/19/cybersecurity-and-infrastructure-security-agency",
        "Established in November 2018, CISA is responsible for protecting the Nation's critical infrastructure from physical and cyber threats.",
    ),
    (
        "official:bank-canada",
        "The Bank of Canada Act received royal assent on July 3, 1934.",
        "temporal_instant",
        "received_assent_on",
        "deterministic_constructible",
        "verified",
        "Our history",
        "https://www.bankofcanada.ca/about/our-history/",
        "The Act received royal assent on July 3, 1934.",
    ),
    (
        "official:bank-canada",
        "The Bank of Canada opened its doors in March 1935.",
        "temporal_instant",
        "started_in",
        "deterministic_constructible",
        "verified",
        "Our history",
        "https://www.bankofcanada.ca/about/our-history/",
        "In March 1935, the Bank of Canada opened its doors as a privately owned institution with shares sold to the public.",
    ),
    (
        "official:bundesbank",
        "The Bundesbank Act was passed on 26 July 1957.",
        "temporal_instant",
        "passed_on",
        "deterministic_constructible",
        "verified",
        "Timeline",
        "https://www.bundesbank.de/en/bundesbank/history",
        "The Bundesbank Act (Gesetz über die Deutsche Bundesbank) is passed on 26 July 1957 and enters into force on 1 August.",
    ),
    (
        "official:bundesbank",
        "The Bundesbank Act entered into force on 1 August 1957.",
        "temporal_instant",
        "entered_into_force_on",
        "deterministic_constructible",
        "verified",
        "Timeline",
        "https://www.bundesbank.de/en/bundesbank/history",
        "The Bundesbank Act (Gesetz über die Deutsche Bundesbank) is passed on 26 July 1957 and enters into force on 1 August.",
    ),
    (
        "official:riksbank",
        "Sveriges Riksbank was founded in 1668.",
        "temporal_instant",
        "founded_in",
        "deterministic_constructible",
        "verified",
        "History",
        "https://www.riksbank.se/en-gb/about-the-riksbank/history/",
        "In 1668, the Riksdag, Sweden's parliament, decided to found Riksens Ständers Bank (the Estates of the Realm Bank), which in 1867 received the name Sveriges Riksbank.",
    ),
    (
        "official:riksbank",
        "Riksens Ständers Bank received the name Sveriges Riksbank in 1867.",
        "temporal_instant",
        "renamed_in",
        "deterministic_constructible",
        "verified",
        "History",
        "https://www.riksbank.se/en-gb/about-the-riksbank/history/",
        "In 1668, the Riksdag, Sweden's parliament, decided to found Riksens Ständers Bank (the Estates of the Realm Bank), which in 1867 received the name Sveriges Riksbank.",
    ),
    (
        "official:boj",
        "The Bank of Japan began operating on October 10, 1882.",
        "temporal_instant",
        "started_on",
        "deterministic_constructible",
        "verified",
        "Outline of the Bank",
        "https://www.boj.or.jp/en/about/outline/",
        "The Bank of Japan was established under the Bank of Japan Act (promulgated in June 1882) and began operating on October 10, 1882, as the nation's central bank.",
    ),
    (
        "official:boj",
        "The Bank of Japan Policy Board was established in June 1949.",
        "temporal_instant",
        "established_in",
        "deterministic_constructible",
        "verified",
        "History",
        "https://www.boj.or.jp/en/about/outline/history/",
        "1949 | June | The Policy Board is established.",
    ),
    (
        "official:abs",
        "The Australian Bureau of Statistics Act 1975 establishes the ABS as an independent statutory authority.",
        "temporal_interval_or_status",
        "established_by",
        "deterministic_constructible",
        "verified",
        "Legislative framework",
        "https://www.abs.gov.au/about/legislation-and-policy/legislative-framework",
        "The Australian Bureau of Statistics Act 1975 establishes the ABS as an independent statutory authority.",
    ),
    (
        "official:abs",
        "The Commonwealth Bureau of Census and Statistics was established in 1906.",
        "temporal_instant",
        "established_in",
        "deterministic_constructible",
        "verified",
        "Labour statistics overview",
        "https://www.abs.gov.au/statistics/detailed-methodology-information/concepts-sources-methods/labour-statistics-concepts-sources-and-methods/2021/overview",
        "The Commonwealth Bureau of Census and Statistics was established in 1906 and was later replaced by the Australian Bureau of Statistics in 1974.",
    ),
    (
        "official:stats-nz",
        "Stats NZ has over 1,000 employees.",
        "count",
        "greater_than",
        "deterministic_constructible",
        "verified",
        "About us",
        "https://www.stats.govt.nz/about-us/",
        "Stats NZ is a government department with over 1,000 employees.",
    ),
    (
        "official:stats-nz",
        "Stats NZ improves lives more than every other government department.",
        "count",
        "qualitative_superlative",
        "not_applicable",
        None,
        "About us",
        "https://www.stats.govt.nz/about-us/",
        "About Aotearoa, for Aotearoa – data that improves lives today and for generations to come.",
    ),
)


def main() -> None:
    cases = []
    for index, item in enumerate(CASES, start=321):
        family, claim, dimension, relation, label, state, title, url, passage = item
        evidence_id = f"V3-{index}:E1"
        constructible = label != "not_applicable"
        cases.append(
            V3AnnotationCase(
                case_id=f"V3-{index}",
                source_candidate_id=f"V4-STAGE9B-{index}",
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
        workbook_id="verification-construction-v4-stage9b-fresh-calibration-workbook-v1",
        cases=tuple(cases),
    )
    payload = json.dumps(workbook.model_dump(mode="json"), indent=2) + "\n"
    OUTPUT.write_text(payload, encoding="utf-8")
    PUBLIC.write_text(payload, encoding="utf-8")
    print(
        f"{OUTPUT.relative_to(ROOT)} cases=20 families=10 sha256={hashlib.sha256(payload.encode()).hexdigest()} model_calls=0"
    )


if __name__ == "__main__":
    main()
