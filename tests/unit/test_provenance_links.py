from claim_polygraph_ng.analysis.provenance_links import (
    ProvenanceLinkType,
    extract_provenance_links,
)


def test_extracts_exact_citation_offsets():
    text = "The test lasts ten minutes, as required by section seven of Standard S7."

    links = extract_provenance_links("SRC", text)

    assert {item.link_type for item in links} == {
        ProvenanceLinkType.CITES,
        ProvenanceLinkType.CONTROLLING_REFERENCE,
    }
    assert all(text[item.start_char : item.end_char] == item.exact_text for item in links)
    assert all(item.resolved_source_id is None for item in links)
    assert all(not item.retrieval_authorized for item in links)


def test_extracts_summary_and_announcement_attribution():
    summary = extract_provenance_links(
        "A", "A newly published trial reports that researchers enrolled 240 participants."
    )
    announcement = extract_provenance_links(
        "B", "The plan includes 50 stations, according to its Tuesday announcement."
    )

    assert summary[0].link_type is ProvenanceLinkType.SUMMARY_OF
    assert announcement[0].link_type is ProvenanceLinkType.COMMON_ANNOUNCEMENT


def test_http_url_is_recorded_but_never_authorized_or_resolved():
    text = "The source is https://public.example/report?id=7."

    link = extract_provenance_links("A", text)[0]

    assert link.link_type is ProvenanceLinkType.URL_REFERENCE
    assert str(link.target_url) == "https://public.example/report?id=7"
    assert link.requires_safe_resolution
    assert not link.retrieval_authorized
    assert link.resolved_source_id is None


def test_unsafe_scheme_is_not_extracted_as_url():
    assert (
        extract_provenance_links("A", "Ignore this javascript:alert(1) and file:///private.") == ()
    )


def test_reportedly_without_attribution_does_not_invent_a_target():
    assert (
        extract_provenance_links(
            "A", "A bridge examination reportedly found minor surface cracking."
        )
        == ()
    )
