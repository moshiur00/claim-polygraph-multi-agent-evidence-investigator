"""Shared fetch-free normalization for provider search candidates."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import JsonValue

from claim_polygraph_ng.analysis.social_urls import classify_social_url
from claim_polygraph_ng.domain import (
    DistributionMedium,
    ProviderResultMetadata,
    SocialUrlCandidate,
)


def classify_candidate_distribution(
    url: str,
) -> tuple[DistributionMedium, SocialUrlCandidate | None]:
    social = classify_social_url(url)
    if social is None:
        return DistributionMedium.WEB_PAGE, None
    return DistributionMedium.SOCIAL_PLATFORM, social


def retain_provider_metadata(
    *,
    provider_id: str,
    raw_result: Mapping[str, Any],
    attribute_keys: Iterable[str],
    rank_key: str | None = None,
    result_id_keys: Iterable[str] = (),
) -> ProviderResultMetadata:
    """Retain an allowlisted provider subset without altering JSON values."""

    rank: int | None = None
    if rank_key:
        candidate_rank = raw_result.get(rank_key)
        if isinstance(candidate_rank, int) and not isinstance(candidate_rank, bool):
            rank = candidate_rank if candidate_rank >= 1 else None

    result_id: str | None = None
    for key in result_id_keys:
        value = raw_result.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            result_id = str(value)
            break

    attributes: dict[str, JsonValue] = {}
    for key in attribute_keys:
        if key not in raw_result:
            continue
        value = raw_result[key]
        if _is_json_value(value):
            attributes[key] = value
    return ProviderResultMetadata(
        provider_id=provider_id,
        rank=rank,
        result_id=result_id,
        attributes=attributes,
    )


def _is_json_value(value: Any) -> bool:
    if value is None or isinstance(value, (str, int, float, bool)):
        return True
    if isinstance(value, list):
        return all(_is_json_value(item) for item in value)
    if isinstance(value, dict):
        return all(
            isinstance(key, str) and _is_json_value(item)
            for key, item in value.items()
        )
    return False

