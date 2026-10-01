import pytest

from api.roles import devops, qa
from api.routes import qa_test_runs
from domain.services import qa_workflow_provisioning_service


class FakeCursor:
    def __init__(self, documents):
        self.documents = documents

    def sort(self, *_args):
        return self

    def limit(self, *_args):
        return self

    async def to_list(self, *_args):
        return self.documents


class FakeCollection:
    def __init__(self, documents):
        self.documents = documents

    def find(self, *_args):
        return FakeCursor(self.documents)

    async def replace_one(self, *_args, **_kwargs):
        return None


class FakeTaskRepository:
    async def find_all(self, _query):
        return [
            {"id": "BUG-1", "type": "bug", "status": "open", "priority": "critical"},
            {"id": "BUG-2", "type": "bug", "status": "done", "priority": "low"},
        ]


@pytest.mark.anyio
async def test_qa_snapshot_aggregates_test_runs_and_open_bugs(monkeypatch):
    monkeypatch.setattr(qa, "TaskRepository", FakeTaskRepository)
    monkeypatch.setattr(
        qa,
        "col",
        lambda _name: FakeCollection(
            [{"tests_run": 10, "tests_passed": 8, "tests_failed": 2}]
        ),
    )

    snapshot = await qa._qa_snapshot()

    assert snapshot["total_tests"] == 10
    assert snapshot["passed_tests"] == 8
    assert snapshot["failed_tests"] == 2
    assert len(snapshot["open_bugs"]) == 1
    assert snapshot["regression_risk"] == "HIGH"


def test_qa_test_suite_view_normalizes_ci_fields():
    suite = qa._test_suite_view(
        {
            "test_suite": "github-actions",
            "status": "failed",
            "tests_run": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "tests_skipped": 0,
            "duration_seconds": 12.5,
            "repository": "Mounesh05/vaani-restaurant-automation",
        }
    )

    assert suite["name"] == "github-actions"
    assert suite["status"] == "failed"
    assert suite["total"] == 0
    assert suite["pass_rate"] == 0
    assert suite["duration"] == 12.5


def test_qa_test_health_marks_zero_test_failures_as_blocking():
    failed = qa._test_suite_view(
        {"test_suite": "github-actions", "status": "failed", "tests_run": 0}
    )
    passed = qa._test_suite_view(
        {"test_suite": "backend", "status": "passed", "tests_run": 54, "tests_passed": 54}
    )

    assert failed["status"] == "failed"
    assert failed["total"] == 0
    assert passed["pass_rate"] == 100.0


@pytest.mark.anyio
async def test_devops_snapshot_uses_workflow_and_deployment_events(monkeypatch):
    monkeypatch.setattr(
        devops,
        "col",
        lambda _name: FakeCollection(
            [
                {
                    "event_type": "workflow_run",
                    "payload": {"workflow_run": {"conclusion": "success"}},
                },
                {
                    "event_type": "deployment_status",
                    "payload": {"deployment_status": {"state": "failure"}},
                },
            ]
        ),
    )

    snapshot = await devops._devops_snapshot()

    assert len(snapshot["pipelines"]) == 1
    assert len(snapshot["deployments"]) == 1
    assert snapshot["successful"] == 1
    assert snapshot["failed"] == 1


@pytest.mark.anyio
async def test_test_run_submission_is_idempotent_and_persists(monkeypatch):
    stored = {}

    class Collection:
        async def replace_one(self, query, document, upsert):
            stored.update(document)
            assert query["id"] == document["id"]
            assert upsert is True

    monkeypatch.setattr(qa_test_runs.settings, "QA_TEST_RESULTS_TOKEN", "ci-secret")
    monkeypatch.setattr(qa_test_runs, "col", lambda _name: Collection())

    response = await qa_test_runs.submit_test_run(
        qa_test_runs.TestRunSubmission(
            project_id="PROJ-1",
            repository="Mounesh05/SAMANVAYA",
            branch="testing",
            commit_sha="abcdef1234567",
            test_suite="backend",
            tests_run=10,
            tests_passed=8,
            tests_failed=2,
            status="failed",
        ),
        "ci-secret",
    )

    assert response["status"] == "accepted"
    assert stored["tests_failed"] == 2


def test_test_run_submission_rejects_inconsistent_counts():
    with pytest.raises(ValueError):
        qa_test_runs.TestRunSubmission(
            project_id="PROJ-1",
            repository="repo",
            branch="testing",
            commit_sha="abcdef1234567",
            test_suite="backend",
            tests_run=1,
            tests_passed=1,
            tests_failed=1,
            status="failed",
        )


@pytest.mark.anyio
async def test_qa_workflow_provisioning_updates_secrets_and_workflow(monkeypatch):
    calls = []

    class FakeGitHubClient:
        async def get_repository(self, owner, repo):
            return {"default_branch": "main"}

        async def get_actions_public_key(self, owner, repo):
            return {"key": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=", "key_id": "key-1"}

        async def set_actions_secret(self, owner, repo, name, value, public_key):
            calls.append(("secret", name, value))

        async def get_file(self, owner, repo, path, ref=None):
            return None

        async def upsert_file(self, owner, repo, path, content, message, branch, sha):
            calls.append(("workflow", path, branch, "Samanvaya QA" in content))
            return {"content": {"html_url": "https://github.com/example/repo/blob/main/.github/workflows/samanvaya-qa.yml"}}

    monkeypatch.setattr(
        qa_workflow_provisioning_service.settings,
        "SAMANVAYA_PUBLIC_API_URL",
        "https://samanvaya.example",
    )
    monkeypatch.setattr(
        qa_workflow_provisioning_service.settings,
        "QA_TEST_RESULTS_TOKEN",
        "ci-secret",
    )

    result = await qa_workflow_provisioning_service.QAWorkflowProvisioningService(
        FakeGitHubClient()
    ).provision("example", "repo", "PRJ-1")

    assert result["status"] == "provisioned"
    assert [call[1] for call in calls[:3]] == [
        "SAMANVAYA_API_URL",
        "SAMANVAYA_PROJECT_ID",
        "SAMANVAYA_TEST_RESULTS_TOKEN",
    ]
    assert calls[-1] == ("workflow", ".github/workflows/samanvaya-qa.yml", "main", True)


@pytest.mark.anyio
async def test_qa_workflow_provisioning_requires_https_public_url(monkeypatch):
    monkeypatch.setattr(
        qa_workflow_provisioning_service.settings,
        "SAMANVAYA_PUBLIC_API_URL",
        "http://localhost:8001",
    )
    monkeypatch.setattr(
        qa_workflow_provisioning_service.settings,
        "QA_TEST_RESULTS_TOKEN",
        "ci-secret",
    )

    with pytest.raises(ValueError, match="HTTPS public URL"):
        await qa_workflow_provisioning_service.QAWorkflowProvisioningService(
            object()
        ).provision("example", "repo", "PRJ-1")
