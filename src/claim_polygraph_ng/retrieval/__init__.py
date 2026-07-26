"""Safe document retrieval and text extraction."""

from claim_polygraph_ng.retrieval.fetcher import (
    ContentFetcher,
    FetchError,
    HttpStatusError,
    InvalidDocumentContentError,
    NetworkFetchError,
    PdfPermissionRequiredError,
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
    PdfExtractionPolicy,
    RankedPassage,
    UrlSafetyPolicy,
)
from claim_polygraph_ng.retrieval.passages import (
    deduplicate_chunks,
    rank_passages,
    segment_document,
)
from claim_polygraph_ng.retrieval.pdf import (
    EncryptedPdfError,
    PdfExtractionError,
    PdfPageLimitError,
    PdfTextLimitError,
    extract_pdf_text,
)
from claim_polygraph_ng.retrieval.text import extract_document_text, extract_readable_text

__all__ = [
    "ChunkingPolicy",
    "ContentFetcher",
    "DocumentChunk",
    "EncryptedPdfError",
    "FetchError",
    "FetchedDocument",
    "HttpStatusError",
    "InvalidDocumentContentError",
    "NetworkFetchError",
    "PdfExtractionError",
    "PdfExtractionPolicy",
    "PdfPageLimitError",
    "PdfPermissionRequiredError",
    "PdfTextLimitError",
    "RankedPassage",
    "RedirectLimitError",
    "ResponseTooLargeError",
    "SafeHttpFetcher",
    "SystemHostResolver",
    "UnsafeUrlError",
    "UnsupportedContentTypeError",
    "UrlSafetyPolicy",
    "deduplicate_chunks",
    "extract_document_text",
    "extract_pdf_text",
    "extract_readable_text",
    "rank_passages",
    "segment_document",
]
