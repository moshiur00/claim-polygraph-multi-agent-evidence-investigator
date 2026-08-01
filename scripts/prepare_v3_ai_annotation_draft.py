"""Convert an AI-simulated V3 workbook into a safe, non-human review draft."""

import json
from pathlib import Path

from claim_polygraph_ng.evaluation.v3_annotation import V3AnnotationWorkbook


AI_DRAFT_IDENTITY = "AI-assisted draft - not human reviewed"


def prepare_ai_draft(source: str | Path, destination: str | Path) -> None:
    payload = json.loads(Path(source).read_text(encoding="utf-8"))
    payload.pop("_simulation_notice", None)
    payload["frozen"] = False
    for case in payload["cases"]:
        annotation = case.get("annotation")
        if annotation is not None:
            annotation["annotator_identity"] = AI_DRAFT_IDENTITY
            notes = list(annotation.get("ambiguity_notes") or [])
            marker = (
                "AI-prepared proposal only; a human annotator must verify every "
                "field and replace the draft identity."
            )
            if marker not in notes:
                notes.insert(0, marker)
            annotation["ambiguity_notes"] = notes
        case["approval"] = None
    workbook = V3AnnotationWorkbook.model_validate(payload)
    Path(destination).write_text(
        workbook.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    root = Path(__file__).parents[1]
    source = Path(
        r"C:\Users\moshi\Downloads"
        r"\verification_construction_v3_annotation_workbook_v1_COMPLETED.json"
    )
    destination = (
        root / "benchmarks/verification_construction_v3_ai_annotation_draft_v1.json"
    )
    prepare_ai_draft(source, destination)
    public_destination = root / "dashboard/public/v3-ai-annotation-draft.json"
    prepare_ai_draft(source, public_destination)
    print(destination.relative_to(root))
    print(public_destination.relative_to(root))


if __name__ == "__main__":
    main()
