"""Bounded text extraction from untrusted PDF documents."""

from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from claim_polygraph_ng.retrieval.fetcher import FetchError
from claim_polygraph_ng.retrieval.models import PdfExtractionPolicy


class PdfExtractionError(FetchError):
    """Base class for controlled PDF extraction failures."""


class EncryptedPdfError(PdfExtractionError):
    """Encrypted PDFs are outside the supported extraction boundary."""


class PdfPageLimitError(PdfExtractionError):
    """A PDF contains more pages than the extraction policy permits."""


class PdfTextLimitError(PdfExtractionError):
    """Extracted PDF text exceeded the configured character limit."""


def extract_pdf_text(
    content: bytes,
    policy: PdfExtractionPolicy | None = None,
) -> str:
    """Extract page text while enforcing page and output-size limits."""
    active_policy = policy or PdfExtractionPolicy()
    if not content:
        raise PdfExtractionError("PDF content is empty")

    try:
        reader = PdfReader(BytesIO(content), strict=False)
        if reader.is_encrypted:
            raise EncryptedPdfError("encrypted PDFs are not supported")
        page_count = len(reader.pages)
        if page_count > active_policy.maximum_pages:
            raise PdfPageLimitError(
                f"PDF has {page_count} pages; limit is {active_policy.maximum_pages}"
            )

        parts: list[str] = []
        character_count = 0
        for page in reader.pages:
            page_text = page.extract_text() or ""
            character_count += len(page_text)
            if character_count > active_policy.maximum_extracted_characters:
                raise PdfTextLimitError("extracted PDF text exceeds configured character limit")
            if page_text.strip():
                parts.append(page_text)
    except PdfExtractionError:
        raise
    except (PdfReadError, OSError, ValueError) as error:
        raise PdfExtractionError(f"could not read PDF: {error}") from error

    return "\n\n".join(parts)
