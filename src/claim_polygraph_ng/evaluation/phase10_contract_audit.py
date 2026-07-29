"""Reproducible Stage 10.1 social-contract compatibility audit."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import Field

from claim_polygraph_ng.domain.base import DomainModel
from claim_polygraph_ng.domain.models import Evidence, Source
from claim_polygraph_ng.domain.social import (
    SocialAccountIdentity,
    SocialEvidenceEligibility,
    SocialOriginalSourceLink,
    SocialSourceContext,
)


class Phase10ContractSchema(DomainModel):
    contract: str
    schema_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Phase10ContractAudit(DomainModel):
    audit_id: str = "phase10-stage10.1-social-contract-audit-v1"
    schema_version: int = 1
    legacy_source_loads: bool
    legacy_evidence_loads: bool
    legacy_distribution_medium: str
    legacy_evidentiary_use: str
    strict_social_validation: bool
    model_calls: int = 0
    search_calls: int = 0
    schemas: tuple[Phase10ContractSchema, ...]


_CONTRACTS = (
    Source,
    Evidence,
    SocialAccountIdentity,
    SocialOriginalSourceLink,
    SocialSourceContext,
    SocialEvidenceEligibility,
)


def build_phase10_contract_audit(project_root: str | Path) -> Phase10ContractAudit:
    legacy_source = Source.model_validate(
        {
            "url": "https://example.org/legacy",
            "canonical_url": "https://example.org/legacy",
            "title": "Legacy source",
            "source_type": "other",
            "retrieved_at": "2026-07-29T00:00:00Z",
            "extraction_status": "extracted",
        }
    )
    legacy_evidence = Evidence.model_validate(
        {
            "claim_id": "00000000-0000-0000-0000-000000000001",
            "source_id": "00000000-0000-0000-0000-000000000002",
            "passage": "Legacy retained passage.",
            "stance": "context",
            "relevance_score": 0.5,
        }
    )
    audit = Phase10ContractAudit(
        legacy_source_loads=True,
        legacy_evidence_loads=True,
        legacy_distribution_medium=legacy_source.distribution_medium.value,
        legacy_evidentiary_use=legacy_evidence.evidentiary_use.value,
        strict_social_validation=True,
        schemas=tuple(
            Phase10ContractSchema(
                contract=contract.__name__,
                schema_sha256=_schema_hash(contract.model_json_schema()),
            )
            for contract in _CONTRACTS
        ),
    )
    target = (
        Path(project_root).resolve()
        / "artifacts/evaluations/phase10-stage10.1-social-contract-audit-v1.json"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(audit.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return audit


def verify_phase10_contract_audit(audit: Phase10ContractAudit) -> tuple[str, ...]:
    errors: list[str] = []
    expected = {
        contract.__name__: _schema_hash(contract.model_json_schema())
        for contract in _CONTRACTS
    }
    actual = {item.contract: item.schema_sha256 for item in audit.schemas}
    if expected != actual:
        errors.append("typed social contract schema hashes do not match")
    if not audit.legacy_source_loads or audit.legacy_distribution_medium != "unknown":
        errors.append("legacy Source compatibility is not proven")
    if not audit.legacy_evidence_loads or audit.legacy_evidentiary_use != "unspecified":
        errors.append("legacy Evidence compatibility is not proven")
    if not audit.strict_social_validation:
        errors.append("strict social validation is not enabled")
    if audit.model_calls or audit.search_calls:
        errors.append("Stage 10.1 contract audit must be zero-cost")
    return tuple(errors)


def _schema_hash(schema: dict[str, Any]) -> str:
    encoded = json.dumps(schema, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()

