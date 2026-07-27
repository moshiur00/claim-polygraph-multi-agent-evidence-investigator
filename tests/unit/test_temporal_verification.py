"""Tests for precision-aware temporal verification."""

from datetime import date
from uuid import uuid4

from claim_polygraph_ng.analysis.temporal_verification import (
    TemporalEvidenceFact,
    TemporalFactStatus,
    TemporalVerificationRequest,
    verify_temporal_assertion,
)
from claim_polygraph_ng.domain import (
    AssertionVerificationState,
    DatePrecision,
    TemporalInstant,
    TemporalInterval,
    TemporalRelation,
)


def _instant(value, precision=DatePrecision.DAY):
    return TemporalInstant(value=date.fromisoformat(value), precision=precision)


def _interval(start=None, end=None, precision=DatePrecision.DAY):
    return TemporalInterval(
        start=_instant(start, precision) if start else None,
        end=_instant(end, precision) if end else None,
    )


def _request(relation, facts=(), reference=None, claimed=None, **kwargs):
    return TemporalVerificationRequest(
        claim_id=uuid4(),
        claim_text_span="Project-authored temporal assertion.",
        relation=relation,
        reference_date=_instant(reference) if reference else None,
        claimed_interval=claimed,
        facts=facts,
        **kwargs,
    )


def _fact(interval=None, status=TemporalFactStatus.UNKNOWN, publication=None, **kwargs):
    return TemporalEvidenceFact(
        evidence_id=uuid4(),
        effective_interval=interval,
        status=status,
        publication_date=_instant(publication) if publication else None,
        **kwargs,
    )


def test_before_after_during_and_exact_start() -> None:
    before = verify_temporal_assertion(
        _request(
            TemporalRelation.BEFORE,
            (_fact(_interval("2020-01-01", "2020-12-31")),),
            reference="2021-01-01",
        )
    )
    after = verify_temporal_assertion(
        _request(
            TemporalRelation.AFTER,
            (_fact(_interval("2022-01-01", "2022-12-31")),),
            reference="2021-01-01",
        )
    )
    during = verify_temporal_assertion(
        _request(
            TemporalRelation.DURING,
            (_fact(_interval("2020-03-01", "2020-04-01")),),
            claimed=_interval("2020-01-01", "2020-12-31"),
        )
    )
    started = verify_temporal_assertion(
        _request(
            TemporalRelation.STARTED,
            (_fact(_interval("2020-03-01", "2021-01-01")),),
            reference="2020-03-01",
        )
    )

    assert all(
        item.state is AssertionVerificationState.VERIFIED
        for item in (before, after, during, started)
    )


def test_active_inactive_changed_and_conflict() -> None:
    active_fact = _fact(
        _interval("2020-01-01", "2025-12-31"),
        TemporalFactStatus.ACTIVE,
    )
    active = verify_temporal_assertion(
        _request(TemporalRelation.ACTIVE, (active_fact,), reference="2023-01-01")
    )
    inactive = verify_temporal_assertion(
        _request(
            TemporalRelation.ACTIVE,
            (_fact(_interval("2020-01-01", "2025-12-31"), TemporalFactStatus.INACTIVE),),
            reference="2023-01-01",
        )
    )
    changed = verify_temporal_assertion(
        _request(
            TemporalRelation.CHANGED_STATUS,
            (_fact(_interval("2023-05-05", "2023-05-05"), TemporalFactStatus.CHANGED),),
            reference="2023-05-05",
        )
    )
    conflict = verify_temporal_assertion(
        _request(
            TemporalRelation.ACTIVE,
            (
                active_fact,
                _fact(_interval("2020-01-01", "2025-12-31"), TemporalFactStatus.INACTIVE),
            ),
            reference="2023-01-01",
        )
    )

    assert active.state is AssertionVerificationState.VERIFIED
    assert inactive.state is AssertionVerificationState.CONTRADICTED
    assert changed.state is AssertionVerificationState.VERIFIED
    assert conflict.state is AssertionVerificationState.QUALIFIED


def test_coarse_precision_and_retrospective_sources_preserve_uncertainty() -> None:
    coarse = verify_temporal_assertion(
        _request(
            TemporalRelation.STARTED,
            (_fact(_interval("2020-01-01", precision=DatePrecision.YEAR)),),
            reference="2020-06-01",
        )
    )
    unmarked = verify_temporal_assertion(
        _request(
            TemporalRelation.ACTIVE,
            (
                _fact(
                    _interval("2020-01-01", "2020-12-31"),
                    TemporalFactStatus.ACTIVE,
                    publication="2021-01-01",
                ),
            ),
            reference="2020-06-01",
        )
    )
    retrospective = verify_temporal_assertion(
        _request(
            TemporalRelation.ACTIVE,
            (
                _fact(
                    _interval("2020-01-01", "2020-12-31"),
                    TemporalFactStatus.ACTIVE,
                    publication="2021-01-01",
                    retrospective=True,
                ),
            ),
            reference="2020-06-01",
        )
    )

    assert coarse.state is AssertionVerificationState.QUALIFIED
    assert unmarked.state is AssertionVerificationState.QUALIFIED
    assert retrospective.state is AssertionVerificationState.VERIFIED


def test_missing_reference_and_effective_dates_fail_closed() -> None:
    missing_reference = verify_temporal_assertion(
        _request(
            TemporalRelation.ACTIVE,
            (_fact(_interval("2020-01-01", "2020-12-31"), TemporalFactStatus.ACTIVE),),
            requires_reference_date=True,
        )
    )
    no_effective = verify_temporal_assertion(
        _request(
            TemporalRelation.BEFORE,
            (_fact(publication="2020-01-01"),),
            reference="2021-01-01",
        )
    )

    assert missing_reference.state is AssertionVerificationState.INSUFFICIENT
    assert no_effective.state is AssertionVerificationState.INSUFFICIENT
