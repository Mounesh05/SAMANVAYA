"""
Bug sweep after CR-008: security and broken-call fixes found by scanning
every API route and every frontend API call.
"""

import inspect
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException


def make_user(employee_id, role, **extra):
    return {"employee_id": employee_id, "id": employee_id, "role": role, "organizational_role": role,
            "project_ids": [], "team_id": None, "org_id": "O1", "is_admin": False, **extra}


def dependency_of(endpoint, name="user"):
    return inspect.signature(endpoint).parameters[name].default.dependency


async def refused(call, status):
    with pytest.raises(HTTPException) as error:
        await call
    assert error.value.status_code == status
    return error.value


# ── Approvals clean-up was open to every user ───────────────────────────────

@pytest.mark.asyncio
async def test_only_admins_clean_up_expired_approvals():
    from api.routes import approvals
    check = dependency_of(approvals.cleanup_expired_approvals, "current_user")
    await refused(check(user=make_user("DEV-1", "DEVELOPER")), 403)
    await refused(check(user=make_user("CEO-1", "CEO")), 403)
    admin = make_user("ADM-1", "DEVELOPER", is_admin=True)
    assert await check(user=admin) is admin


# ── GitHub read-through routes used the server token for anyone ─────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["get_repository_info", "list_repositories", "list_branches"])
async def test_github_read_through_needs_repository_link_rights(name):
    from api.routes import github
    check = dependency_of(getattr(github, name))
    for role in ["DEVELOPER", "QA", "HR", "CEO", "PM"]:  # CR-015: not PM
        await refused(check(user=make_user("X", role)), 403)
    for role in ["LEAD", "DEVOPS"]:
        assert (await check(user=make_user("X", role)))["role"] == role


@pytest.mark.asyncio
async def test_github_errors_do_not_leak_internal_details():
    from api.routes import github
    failing = AsyncMock(side_effect=RuntimeError("Bearer ghp_SECRET token rejected"))
    with patch.object(github, "GitHubSyncService") as service:
        service.return_value.get_repository_info = failing
        error = await refused(github.get_repository_info(owner="o", repo="r", user=make_user("L", "LEAD")), 500)
    assert "SECRET" not in error.detail and "Bearer" not in error.detail


# ── Risk configurations were readable for any project ───────────────────────

class TestRiskConfigReads:
    PROJECT_B = {"id": "PRJ-B", "team_id": "TEAM-B", "org_id": "O1"}

    async def _call(self, endpoint, user, *args):
        with patch("core.authorization._project_repo") as projects:
            projects.find_by_id = AsyncMock(return_value=self.PROJECT_B)
            return await endpoint(*args, current_user=user)

    @pytest.mark.asyncio
    async def test_project_config_needs_project_access(self):
        from api.routes import risk_configurations as rc
        outsider = make_user("DEV-1", "DEVELOPER", project_ids=["PRJ-A"])
        await refused(self._call(rc.get_risk_configuration, outsider, "PRJ-B"), 403)
        await refused(self._call(rc.validate_configuration, outsider, "PRJ-B"), 403)
        with patch("core.authorization._project_repo") as projects:
            projects.find_by_id = AsyncMock(return_value=self.PROJECT_B)
            await refused(rc.list_risk_configurations(project_id="PRJ-B", include_inactive=False,
                                                      current_user=outsider), 403)

    @pytest.mark.asyncio
    async def test_global_config_stays_readable(self):
        from api.routes import risk_configurations as rc
        service = AsyncMock()
        service.list_configurations = AsyncMock(return_value=[])
        with patch.object(rc, "get_risk_config_service", return_value=service):
            assert await rc.list_risk_configurations(project_id=None, include_inactive=False,
                                                     current_user=make_user("DEV-1", "DEVELOPER")) == []


# ── First-run setup secret ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_setup_secret_is_compared_safely(monkeypatch):
    from api.routes import setup
    monkeypatch.setattr(setup.settings, "DEMO_SETUP_SECRET", "right-secret")
    monkeypatch.setattr(type(setup.settings), "is_development", lambda self: True)
    account = {"email": "someone@samanvaya.com", "organisation_password": "x", "employee_password": "y"}
    payload = setup.SetupRequest(setup_secret="wrong-secret", ceo=account, admin=account)  # CR-012 shape
    await refused(setup.initialize_demo_admin(payload), 403)
    assert "hmac.compare_digest" in inspect.getsource(setup.initialize_demo_admin)


# ── CI test results ─────────────────────────────────────────────────────────

def submission(**overrides):
    from api.routes import qa_test_runs
    values = dict(project_id="PROJ-1", repository="acme/shop", branch="main", commit_sha="abcdef1234567",
                  test_suite="backend", tests_run=3, tests_passed=3, tests_failed=0, status="passed")
    values.update(overrides)
    return qa_test_runs.TestRunSubmission(**values)


@pytest.mark.anyio
async def test_results_are_refused_for_a_project_without_ci(mock_db, monkeypatch):
    from api.routes import qa_test_runs
    monkeypatch.setattr(qa_test_runs.settings, "QA_TEST_RESULTS_TOKEN", "ci-secret")
    monkeypatch.setattr(qa_test_runs, "col", lambda name: mock_db[name])
    await refused(qa_test_runs.submit_test_run(submission(), "ci-secret"), 403)
    assert await mock_db.test_runs.count_documents({}) == 0


@pytest.mark.anyio
async def test_results_from_the_configured_repository_are_stored_and_listed(mock_db, monkeypatch):
    from api.routes import qa_test_runs
    from domain.services import qa_service
    monkeypatch.setattr(qa_test_runs.settings, "QA_TEST_RESULTS_TOKEN", "ci-secret")
    monkeypatch.setattr(qa_test_runs, "col", lambda name: mock_db[name])
    monkeypatch.setattr(qa_service.QAService, "accessible_project", AsyncMock(return_value={"id": "PROJ-1"}))
    await mock_db.qa_ci_configs.insert_one({"project_id": "PROJ-1", "repository": "acme/shop", "branch": "main"})
    await refused(qa_test_runs.submit_test_run(submission(repository="evil/repo"), "ci-secret"), 403)
    await qa_test_runs.submit_test_run(submission(), "ci-secret")
    await qa_test_runs.submit_test_run(submission(commit_sha="1234567abcdef", source="manual"), "ci-secret")

    listed = await qa_test_runs.list_test_runs(project_id="PROJ-1", source=None, branch=None, limit=50,
                                               user=make_user("QA-1", "QA"))
    assert listed["count"] == 2 and all("_id" not in run for run in listed["runs"])
    manual = await qa_test_runs.list_test_runs(project_id="PROJ-1", source="manual", branch=None, limit=50,
                                               user=make_user("QA-1", "QA"))
    assert [run["commit_sha"] for run in manual["runs"]] == ["1234567abcdef"]


@pytest.mark.anyio
async def test_listing_follows_qa_project_access(mock_db, monkeypatch):
    from api.routes import qa_test_runs
    from domain.services import qa_service
    monkeypatch.setattr(qa_test_runs, "col", lambda name: mock_db[name])
    monkeypatch.setattr(qa_service.QAService, "accessible_project",
                        AsyncMock(side_effect=HTTPException(status_code=403, detail="no")))
    await refused(qa_test_runs.list_test_runs(project_id="PROJ-1", source=None, branch=None, limit=50,
                                              user=make_user("HR-1", "HR")), 403)
