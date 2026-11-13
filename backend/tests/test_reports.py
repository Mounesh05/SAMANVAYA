"""
CR-011: report downloads (existing roles only: CEO, PM, HR, plus admin flag).

Every report needs EXPORT_DATA and the matching view right (D1-A), is scoped
to accessible projects / own organisation, is aggregated for performance with
small groups hidden (D2-A), needs a purpose (D3-A) and is audited.
"""

from datetime import date, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from domain.services import report_service as reports


def user(role, **extra):
    return {"employee_id": f"{role}-1", "name": role, "role": role, "organizational_role": role,
            "is_admin": False, "org_id": "O1", "project_ids": [], **extra}


CEO, PM, HR, QA, DEV = user("CEO"), user("PM"), user("HR"), user("QA"), user("DEVELOPER")
TODAY = date.today()


@pytest.fixture
async def data(mock_db, monkeypatch):
    monkeypatch.setattr(reports, "col", lambda name: mock_db[name])
    monkeypatch.setattr(reports, "get_accessible_project_ids", AsyncMock(return_value=["P1"]))
    audit = AsyncMock()
    monkeypatch.setattr(reports, "log_audit", audit)
    day = TODAY.isoformat()
    await mock_db.projects.insert_many([
        {"id": "P1", "name": "Shop", "status": "active", "org_id": "O1"},
        {"id": "P2", "name": "Bank", "status": "active", "org_id": "O1"},
        {"id": "PX", "name": "Other org", "status": "active", "org_id": "O2"},
    ])
    await mock_db.sprints.insert_many([
        {"id": "S1", "project_id": "P1", "name": "Sprint 1", "status": "completed", "start_date": day, "end_date": day},
        {"id": "S2", "project_id": "P2", "name": "Sprint 2", "status": "active", "start_date": day, "end_date": day},
    ])
    await mock_db.stories.insert_many([
        {"sprint_id": "S1", "points": 5, "status": "done"}, {"sprint_id": "S1", "points": 3, "status": "todo"},
        {"sprint_id": "S1", "points": 8, "status": "draft"}, {"sprint_id": "S2", "points": 2, "status": "done"},
    ])
    await mock_db.risks.insert_many([
        {"project_id": "P1", "status": "open", "risk_level": "CRITICAL"},
        {"project_id": "P1", "status": "open", "risk_level": "HIGH"},
        {"project_id": "P1", "status": "closed", "risk_level": "CRITICAL"},
    ])
    await mock_db.code_quality_runs.insert_many([
        {"repository_id": "P1", "run_id": "R1", "created_at": day + "T10:00:00", "quality_score": 82, "quality_grade": "B"},
        {"repository_id": "P2", "run_id": "R2", "created_at": day + "T10:00:00", "quality_score": 40},
    ])
    team_a = [f"A{i}" for i in range(6)]
    await mock_db.users.insert_many(
        [{"employee_id": e, "team_id": "TEAM-A", "org_id": "O1"} for e in team_a]
        + [{"employee_id": "B1", "team_id": "TEAM-B", "org_id": "O1"}, {"employee_id": "B2", "team_id": "TEAM-B", "org_id": "O1"},
           {"employee_id": "Z1", "team_id": "TEAM-Z", "org_id": "O2"}])
    await mock_db.developer_performances.insert_many(
        [{"developer_id": e, "project_id": "P1", "grade": "A", "period_label": "2026-Q4", "period_start": day} for e in team_a]
        + [{"developer_id": e, "project_id": "P2", "grade": "B", "period_label": "2026-Q4", "period_start": day} for e in ("B1", "B2")]
        + [{"developer_id": "Z1", "project_id": "PX", "grade": "C", "period_label": "2026-Q4", "period_start": day}])
    yield mock_db, audit


async def refused(call, status):
    with pytest.raises(HTTPException) as error:
        await call
    assert error.value.status_code == status


class TestWhoCanDownload:
    def test_available_reports_follow_export_and_view_rights(self):
        names = lambda u: {r["type"] for r in reports.available_reports(u)}  # noqa: E731
        assert names(CEO) == set(reports.REPORTS)
        assert names(PM) == {"sprint_velocity", "quality_trends", "delivery_risk"}
        assert names(HR) == {"performance_distribution"}
        assert names(QA) == set() and names(DEV) == set()
        assert names(user("DEVELOPER", is_admin=True)) == {"quality_trends"}  # admin: only what the role can see

    @pytest.mark.parametrize("designation, allowed", [
        ("HR_MANAGER", True), ("HRBP", True), ("RECRUITER", False), ("COMPENSATION_BENEFITS", False)])
    def test_hr_designations(self, designation, allowed):
        assert bool(reports.available_reports(user("HR", designation=designation))) is allowed

    @pytest.mark.anyio
    async def test_refusals(self, data):
        await refused(reports.generate(QA, "sprint_velocity", purpose="weekly"), 403)
        await refused(reports.generate(HR, "sprint_velocity", purpose="weekly"), 403)
        await refused(reports.generate(PM, "performance_distribution", purpose="weekly"), 403)
        await refused(reports.generate(CEO, "salaries", purpose="weekly"), 404)
        await refused(reports.generate(CEO, "delivery_risk", purpose="  "), 422)
        await refused(reports.generate(CEO, "delivery_risk", purpose="x", start=TODAY - timedelta(days=400), end=TODAY), 422)


