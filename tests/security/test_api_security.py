"""Security-boundary checks for the Stage 7 API."""

import asyncio

import httpx

from claim_polygraph_ng.api import ApiDependencies, create_app
from claim_polygraph_ng.application.claim_extraction import ClaimExtractionService
from claim_polygraph_ng.domain.investigation import InvestigationReport
from claim_polygraph_ng.persistence import (
    SQLiteInvestigationRepository,
    SQLiteReviewLedger,
)
from claim_polygraph_ng.retrieval import SafeHttpFetcher


async def _call(app, method: str, path: str, **kwargs):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://security"
    ) as client:
        return await client.request(method, path, **kwargs)


def _app(tmp_path):
    async def fail(_claim: str) -> InvestigationReport:
        raise RuntimeError("provider-token=super-secret")

    return create_app(
        ApiDependencies(
            investigations=SQLiteInvestigationRepository(tmp_path / "investigations.db"),
            reviews=SQLiteReviewLedger(tmp_path / "reviews.db"),
            graph_checkpoint_path=tmp_path / "graph.db",
            investigate=fail,
            extract_claims=ClaimExtractionService(SafeHttpFetcher().fetch).extract,
        )
    )


def test_provider_failure_does_not_leak_exception_or_secret(tmp_path) -> None:
    response = asyncio.run(
        _call(
            _app(tmp_path),
            "POST",
            "/api/investigations",
            json={"claim": "A provider failure security fixture."},
        )
    )

    body = response.text
    assert response.status_code == 502
    assert "super-secret" not in body
    assert "provider-token" not in body
    assert "Traceback" not in body
    assert response.json()["detail"] == "investigation provider failed: RuntimeError"


def test_cors_allows_declared_dashboard_but_not_arbitrary_origin(tmp_path) -> None:
    app = _app(tmp_path)
    trusted = asyncio.run(
        _call(
            app,
            "OPTIONS",
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
    )
    untrusted = asyncio.run(
        _call(
            app,
            "OPTIONS",
            "/health",
            headers={
                "Origin": "https://attacker.example",
                "Access-Control-Request-Method": "GET",
            },
        )
    )

    assert trusted.status_code == 200
    assert trusted.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-origin" not in untrusted.headers
    assert trusted.headers["access-control-allow-origin"] != "*"


def test_public_url_claim_extraction_rejects_loopback_without_fetching(tmp_path) -> None:
    response = asyncio.run(
        _call(
            _app(tmp_path),
            "POST",
            "/api/claim-inputs/extract",
            json={"kind": "public_url", "url": "http://127.0.0.1/private"},
        )
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "claim extraction failed: UnsafeUrlError"
