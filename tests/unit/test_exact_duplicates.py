import pytest

from claim_polygraph_ng.analysis.exact_duplicates import (
    cluster_exact_duplicates,
    fingerprint_content,
    normalize_exact_content,
)


def test_representation_only_differences_share_a_fingerprint():
    first = fingerprint_content("A", " Café\tmeasured \uff14\uff12 units.\r\n")
    second = fingerprint_content("B", "café measured 42 units.\n")

    assert first.sha256 == second.sha256
    assert first.normalized_character_count == second.normalized_character_count


def test_substantive_punctuation_or_number_change_does_not_merge():
    records = (
        ("A", "The measured value was 42."),
        ("B", "The measured value was 43."),
        ("C", "The measured value was 42!"),
    )

    assert cluster_exact_duplicates(records) == ()


def test_clusters_are_stable_and_keep_all_member_ids():
    records = (
        ("C", "Identical project-authored content."),
        ("A", " identical  project-authored content. "),
        ("B", "Different project-authored content."),
    )

    forward = cluster_exact_duplicates(records)
    reverse = cluster_exact_duplicates(tuple(reversed(records)))

    assert forward == reverse
    assert len(forward) == 1
    assert forward[0].representative_id == "A"
    assert forward[0].member_ids == ("A", "C")


def test_duplicate_record_ids_are_rejected():
    with pytest.raises(ValueError, match="unique"):
        cluster_exact_duplicates((("A", "one"), ("A", "two")))


def test_empty_content_has_a_reproducible_fingerprint():
    assert normalize_exact_content(" \n\t") == ""
    assert fingerprint_content("A", " ").normalized_character_count == 0