class TestContents:
    @pytest.mark.anyio
    async def test_sprint_velocity_is_scoped_and_ignores_drafts(self, data):
        result = await reports.generate(PM, "sprint_velocity", purpose="sprint review")
        assert [r["sprint_id"] for r in result["rows"]] == ["S1"]
        row = result["rows"][0]
        assert (row["points_committed"], row["points_completed"], row["completion_pct"], row["stories_open"]) == (8, 5, 62.5, 1)

    @pytest.mark.anyio
    async def test_a_project_outside_your_access_is_refused(self, data):
        await refused(reports.generate(PM, "delivery_risk", purpose="x" * 5, project_id="P2"), 403)

    @pytest.mark.anyio
    async def test_delivery_risk_counts_open_risks(self, data):
        rows = (await reports.generate(PM, "delivery_risk", purpose="board pack"))["rows"]
        assert rows == [{"project_id": "P1", "project_name": "Shop", "status": "active",
                         "open_risks": 2, "critical_risks": 1, "high_risks": 1}]

    @pytest.mark.anyio
    async def test_quality_trends_are_scoped(self, data):
        rows = (await reports.generate(PM, "quality_trends", purpose="quality review"))["rows"]
        assert [(r["project_id"], r["quality_score"]) for r in rows] == [("P1", 82)]

    @pytest.mark.anyio
    async def test_performance_is_aggregated_and_hides_small_groups(self, data):
        result = await reports.generate(HR, "performance_distribution", purpose="calibration")
        assert result["rows"] == [
            {"period": "2026-Q4", "team_id": "TEAM-A", "grade": "A", "people": 6},
            {"period": "2026-Q4", "team_id": "TEAM-B", "grade": "B", "people": "fewer than 5"},
        ]  # TEAM-Z is another organisation
        assert "developer_id" not in str(result["rows"]) and result["limitations"]

    @pytest.mark.anyio
    async def test_every_export_is_audited_with_purpose_and_digest(self, data):
        _, audit = data
        result = await reports.generate(CEO, "delivery_risk", purpose="board pack")
        details = audit.await_args.kwargs["details"]
        assert audit.await_args.kwargs["action"].value == "EXPORT_DATA"
        assert details["purpose"] == "board pack" and details["digest"] == result["digest"]
        assert details["row_count"] == len(result["rows"])


class TestCsv:
    def test_formula_cells_are_escaped(self):
        text = reports.to_csv(["a", "b"], [{"a": "=HYPERLINK(\"x\")", "b": "@SUM(1)"}, {"a": "-2", "b": "safe"}])
        assert "'=HYPERLINK" in text and "'@SUM" in text and "'-2" in text and "safe" in text

    @pytest.mark.anyio
    async def test_route_returns_a_csv_download(self, data):
        from api.routes.reports import ReportRequest, generate_report
        response = await generate_report("delivery_risk", ReportRequest(purpose="board pack"), PM)
        assert response.media_type.startswith("text/csv")
        assert "attachment" in response.headers["content-disposition"]
        assert response.body.decode().splitlines()[0] == ",".join(reports.REPORTS["delivery_risk"]["columns"])

    @pytest.mark.anyio
    async def test_too_many_rows_is_refused(self, data, monkeypatch):
        monkeypatch.setattr(reports, "MAX_ROWS", 0)
        await refused(reports.generate(PM, "delivery_risk", purpose="board pack"), 422)


class TestCeoOrganisationFix:
    def test_other_organisation_is_refused(self):
        from api.roles.ceo import _own_org
        with pytest.raises(HTTPException) as error:
            _own_org(user("CEO", org_id="O1"), "O2")
        assert error.value.status_code == 403
        assert _own_org(user("CEO", org_id="O1"), "O1") == "O1"

    def test_single_organisation_installs_keep_working(self):
        from api.roles.ceo import _own_org
        assert _own_org({"role": "CEO"}, "O7") == "O7"
