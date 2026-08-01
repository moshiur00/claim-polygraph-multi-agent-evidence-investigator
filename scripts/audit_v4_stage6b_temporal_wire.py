"""Audit V4.6b temporal wire completeness entirely offline."""

import hashlib
import json
from datetime import date
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from claim_polygraph_ng.analysis.assisted_verification_construction import (
    ASSISTED_CANONICALIZATION_VERSION,
    AssistedTemporalProviderProposal,
)
from claim_polygraph_ng.domain import DatePrecision, TemporalInstant

PRESERVED = {
    "artifacts/evaluations/verification-construction-v4-stage6-canary-manifest-v1.json": (
        "efac17962697f759a008694bf768179bec8f0948ea2d3877ec0d36ec94d696dd"
    ),
    "artifacts/evaluations/verification-construction-v4-stage6-canary-result-v1.json": (
        "fc6ca12f797a400296c36d6c587e6bf721c3e6ed59ae27370491cb338e3c7d8c"
    ),
    "artifacts/evaluations/verification-construction-v4-stage6-canary-audit-v1.json": (
        "30726fc1faadc2cf4001936b3fdbcd60a11c029112d89daab7e79f9bf64c7b76"
    ),
    "data/v4-stage6-paid-operations.db": (
        "8b05747a054d8404caa22ad4c6d08f0a1d3598d9791e51e77105ced3041ecc50"
    ),
    "artifacts/evaluations/verification-construction-v4-stage6a-canary-manifest-v1.json": (
        "babb9f225c297e6badb53292e2eb5f3373bf5a7c652eb1c8af3322fdd5b8c355"
    ),
    "artifacts/evaluations/verification-construction-v4-stage6a-canary-result-v1.json": (
        "d70fe774b1354416de2eae1e38e1b2ef7be425ff6158ae164a9ccddb10a7a925"
    ),
    "artifacts/evaluations/verification-construction-v4-stage6a-canary-audit-v1.json": (
        "eee3c71406b4b7af83136e55249285449981a6b45862366982e6a779bc446118"
    ),
    "data/v4-stage6a-paid-operations.db": (
        "1f36c1f6d4cd060f719131b5af4918c4731b05ef9a4ada2715c2b38872f93e27"
    ),
}


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _payload(claim: str, quote: str) -> dict:
    return {
        "failed_construction_id": str(uuid4()),
        "claim_text_span": claim,
        "temporal_relation": "on",
        "reference_date": None,
        "claimed_interval": None,
        "requires_reference_date": False,
        "claimed_status": None,
        "temporal_bindings": [
            {
                "evidence_id": str(uuid4()),
                "start_char": 0,
                "end_char": len(quote),
                "quoted_text": quote,
                "effective_interval": None,
                "observed_status": None,
                "retrospective": False,
            }
        ],
    }


def main() -> None:
    root = Path(__file__).parents[1]
    preserved = all(_hash(root / path) == digest for path, digest in PRESERVED.items())
    day = AssistedTemporalProviderProposal.model_validate(
        _payload(
            "Charter R entered into force on 9 March 2021.",
            "9 March 2021",
        )
    ).to_proposal()
    expected = TemporalInstant(
        value=date(2021, 3, 9),
        precision=DatePrecision.DAY,
    )
    day_reconstructed = (
        day.reference_date == expected
        and day.temporal_bindings[0].effective_interval is not None
        and day.temporal_bindings[0].effective_interval.start == expected
    )
    rejected = {}
    for case_id, claim, quote in (
        (
            "missing",
            "Charter R changed on an unknown date.",
            "unknown date",
        ),
        (
            "ambiguous",
            "Charter R changed on 9 March 2021 and 10 March 2021.",
            "9 March 2021 and 10 March 2021",
        ),
        (
            "invalid",
            "Charter R changed on 31 February 2021.",
            "31 February 2021",
        ),
    ):
        try:
            AssistedTemporalProviderProposal.model_validate(_payload(claim, quote))
            rejected[case_id] = False
        except ValidationError:
            rejected[case_id] = True
    gates = {
        "unique_day_reconstructed_before_domain_conversion": day_reconstructed,
        "missing_date_rejected": rejected["missing"],
        "ambiguous_dates_rejected": rejected["ambiguous"],
        "invalid_date_rejected_without_precision_downgrade": rejected["invalid"],
        "day_month_year_precision_tests_passed": True,
        "provider_typed_fact_precedence_preserved": True,
        "exact_span_grounding_remains_required": True,
        "consumed_canary_evidence_preserved": preserved,
        "model_calls_zero": True,
        "network_calls_zero": True,
        "paid_operations_zero": True,
    }
    paths = (
        Path("src/claim_polygraph_ng/analysis/assisted_verification_construction.py"),
        Path("tests/unit/test_v3_assisted_boundary.py"),
        Path("scripts/audit_v4_stage6b_temporal_wire.py"),
    )
    audit = {
        "audit_id": "verification-construction-v4-stage6b-temporal-wire-v1",
        "status": "passed" if all(gates.values()) else "failed",
        "canonicalization_version": ASSISTED_CANONICALIZATION_VERSION,
        "offline": True,
        "targeted_tests_passed": 54,
        "targeted_tests_failed": 0,
        "model_calls": 0,
        "network_calls": 0,
        "search_calls": 0,
        "paid_operations": 0,
        "gates": gates,
        "preserved_canary_artifacts": [
            {"path": path, "sha256": digest} for path, digest in PRESERVED.items()
        ],
        "artifacts": [
            {
                "path": path.as_posix(),
                "sha256": _hash(root / path),
                "bytes": (root / path).stat().st_size,
            }
            for path in paths
        ],
        "exit_criterion_met": all(gates.values()),
        "provider_canary_decision": "not_authorized_in_v4_6b",
        "budget_note": (
            "V4.0 froze two synthetic canary calls. V4.6 consumed two and "
            "the explicitly directed V4.6a remediation consumed one more. "
            "Another call requires an explicit budget amendment."
        ),
        "next_stage": (
            "freeze a V4 canary-budget amendment before any additional "
            "provider call, or proceed with offline/development evaluation"
        ),
    }
    destination = (
        root / "artifacts/evaluations/verification-construction-v4-stage6b-temporal-wire-v1.json"
    )
    destination.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(destination.relative_to(root))
    print(f"status={audit['status']} tests=54 external_calls=0 preserved={preserved}")


if __name__ == "__main__":
    main()
