"""Minimal deterministic extraction of readable text from fetched documents."""

import re
from html.parser import HTMLParser


class _ReadableTextParser(HTMLParser):
    """Collect visible text while excluding active and non-content elements."""

    _IGNORED_TAGS = frozenset({"script", "style", "noscript", "svg", "template"})

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

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._IGNORED_TAGS and self._ignored_depth:
            self._ignored_depth -= 1

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
        extracted = " ".join(parser.parts)
    return re.sub(r"\s+", " ", extracted).strip()
