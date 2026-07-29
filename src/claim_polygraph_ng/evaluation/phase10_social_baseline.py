"""Stage 10.0 reproducible social-evidence policy baseline."""

from __future__ import annotations

import hashlib
from pathlib import Path

from pydantic import Field, model_validator

from claim_polygraph_ng.domain.base import DomainModel


class Phase10ArtifactHash(DomainModel):
    artifact_id: str = Field(pattern=r"^[a-z0-9_]+$")
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Phase10ResourcePolicy(DomainModel):
    model_calls: int = 0
    search_calls: int = 0
    network_calls: int = 0
    pdf_downloads: int = 0


class Phase10BaselineObservation(DomainModel):
    concern: str
    current_behavior: str
    remediation_gap: str
    enforcement_point: str


class Phase10SocialUseRule(DomainModel):
    material_type: str
    allowed_uses: tuple[str, ...]
    independent_proof: bool
    required_controls: tuple[str, ...]


class Phase10CompatibilityRule(DomainModel):
    surface: str
    rule: str


class Phase10SocialBaselineManifest(DomainModel):
    manifest_id: str = "phase10-stage10.0-social-evidence-baseline-v1"
    schema_version: int = 1
    generated_from_existing_artifacts_only: bool = True
    default_orchestrator: str = "langgraph"
    authoritative_domain_service: str = "InvestigationService"
    rollback_path: str = "direct"
    adr_status: str = "proposed"
    resource_policy: Phase10ResourcePolicy = Phase10ResourcePolicy()
    observations: tuple[Phase10BaselineObservation, ...]
    policy_matrix: tuple[Phase10SocialUseRule, ...]
    non_negotiable_safeguards: tuple[str, ...]
    compatibility_rules: tuple[Phase10CompatibilityRule, ...]
    artifacts: tuple[Phase10ArtifactHash, ...]

    @model_validator(mode="after")
    def validate_manifest(self) -> Phase10SocialBaselineManifest:
        for values, label in (
            ((item.concern for item in self.observations), "observation concerns"),
            ((item.material_type for item in self.policy_matrix), "material types"),
            ((item.surface for item in self.compatibility_rules), "compatibility surfaces"),
            ((item.artifact_id for item in self.artifacts), "artifact IDs"),
            ((item.path for item in self.artifacts), "artifact paths"),
        ):
            materialized = tuple(values)
            if len(materialized) != len(set(materialized)):
                raise ValueError(f"{label} must be unique")
        if any(self.resource_policy.model_dump().values()):
            raise ValueError("Stage 10.0 must not consume external resources")
        if len(self.policy_matrix) < 8:
            raise ValueError("social-use policy matrix is incomplete")
        if len(self.non_negotiable_safeguards) < 6:
            raise ValueError("social-evidence safeguards are incomplete")
        return self


class Phase10BaselineVerification(DomainModel):
    valid: bool
    checked_artifact_count: int
    checked_policy_rule_count: int
    errors: tuple[str, ...]


_ARTIFACTS = (
    ("serpapi_adapter", "src/claim_polygraph_ng/providers/serpapi.py"),
    ("multi_agent_research", "src/claim_polygraph_ng/application/multi_agent_service.py"),
    ("independence_analysis", "src/claim_polygraph_ng/analysis/independence.py"),
    (
        "investigation_provenance",
        "src/claim_polygraph_ng/analysis/investigation_provenance.py",
    ),
    ("readiness", "src/claim_polygraph_ng/analysis/readiness.py"),
    ("retrieval_evaluation", "src/claim_polygraph_ng/evaluation/retrieval.py"),
    ("source_enums", "src/claim_polygraph_ng/domain/enums.py"),
    ("source_models", "src/claim_polygraph_ng/domain/models.py"),
    ("phase10_plan", "docs/PHASE_10_SOCIAL_MEDIA_EVIDENCE_GOVERNANCE_PLAN.md"),
    ("stage10_0_policy", "docs/PHASE_10_STAGE_10.0_BASELINE_AND_POLICY.md"),
    ("adr_0022", "docs/adr/0022-social-media-evidence-governance.md"),
    (
        "baseline_builder",
        "src/claim_polygraph_ng/evaluation/phase10_social_baseline.py",
    ),
)


