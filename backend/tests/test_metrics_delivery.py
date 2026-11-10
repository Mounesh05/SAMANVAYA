"""
Tests for intelligence.metrics.delivery (DORA metrics), with hand-calculated values.
"""

from datetime import date, datetime, timezone

import pytest

from intelligence.metrics.delivery import (
    change_fail_rate,
    deployment_failure_rate,
    deployment_frequency,
    dora_report,
    fail_rate_level,
    failed_changes,
    frequency_level,
    lead_time_level,
    lead_times_hours,
    recovery_hours,
    recovery_level,
    rework_rate,
)

UTC = timezone.utc
START, END = date(2026, 11, 2), date(2026, 11, 15)        # 14 days, Monday to Sunday


def t(day, hour=0):
    return datetime(2026, 11, day, hour, tzinfo=UTC).isoformat()


DEPLOYMENTS = [
    # D1: two commits, the first committed 2 days before
    {"id": "D1", "status": "success", "created_at": t(2, 9), "finished_at": t(2, 10),
     "commits": [{"sha": "a", "committed_at": t(1, 8)}, {"sha": "b", "committed_at": t(2, 4)}]},
    # D2: a failed attempt (never reached production)
    {"id": "D2", "status": "failure", "created_at": t(3, 9), "finished_at": t(3, 9),
     "commits": [{"sha": "c", "committed_at": t(3, 5)}]},
    # D3: the retry; it includes c again plus d, and later causes an incident
    {"id": "D3", "status": "success", "created_at": t(3, 11), "finished_at": t(3, 12),
     "commits": [{"sha": "c", "committed_at": t(3, 5)}, {"sha": "d", "committed_at": t(3, 10)}]},
    # D4: rolled back by D5
    {"id": "D4", "status": "success", "created_at": t(9, 9), "finished_at": t(9, 10),
     "commits": [{"sha": "e", "committed_at": t(5, 10)}]},
    {"id": "D5", "status": "success", "created_at": t(9, 11), "finished_at": t(9, 11), "is_rollback": True,
     "rolled_back_deployment_id": "D4", "commits": []},
    # D6: hotfix; a, already deployed by D1, is not counted again
    {"id": "D6", "status": "success", "created_at": t(12, 15), "finished_at": t(12, 16), "is_hotfix": True,
     "commits": [{"sha": "a", "committed_at": t(1, 8)}, {"sha": "f", "committed_at": t(12, 14)}]},
    # outside the window
    {"id": "D0", "status": "success", "created_at": t(20, 9), "finished_at": t(20, 9), "commits": []},
]
INCIDENTS = [
    {"id": "I1", "caused_by_deployment_id": "D3", "started_at": t(4, 9),
     "resolved_at": datetime(2026, 11, 4, 9, 30, tzinfo=UTC).isoformat()},
    {"id": "I2", "cause": "change", "started_at": t(10, 8), "resolved_at": t(10, 14)},
    {"id": "I3", "cause": "external", "started_at": t(11, 0), "resolved_at": t(13, 0)},   # data-centre outage
    {"id": "I4", "caused_by_deployment_id": "D6", "started_at": t(13, 0)},                # still open
]


def test_deployment_frequency_counts_successful_production_deployments():
    f = deployment_frequency(DEPLOYMENTS, START, END)
    assert (f.deployments, f.days, f.deploy_days) == (5, 14, 4)       # D1 D3 D4 D5 D6; days 2, 3, 9, 12
    assert f.per_week == 2.5 and f.deploy_day_share == round(400 / 14, 2)
    assert f.to_dict()["level"] == "high"


def test_lead_time_per_commit_at_first_successful_deployment():
    hours = sorted(lead_times_hours(DEPLOYMENTS, START, END))
    # a: Nov 1 08 -> D1 Nov 2 10 = 26h;  b: 6h;  c: Nov 3 05 -> D3 Nov 3 12 = 7h (failed D2 ignored)
    # d: 2h;  e: Nov 5 10 -> Nov 9 10 = 96h;  f: 2h;  a is not counted again for D6
    assert hours == [2.0, 2.0, 6.0, 7.0, 26.0, 96.0]


