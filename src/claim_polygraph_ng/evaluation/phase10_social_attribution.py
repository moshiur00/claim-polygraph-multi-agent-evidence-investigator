"""Stage 10.3 authenticity and attribution safety gate."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from pydantic import Field

from claim_polygraph_ng.domain import (
    SocialCaptureMethod,
    SocialSourceContext,
    evaluate_social_evidence_eligibility,
)
from claim_polygraph_ng.domain.base import DomainModel


class Phase10AttributionArtifact(DomainModel):
    artifact_id: str
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Phase10AttributionAudit(DomainModel):
    audit_id: str = "phase10-stage10.3-authenticity-attribution-gate-audit-v1"
    fixture_id: str
    case_count: int
    exact_match_count: int
    decision_counts: dict[str, int]
    copied_material_case_count: int
    unavailable_case_count: int
    verified_archive_case_count: int
    decisive_permission_count: int
    model_calls: int = 0
    search_calls: int = 0
    social_page_fetches: int = 0
    valid: bool
    errors: tuple[str, ...]
    artifacts: tuple[Phase10AttributionArtifact, ...]


_ARTIFACTS = (
    ("fixtures", "benchmarks/phase10_social_attribution_fixtures_v1.json"),
    ("contracts", "src/claim_polygraph_ng/domain/social.py"),
    ("attribution", "src/claim_polygraph_ng/analysis/social_attribution.py"),
    ("authoritative_service", "src/claim_polygraph_ng/application/investigation_service.py"),
    ("multi_agent_service", "src/claim_polygraph_ng/application/multi_agent_service.py"),
    ("shared_operations", "src/claim_polygraph_ng/application/research_executor.py"),
)


def build_phase10_social_attribution_audit(
    project_root: str | Path,
) -> Phase10AttributionAudit:
    root = Path(project_root).resolve()
    fixture = json.loads(
        (root / "benchmarks/phase10_social_attribution_fixtures_v1.json").read_text(
            "utf-8"
        )
    )
    errors: list[str] = []
    exact = 0
    decisions: Counter[str] = Counter()
    copied = 0
    unavailable = 0
    verified_archives = 0
    decisive = 0
    for case in fixture["cases"]:
        context = SocialSourceContext.model_validate(case["context"])
        result = evaluate_social_evidence_eligibility(context)
        decisions[result.decision.value] += 1
        copied += context.capture_method in {
            SocialCaptureMethod.SCREENSHOT,
            SocialCaptureMethod.COPIED_TEXT,
        }
        unavailable += context.unavailable_or_deleted
        verified_archives += bool(
            context.archive_reference
            and context.archive_reference.reliability_verified
        )
        decisive += result.decisive_use_allowed
        expected = (
            case["decision"],
            tuple(case["allowed_uses"]),
            case["requires_human_review"],
        )
        actual = (
            result.decision.value,
            tuple(item.value for item in result.allowed_uses),
            result.requires_human_review,
        )
        if actual == expected:
            exact += 1
        else:
            errors.append(f"{case['case_id']}: attribution policy mismatch")
    if fixture.get("network_calls_permitted") != 0:
        errors.append("fixture permits network calls")
    if decisive:
        errors.append("Stage 10.3 granted decisive social evidence permission")
    return Phase10AttributionAudit(
        fixture_id=fixture["fixture_id"],
        case_count=len(fixture["cases"]),
        exact_match_count=exact,
        decision_counts=dict(sorted(decisions.items())),
        copied_material_case_count=copied,
        unavailable_case_count=unavailable,
        verified_archive_case_count=verified_archives,
        decisive_permission_count=decisive,
        valid=not errors and exact == len(fixture["cases"]),
        errors=tuple(errors),
        artifacts=tuple(
            Phase10AttributionArtifact(
                artifact_id=artifact_id,
                path=path,
                sha256=_sha256(root / path),
            )
            for artifact_id, path in _ARTIFACTS
        ),
    )


def export_phase10_social_attribution_audit(
    project_root: str | Path,
) -> Phase10AttributionAudit:
    root = Path(project_root).resolve()
    audit = build_phase10_social_attribution_audit(root)
    target = (
        root
        / "artifacts/evaluations/"
        "phase10-stage10.3-authenticity-attribution-gate-audit-v1.json"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(audit.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return audit


def verify_phase10_social_attribution_audit(
    audit: Phase10AttributionAudit,
    project_root: str | Path,
) -> tuple[str, ...]:
    root = Path(project_root).resolve()
    errors = list(audit.errors)
    if not audit.valid or audit.exact_match_count != audit.case_count:
        errors.append("attribution fixture gate is incomplete")
    if (
        audit.model_calls
        or audit.search_calls
        or audit.social_page_fetches
        or audit.decisive_permission_count
    ):
        errors.append("attribution safety resource or permission gate failed")
    for artifact in audit.artifacts:
        candidate = (root / artifact.path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            errors.append(f"{artifact.artifact_id}: path escapes project root")
            continue
        if not candidate.is_file():
            errors.append(f"{artifact.artifact_id}: file missing")
        elif _sha256(candidate) != artifact.sha256:
            errors.append(f"{artifact.artifact_id}: SHA-256 mismatch")
    return tuple(dict.fromkeys(errors))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

