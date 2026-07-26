"""Minimal deterministic extraction of readable text from fetched documents."""

import re
from html.parser import HTMLParser


class _ReadableTextParser(HTMLParser):
    """Collect visible text while excluding active and non-content elements."""

    _IGNORED_TAGS = frozenset({"script", "style", "noscript", "svg", "template"})
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
        if tag.lower() in self._IGNORED_TAGS:
            self._ignored_depth += 1
        elif tag.lower() in self._BLOCK_TAGS and not self._ignored_depth:
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
    return "\n\n".join(paragraph for paragraph in paragraphs if paragraph)
