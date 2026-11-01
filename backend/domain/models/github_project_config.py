"""Persistent GitHub repository configuration for a Samanvaya project."""

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
