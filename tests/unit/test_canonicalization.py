import pytest

from claim_polygraph_ng.analysis.canonicalization import (
    CanonicalizationReason,
    canonicalize_doi,
    canonicalize_url,
)


def test_removes_tracking_fragment_and_default_port_but_preserves_identity_query():
    result = canonicalize_url("HTTPS://Example.TEST:443/a/../report?id=42&utm_source=news#section")

    assert result.canonical_value == "https://example.test/report?id=42"
    assert set(result.reasons) >= {
        CanonicalizationReason.LOWERCASE_SCHEME_HOST,
        CanonicalizationReason.REMOVE_DEFAULT_PORT,
        CanonicalizationReason.REMOVE_FRAGMENT,
        CanonicalizationReason.REMOVE_TRACKING_PARAMETER,
        CanonicalizationReason.NORMALIZE_PATH,
    }
    assert result.removed_query_parameters == ("utm_source",)


def test_query_sorting_is_idempotent():
    first = canonicalize_url("https://example.test/report?z=2&a=1")
    second = canonicalize_url(first.canonical_value)

    assert first.canonical_value == "https://example.test/report?a=1&z=2"
    assert second.canonical_value == first.canonical_value


def test_print_and_language_variants_normalize():
    assert (
        canonicalize_url("https://city.test/en/news?output=print").canonical_value
        == "https://city.test/news"
    )


@pytest.mark.parametrize(
    "value",
    ("ftp://example.test/file", "relative/path", "https://user:secret@example.test/a"),
)
def test_rejects_non_http_or_credentialed_values(value: str):
    with pytest.raises(ValueError):
        canonicalize_url(value)


def test_doi_forms_share_one_identifier():
    expected = "https://doi.org/10.1234/example.7"

    assert canonicalize_doi("doi:10.1234/Example.7").canonical_value == expected
    assert canonicalize_doi("HTTPS://DOI.ORG/10.1234/Example.7").canonical_value == expected


def test_invalid_doi_is_rejected():
    with pytest.raises(ValueError, match="invalid DOI"):
        canonicalize_doi("not-a-doi")