_OBSERVATIONS = (
    Phase10BaselineObservation(
        concern="general_search_ingestion",
        current_behavior="SerpAPI emits general results as SourceType.OTHER.",
        remediation_gap="Distribution medium and authority are not separated.",
        enforcement_point="provider normalization",
    ),
    Phase10BaselineObservation(
        concern="evidence_creation",
        current_behavior="Relevant fetched passages can be persisted as evidence.",
        remediation_gap="No social-specific evidence-use eligibility decision exists.",
        enforcement_point="research consolidation",
    ),
    Phase10BaselineObservation(
        concern="independence",
        current_behavior="Family analysis uses host, publisher, duplicates and citations.",
        remediation_gap="Cross-platform copies can hide a shared origin.",
        enforcement_point="provenance and independence",
    ),
    Phase10BaselineObservation(
        concern="source_quality",
        current_behavior="Quality is explained from retained source metadata.",
        remediation_gap="Account authenticity, post type and author scope are absent.",
        enforcement_point="source-quality assessment",
    ),
    Phase10BaselineObservation(
        concern="readiness",
        current_behavior="Unknown source quality can contribute to review routing.",
        remediation_gap="No mandatory social-only decisive-evidence safeguard exists.",
        enforcement_point="readiness and publication",
    ),
    Phase10BaselineObservation(
        concern="evaluation_live_parity",
        current_behavior="Retrieval evaluation applies some low-quality host penalties.",
        remediation_gap="Evaluation heuristics do not enforce live evidence safety.",
        enforcement_point="authoritative workflow",
    ),
    Phase10BaselineObservation(
        concern="reporting",
        current_behavior="Reports expose sources, evidence, reasoning and review state.",
        remediation_gap="Approved social use and shared origin are not explicit.",
        enforcement_point="report and dashboard",
    ),
)


_POLICY_MATRIX = (
    Phase10SocialUseRule(
        material_type="unknown_individual_post",
        allowed_uses=("lead", "public_reaction_context"),
        independent_proof=False,
        required_controls=("resolve_identity", "resolve_origin", "corroborate"),
    ),
    Phase10SocialUseRule(
        material_type="authenticated_individual_statement",
        allowed_uses=("proof_statement_was_made",),
        independent_proof=False,
        required_controls=("authenticate_account", "limit_proposition_to_statement"),
    ),
    Phase10SocialUseRule(
        material_type="eyewitness_post",
        allowed_uses=("qualified_observation",),
        independent_proof=False,
        required_controls=("authenticate", "verify_time_place", "corroborate"),
    ),
    Phase10SocialUseRule(
        material_type="verified_institutional_account",
        allowed_uses=("first_party_statement_within_scope",),
        independent_proof=True,
        required_controls=("verify_account", "verify_scope", "prefer_official_record"),
    ),
    Phase10SocialUseRule(
        material_type="government_account",
        allowed_uses=("official_announcement_within_scope",),
        independent_proof=True,
        required_controls=("verify_account", "distinguish_controlling_instrument"),
    ),
    Phase10SocialUseRule(
        material_type="academic_institution_post",
        allowed_uses=("discovery", "first_party_announcement"),
        independent_proof=False,
        required_controls=("resolve_paper_or_data", "cite_underlying_source"),
    ),
    Phase10SocialUseRule(
        material_type="repost_quote_or_screenshot",
        allowed_uses=("lead",),
        independent_proof=False,
        required_controls=("find_original", "record_derivation", "authenticate"),
    ),
    Phase10SocialUseRule(
        material_type="post_linking_report",
        allowed_uses=("discovery", "context"),
        independent_proof=False,
        required_controls=("cite_underlying_report", "share_evidence_family"),
    ),
)


