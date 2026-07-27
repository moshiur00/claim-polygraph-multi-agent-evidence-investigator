from claim_polygraph_ng.analysis.evidence_families import (
    DependencyStatus,
    FamilySourceRecord,
    infer_evidence_families,
)


def _record(source_id: str, text: str, url: str) -> FamilySourceRecord:
    return FamilySourceRecord(source_id=source_id, text=text, url=url)


def test_exact_copies_form_one_family_with_a_reason():
    result = infer_evidence_families(
        "component",
        (
            _record("A", "The measured value was 42.", "https://a.test/report"),
            _record("B", " the measured value was 42. ", "https://b.test/report"),
        ),
    )

    assert result.independent_family_count == 1
    assert result.dependency_edges[0].status is DependencyStatus.CONFIRMED_DEPENDENT
    assert result.families[0].grouping_reasons == ("exact_content",)


def test_explicit_independent_analyses_stay_separate():
    result = infer_evidence_families(
        "component",
        (
            _record(
                "A",
                "Using public Series Z, our regression finds a downward trend.",
                "https://a.test/report",
            ),
            _record(
                "B",
                "Our independently written model of public Series Z finds a downward trend.",
                "https://b.test/report",
            ),
        ),
    )

    assert result.independent_family_count == 2
    assert result.dependency_edges[0].status is DependencyStatus.LIKELY_INDEPENDENT


def test_ambiguous_paraphrase_stays_unknown_and_separate():
    result = infer_evidence_families(
        "component",
        (
            _record(
                "A",
                "Inspectors observed shallow surface cracks without structural failure.",
                "https://a.test/report",
            ),
            _record(
                "B",
                "An examination reportedly found minor cracking without structural damage.",
                "https://b.test/report",
            ),
        ),
    )

    assert result.independent_family_count == 2
    assert result.unresolved_pair_count == 1
    assert result.dependency_edges[0].status is DependencyStatus.UNKNOWN


def test_family_inference_is_order_invariant():
    records = (
        _record("C", "A company announcement says that 50 stations are planned.", "https://c.test"),
        _record(
            "A", "The plan has 50 stations according to a company announcement.", "https://a.test"
        ),
        _record("B", "An independent measurement found 49 stations.", "https://b.test"),
    )

    assert infer_evidence_families("component", records) == infer_evidence_families(
        "component", tuple(reversed(records))
    )
