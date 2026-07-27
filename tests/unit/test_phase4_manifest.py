import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from claim_polygraph_ng.evaluation.phase4_manifest import (
    BaselineArtifact,
    Phase4ExperimentManifest,
    load_phase4_manifest,
    verify_phase4_manifest,
)


def test_repository_phase4_manifest_verifies() -> None:
    root = Path(__file__).parents[2]
    manifest = load_phase4_manifest(
        root / "artifacts/evaluations/phase4-experiment-manifest-v1.json"
    )

    result = verify_phase4_manifest(manifest, root)

    assert result.valid
    assert result.checked_artifact_count == 8
    assert result.errors == ()
    assert manifest.pilot_case_ids == ("CPNG-014", "CPNG-016", "CPNG-020")


def test_manifest_verifier_detects_changed_artifact(tmp_path: Path) -> None:
    dataset = tmp_path / "benchmark.json"
    dataset.write_text(
        json.dumps(
            {
                "dataset_id": "initial_claims",
                "version": 5,
                "cases": [{"case_id": case_id} for case_id in ("A", "B", "C")],
            }
        ),
        encoding="utf-8",
    )
    manifest = Phase4ExperimentManifest(
        manifest_id="test",
        schema_version=1,
        dataset_id="initial_claims",
        dataset_version=5,
        benchmark_case_ids=("A", "B", "C"),
        pilot_case_ids=("A", "B", "C"),
        pilot_selection_rationale={"A": "one", "B": "two", "C": "three"},
        artifacts=(
            BaselineArtifact(
                artifact_id="benchmark",
                path="benchmark.json",
                sha256="0" * 64,
            ),
        ),
        phase3_metrics={"accuracy": 0.9},
        pilot_gate={
            "minimum_improved_cases": 2,
            "maximum_mean_cost_ratio": 2.0,
            "maximum_median_latency_ratio": 2.5,
            "verdict_regressions_allowed": 0,
            "provenance_regressions_allowed": 0,
        },
    )

    result = verify_phase4_manifest(manifest, tmp_path)

    assert not result.valid
    assert result.errors == ("benchmark: SHA-256 mismatch",)


def test_manifest_verifier_reports_identity_case_and_gate_failures(tmp_path: Path) -> None:
    dataset = tmp_path / "benchmark.json"
    dataset.write_text(
        json.dumps({"dataset_id": "wrong", "version": 4, "cases": []}),
        encoding="utf-8",
    )
    gate = tmp_path / "gate.json"
    gate.write_text(
        json.dumps({"dataset_id": "wrong", "dataset_version": 4, "release_ready": False}),
        encoding="utf-8",
    )
    manifest = _manifest_for(
        (
            _artifact("benchmark", dataset, tmp_path),
            _artifact("phase3_gate_audit", gate, tmp_path),
        )
    )

    result = verify_phase4_manifest(manifest, tmp_path)

    assert not result.valid
    assert set(result.errors) == {
        "benchmark: dataset_id mismatch",
        "benchmark: dataset version mismatch",
        "benchmark: missing declared cases A, B, C",
        "phase3_gate_audit: dataset_id mismatch",
        "phase3_gate_audit: dataset version mismatch",
        "phase3_gate_audit: baseline is not release-ready",
    }


def test_manifest_verifier_rejects_missing_and_escaping_paths(tmp_path: Path) -> None:
    manifest = _manifest_for(
        (
            BaselineArtifact(
                artifact_id="benchmark",
                path="missing.json",
                sha256="0" * 64,
            ),
            BaselineArtifact(
                artifact_id="escape",
                path="../escape.json",
                sha256="0" * 64,
            ),
        )
    )

    result = verify_phase4_manifest(manifest, tmp_path)

    assert result.checked_artifact_count == 0
    assert set(result.errors) == {
        "benchmark: file is missing",
        "escape: path escapes project root",
    }


def test_manifest_requires_three_explained_pilot_cases() -> None:
    with pytest.raises(ValidationError, match="exactly three distinct"):
        _manifest_for((), pilot_case_ids=("A", "A", "B"))
    with pytest.raises(ValidationError, match="selection rationale"):
        _manifest_for((), rationales={"A": "one", "B": "two"})


def _artifact(artifact_id: str, path: Path, root: Path) -> BaselineArtifact:
    return BaselineArtifact(
        artifact_id=artifact_id,
        path=path.relative_to(root).as_posix(),
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )


def _manifest_for(
    artifacts: tuple[BaselineArtifact, ...],
    *,
    pilot_case_ids: tuple[str, ...] = ("A", "B", "C"),
    rationales: dict[str, str] | None = None,
) -> Phase4ExperimentManifest:
    return Phase4ExperimentManifest(
        manifest_id="test",
        schema_version=1,
        dataset_id="initial_claims",
        dataset_version=5,
        benchmark_case_ids=("A", "B", "C"),
        pilot_case_ids=pilot_case_ids,
        pilot_selection_rationale=rationales
        if rationales is not None
        else {"A": "one", "B": "two", "C": "three"},
        artifacts=artifacts,
        phase3_metrics={"accuracy": 0.9},
        pilot_gate={
            "minimum_improved_cases": 2,
            "maximum_mean_cost_ratio": 2.0,
            "maximum_median_latency_ratio": 2.5,
            "verdict_regressions_allowed": 0,
            "provenance_regressions_allowed": 0,
        },
    )
