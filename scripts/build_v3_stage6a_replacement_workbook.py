"""Build the fresh, unannotated V3.6a replacement-calibration workbook."""

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

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT
    / "benchmarks/"
    "verification_construction_v3_stage6a_replacement_calibration_workbook_v1.json"
)
PUBLIC_OUTPUT = ROOT / "dashboard/public/v3-stage6a-replacement-calibration.json"

# Accessible HTML only. These passages are navigation aids, not gold labels.
CASES = (
    (
        "NASA-ROTATION",
        "official:nasa-mars",
        "A day on Mars lasts 24.6 hours.",
        "duration",
        "equal",
        "Mars Facts",
        "https://science.nasa.gov/mars/facts/?print=detailedfacts",
        "As Mars orbits the Sun, it completes one rotation every 24.6 hours, "
        "which is very similar to one day on Earth (23.9 hours).",
    ),
    (
        "NASA-YEAR",
        "official:nasa-mars",
        "A Martian year is equal to 687 Earth days.",
        "duration",
        "equal",
        "Mars Facts",
        "https://science.nasa.gov/mars/facts/?print=detailedfacts",
        "A year on Mars lasts 669.6 sols, which is the same as 687 Earth days.",
    ),
    (
        "WHO-FORCE",
        "official:who-history",
        "WHO's Constitution entered into force on 7 April 1948.",
        "date",
        "entered_into_force_on",
        "WHO History",
        "https://www.who.int/about/history/",
        "WHO's Constitution came into force on 7 April 1948 - a date we now "
        "celebrate every year as World Health Day.",
    ),
    (
        "WHO-SIGNED",
        "official:who-history",
        "WHO's Constitution was signed on 22 July 1946.",
        "date",
        "signed_on",
        "WHO History",
        "https://www.who.int/about/history/",
        "The Conference drafted and adopted the Constitution of the World "
        "Health Organization, signed 22 July 1946 by representatives of 51 "
        "Members of the UN and of 10 other nations.",
    ),
    (
        "NIST-SECOND",
        "official:nist-si",
        "The SI definition of the second fixes the cesium frequency at 9,192,631,770 hertz.",
        "frequency",
        "equal",
        "Definitions of SI Base Units",
        "https://www.nist.gov/si-redefinition/definitions-si-base-units",
        "The second is defined by taking the fixed numerical value of the cesium "
        "frequency to be 9,192,631,770 when expressed in the unit Hz.",
    ),
    (
        "NIST-MOLE",
        "official:nist-si",
        "One mole contains exactly 6.02214076 x 10^23 elementary entities.",
        "count",
        "equal",
        "Definitions of SI Base Units",
        "https://www.nist.gov/si-redefinition/definitions-si-base-units",
        "One mole contains exactly 6.02214076 x 10^23 elementary entities.",
    ),
    (
        "CENSUS-POPULATION",
        "official:us-census-2020",
        "The United States population was 331,449,281 on 1 April 2020.",
        "count",
        "equal_as_of",
        "The 2020 Census: Our Growing Nation",
        "https://www.census.gov/newsroom/blogs/director/2021/04/"
        "2020-census-our-growing-nation.html",
        "According to the 2020 Census, there were 331,449,281 people living "
        "in the United States as of April 1, 2020, which represents a growth "
        "of 7.4% since 2010.",
    ),
    (
        "CENSUS-GROWTH",
        "official:us-census-2020",
        "The U.S. population grew 7.4 percent from 2010 to 2020.",
        "percentage_or_rate",
        "equal_over_interval",
        "The 2020 Census: Our Growing Nation",
        "https://www.census.gov/newsroom/blogs/director/2021/04/"
        "2020-census-our-growing-nation.html",
        "According to the 2020 Census, there were 331,449,281 people living "
        "in the United States as of April 1, 2020, which represents a growth "
        "of 7.4% since 2010.",
    ),
    (
        "EPA-GALLON",
        "official:epa-conversions",
        "One U.S. gallon converts to 3.785 liters.",
        "volume",
        "conversion",
        "EPA ExpoBox Unit Conversion Table",
        "https://www.epa.gov/expobox/epa-expobox-unit-conversion-table",
        "gallons (gal) | 3.785 | liters (L)",
    ),
    (
        "EPA-POUND",
        "official:epa-conversions",
        "One pound converts to 454 grams.",
        "mass",
        "conversion",
        "EPA ExpoBox Unit Conversion Table",
        "https://www.epa.gov/expobox/epa-expobox-unit-conversion-table",
        "pounds (lb) | 454 | grams (g)",
    ),
    (
        "FDA-CUP",
        "official:fda-household-measures",
        "For U.S. nutrition labeling, one cup means 240 milliliters.",
        "volume",
        "conversion",
        "Metric Equivalents of Household Measures",
        "https://www.fda.gov/regulatory-information/search-fda-guidance-documents/"
        "guidance-industry-guidelines-determining-metric-equivalents-household-measures",
        "For purposes of nutrition labeling, 1 cup means 240 mL, 1 tablespoon "
        "means 15 mL, 1 teaspoon means 5 mL, 1 fluid ounce means 30 mL, and "
        "1 ounce means 28 g.",
    ),
    (
        "FDA-TEASPOON",
        "official:fda-household-measures",
        "For U.S. nutrition labeling, one teaspoon means 5 milliliters.",
        "volume",
        "conversion",
        "Metric Equivalents of Household Measures",
        "https://www.fda.gov/regulatory-information/search-fda-guidance-documents/"
        "guidance-industry-guidelines-determining-metric-equivalents-household-measures",
        "For purposes of nutrition labeling, 1 cup means 240 mL, 1 tablespoon "
        "means 15 mL, 1 teaspoon means 5 mL, 1 fluid ounce means 30 mL, and "
        "1 ounce means 28 g.",
    ),
    (
        "CDC-SLEEP-RANGE",
        "official:cdc-niosh-sleep",
        "Most adults need between 7 and 8 hours of quality sleep each night.",
        "duration",
        "range",
        "Basic Information about Sleep and Fatigue",
        "https://archive.cdc.gov/www_cdc_gov/niosh/emres/longhourstraining/"
        "sleepfatigue.html",
        "How much sleep do you need? Most adults need 7 to 8 hours of quality "
        "sleep per night.",
    ),
    (
        "CDC-SLEEP-LOW",
        "official:cdc-niosh-sleep",
        "Some adults function well on 6 hours of sleep or less, but this is rare.",
        "duration",
        "less_than_or_equal",
        "Basic Information about Sleep and Fatigue",
        "https://archive.cdc.gov/www_cdc_gov/niosh/emres/longhourstraining/"
        "sleepfatigue.html",
        "Some function well on 6 hours or less, but this is rare.",
    ),
    (
        "DOE-B20",
        "official:doe-fuels-glossary",
        "B20 fuel contains 20 percent biodiesel and 80 percent petroleum diesel by volume.",
        "percentage_or_rate",
        "composition",
        "Full Text Glossary",
        "https://www.energy.gov/cmei/fuels/full-text-glossary",
        "B20: A mixture of 20% biodiesel and 80% petroleum diesel based on volume.",
    ),
    (
        "DOE-BARREL-ENERGY",
        "official:doe-fuels-glossary",
        "A barrel of crude oil contains about 5.8 million Btu of energy.",
        "energy",
        "approximately_equal",
        "Full Text Glossary",
        "https://www.energy.gov/cmei/fuels/full-text-glossary",
        "For crude oil, one barrel contains about 5.8 x 10^6 Btu of energy.",
    ),
    (
        "NWS-HPA",
        "official:nws-pressure",
        "Standard sea-level pressure is 1013.25 hectopascals.",
        "pressure",
        "equal",
        "Pressure",
        "https://www.weather.gov/source/zhu/ZHU_Training_Page/winds/pressure_winds/"
        "Pressure.htm",
        "The standard pressure at sea-level is 1013.25 millibars and 1013.25 hPa.",
    ),
    (
        "NWS-CONVERSION",
        "official:nws-pressure",
        "One hectopascal equals 100 pascals.",
        "pressure",
        "conversion",
        "Pressure",
        "https://www.weather.gov/source/zhu/ZHU_Training_Page/winds/pressure_winds/"
        "Pressure.htm",
        "Thus, 1 hectopascal (hPa) equals 100 Pa which equals 1 millibar.",
    ),
    (
        "IEA-DEMAND",
        "official:iea-electricity-2026",
        "Global electricity demand grew more than twice as fast as overall energy demand in 2025.",
        "percentage_or_rate",
        "greater_than_ratio",
        "Global Energy Review 2026: Electricity demand",
        "https://www.iea.org/reports/global-energy-review-2026/electricity-demand",
        "Electricity grew around 3%; overall energy demand grew 1.3%.",
    ),
    (
        "FACTCHECK-HOUSING",
        "factcheck:us-housing-prices",
        "U.S. home-sale price measures rose no more than 37 percent during Joe Biden's presidency.",
        "percentage_or_rate",
        "less_than_or_equal",
        "Vance's Misleading Claims on Housing Prices and Illegal Immigration",
        "https://www.factcheck.org/2025/12/"
        "vances-misleading-claims-on-housing-prices-and-illegal-immigration/",
        "Home sales price measures show at most a 37% increase.",
    ),
)


def main() -> None:
    records: list[V3AnnotationCase] = []
    for index, (
        candidate_id,
        family,
        claim,
        dimension,
        relation,
        title,
        url,
        passage,
    ) in enumerate(CASES, start=101):
        evidence_id = f"V3-{index}:E1"
        records.append(
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
                        source_class="official_or_fact_check",
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
                        "No benchmark model call was used.",
                    ),
                    model_calls=0,
                ),
            )
        )
    workbook = V3ReplacementCalibrationWorkbook(cases=tuple(records))
    serialized = json.dumps(workbook.model_dump(mode="json"), indent=2) + "\n"
    OUTPUT.write_text(serialized, encoding="utf-8")
    PUBLIC_OUTPUT.write_text(serialized, encoding="utf-8")
    print(f"{OUTPUT.relative_to(ROOT)} cases={len(records)} model_calls=0")


if __name__ == "__main__":
    main()
