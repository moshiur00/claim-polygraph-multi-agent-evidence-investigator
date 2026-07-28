"""Measured Stage 8.11 backend-decision test."""

from claim_polygraph_ng.evaluation.job_backend import (
    JobBackendTarget,
    run_job_backend_gate,
)


def test_sqlite_job_backend_passes_bounded_single_host_gate(tmp_path) -> None:
    result = run_job_backend_gate(
        tmp_path,
        target=JobBackendTarget(
            queue_capacity=12,
            admitted_jobs=8,
            concurrent_submitters=4,
        ),
    )
    assert result.passed, result.failed_checks
    assert not result.postgresql_required_for_mvp
    assert not result.distributed_queue_required_for_mvp
    assert result.duplicate_paid_operations == 0
