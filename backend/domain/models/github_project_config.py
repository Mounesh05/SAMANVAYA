"""Persistent GitHub repository configuration for a Samanvaya project."""

from typing import Optional

from pydantic import BaseModel, Field


class DeveloperBranchMapping(BaseModel):
    """Maps one Samanvaya employee to a verified GitHub branch."""

    employee_id: str
    github_username: str
    branch: str


class GitHubProjectConfig(BaseModel):
    """Repository and verified developer branch settings for a project."""

    project_id: str
    repository_owner: str
    repository_name: str
    repository_url: str
    default_branch: str
    developer_mappings: list[DeveloperBranchMapping] = Field(default_factory=list)
    # DORA: which GitHub deployment environments are production, and (for teams
    # that deploy with a GitHub Actions workflow instead of GitHub Deployments)
    # the name of that workflow; its successful runs on the default branch count
    # as production deployments.
    production_environments: list[str] = Field(default_factory=lambda: ["production", "prod", "live"])
    deploy_workflow: Optional[str] = None
