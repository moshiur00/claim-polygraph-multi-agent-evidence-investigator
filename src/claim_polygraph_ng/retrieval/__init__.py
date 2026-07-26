"""Safe document retrieval and text extraction."""

from claim_polygraph_ng.retrieval.fetcher import (
    ContentFetcher,
    FetchError,
    HttpStatusError,
    NetworkFetchError,
    RedirectLimitError,
    ResponseTooLargeError,
    SafeHttpFetcher,
    SystemHostResolver,
    UnsafeUrlError,
    UnsupportedContentTypeError,
)
from claim_polygraph_ng.retrieval.models import FetchedDocument, UrlSafetyPolicy
from claim_polygraph_ng.retrieval.text import extract_readable_text

__all__ = [
    "ContentFetcher",
    "FetchError",
    "FetchedDocument",
    "HttpStatusError",
    "NetworkFetchError",
    "RedirectLimitError",
    "ResponseTooLargeError",
    "SafeHttpFetcher",
    "SystemHostResolver",
    "UnsafeUrlError",
    "UnsupportedContentTypeError",
    "UrlSafetyPolicy",
    "extract_readable_text",
]
