# Phase 5 source-quality calibration review

Review all eight cases in
`benchmarks/phase5_source_quality_calibration_v1.json`.

For each case, confirm:

- the metadata describes the scenario;
- all eight expected findings are justified by that metadata;
- missing information remains `unknown`;
- source type is not treated as proof of authority or truth;
- directness and conflict of interest remain separate; and
- the rationale explains any non-obvious distinction.

Finding meanings:

- `favorable`: explicit metadata supports the dimension;
- `mixed`: explicit signals point in materially different directions;
- `unfavorable`: explicit metadata identifies a weakness;
- `unknown`: available metadata is insufficient; and
- `not_applicable`: the dimension is expressly inapplicable.

To approve, provide:

- annotator identity;
- distinct approver identity;
- approval date; and
- any corrected case IDs and labels.

AI-assisted draft agreement is not human validation. The benchmark must retain
`ai_assisted_draft` status until both people have reviewed the labels.
