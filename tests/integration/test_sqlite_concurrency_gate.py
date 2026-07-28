"""Stage 8.10 bounded SQLite concurrency and recovery gate."""

from claim_polygraph_ng.evaluation.sqlite_concurrency import (
    SQLiteMvpConcurrencyTarget,
    run_sqlite_concurrency_gate,
)


def test_sqlite_meets_declared_local_mvp_concurrency_target(tmp_path) -> None:
    result = run_sqlite_concurrency_gate(
        tmp_path,
        target=SQLiteMvpConcurrencyTarget(
            simultaneous_investigations=4,
            writes_per_investigation=10,
            simultaneous_graph_runs=4,
        ),
    )

    assert result.passed, result.failed_checks
    assert result.journal_mode == "wal"
    assert result.successful_writes == result.attempted_writes
    assert result.locked_errors == 0
    assert result.review_successes == 1
    assert result.review_clean_conflicts == 3
    assert result.review_chain_valid
    assert result.checkpoint_restart_matches == result.checkpoint_runs == 4
