"""Security tests for untrusted URL retrieval."""

import asyncio

import httpx
import pytest

from claim_polygraph_ng.retrieval import (
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
                headers={"content-type": "application/pdf"},
                content=b"%PDF",
            )
        ),
    )

    with pytest.raises(UnsupportedContentTypeError):
        asyncio.run(fetcher.fetch("https://public.example/document.pdf"))
