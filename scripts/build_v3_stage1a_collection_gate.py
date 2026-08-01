"""Build the deterministic V3.1a public-HTML collection gate artifact."""

from pathlib import Path

from claim_polygraph_ng.evaluation.v3_dataset_assembly import (
    assemble_public_html_collection_gate,
)


def main() -> None:
    root = Path(__file__).parents[1]
    audit = assemble_public_html_collection_gate(
        root / "benchmarks/initial_claims_v1.json",
        root / "benchmarks/verification_construction_v3_public_html_collection_v1.json",
    )
    destination = (
        root
        / "artifacts/evaluations/"
        "verification-construction-v3-stage1a-public-html-collection-gate-v1.json"
    )
    destination.write_text(
        audit.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    print(destination.relative_to(root))
    print(
        f"cases={audit.total_case_count} families={audit.total_family_count} "
        f"splits={audit.split_counts} passed={audit.collection_gate_passed}"
    )


if __name__ == "__main__":
    main()
