"""Leakage-safe, interpretable empirical confidence calibration."""

import math
from collections import Counter

from claim_polygraph_ng.domain.confidence import (
    CalibrationCase,
    CalibrationMetrics,
    CalibrationSplit,
    CalibrationStatus,
    ConfidenceCalibrationDataset,
    ConfidenceCalibrationResult,
    ConfidenceCalibrator,
    ReliabilityBin,
)

MINIMUM_TOTAL_CASES = 200
MINIMUM_FIT_CASES = 140
MINIMUM_EVALUATION_CASES = 60
MINIMUM_CASES_PER_LABEL = 20
MINIMUM_DOMAINS = 3
ABSTENTION_THRESHOLD = 0.7


def evaluate_confidence_calibration(
    dataset: ConfidenceCalibrationDataset,
    *,
    reviewed_candidate_count: int | None = None,
    excluded_incomplete_feature_count: int = 0,
    compatible_public_case_count: int = 0,
) -> ConfidenceCalibrationResult:
    """Fit only after support checks and evaluate exclusively out of sample."""
    fit = tuple(item for item in dataset.cases if item.split is CalibrationSplit.FIT)
    evaluation = tuple(item for item in dataset.cases if item.split is CalibrationSplit.EVALUATION)
    domains = Counter(item.domain for item in dataset.cases)
    labels = Counter(item.reference_label for item in dataset.cases)
    reasons = _insufficiency_reasons(dataset, fit, evaluation, domains, labels)
    common = {
        "evaluation_id": "phase8-stage8.9-confidence-calibration-v1",
        "dataset_id": dataset.dataset_id,
        "dataset_version": dataset.version,
        "total_case_count": len(dataset.cases),
        "reviewed_candidate_count": (
            len(dataset.cases) if reviewed_candidate_count is None else reviewed_candidate_count
        ),
        "excluded_incomplete_feature_count": excluded_incomplete_feature_count,
        "compatible_public_case_count": compatible_public_case_count,
        "fit_case_count": len(fit),
        "evaluation_case_count": len(evaluation),
        "domain_counts": dict(sorted(domains.items())),
        "label_counts": dict(sorted(labels.items())),
    }
    if reasons:
        return ConfidenceCalibrationResult(
            **common,
            status=CalibrationStatus.INSUFFICIENT_DATA,
            insufficiency_reasons=tuple(reasons),
            confidence_available=False,
        )

    raw_fit = tuple(_raw_score(item) for item in fit)
    raw_evaluation = tuple(_raw_score(item) for item in evaluation)
    targets_fit = tuple(float(item.correct) for item in fit)
    targets_evaluation = tuple(float(item.correct) for item in evaluation)
    base_probability = sum(targets_fit) / len(targets_fit)
    platt_parameters = _fit_platt(raw_fit, targets_fit)
    methods = (
        (
            "fit_base_rate",
            tuple(base_probability for _ in evaluation),
            (base_probability,),
        ),
        (
            "frozen_linear_score",
            raw_evaluation,
            (),
        ),
        (
            "platt_logistic",
            tuple(
                _sigmoid(platt_parameters[0] * score + platt_parameters[1])
                for score in raw_evaluation
            ),
            platt_parameters,
        ),
    )
    metrics = tuple(
        _metrics(name, probabilities, targets_evaluation) for name, probabilities, _ in methods
    )
    selected_index = min(
        range(len(metrics)),
        key=lambda index: (
            metrics[index].brier_score,
            metrics[index].expected_calibration_error,
            metrics[index].method,
        ),
    )
    baseline = metrics[0]
    selected = metrics[selected_index]
    improves = selected.brier_score <= baseline.brier_score - 0.005
    safe = selected.expected_calibration_error <= 0.1 and (
        selected.accepted_accuracy is None
        or baseline.accepted_accuracy is None
        or selected.accepted_accuracy >= baseline.accepted_accuracy
    )
    if selected_index == 0 or not improves or not safe:
        return ConfidenceCalibrationResult(
            **common,
            status=CalibrationStatus.NOT_PROMOTED,
            compared_metrics=metrics,
            confidence_available=False,
        )
    return ConfidenceCalibrationResult(
        **common,
        status=CalibrationStatus.PROMOTED,
        compared_metrics=metrics,
        selected_calibrator=ConfidenceCalibrator(
            calibrator_version="confidence-calibrator-v1",
            method=methods[selected_index][0],
            feature_version=dataset.feature_version,
            parameters=methods[selected_index][2],
        ),
        confidence_available=True,
    )


