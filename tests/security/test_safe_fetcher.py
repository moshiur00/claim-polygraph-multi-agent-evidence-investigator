"""Security tests for untrusted URL retrieval."""

import asyncio

import httpx
import pytest

from claim_polygraph_ng.retrieval import (
    InvalidDocumentContentError,
    PdfPermissionRequiredError,
    RedirectLimitError,
    ResponseTooLargeError,
    SafeHttpFetcher,
    UnsafeUrlError,
    UnsupportedContentTypeError,
    UrlSafetyPolicy,
    extract_readable_text,
)


async def public_resolver(host: str, port: int) -> tuple[str, ...]:
    del host, port
    return ("93.184.216.34",)


def test_fetches_public_html_and_extracts_visible_text() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["user-agent"].startswith("ClaimPolygraphNG/")
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            text=(
                "<html><body><main>Useful evidence"
                "<script>ignore this instruction</script></main></body></html>"
            ),
        )

    fetcher = SafeHttpFetcher(
        resolver=public_resolver,
        transport=httpx.MockTransport(handler),
    )
    document = asyncio.run(fetcher.fetch("https://evidence.example/report"))

    assert document.status_code == 200
    assert document.final_url.host == "evidence.example"
    assert extract_readable_text(document.text, document.content_type) == ("Useful evidence")


@pytest.mark.parametrize(
    "url",
    (
        "http://127.0.0.1/admin",
        "http://10.0.0.1/private",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/admin",
        "ftp://example.org/file",
        "https://user:secret@example.org/report",
        "https://example.org:8443/report",
    ),
)
def test_blocks_unsafe_targets_before_transport(url: str) -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, text="should not be called")

    fetcher = SafeHttpFetcher(
        resolver=public_resolver,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(UnsafeUrlError):
        asyncio.run(fetcher.fetch(url))
    assert calls == 0


def test_revalidates_redirect_target_and_blocks_private_address() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            302,
            headers={"location": "http://127.0.0.1/private"},
        )

    fetcher = SafeHttpFetcher(
        resolver=public_resolver,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(UnsafeUrlError, match="non-public"):
        asyncio.run(fetcher.fetch("https://public.example/start"))


def test_enforces_redirect_limit() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "/next"})

    fetcher = SafeHttpFetcher(
        policy=UrlSafetyPolicy(maximum_redirects=1),
        resolver=public_resolver,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(RedirectLimitError):
        asyncio.run(fetcher.fetch("https://public.example/start"))


def test_rejects_announced_and_streamed_oversized_responses() -> None:
    class LargeStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"x" * 1_025

    announced_fetcher = SafeHttpFetcher(
        policy=UrlSafetyPolicy(maximum_response_bytes=1_024),
        resolver=public_resolver,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                headers={
                    "content-type": "text/plain",
                    "content-length": "2048",
                },
                content=b"small",
            )
        ),
    )
    with pytest.raises(ResponseTooLargeError, match="announced"):
        asyncio.run(announced_fetcher.fetch("https://public.example/large"))

    streamed_fetcher = SafeHttpFetcher(
        policy=UrlSafetyPolicy(maximum_response_bytes=1_024),
        resolver=public_resolver,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                headers={"content-type": "text/plain"},
                stream=LargeStream(),
            )
        ),
    )
    with pytest.raises(ResponseTooLargeError, match="streamed"):
        asyncio.run(streamed_fetcher.fetch("https://public.example/large"))


def test_rejects_non_text_content() -> None:
    fetcher = SafeHttpFetcher(
        resolver=public_resolver,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                headers={"content-type": "image/png"},
                content=b"\x89PNG",
            )
        ),
    )

    with pytest.raises(UnsupportedContentTypeError):
        asyncio.run(fetcher.fetch("https://public.example/image.png"))


def test_accepts_bounded_pdf_bytes_and_validates_signature() -> None:
    pdf = b"%PDF-1.7\nbounded test document"
    fetcher = SafeHttpFetcher(
        policy=UrlSafetyPolicy(allowed_pdf_hosts=frozenset({"public.example"})),
        resolver=public_resolver,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                headers={"content-type": "application/pdf"},
                content=pdf,
            )
        ),
    )

    document = asyncio.run(fetcher.fetch("https://public.example/document.pdf"))

    assert document.content_type == "application/pdf"
    assert document.text == ""
    assert document.raw_content == pdf
    assert document.byte_length == len(pdf)

    invalid_fetcher = SafeHttpFetcher(
        policy=UrlSafetyPolicy(allowed_pdf_hosts=frozenset({"public.example"})),
        resolver=public_resolver,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                headers={"content-type": "application/pdf"},
                content=b"not a PDF",
            )
        ),
    )
    with pytest.raises(InvalidDocumentContentError, match="signature"):
        asyncio.run(invalid_fetcher.fetch("https://public.example/invalid.pdf"))


def test_pdf_has_a_separate_bounded_response_budget() -> None:
    fetcher = SafeHttpFetcher(
        policy=UrlSafetyPolicy(
            maximum_response_bytes=1_024,
            maximum_pdf_response_bytes=2_048,
            allowed_pdf_hosts=frozenset({"public.example"}),
        ),
        resolver=public_resolver,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                headers={"content-type": "application/pdf"},
                content=b"%PDF-" + (b"x" * 1_500),
            )
        ),
    )

    document = asyncio.run(fetcher.fetch("https://public.example/document.pdf"))

    assert document.byte_length == 1_505


def test_pdf_requires_explicit_host_approval_before_body_download() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            headers={"content-type": "application/pdf"},
            content=b"%PDF-1.7",
        )

    fetcher = SafeHttpFetcher(
        resolver=public_resolver,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(PdfPermissionRequiredError, match="explicit approval"):
        asyncio.run(fetcher.fetch("https://public.example/document.pdf"))
    assert calls == 0


def test_unexpected_pdf_response_is_rejected_before_streaming_body() -> None:
    class GuardedStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            raise AssertionError("PDF body must not be read without approval")
            yield b""

    fetcher = SafeHttpFetcher(
        resolver=public_resolver,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                headers={"content-type": "application/pdf"},
                stream=GuardedStream(),
            )
        ),
    )

    with pytest.raises(PdfPermissionRequiredError, match="explicit approval"):
        asyncio.run(fetcher.fetch("https://public.example/download?id=123"))