def test_change_fail_rate_from_incidents_and_rollbacks():
    assert failed_changes(DEPLOYMENTS, INCIDENTS) == {"D3", "D4", "D6"}
    assert change_fail_rate(DEPLOYMENTS, INCIDENTS, START, END) == 60.0          # 3 of 5
    assert change_fail_rate([], [], START, END) is None


def test_failed_attempts_are_reported_separately():
    assert deployment_failure_rate(DEPLOYMENTS, START, END) == round(100 / 6, 2)   # D2 of 6 finished attempts


def test_recovery_time_counts_only_change_caused_incidents():
    assert sorted(recovery_hours(INCIDENTS, START, END)) == [0.5, 6.0]               # I3 external, I4 open
    assert sorted(recovery_hours(INCIDENTS, START, END, change_only=False)) == [0.5, 6.0, 48.0]


def test_rework_rate():
    assert rework_rate(DEPLOYMENTS, START, END) == 40.0                              # D5 rollback, D6 hotfix
    # an incident naming D3 as its fix makes D3 rework too
    assert rework_rate(DEPLOYMENTS, START, END, [{"fixed_by_deployment_id": "D3"}]) == 60.0


# "once a month" = 12 per year = 12/52 = 0.2308 per week
@pytest.mark.parametrize("per_week, level", [(14, "elite"), (7, "elite"), (6.9, "high"), (1, "high"),
                                              (0.5, "medium"), (0.24, "medium"), (0.23, "low"), (None, None)])
def test_frequency_levels(per_week, level):
    assert frequency_level(per_week) == level


@pytest.mark.parametrize("hours, level", [(5, "elite"), (23.9, "elite"), (24, "high"), (167, "high"),
                                          (168, "medium"), (719, "medium"), (720, "low"), (None, None)])
def test_lead_time_levels(hours, level):
    assert lead_time_level(hours) == level


@pytest.mark.parametrize("percent, level", [(0, "elite"), (5, "elite"), (5.1, "high"), (10, "high"),
                                            (15, "medium"), (15.1, "low"), (64, "low"), (None, None)])
def test_fail_rate_levels(percent, level):
    assert fail_rate_level(percent) == level


@pytest.mark.parametrize("hours, level", [(0.5, "elite"), (1, "high"), (23, "high"), (24, "medium"),
                                          (167, "medium"), (168, "low"), (None, None)])
def test_recovery_levels(hours, level):
    assert recovery_level(hours) == level


def test_dora_report():
    report = dora_report(DEPLOYMENTS, INCIDENTS, START, END)
    assert report["deployment_frequency"]["deployments"] == 5
    assert report["change_lead_time_hours"]["median"] == 6.5 and report["change_lead_time_hours"]["level"] == "elite"
    assert report["change_fail_rate"]["percent"] == 60.0 and report["change_fail_rate"]["level"] == "low"
    assert report["failed_deployment_recovery_hours"]["median"] == 3.25
    assert report["failed_deployment_recovery_hours"]["level"] == "high"
    assert report["time_to_restore_all_incidents_hours"]["n"] == 3
    assert report["levels"] == {"deployment_frequency": "high", "change_lead_time": "elite",
                                "change_fail_rate": "low", "failed_deployment_recovery_time": "high"}
    assert report["lowest_level"] == "low"
    assert "2023 Accelerate State of DevOps" in report["levels_source"]
    weeks = {w["week"]: w for w in report["weekly"]}
    assert weeks["2026-11-02"]["deployments"] == 2 and weeks["2026-11-02"]["change_fail_rate"] == 50.0
    assert weeks["2026-11-09"]["deployments"] == 3


def test_empty_project():
    report = dora_report([], [], START, END)
    assert report["deployment_frequency"]["deployments"] == 0
    assert report["deployment_frequency"]["level"] == "low"
    assert report["change_fail_rate"]["percent"] is None and report["lowest_level"] == "low"
