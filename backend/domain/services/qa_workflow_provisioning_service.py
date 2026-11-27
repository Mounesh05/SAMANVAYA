"""Install the managed QA scripts, workflow and Actions secrets in a linked repository."""

from pathlib import Path
from typing import Any

from core.ci_credentials import project_ci_token
from core.config import settings
from integrations.github.client import GitHubClient


TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "integrations/github/qa_templates"
RUN_TESTS_SCRIPT_PATH = "ci/run_tests.sh"
UPLOAD_SCRIPT_PATH = "ci/upload_junit_results.py"
WORKFLOW_PATH = ".github/workflows/samanvaya-qa.yml"


class QAWorkflowProvisioningService:
    def __init__(self, github_client: GitHubClient | None = None):
        self.github = github_client or GitHubClient()

    async def provision(
        self, owner: str, repo: str, project_id: str, branch: str | None = None
    ) -> dict[str, Any]:
        if not settings.SAMANVAYA_PUBLIC_API_URL:
            raise ValueError("SAMANVAYA_PUBLIC_API_URL must be configured before provisioning")
        if not settings.SAMANVAYA_PUBLIC_API_URL.startswith("https://"):
            raise ValueError("SAMANVAYA_PUBLIC_API_URL must be an HTTPS public URL")
        if not settings.QA_TEST_RESULTS_TOKEN:
            raise ValueError("QA_TEST_RESULTS_TOKEN must be configured before provisioning")

        # Load every template before writing secrets. Install the workflow last so it can find both scripts.
        files = {
            path: ((TEMPLATE_DIR / Path(path).name).read_text(encoding="utf-8"), message)
            for path, message in (
                (RUN_TESTS_SCRIPT_PATH, "chore: provision Samanvaya CI test execution script"),
                (UPLOAD_SCRIPT_PATH, "chore: provision Samanvaya CI result upload script"),
                (WORKFLOW_PATH, "chore: provision Samanvaya QA workflow"),
            )
        }
        repository = await self.github.get_repository(owner, repo)
        public_key = await self.github.get_actions_public_key(owner, repo)
        for name, value in {
            "SAMANVAYA_API_URL": settings.SAMANVAYA_PUBLIC_API_URL,
            "SAMANVAYA_PROJECT_ID": project_id,
            "SAMANVAYA_TEST_RESULTS_TOKEN": project_ci_token(project_id, f"{owner}/{repo}"),
        }.items():
            await self.github.set_actions_secret(owner, repo, name, value, public_key)

        target_branch = branch or repository.get("default_branch")
        workflow_url = None
        for path, (content, message) in files.items():
            existing = await self.github.get_file(owner, repo, path, ref=target_branch)
            result = await self.github.upsert_file(
                owner, repo, path, content, message, branch=target_branch,
                sha=existing.get("sha") if existing else None,
            )
            if path == WORKFLOW_PATH:
                workflow_url = result.get("content", {}).get("html_url")
        return {
            "repository": f"{owner}/{repo}",
            "project_id": project_id,
            "branch": target_branch,
            "workflow_path": WORKFLOW_PATH,
            "workflow_url": workflow_url,
            "status": "provisioned",
        }
