import pytest
import httpx
from unittest.mock import AsyncMock, patch

from integrations.github.client import GitHubClient


@pytest.mark.asyncio
async def test_list_branches_uses_repository_read_endpoint():
    client = GitHubClient(token="test-token")
    response = httpx.Response(
        200,
        json=[{"name": "main"}, {"name": "feature/mounesh-events"}],
        request=httpx.Request("GET", "https://api.github.com"),
    )

    async def fake_request(method, url, **kwargs):
        assert method == "GET"
        assert url == "https://api.github.com/repos/Mounesh05/campusconnect-demo/branches"
        assert kwargs["params"] == {"per_page": 100}
        return response

    client._make_request = fake_request

    branches = await client.list_branches("Mounesh05", "campusconnect-demo")

    assert [branch["name"] for branch in branches] == [
        "main",
        "feature/mounesh-events",
    ]


@pytest.mark.asyncio
async def test_pull_request_evidence_includes_diff_commits_checks_reviews_and_comments():
    from domain.services.github_api_service import GitHubAPIService

    service = GitHubAPIService()
    service.client.get_pull_request = AsyncMock(return_value={
        "number": 1,
        "head": {"sha": "abc123"},
        "user": {"login": "developer"},
    })
    service.client.get_pr_files = AsyncMock(return_value=[{
        "filename": "events.py",
        "patch": "+def create_event():",
    }])
    service.client.get_pr_commits = AsyncMock(return_value=[{"sha": "abc123"}])
    service.client.get_commit_check_runs = AsyncMock(return_value={
        "check_runs": [{"name": "tests", "conclusion": "success"}],
    })
    service.client.get_pr_reviews = AsyncMock(return_value=[{"state": "approved"}])
    service.client.get_pr_comments = AsyncMock(return_value=[{"body": "Looks good"}])

    evidence = await service.fetch_pull_request_evidence("owner", "repo", 1)

    assert evidence["files"][0]["patch"] == "+def create_event():"
    assert evidence["commits"][0]["sha"] == "abc123"
    assert evidence["check_runs"]["check_runs"][0]["name"] == "tests"
    assert evidence["reviews"][0]["state"] == "approved"
    assert evidence["comments"][0]["body"] == "Looks good"


@pytest.mark.asyncio
async def test_list_branches_route_returns_branch_data():
    from api.routes.github import list_branches

    fake_client = GitHubClient(token="test-token")
    fake_client.list_branches = AsyncMock(
        return_value=[{"name": "main"}, {"name": "feature/mounesh-events"}]
    )

    with patch("api.routes.github.GitHubSyncService") as service:
        service.return_value.api_service.client = fake_client
        result = await list_branches(
            owner="Mounesh05",
            repo="campusconnect-demo",
            user={"employee_id": "DEMO-CEO"},
        )

    assert result["total"] == 2
    assert result["branches"][1]["name"] == "feature/mounesh-events"


@pytest.mark.asyncio
async def test_project_github_config_validates_and_persists_branch_mapping():
    from api.routes.github import save_project_github_config
    from domain.models.github_project_config import GitHubProjectConfig

    config = GitHubProjectConfig(
        project_id="PRJ-1",
        repository_owner="Mounesh05",
        repository_name="campusconnect-demo",
        repository_url="https://github.com/Mounesh05/campusconnect-demo",
        default_branch="main",
        developer_mappings=[{
            "employee_id": "DEMO-MOUNESH",
            "github_username": "Mounesh05",
            "branch": "feature/mounesh-events",
        }],
    )
    collection = AsyncMock()
    service = AsyncMock()
    service.get_repository_info.return_value = {"default_branch": "main"}
    service.api_service.client.list_branches.return_value = [
        {"name": "main"},
        {"name": "feature/mounesh-events"},
    ]

    with patch("api.routes.github.GitHubSyncService", return_value=service):
        with patch("api.routes.github.col", return_value=collection):
            with patch("api.routes.github.verify_project_access", new=AsyncMock()):
                result = await save_project_github_config(
                    project_id="PRJ-1",
                    config=config,
                    user={"role": "PM"},
                )

    collection.replace_one.assert_awaited_once()
    assert result["default_branch"] == "main"
    assert result["developer_mappings"][0]["branch"] == "feature/mounesh-events"
