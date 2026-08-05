"""Minimal deterministic extraction of readable text from fetched documents."""

import re
from html.parser import HTMLParser

from claim_polygraph_ng.retrieval.models import FetchedDocument, PdfExtractionPolicy
from claim_polygraph_ng.retrieval.pdf import extract_pdf_text


class _ReadableTextParser(HTMLParser):
    """Collect visible text while excluding active and non-content elements."""

    _IGNORED_TAGS = frozenset(
        {
            "script", "style", "noscript", "svg", "template",
            "nav", "footer", "aside", "header", "form", "button", "select", "option",
        }
    )
    _BLOCK_TAGS = frozenset(
        {
            "article",
            "aside",
            "blockquote",
            "br",
            "dd",
            "div",
            "dl",
            "dt",
            "figcaption",
            "figure",
            "footer",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "header",
            "li",
            "main",
            "nav",
            "ol",
            "p",
            "pre",
            "section",
            "table",
            "td",
            "th",
            "tr",
            "ul",
        }
    )

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored_depth = 0
        self.parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        del attrs
        lowered = tag.lower()
        if lowered in self._IGNORED_TAGS:
            self._ignored_depth += 1
        elif lowered in self._BLOCK_TAGS and not self._ignored_depth:
            self.parts.append("\n\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._IGNORED_TAGS and self._ignored_depth:
            self._ignored_depth -= 1
        elif tag.lower() in self._BLOCK_TAGS and not self._ignored_depth:
            self.parts.append("\n\n")

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self.parts.append(data)


def extract_readable_text(text: str, content_type: str) -> str:
    """Extract normalized visible text from supported response content."""
    if content_type == "text/plain":
        extracted = text
    else:
        parser = _ReadableTextParser()
        parser.feed(text)
        parser.close()
        extracted = "".join(parser.parts)

    paragraphs = [
        re.sub(r"\s+", " ", paragraph).strip()
        for paragraph in re.split(r"(?:\r?\n\s*){2,}", extracted)
    ]
    return "\n\n".join(
        paragraph for paragraph in paragraphs if paragraph and not _boilerplate_line(paragraph)
    )


def _boilerplate_line(value: str) -> bool:
    """Drop only short, unmistakable page controls; preserve substantive prose."""
    lowered = value.casefold().strip()
    if len(lowered) > 180:
        return False
    controls = {
        "skip to main content", "log in", "sign in", "subscribe", "menu",
        "privacy policy", "cookie policy", "contact us", "follow us", "share this",
        "previous", "next", "print", "printer-friendly",
    }
    return lowered in controls


def extract_document_text(
    document: FetchedDocument,
    pdf_policy: PdfExtractionPolicy | None = None,
) -> str:
    """Extract readable text according to the fetched document's media type."""
    if document.content_type == "application/pdf":
        if document.raw_content is None:
            raise ValueError("PDF document is missing raw content")
        extracted = extract_pdf_text(document.raw_content, pdf_policy)
        return extract_readable_text(extracted, "text/plain")
    return extract_readable_text(document.text, document.content_type)
