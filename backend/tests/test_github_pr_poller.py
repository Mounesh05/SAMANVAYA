"""Background check of linked repositories for new or changed pull requests.

Installs that GitHub cannot reach with webhooks (localhost) otherwise only
see pull requests after someone clicks Sync PR.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.config import settings
from domain.services import github_pr_poller
from domain.services.github_pr_poller import GitHubPRPoller

CONFIG = {"project_id": "PRJ-BFAAEA0A", "repository_owner": "Mallikarjuna902", "repository_name": "samanvaya-pilot",
          "repository_url": "https://github.com/Mallikarjuna902/samanvaya-pilot", "default_branch": "main"}


@pytest.fixture
async def db(mock_db, monkeypatch):
    monkeypatch.setattr(github_pr_poller, "col", lambda name: mock_db[name])
    await mock_db["github_project_configs"].insert_one(dict(CONFIG))
    return mock_db


def fake_service(prs):
    service = MagicMock()
    service.api_service.list_pull_requests = AsyncMock(return_value=prs)
    service.sync_pull_request = AsyncMock(return_value={})
    return service


@pytest.mark.anyio
async def test_new_pull_requests_are_synced_once_until_they_change(db):
    prs = [{"number": 1, "updated_at": "2026-11-15T06:00:00Z"}, {"number": 2, "updated_at": "2026-11-15T06:05:00Z"}]
    service = fake_service(prs)
    poller = GitHubPRPoller(interval_seconds=180, sync_service=service)

    assert (await poller.poll_once())["synced"] == 2
    service.api_service.list_pull_requests.assert_awaited_with("Mallikarjuna902", "samanvaya-pilot", state="all", per_page=20)
    service.sync_pull_request.assert_any_await("Mallikarjuna902", "samanvaya-pilot", 1, "PRJ-BFAAEA0A", triggered_by="github-poller")

    # Nothing changed: no re-sync (and no repeated AI review).
    service.sync_pull_request.reset_mock()
    assert (await poller.poll_once())["synced"] == 0
    service.sync_pull_request.assert_not_awaited()

    # PR #1 got a push, review or merge: only it is synced again.
    prs[0]["updated_at"] = "2026-11-15T07:00:00Z"
    assert (await poller.poll_once())["synced"] == 1
    service.sync_pull_request.assert_awaited_once_with("Mallikarjuna902", "samanvaya-pilot", 1, "PRJ-BFAAEA0A", triggered_by="github-poller")


@pytest.mark.anyio
async def test_a_failed_sync_is_retried_next_round(db):
    service = fake_service([{"number": 1, "updated_at": "2026-11-15T06:00:00Z"}])
    service.sync_pull_request.side_effect = [RuntimeError("GitHub timeout"), {}]
    poller = GitHubPRPoller(interval_seconds=180, sync_service=service)
    assert (await poller.poll_once())["failed"] == 1
    assert (await poller.poll_once())["synced"] == 1


@pytest.mark.anyio
async def test_one_unreachable_repository_does_not_stop_the_others(db):
    await db["github_project_configs"].insert_one({**CONFIG, "project_id": "PRJ-2", "repository_name": "other"})
    service = fake_service([{"number": 3, "updated_at": "2026-11-15T06:00:00Z"}])
    service.api_service.list_pull_requests.side_effect = [RuntimeError("404"), [{"number": 3, "updated_at": "x"}]]
    summary = await GitHubPRPoller(interval_seconds=180, sync_service=service).poll_once()
    assert (summary["repositories"], summary["failed"], summary["synced"]) == (2, 1, 1)


@pytest.mark.anyio
async def test_the_same_pr_number_in_two_projects_is_tracked_separately(db):
    await db["github_project_configs"].insert_one({**CONFIG, "project_id": "PRJ-2"})
    service = fake_service([{"number": 1, "updated_at": "2026-11-15T06:00:00Z"}])
    assert (await GitHubPRPoller(interval_seconds=180, sync_service=service).poll_once())["synced"] == 2


@pytest.mark.anyio
@pytest.mark.parametrize("token,interval,enabled", [("", 180, False), ("t", 0, False), ("t", 180, True)])
async def test_it_only_runs_with_a_token_and_an_interval(monkeypatch, token, interval, enabled):
    monkeypatch.setattr(settings, "GITHUB_TOKEN", token)
    poller = GitHubPRPoller(interval_seconds=interval, sync_service=fake_service([]))
    assert poller.enabled is enabled
    await poller.start()
    assert (poller._task is not None) is enabled
    await poller.stop()
    assert poller._task is None


def test_the_app_starts_and_stops_the_poller():
    import inspect
    import main
    source = inspect.getsource(main.lifespan)
    assert "await pr_poller.start()" in source and "await pr_poller.stop()" in source
