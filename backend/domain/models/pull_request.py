"""
Pull Request domain models.
PRs are automatically collected from GitHub and analyzed for risk.
"""

from pydantic import BaseModel
from typing import Optional


class PRCreate(BaseModel):
    """Request model for creating/importing a PR from GitHub."""
    
    pr_number: int
    repo_id: str
    project_id: str
    title: str
    author_id: str
    author_login: str
    branch: str
    base_branch: str = "main"


class PullRequest(PRCreate):
    """Complete PR model with analysis results."""
    
    id: str
    status: str = "open"  # open|merged|closed
    review_status: str = "pending"  # pending|in_review|approved|changes_requested
    ci_status: Optional[str] = None  # pending|passing|failing
    
    # AI-calculated fields (from Layer 5 Intelligence + Layer 6 Agents)
    alignment_score: Optional[int] = None  # 0-100
    risk_score: Optional[int] = None  # 0-100
    risk_level: Optional[str] = None  # LOW|MEDIUM|HIGH|CRITICAL
    
    # GitHub metadata
    files_changed_count: Optional[int] = None
    commit_count: Optional[int] = None
    
    created_at: str = ""
    merged_at: Optional[str] = None
    # Set by GitHub sync for PR metrics (intelligence/metrics/pull_requests.py)
    closed_at: Optional[str] = None
    lines_added: Optional[int] = None              # generated / lock files excluded
    lines_deleted: Optional[int] = None
    generated_lines_excluded: Optional[int] = None
    size_bucket: Optional[str] = None              # XS | S | M | L | XL
    first_review_at: Optional[str] = None          # first human review
    review_rounds: Optional[int] = None            # "changes requested" reviews
    reviews: Optional[list] = None                 # [{reviewer, is_bot, state, submitted_at}]