_SAFEGUARDS = (
    "Social platform is a distribution medium, not an authority classification.",
    "Models cannot override deterministic evidence-use eligibility.",
    "Cross-platform repetition with a shared origin is not independent corroboration.",
    "Social-only decisive evidence cannot yield a publishable supported verdict.",
    "Social-only decisive evidence cannot yield a publishable contradicted verdict.",
    "Social sources are retained with limitations rather than silently discarded.",
    "Unsafe provisional reports may be reviewed but publication remains blocked.",
)


_COMPATIBILITY = (
    Phase10CompatibilityRule(
        surface="persisted_source_type",
        rule="Existing SourceType values and SourceType.OTHER records remain readable.",
    ),
    Phase10CompatibilityRule(
        surface="new_social_fields",
        rule="Additive fields default to unknown or the safest non-decisive use.",
    ),
    Phase10CompatibilityRule(
        surface="historical_artifacts",
        rule="Evidence, reports, reviews, checkpoints and receipts are not rewritten.",
    ),
    Phase10CompatibilityRule(
        surface="checkpoint_reconstruction",
        rule="Versioned reconstruction preserves legacy state semantics.",
    ),
    Phase10CompatibilityRule(
        surface="rollback",
        rule="The direct authoritative workflow remains available throughout Phase 10.",
    ),
)


def build_phase10_social_baseline(
    project_root: str | Path,
) -> Phase10SocialBaselineManifest:
    root = Path(project_root).resolve()
    manifest = Phase10SocialBaselineManifest(
        observations=_OBSERVATIONS,
        policy_matrix=_POLICY_MATRIX,
        non_negotiable_safeguards=_SAFEGUARDS,
        compatibility_rules=_COMPATIBILITY,
        artifacts=tuple(
            Phase10ArtifactHash(
                artifact_id=artifact_id,
                path=path,
                sha256=_sha256(root / path),
            )
            for artifact_id, path in _ARTIFACTS
        ),
    )
    target = (
        root
        / "artifacts/evaluations/phase10-stage10.0-social-evidence-baseline-v1.json"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return manifest


def load_phase10_social_baseline(
    path: str | Path,
) -> Phase10SocialBaselineManifest:
    return Phase10SocialBaselineManifest.model_validate_json(
        Path(path).read_text(encoding="utf-8")
    )


def verify_phase10_social_baseline(
    manifest: Phase10SocialBaselineManifest,
    project_root: str | Path,
) -> Phase10BaselineVerification:
    root = Path(project_root).resolve()
    errors: list[str] = []
    checked = 0
    for artifact in manifest.artifacts:
        candidate = (root / artifact.path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            errors.append(f"{artifact.artifact_id}: path escapes project root")
            continue
        if not candidate.is_file():
            errors.append(f"{artifact.artifact_id}: file missing")
            continue
        checked += 1
        if _sha256(candidate) != artifact.sha256:
            errors.append(f"{artifact.artifact_id}: SHA-256 mismatch")

    expected_rules = {item.material_type: item for item in _POLICY_MATRIX}
    for rule in manifest.policy_matrix:
        if expected_rules.get(rule.material_type) != rule:
            errors.append(f"{rule.material_type}: policy rule mismatch")

    required_safeguards = set(_SAFEGUARDS)
    if not required_safeguards.issubset(manifest.non_negotiable_safeguards):
        errors.append("non-negotiable safeguards are incomplete")
    if manifest.resource_policy != Phase10ResourcePolicy():
        errors.append("Stage 10.0 resource policy is not zero-cost")

    return Phase10BaselineVerification(
        valid=not errors,
        checked_artifact_count=checked,
        checked_policy_rule_count=len(manifest.policy_matrix),
        errors=tuple(errors),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

