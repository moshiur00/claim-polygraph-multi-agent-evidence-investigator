import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from claim_polygraph_ng.evaluation.phase4_manifest import BaselineArtifact
from claim_polygraph_ng.evaluation.phase5_manifest import (
    Phase5ExperimentManifest,
    ProvenanceBenchmark,
    load_phase5_manifest,
    verify_phase5_manifest,
)


def test_repository_phase5_manifest_verifies() -> None:
    root = Path(__file__).parents[2]
    manifest = load_phase5_manifest(
        root / "artifacts/evaluations/phase5-source-intelligence-manifest-v1.json"
    )

    result = verify_phase5_manifest(manifest, root)

    assert result.valid
    assert result.benchmark_reviewed
    assert result.checked_artifact_count == 2
    assert result.errors == ()
    assert len(manifest.fixture_case_ids) == 12
    assert not manifest.paid_model_calls_authorized
    assert not manifest.pdf_downloads_authorized


def test_review_requires_distinct_people() -> None:
    with pytest.raises(ValidationError, match="distinct"):
        ProvenanceBenchmark(
            dataset_id="test",
            version=1,
            status="reviewed",
            annotated_by="Person",
            approved_by="person",
            approval_date="2026-07-27",
            cases=(_case(),),
        )


def test_verifier_detects_changed_fixture(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps(
            {
                "dataset_id": "test",
                "version": 1,
                "status": "draft",
                "cases": [_case(index) for index in range(1, 11)],
            }
        ),
        encoding="utf-8",
    )
    manifest = _manifest(
        BaselineArtifact(
            artifact_id="provenance_benchmark",
            path="fixture.json",
            sha256="0" * 64,
        )
    )

    result = verify_phase5_manifest(manifest, tmp_path)

    assert "provenance_benchmark: SHA-256 mismatch" in result.errors


def test_reviewed_fixture_verifies(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps(
            {
                "dataset_id": "test",
                "version": 1,
                "status": "reviewed",
                "annotated_by": "Annotator",
                "approved_by": "Approver",
                "approval_date": "2026-07-27",
                "cases": [_case(index) for index in range(1, 11)],
            }
        ),
        encoding="utf-8",
    )
    artifact = BaselineArtifact(
        artifact_id="provenance_benchmark",
        path="fixture.json",
        sha256=hashlib.sha256(fixture.read_bytes()).hexdigest(),
    )

    result = verify_phase5_manifest(_manifest(artifact), tmp_path)

    assert result.valid
    assert result.benchmark_reviewed


def _case(index: int = 1) -> dict:
    left = index * 2 - 1
    right = index * 2
    return {
        "case_id": f"PROV-{index:03d}",
        "scenario": "exact",
        "component_claim": "A test claim.",
        "sources": [
            {
                "source_id": f"SRC-{left:03d}",
                "url": "https://a.test/one",
                "title": "One",
                "publisher": "A",
                "published_at": "2026-01-01",
                "excerpt": "A sufficiently long project-authored fixture excerpt.",
                "rights_basis": "synthetic_project_authored",
            },
            {
                "source_id": f"SRC-{right:03d}",
                "url": "https://b.test/two",
                "title": "Two",
                "publisher": "B",
                "published_at": "2026-01-02",
                "excerpt": "A second sufficiently long project-authored fixture excerpt.",
                "rights_basis": "synthetic_project_authored",
            },
        ],
        "expected_relationships": [
            {
                "left_source_id": f"SRC-{left:03d}",
                "right_source_id": f"SRC-{right:03d}",
                "relationship": "independent",
                "same_canonical_document": False,
                "same_evidence_family": False,
                "rationale": "Independent sources.",
            }
        ],
    }


def _manifest(artifact: BaselineArtifact) -> Phase5ExperimentManifest:
    return Phase5ExperimentManifest(
        manifest_id="phase5-test",
        schema_version=1,
        provenance_dataset_id="test",
        provenance_dataset_version=1,
        fixture_case_ids=tuple(f"PROV-{index:03d}" for index in range(1, 11)),
        artifacts=(artifact,),
        thresholds={
            "canonical_precision": 1,
            "exact_duplicate_precision": 1,
            "exact_duplicate_recall": 1,
            "derivative_precision": 0.95,
            "derivative_recall": 0.9,
            "family_accuracy": 0.9,
            "maximum_false_independent_rate": 0.05,
            "maximum_verdict_regressions": 0,
            "minimum_citation_full_rate": 0.95,
            "maximum_added_latency_ratio": 0.2,
            "maximum_added_model_cost_usd": 0.005,
        },
    )
