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
from claim_polygraph_ng.retrieval.models import (
    ChunkingPolicy,
    DocumentChunk,
    FetchedDocument,
    RankedPassage,
    UrlSafetyPolicy,
)
from claim_polygraph_ng.retrieval.passages import (
    deduplicate_chunks,
    rank_passages,
    segment_document,
)
from claim_polygraph_ng.retrieval.text import extract_readable_text

__all__ = [
    "ChunkingPolicy",
    "ContentFetcher",
    "DocumentChunk",
    "FetchError",
    "FetchedDocument",
    "HttpStatusError",
    "NetworkFetchError",
    "RankedPassage",
    "RedirectLimitError",
    "ResponseTooLargeError",
    "SafeHttpFetcher",
    "SystemHostResolver",
    "UnsafeUrlError",
    "UnsupportedContentTypeError",
    "UrlSafetyPolicy",
    "deduplicate_chunks",
    "extract_readable_text",
    "rank_passages",
    "segment_document",
]
