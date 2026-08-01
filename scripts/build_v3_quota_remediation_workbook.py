"""Build the approved V3 quota-remediation workbook without altering old reviews."""

import json
from pathlib import Path

from claim_polygraph_ng.evaluation.v3_annotation import (
    V3AnnotationCase,
    V3AnnotationWorkbook,
    V3EvidenceSpan,
    V3ExactTextSpan,
    V3MachinePreparedProposal,
    V3ReviewEvidence,
    load_annotation_workbook,
)


def main() -> None:
    root = Path(__file__).parents[1]
    reviewed = load_annotation_workbook(
        root / "benchmarks/verification_construction_v3_human_reviewed_v1.json"
    )
    collection = json.loads(
        (
            root
            / "benchmarks/verification_construction_v3_quota_remediation_candidates_v1.json"
        ).read_text(encoding="utf-8")
    )
    replacements = {
        item["replacement_case_id"]: item for item in collection["cases"]
    }
    cases = []
    for existing in reviewed.cases:
        replacement = replacements.get(existing.case_id)
        if replacement is None:
            cases.append(existing)
            continue
        if existing.split.value != replacement["split"]:
            raise ValueError(f"split changed for replacement {existing.case_id}")
        claim = replacement["claim_text"]
        passage = replacement["source_excerpt"]
        evidence_id = f"{replacement['source_candidate_id']}:E1"
        evidence = V3ReviewEvidence(
            evidence_id=evidence_id,
            title=replacement["source_title"],
            url=replacement["source_url"],
            source_class=replacement["source_class"],
            passage=passage,
        )
        cases.append(
            V3AnnotationCase(
                case_id=existing.case_id,
                source_candidate_id=replacement["source_candidate_id"],
                split=existing.split,
                origin_family_id=replacement["origin_family_id"],
                claim_text=claim,
                evidence=(evidence,),
                proposal=V3MachinePreparedProposal(
                    dimension_bucket=replacement["dimension"],
                    comparator_or_relation="equal",
                    claim_span=V3ExactTextSpan(
                        start_char=0,
                        end_char=len(claim),
                        quoted_text=claim,
                    ),
                    evidence_spans=(
                        V3EvidenceSpan(
                            evidence_id=evidence_id,
                            start_char=0,
                            end_char=len(passage),
                            quoted_text=passage,
                        ),
                    ),
                    machine_notes=(
                        "Quota-remediation navigation aid; not human gold.",
                        "This replacement requires annotation and distinct approval.",
                        "Collected from accessible official HTML without a model call.",
                    ),
                    model_calls=0,
                ),
                annotation=None,
                approval=None,
            )
        )
    workbook = V3AnnotationWorkbook(
        workbook_id="verification-construction-v3-remediation-workbook-v2",
        cases=tuple(cases),
    )
    destination = (
        root / "benchmarks/verification_construction_v3_remediation_workbook_v2.json"
    )
    destination.write_text(workbook.model_dump_json(indent=2) + "\n", encoding="utf-8")
    pending = [case.case_id for case in workbook.cases if case.annotation is None]
    if pending != ["V3-009", "V3-022", "V3-031", "V3-045", "V3-053"]:
        raise ValueError(f"unexpected pending remediation cases: {pending}")
    print(destination.relative_to(root))
    print(f"preserved_approvals=55 pending_annotation={len(pending)} model_calls=0")


if __name__ == "__main__":
    main()
