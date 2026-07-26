"""SSRF-aware HTTP retrieval with bounded redirects and response sizes."""

import asyncio
import ipaddress
import socket
import ssl
from collections.abc import Awaitable, Callable
from typing import Protocol

import httpx
import truststore

from claim_polygraph_ng.retrieval.models import FetchedDocument, UrlSafetyPolicy

AddressResolver = Callable[[str, int], Awaitable[tuple[str, ...]]]


class FetchError(RuntimeError):
    """Base class for controlled retrieval failures."""


class UnsafeUrlError(FetchError):
    """The target violates network-safety policy."""


class RedirectLimitError(FetchError):
    """The response exceeded the configured redirect budget."""


class ResponseTooLargeError(FetchError):
    """The response exceeded the configured byte limit."""


class UnsupportedContentTypeError(FetchError):
    """The response is not an allowed textual document."""


class HttpStatusError(FetchError):
    """The remote server returned a non-success status."""


class NetworkFetchError(FetchError):
    """The HTTP client could not complete the request."""


class ContentFetcher(Protocol):
    """Fetch textual content for one public result URL."""

    provider_id: str

    async def fetch(self, url: str) -> FetchedDocument: ...


class SystemHostResolver:
    """Resolve all addresses for a hostname using the running event loop."""

    async def __call__(self, host: str, port: int) -> tuple[str, ...]:
        loop = asyncio.get_running_loop()
        records = await loop.getaddrinfo(
            host,
            port,
            type=socket.SOCK_STREAM,
        )
        return tuple(sorted({record[4][0] for record in records}))


class SafeHttpFetcher:
    """Fetch public text while validating the initial URL and every redirect."""

    provider_id = "safe-http-fetcher"
    _REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})

    def __init__(
        self,
        *,
        policy: UrlSafetyPolicy | None = None,
        resolver: AddressResolver | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        ssl_context: ssl.SSLContext | None = None,
    ) -> None:
        self._policy = policy or UrlSafetyPolicy()
        self._resolver = resolver or SystemHostResolver()
        self._transport = transport
        self._ssl_context = ssl_context or truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    async def fetch(self, url: str) -> FetchedDocument:
        """Fetch a URL after enforcing policy at every hop."""
        requested_url = httpx.URL(url)
        current_url = requested_url
        redirects: list[str] = []
        timeout = httpx.Timeout(self._policy.timeout_seconds)

        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=False,
                transport=self._transport,
                trust_env=False,
                verify=self._ssl_context,
            ) as client:
                for redirect_number in range(self._policy.maximum_redirects + 1):
                    await self._validate_target(current_url)
                    async with client.stream(
                        "GET",
                        current_url,
                        headers={
                            "Accept": "text/html, application/xhtml+xml, text/plain",
                            "User-Agent": self._policy.user_agent,
                        },
                    ) as response:
                        if response.status_code in self._REDIRECT_STATUSES:
                            location = response.headers.get("location")
                            if not location:
                                raise HttpStatusError(
                                    f"redirect {response.status_code} has no location"
                                )
                            if redirect_number >= self._policy.maximum_redirects:
                                raise RedirectLimitError("maximum redirect count exceeded")
                            redirects.append(str(current_url))
                            current_url = current_url.join(location)
                            continue

                        if not 200 <= response.status_code < 300:
                            raise HttpStatusError(
                                f"unexpected HTTP status {response.status_code} for {current_url}"
                            )

                        content_type = self._validate_content_type(response)
                        content = await self._read_bounded(response)
                        encoding = response.encoding or "utf-8"
                        text = content.decode(encoding, errors="replace")
                        return FetchedDocument(
                            requested_url=str(requested_url),
                            final_url=str(current_url),
                            status_code=response.status_code,
                            content_type=content_type,
                            text=text,
                            byte_length=len(content),
                            redirect_chain=tuple(redirects),
                        )
        except FetchError:
            raise
        except (httpx.HTTPError, UnicodeError, ValueError) as error:
            raise NetworkFetchError(str(error)) from error

        raise NetworkFetchError("request ended without a response")

    async def _validate_target(self, url: httpx.URL) -> None:
        if url.scheme not in self._policy.allowed_schemes:
            raise UnsafeUrlError(f"URL scheme is not allowed: {url.scheme}")
        if not url.host:
            raise UnsafeUrlError("URL must contain a hostname")
        if url.username or url.password:
            raise UnsafeUrlError("URL credentials are not allowed")

        port = url.port or (443 if url.scheme == "https" else 80)
        if port not in self._policy.allowed_ports:
            raise UnsafeUrlError(f"URL port is not allowed: {port}")

        try:
            literal_address = ipaddress.ip_address(url.host)
        except ValueError:
            try:
                resolved = await self._resolver(url.host, port)
            except OSError as error:
                raise NetworkFetchError(f"DNS resolution failed: {error}") from error
            if not resolved:
                raise NetworkFetchError("DNS resolution returned no addresses") from None
            addresses = tuple(ipaddress.ip_address(value) for value in resolved)
        else:
            addresses = (literal_address,)

        blocked = tuple(str(address) for address in addresses if not address.is_global)
        if blocked:
            raise UnsafeUrlError("URL resolves to a non-public address: " + ", ".join(blocked))

    def _validate_content_type(self, response: httpx.Response) -> str:
        raw_content_type = response.headers.get("content-type", "")
        content_type = raw_content_type.split(";", maxsplit=1)[0].strip().lower()
        if content_type not in self._policy.allowed_content_types:
            raise UnsupportedContentTypeError(
                f"content type is not allowed: {content_type or 'missing'}"
            )

        content_length = response.headers.get("content-length")
        if content_length:
            try:
                announced_size = int(content_length)
            except ValueError:
                announced_size = 0
            if announced_size > self._policy.maximum_response_bytes:
                raise ResponseTooLargeError("announced response size exceeds configured limit")
        return content_type

    async def _read_bounded(self, response: httpx.Response) -> bytes:
        chunks: list[bytes] = []
        total = 0
        async for chunk in response.aiter_bytes():
            total += len(chunk)
            if total > self._policy.maximum_response_bytes:
                raise ResponseTooLargeError("streamed response size exceeds configured limit")
            chunks.append(chunk)
        return b"".join(chunks)