def _insufficiency_reasons(dataset, fit, evaluation, domains, labels):
    reasons = []
    if len(dataset.cases) < MINIMUM_TOTAL_CASES:
        reasons.append(f"At least {MINIMUM_TOTAL_CASES} feature-complete cases are required.")
    if len(fit) < MINIMUM_FIT_CASES:
        reasons.append(f"At least {MINIMUM_FIT_CASES} fit cases are required.")
    if len(evaluation) < MINIMUM_EVALUATION_CASES:
        reasons.append(
            f"At least {MINIMUM_EVALUATION_CASES} held-out evaluation cases are required."
        )
    if len(domains) < MINIMUM_DOMAINS:
        reasons.append(f"At least {MINIMUM_DOMAINS} represented domains are required.")
    sparse = sorted(label for label, count in labels.items() if count < MINIMUM_CASES_PER_LABEL)
    if not labels:
        reasons.append("No reference-label sample support is available.")
    elif sparse:
        reasons.append(
            "Every reference label requires at least "
            f"{MINIMUM_CASES_PER_LABEL} cases; sparse labels: {', '.join(sparse)}."
        )
    return reasons


def _raw_score(case: CalibrationCase) -> float:
    features = case.features
    family_score = min(features.independent_family_count / 3, 1)
    verification_score = 1 - features.unresolved_verification_rate
    contradiction_score = 1 - abs(features.contradiction_balance)
    score = (
        0.25 * features.evidence_quality
        + 0.15 * family_score
        + 0.2 * features.citation_support_rate
        + 0.15 * verification_score
        + 0.15 * features.retrieval_coverage
        + 0.05 * contradiction_score
        + 0.05 * (1 - features.model_disagreement)
    )
    return min(1.0, max(0.0, score))


def _fit_platt(scores, targets):
    slope = 1.0
    intercept = 0.0
    learning_rate = 0.1
    for _ in range(1_000):
        probabilities = tuple(_sigmoid(slope * score + intercept) for score in scores)
        slope_gradient = sum(
            (probability - target) * score
            for probability, target, score in zip(probabilities, targets, scores, strict=True)
        ) / len(scores)
        intercept_gradient = sum(
            probability - target for probability, target in zip(probabilities, targets, strict=True)
        ) / len(scores)
        slope -= learning_rate * slope_gradient
        intercept -= learning_rate * intercept_gradient
    return (round(slope, 10), round(intercept, 10))


def _metrics(method, probabilities, targets):
    count = len(targets)
    brier = (
        sum(
            (probability - target) ** 2
            for probability, target in zip(probabilities, targets, strict=True)
        )
        / count
    )
    bins = []
    ece = 0.0
    for index in range(10):
        lower = index / 10
        upper = (index + 1) / 10
        members = tuple(
            (probability, target)
            for probability, target in zip(probabilities, targets, strict=True)
            if lower <= probability <= upper and (index == 9 or probability < upper)
        )
        if members:
            mean = sum(item[0] for item in members) / len(members)
            accuracy = sum(item[1] for item in members) / len(members)
            ece += len(members) / count * abs(mean - accuracy)
        else:
            mean = accuracy = None
        bins.append(
            ReliabilityBin(
                lower_bound=lower,
                upper_bound=upper,
                count=len(members),
                mean_confidence=mean,
                observed_accuracy=accuracy,
            )
        )
    accepted = tuple(
        target
        for probability, target in zip(probabilities, targets, strict=True)
        if probability >= ABSTENTION_THRESHOLD
    )
    return CalibrationMetrics(
        method=method,
        evaluation_count=count,
        brier_score=round(brier, 10),
        expected_calibration_error=round(ece, 10),
        reliability_bins=tuple(bins),
        abstention_threshold=ABSTENTION_THRESHOLD,
        coverage_under_abstention=len(accepted) / count,
        accepted_accuracy=(sum(accepted) / len(accepted) if accepted else None),
    )


def _sigmoid(value):
    if value >= 0:
        term = math.exp(-value)
        return 1 / (1 + term)
    term = math.exp(value)
    return term / (1 + term)
