"""Deterministic extraction of explicit, untrusted provenance references."""

import re
from enum import StrEnum

from pydantic import AnyHttpUrl, Field

from claim_polygraph_ng.domain.base import DomainModel

PROVENANCE_LINK_VERSION = "explicit-links-v1"


class ProvenanceLinkType(StrEnum):
    """Observed relationship language; not a resolved dependency judgment."""

    CITES = "cites"
    SUMMARY_OF = "summary_of"
    ATTRIBUTED_TO = "attributed_to"
    COMMON_ANNOUNCEMENT = "common_announcement"
    CONTROLLING_REFERENCE = "controlling_reference"
    URL_REFERENCE = "url_reference"


class ExtractedProvenanceLink(DomainModel):
    """Exact source-relative reference awaiting safe resolution."""

    source_id: str
    link_type: ProvenanceLinkType
    exact_text: str = Field(min_length=1)
    start_char: int = Field(ge=0)
    end_char: int = Field(gt=0)
    target_text: str = Field(min_length=1)
    target_url: AnyHttpUrl | None = None
    resolved_source_id: str | None = None
    confidence: float = Field(ge=0, le=1)
    extraction_version: str = PROVENANCE_LINK_VERSION
    requires_safe_resolution: bool = True
    retrieval_authorized: bool = False


_PATTERNS: tuple[tuple[ProvenanceLinkType, re.Pattern[str], float], ...] = (
    (
        ProvenanceLinkType.CITES,
        re.compile(
            r"\bas required by (?P<target>[^.!?]{3,100})",
            re.IGNORECASE,
        ),
        0.98,
    ),
    (
        ProvenanceLinkType.SUMMARY_OF,
        re.compile(
            r"\b(?P<target>(?:a|the) [^.!?]{3,70}?) reports that\b",
            re.IGNORECASE,
        ),
        0.94,
    ),
    (
        ProvenanceLinkType.COMMON_ANNOUNCEMENT,
        re.compile(
            r"\baccording to (?P<target>[^.!?]{3,80})",
            re.IGNORECASE,
        ),
        0.96,
    ),
    (
        ProvenanceLinkType.COMMON_ANNOUNCEMENT,
        re.compile(
            r"\b(?P<target>(?:a|the) [^.!?]{3,70}? announcement) says that\b",
            re.IGNORECASE,
        ),
        0.96,
    ),
    (
        ProvenanceLinkType.CONTROLLING_REFERENCE,
        re.compile(r"\b(?P<target>Standard [A-Z][A-Z0-9-]*)\b"),
        0.98,
    ),
)
_URL = re.compile(r"https?://[^\s<>()\"']+", re.IGNORECASE)


def extract_provenance_links(source_id: str, text: str) -> tuple[ExtractedProvenanceLink, ...]:
    """Extract references without resolving, opening, or trusting them."""
    links = []
    seen: set[tuple] = set()
    for link_type, pattern, confidence in _PATTERNS:
        for match in pattern.finditer(text):
            target = match.group("target").strip(" ,;:")
            start, end = match.span()
            key = (link_type, start, end, target.casefold())
            if key in seen:
                continue
            seen.add(key)
            links.append(
                ExtractedProvenanceLink(
                    source_id=source_id,
                    link_type=link_type,
                    exact_text=text[start:end],
                    start_char=start,
                    end_char=end,
                    target_text=target,
                    confidence=confidence,
                )
            )
    for match in _URL.finditer(text):
        raw_url = match.group(0).rstrip(".,;:!?")
        start = match.start()
        end = start + len(raw_url)
        links.append(
            ExtractedProvenanceLink(
                source_id=source_id,
                link_type=ProvenanceLinkType.URL_REFERENCE,
                exact_text=text[start:end],
                start_char=start,
                end_char=end,
                target_text=raw_url,
                target_url=raw_url,
                confidence=1,
            )
        )
    return tuple(
        sorted(links, key=lambda item: (item.start_char, item.end_char, item.link_type.value))
    )
