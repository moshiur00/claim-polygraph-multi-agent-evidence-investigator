"""Tests for bounded PDF text extraction."""

from types import SimpleNamespace

import pytest
from pypdf import PdfWriter

from claim_polygraph_ng.retrieval import (
    EncryptedPdfError,
    FetchedDocument,
    PdfExtractionError,
    PdfExtractionPolicy,
    PdfPageLimitError,
    PdfTextLimitError,
    extract_document_text,
    extract_pdf_text,
)


def _pdf_document(content: bytes) -> FetchedDocument:
    return FetchedDocument(
        requested_url="https://evidence.example/document.pdf",
        final_url="https://evidence.example/document.pdf",
        status_code=200,
        content_type="application/pdf",
        text="",
        raw_content=content,
        byte_length=len(content),
    )


def test_extracts_an_actual_blank_pdf_without_executing_content(tmp_path) -> None:
    path = tmp_path / "blank.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with path.open("wb") as stream:
        writer.write(stream)

    assert extract_document_text(_pdf_document(path.read_bytes())) == ""


def test_normalizes_extracted_pdf_page_text(monkeypatch) -> None:
    class Page:
        def __init__(self, text):
            self.text = text

        def extract_text(self):
            return self.text

    reader = SimpleNamespace(
        is_encrypted=False,
        pages=[Page("First  page\n\nwith evidence"), Page("Second page")],
    )
    monkeypatch.setattr(
        "claim_polygraph_ng.retrieval.pdf.PdfReader",
        lambda stream, strict: reader,
    )

    document = _pdf_document(b"%PDF-fake")

    assert extract_document_text(document) == ("First page\n\nwith evidence\n\nSecond page")


def test_rejects_encrypted_oversized_and_invalid_pdfs(monkeypatch) -> None:
    monkeypatch.setattr(
        "claim_polygraph_ng.retrieval.pdf.PdfReader",
        lambda stream, strict: SimpleNamespace(is_encrypted=True, pages=[]),
    )
    with pytest.raises(EncryptedPdfError):
        extract_pdf_text(b"%PDF-encrypted")

    monkeypatch.setattr(
        "claim_polygraph_ng.retrieval.pdf.PdfReader",
        lambda stream, strict: SimpleNamespace(
            is_encrypted=False,
            pages=[SimpleNamespace(extract_text=lambda: "")] * 2,
        ),
    )
    with pytest.raises(PdfPageLimitError):
        extract_pdf_text(
            b"%PDF-pages",
            PdfExtractionPolicy(maximum_pages=1),
        )

    monkeypatch.setattr(
        "claim_polygraph_ng.retrieval.pdf.PdfReader",
        lambda stream, strict: SimpleNamespace(
            is_encrypted=False,
            pages=[SimpleNamespace(extract_text=lambda: "x" * 1_001)],
        ),
    )
    with pytest.raises(PdfTextLimitError):
        extract_pdf_text(
            b"%PDF-text",
            PdfExtractionPolicy(maximum_extracted_characters=1_000),
        )

    with pytest.raises(PdfExtractionError, match="empty"):
        extract_pdf_text(b"")


def test_document_extraction_requires_pdf_bytes() -> None:
    document = FetchedDocument(
        requested_url="https://evidence.example/document.pdf",
        final_url="https://evidence.example/document.pdf",
        status_code=200,
        content_type="application/pdf",
        text="",
        byte_length=0,
    )

    with pytest.raises(ValueError, match="raw content"):
        extract_document_text(document)
