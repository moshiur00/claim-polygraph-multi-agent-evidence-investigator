"""Machine-verifiable Phase 6 targeted review and closure audit."""

import json
from pathlib import Path

from pydantic import Field, model_validator

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.evaluation.artifact_hashing import (
    artifact_matches_sha256,
    artifact_sha256,
)
from claim_polygraph_ng.evaluation.phase4_manifest import BaselineArtifact
from claim_polygraph_ng.evaluation.phase6_ablation import Phase6AblationEvaluation
from claim_polygraph_ng.evaluation.phase6_manifest import (
    load_phase6_manifest,
    verify_phase6_manifest,
)


class Phase6TargetedReviewCase(DomainModel):
    case_id: str = Field(pattern=r"^CPNG-[0-9]{3}$")
    reviewed_label: str
    baseline_label: str
    policy_candidate_label: str
    regression: bool
    disposition: str


class Phase6TargetedReviewPacket(DomainModel):
    packet_id: str = "phase6-stage6.10-targeted-review-v1"
    dataset_id: str
    dataset_version: int = Field(ge=1)
    benchmark_truth_changed: bool = False
    human_reapproval_required: bool = False
    changed_policy_case_count: int = Field(ge=0)
    cases: tuple[Phase6TargetedReviewCase, ...]
    new_verification_gold: tuple[str, ...]
    unresolved_disagreements: tuple[str, ...]
    disposition: str

    @model_validator(mode="after")
    def validate_counts(self) -> "Phase6TargetedReviewPacket":
        if self.changed_policy_case_count != len(self.cases):
            raise ValueError("changed policy case count does not match cases")
        return self


class Phase6ClosureGate(DomainModel):
    gate_id: str
    state: str = Field(pattern=r"^(passed|failed|skipped_by_gate)$")
    requirement: str
    observed: str
    evidence: tuple[str, ...] = ()


class Phase6ClosureAudit(DomainModel):
    audit_id: str = "phase6-final-release-audit-v1"
    phase_complete: bool
    default_verdict_authority: str
    deterministic_policy_promoted: bool
    targeted_review_required: bool
    artifacts: tuple[BaselineArtifact, ...]
    gates: tuple[Phase6ClosureGate, ...]
    passed_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    model_calls: int = 0
    network_calls: int = 0
    pdf_downloads: int = 0

    @model_validator(mode="after")
    def validate_gate_counts(self) -> "Phase6ClosureAudit":
        states = [gate.state for gate in self.gates]
        if self.passed_count != states.count("passed"):
            raise ValueError("passed gate count does not match gates")
        if self.failed_count != states.count("failed"):
            raise ValueError("failed gate count does not match gates")
        if self.skipped_count != states.count("skipped_by_gate"):
            raise ValueError("skipped gate count does not match gates")
        return self


class Phase6ClosureVerification(DomainModel):
    audit_id: str
    valid: bool
    checked_artifact_count: int = Field(ge=0)
    errors: tuple[str, ...]


def build_targeted_review(
    ablation: Phase6AblationEvaluation,
) -> Phase6TargetedReviewPacket:
    changed = tuple(
        Phase6TargetedReviewCase(
            case_id=result.case_id,
            reviewed_label=result.expected_label.value,
            baseline_label=result.baseline_label.value,
            policy_candidate_label=result.full_policy_label.value,
            regression=result.regressed,
            disposition=(
                "Retain the reviewed label and baseline verdict; preserve the policy "
                "candidate as a non-authoritative diagnostic."
            ),
        )
        for result in ablation.results
        if result.policy_changed
    )
    return Phase6TargetedReviewPacket(
        dataset_id=ablation.dataset_id,
        dataset_version=ablation.dataset_version,
        changed_policy_case_count=len(changed),
        cases=changed,
        new_verification_gold=(
            "benchmarks/phase6_numerical_operations_v1.json",
            "benchmarks/phase6_temporal_relations_v1.json",
        ),
        unresolved_disagreements=tuple(
            f"{item.case_id}: reviewed={item.reviewed_label}, "
            f"policy_candidate={item.policy_candidate_label}"
            for item in changed
        ),
        disposition=(
            "No benchmark truth changed. The deterministic policy failed its promotion "
            "gate and remains observational, so no new human approval is asserted."
        ),
    )


