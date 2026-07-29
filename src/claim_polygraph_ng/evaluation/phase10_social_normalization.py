"""Stage 10.2 deterministic social URL normalization gate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import Field

from claim_polygraph_ng.analysis.social_urls import classify_social_url
from claim_polygraph_ng.domain.base import DomainModel


class Phase10NormalizationArtifact(DomainModel):
    artifact_id: str
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Phase10NormalizationAudit(DomainModel):
    audit_id: str = "phase10-stage10.2-social-normalization-gate-audit-v1"
    fixture_id: str
    fixture_version: int
    case_count: int
    exact_match_count: int
    social_case_count: int
    non_social_case_count: int
    platform_count: int
    unknown_social_path_count: int
    model_calls: int = 0
    search_calls: int = 0
    social_page_fetches: int = 0
    valid: bool
    errors: tuple[str, ...]
    artifacts: tuple[Phase10NormalizationArtifact, ...]


_ARTIFACTS = (
    ("fixtures", "benchmarks/phase10_social_url_fixtures_v1.json"),
    ("normalizer", "src/claim_polygraph_ng/analysis/social_urls.py"),
    ("candidate_contract", "src/claim_polygraph_ng/domain/social.py"),
    ("serpapi_adapter", "src/claim_polygraph_ng/providers/serpapi.py"),
    ("searxng_adapter", "src/claim_polygraph_ng/providers/searxng.py"),
)


def build_phase10_social_normalization_audit(
    project_root: str | Path,
) -> Phase10NormalizationAudit:
    root = Path(project_root).resolve()
    fixture = json.loads(
        (root / "benchmarks/phase10_social_url_fixtures_v1.json").read_text("utf-8")
    )
    errors: list[str] = []
    exact = 0
    social = 0
    non_social = 0
    platforms: set[str] = set()
    unknown_social = 0
    for case in fixture["cases"]:
        result = classify_social_url(case["input_url"])
        expected_platform = case["platform"]
        if expected_platform is None:
            non_social += 1
            if result is None:
                exact += 1
            else:
                errors.append(f"{case['case_id']}: false social classification")
            continue
        social += 1
        platforms.add(expected_platform)
        if case["url_kind"] == "unknown":
            unknown_social += 1
        actual = (
            None
            if result is None
            else {
                "platform": result.platform.value,
                "url_kind": result.url_kind.value,
                "canonical_url": str(result.canonical_url),
                "account_handle": result.account_handle,
                "platform_post_id": result.platform_post_id,
            }
        )
        expected = {
            key: case[key]
            for key in (
                "platform",
                "url_kind",
                "canonical_url",
                "account_handle",
                "platform_post_id",
            )
        }
        if actual == expected:
            exact += 1
        else:
            errors.append(f"{case['case_id']}: normalization mismatch")

    if fixture.get("network_calls_permitted") != 0:
        errors.append("fixture permits network calls")
    return Phase10NormalizationAudit(
        fixture_id=fixture["fixture_id"],
        fixture_version=fixture["version"],
        case_count=len(fixture["cases"]),
        exact_match_count=exact,
        social_case_count=social,
        non_social_case_count=non_social,
        platform_count=len(platforms),
        unknown_social_path_count=unknown_social,
        valid=not errors and exact == len(fixture["cases"]),
        errors=tuple(errors),
        artifacts=tuple(
            Phase10NormalizationArtifact(
                artifact_id=artifact_id,
                path=path,
                sha256=_sha256(root / path),
            )
            for artifact_id, path in _ARTIFACTS
        ),
    )


def export_phase10_social_normalization_audit(
    project_root: str | Path,
) -> Phase10NormalizationAudit:
    root = Path(project_root).resolve()
    audit = build_phase10_social_normalization_audit(root)
    target = (
        root
        / "artifacts/evaluations/"
        "phase10-stage10.2-social-normalization-gate-audit-v1.json"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(audit.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return audit


def verify_phase10_social_normalization_audit(
    audit: Phase10NormalizationAudit,
    project_root: str | Path,
) -> tuple[str, ...]:
    root = Path(project_root).resolve()
    errors = list(audit.errors)
    if not audit.valid or audit.exact_match_count != audit.case_count:
        errors.append("normalization fixture gate is not complete")
    if audit.model_calls or audit.search_calls or audit.social_page_fetches:
        errors.append("normalization gate performed an external operation")
    for artifact in audit.artifacts:
        path = (root / artifact.path).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            errors.append(f"{artifact.artifact_id}: path escapes project root")
            continue
        if not path.is_file():
            errors.append(f"{artifact.artifact_id}: file missing")
        elif _sha256(path) != artifact.sha256:
            errors.append(f"{artifact.artifact_id}: SHA-256 mismatch")
    return tuple(dict.fromkeys(errors))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

