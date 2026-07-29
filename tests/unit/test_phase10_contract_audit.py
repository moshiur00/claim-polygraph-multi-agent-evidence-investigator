"""Stage 10.1 reproducible social-contract audit tests."""

from pathlib import Path

from claim_polygraph_ng.evaluation.phase10_contract_audit import (
    build_phase10_contract_audit,
    verify_phase10_contract_audit,
)


def test_phase10_contract_audit_proves_legacy_compatibility() -> None:
    root = Path(__file__).parents[2]
    audit = build_phase10_contract_audit(root)

    assert audit.legacy_source_loads
    assert audit.legacy_evidence_loads
    assert audit.legacy_distribution_medium == "unknown"
    assert audit.legacy_evidentiary_use == "unspecified"
    assert len(audit.schemas) == 6
    assert verify_phase10_contract_audit(audit) == ()


def test_phase10_contract_audit_detects_schema_hash_tampering() -> None:
    root = Path(__file__).parents[2]
    audit = build_phase10_contract_audit(root)
    payload = audit.model_dump()
    payload["schemas"][0]["schema_sha256"] = "0" * 64
    tampered = type(audit).model_validate(payload)

    assert verify_phase10_contract_audit(tampered) == (
        "typed social contract schema hashes do not match",
    )

