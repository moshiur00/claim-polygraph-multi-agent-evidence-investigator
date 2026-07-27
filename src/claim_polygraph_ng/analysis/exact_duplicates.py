"""Versioned exact-content fingerprints and deterministic duplicate clusters."""

import hashlib
import re
import unicodedata
from collections import defaultdict

from pydantic import Field

from claim_polygraph_ng.domain.base import DomainModel

EXACT_FINGERPRINT_VERSION = "exact-text-v1"
_WHITESPACE = re.compile(r"\s+")


class ContentFingerprint(DomainModel):
    """Fingerprint of one normalized document or evidence passage."""

    record_id: str
    normalization_version: str = EXACT_FINGERPRINT_VERSION
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    normalized_character_count: int = Field(ge=0)


class ExactDuplicateCluster(DomainModel):
    """Auditable group of records with identical normalized content."""

    cluster_id: str = Field(pattern=r"^exact-[0-9a-f]{16}$")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    representative_id: str
    member_ids: tuple[str, ...] = Field(min_length=2)
    normalization_version: str = EXACT_FINGERPRINT_VERSION


def normalize_exact_content(value: str) -> str:
    """Apply only representation-level transformations."""
    normalized = unicodedata.normalize("NFKC", value)
    return _WHITESPACE.sub(" ", normalized).strip().casefold()


def fingerprint_content(record_id: str, content: str) -> ContentFingerprint:
    normalized = normalize_exact_content(content)
    return ContentFingerprint(
        record_id=record_id,
        sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        normalized_character_count=len(normalized),
    )


def cluster_exact_duplicates(
    records: tuple[tuple[str, str], ...],
) -> tuple[ExactDuplicateCluster, ...]:
    """Return stable clusters while preserving all original record IDs."""
    if len({record_id for record_id, _ in records}) != len(records):
        raise ValueError("record IDs must be unique")
    groups: dict[str, list[str]] = defaultdict(list)
    for record_id, content in records:
        groups[fingerprint_content(record_id, content).sha256].append(record_id)
    clusters = []
    for digest, member_ids in groups.items():
        if len(member_ids) < 2:
            continue
        ordered = tuple(sorted(member_ids))
        clusters.append(
            ExactDuplicateCluster(
                cluster_id=f"exact-{digest[:16]}",
                sha256=digest,
                representative_id=ordered[0],
                member_ids=ordered,
            )
        )
    return tuple(sorted(clusters, key=lambda item: item.cluster_id))
