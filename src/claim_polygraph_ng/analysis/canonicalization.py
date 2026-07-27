"""Conservative, versioned URL and publication-identifier canonicalization."""

import posixpath
import re
from enum import StrEnum
from urllib.parse import (
    parse_qsl,
    quote,
    unquote,
    urlencode,
    urlsplit,
    urlunsplit,
)

from claim_polygraph_ng.domain.base import DomainModel

CANONICALIZATION_VERSION = "url-v1"
_TRACKING_KEYS = frozenset(
    {
        "fbclid",
        "gclid",
        "mc_cid",
        "mc_eid",
        "ref_src",
        "utm_campaign",
        "utm_content",
        "utm_medium",
        "utm_source",
        "utm_term",
    }
)
_PRESENTATION_PAIRS = frozenset({("output", "print"), ("view", "print"), ("format", "html")})
_LANGUAGE_SEGMENT = re.compile(r"^[a-z]{2}(?:-[a-z]{2})?$", re.IGNORECASE)
_DOI = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)


class CanonicalizationReason(StrEnum):
    """One deterministic transformation applied to an identifier."""

    LOWERCASE_SCHEME_HOST = "lowercase_scheme_host"
    REMOVE_DEFAULT_PORT = "remove_default_port"
    REMOVE_FRAGMENT = "remove_fragment"
    REMOVE_TRACKING_PARAMETER = "remove_tracking_parameter"
    REMOVE_PRESENTATION_PARAMETER = "remove_presentation_parameter"
    SORT_QUERY = "sort_query"
    NORMALIZE_PATH = "normalize_path"
    REMOVE_LANGUAGE_PATH_VARIANT = "remove_language_path_variant"
    NORMALIZE_DOI = "normalize_doi"


class CanonicalizationResult(DomainModel):
    """Canonical value plus a complete transformation explanation."""

    input_value: str
    canonical_value: str
    version: str = CANONICALIZATION_VERSION
    reasons: tuple[CanonicalizationReason, ...] = ()
    removed_query_parameters: tuple[str, ...] = ()


def canonicalize_url(value: str) -> CanonicalizationResult:
    """Normalize URL identity without following redirects or using the network."""
    parsed = urlsplit(value)
    scheme = parsed.scheme.casefold()
    host = (parsed.hostname or "").casefold().rstrip(".")
    if scheme not in {"http", "https"} or not host:
        raise ValueError("canonicalization requires an absolute HTTP(S) URL")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("URLs containing credentials cannot be canonicalized")

    reasons: set[CanonicalizationReason] = set()
    raw_scheme = value.split(":", maxsplit=1)[0]
    if raw_scheme != scheme or any(character.isupper() for character in parsed.netloc):
        reasons.add(CanonicalizationReason.LOWERCASE_SCHEME_HOST)
    port = parsed.port
    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    if default_port:
        reasons.add(CanonicalizationReason.REMOVE_DEFAULT_PORT)
    netloc = host if port is None or default_port else f"{host}:{port}"

    path = _normalized_path(parsed.path)
    if path != (parsed.path or "/"):
        reasons.add(CanonicalizationReason.NORMALIZE_PATH)
    segments = path.split("/")
    if len(segments) > 2 and _LANGUAGE_SEGMENT.fullmatch(segments[1]):
        path = "/" + "/".join(segments[2:])
        reasons.add(CanonicalizationReason.REMOVE_LANGUAGE_PATH_VARIANT)

    kept: list[tuple[str, str]] = []
    removed: list[str] = []
    original_query = parse_qsl(parsed.query, keep_blank_values=True)
    for key, item_value in original_query:
        normalized_key = key.casefold()
        if normalized_key in _TRACKING_KEYS:
            reasons.add(CanonicalizationReason.REMOVE_TRACKING_PARAMETER)
            removed.append(key)
        elif (normalized_key, item_value.casefold()) in _PRESENTATION_PAIRS:
            reasons.add(CanonicalizationReason.REMOVE_PRESENTATION_PARAMETER)
            removed.append(key)
        else:
            kept.append((key, item_value))
    sorted_query = sorted(kept, key=lambda item: (item[0].casefold(), item[1]))
    if sorted_query != kept:
        reasons.add(CanonicalizationReason.SORT_QUERY)
    if parsed.fragment:
        reasons.add(CanonicalizationReason.REMOVE_FRAGMENT)
    canonical = urlunsplit((scheme, netloc, path, urlencode(sorted_query), ""))
    return CanonicalizationResult(
        input_value=value,
        canonical_value=canonical,
        reasons=tuple(sorted(reasons, key=str)),
        removed_query_parameters=tuple(removed),
    )


def canonicalize_doi(value: str) -> CanonicalizationResult:
    """Normalize a bare DOI or doi.org URL into one stable identifier."""
    candidate = value.strip()
    lowered = candidate.casefold()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if lowered.startswith(prefix):
            candidate = candidate[len(prefix) :]
            break
    candidate = unquote(candidate).strip().casefold()
    if not _DOI.fullmatch(candidate):
        raise ValueError("invalid DOI")
    return CanonicalizationResult(
        input_value=value,
        canonical_value=f"https://doi.org/{candidate}",
        reasons=(CanonicalizationReason.NORMALIZE_DOI,),
    )


def _normalized_path(value: str) -> str:
    decoded = unquote(value or "/")
    normalized = posixpath.normpath(decoded)
    if not normalized.startswith("/"):
        normalized = "/" + normalized
    if normalized == "//":
        normalized = "/"
    return quote(normalized, safe="/:@!$&'()*+,;=-._~")