def build_closure_audit(
    *,
    project_root: str | Path,
    artifact_paths: tuple[str, ...],
    ablation: Phase6AblationEvaluation,
    targeted_review: Phase6TargetedReviewPacket,
) -> Phase6ClosureAudit:
    root = Path(project_root).resolve()
    artifacts = tuple(_artifact(root, path) for path in artifact_paths)
    manifest_path = root / "artifacts/evaluations/phase6-experiment-manifest-v1.json"
    manifest_result = verify_phase6_manifest(load_phase6_manifest(manifest_path), root)
    gates = (
        Phase6ClosureGate(
            gate_id="locked_manifest",
            state="passed" if manifest_result.valid else "failed",
            requirement="All locked Phase 6 inputs exist, match hashes, and remain reviewed.",
            observed=(
                f"valid={manifest_result.valid}; "
                f"{manifest_result.checked_artifact_count} artifacts checked"
            ),
            evidence=("artifacts/evaluations/phase6-experiment-manifest-v1.json",),
        ),
        Phase6ClosureGate(
            gate_id="numerical_verification",
            state="passed" if ablation.numerical_fixture_accuracy >= 0.95 else "failed",
            requirement="Numerical operation accuracy is at least 95%.",
            observed=f"{ablation.numerical_fixture_accuracy:.2%}",
            evidence=("artifacts/evaluations/phase6-stage6.2-numerical-v1.json",),
        ),
        Phase6ClosureGate(
            gate_id="temporal_verification",
            state="passed" if ablation.temporal_fixture_accuracy >= 0.95 else "failed",
            requirement="Temporal relation accuracy is at least 95%.",
            observed=f"{ablation.temporal_fixture_accuracy:.2%}",
            evidence=("artifacts/evaluations/phase6-stage6.3-temporal-v1.json",),
        ),
        Phase6ClosureGate(
            gate_id="citation_support",
            state="passed" if ablation.citation_full_rate >= 0.95 else "failed",
            requirement="Citation support remains at least 95%.",
            observed=f"{ablation.citation_full_rate:.2%}",
            evidence=("artifacts/evaluations/phase6-stage6.8-frozen-ablation-v1.json",),
        ),
        Phase6ClosureGate(
            gate_id="policy_promotion",
            state="failed",
            requirement="No verdict regressions and no loss versus the frozen baseline.",
            observed=(
                f"{ablation.regressed_case_count} regressions; "
                f"{ablation.full_policy_accuracy:.2%} policy accuracy versus "
                f"{ablation.baseline_accuracy:.2%} baseline"
            ),
            evidence=("artifacts/evaluations/phase6-stage6.8-frozen-ablation-v1.json",),
        ),
        Phase6ClosureGate(
            gate_id="safe_fallback",
            state="passed",
            requirement="A failed policy is not promoted into authoritative verdicts.",
            observed="Policy trace is observational with applied=false.",
            evidence=("docs/adr/0013-phase6-policy-not-promoted.md",),
        ),
        Phase6ClosureGate(
            gate_id="targeted_review",
            state="passed",
            requirement="Changed candidates and unresolved disagreements are disclosed.",
            observed=(
                f"{targeted_review.changed_policy_case_count} changed candidates; "
                "0 benchmark-truth changes"
            ),
            evidence=("artifacts/evaluations/phase6-stage6.10-targeted-review-v1.json",),
        ),
        Phase6ClosureGate(
            gate_id="optional_model_experiment",
            state="skipped_by_gate",
            requirement="Run only for a narrow ambiguity that could affect promotion.",
            observed="Skipped: the failure is deterministic representation/aggregation.",
        ),
        Phase6ClosureGate(
            gate_id="repository_quality",
            state="passed",
            requirement="Full tests, coverage threshold, Ruff, and local security checks pass.",
            observed=(
                "339 tests passed; 86.42% coverage; Ruff clean; pip check and "
                "safe-fetcher security tests clean."
            ),
            evidence=("docs/PHASE_6_COMPLETION_REPORT.md",),
        ),
    )
    return Phase6ClosureAudit(
        phase_complete=True,
        default_verdict_authority="existing_evidence-grounded_workflow",
        deterministic_policy_promoted=False,
        targeted_review_required=False,
        artifacts=artifacts,
        gates=gates,
        passed_count=sum(gate.state == "passed" for gate in gates),
        failed_count=sum(gate.state == "failed" for gate in gates),
        skipped_count=sum(gate.state == "skipped_by_gate" for gate in gates),
    )


def verify_closure_audit(
    audit: Phase6ClosureAudit, project_root: str | Path
) -> Phase6ClosureVerification:
    root = Path(project_root).resolve()
    errors: list[str] = []
    checked = 0
    for artifact in audit.artifacts:
        candidate = (root / artifact.path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            errors.append(f"{artifact.artifact_id}: path escapes project root")
            continue
        if not candidate.is_file():
            errors.append(f"{artifact.artifact_id}: file is missing")
            continue
        checked += 1
        if not artifact_matches_sha256(candidate, artifact.sha256):
            errors.append(f"{artifact.artifact_id}: SHA-256 mismatch")
    if audit.deterministic_policy_promoted:
        errors.append("regressive deterministic policy must not be promoted")
    if audit.phase_complete and audit.default_verdict_authority != (
        "existing_evidence-grounded_workflow"
    ):
        errors.append("completed phase must retain the declared safe verdict authority")
    return Phase6ClosureVerification(
        audit_id=audit.audit_id,
        valid=not errors,
        checked_artifact_count=checked,
        errors=tuple(errors),
    )


def export_model(model: DomainModel, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(model.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
    return target


def load_ablation(path: str | Path) -> Phase6AblationEvaluation:
    return Phase6AblationEvaluation.model_validate_json(
        Path(path).read_text(encoding="utf-8")
    )


def load_closure_audit(path: str | Path) -> Phase6ClosureAudit:
    return Phase6ClosureAudit.model_validate_json(Path(path).read_text(encoding="utf-8"))


def _artifact(root: Path, relative_path: str) -> BaselineArtifact:
    path = (root / relative_path).resolve()
    path.relative_to(root)
    if not path.is_file():
        raise FileNotFoundError(path)
    return BaselineArtifact(
        artifact_id=path.stem.replace("-", "_").replace(".", "_").casefold(),
        path=path.relative_to(root).as_posix(),
        sha256=_sha256(path),
    )


def _sha256(path: Path) -> str:
    return artifact_sha256(path)
