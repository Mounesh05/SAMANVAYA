import pytest
from pydantic import ValidationError

from api.routes.code_quality import AnalyzeRequest
from api.routes.evaluation import SimpleEvalRequest


def test_evaluation_rejects_non_positive_pull_request_numbers():
    for pr_number in (0, -1):
        with pytest.raises(ValidationError):
            SimpleEvalRequest(
                github_username="developer",
                repo_owner="owner",
                repo_name="repo",
                pr_number=pr_number,
                human_score=7,
            )


def test_evaluation_rejects_human_scores_outside_zero_to_ten():
    for score in (-0.1, 0, 10.1, 11):
        with pytest.raises(ValidationError):
            SimpleEvalRequest(
                github_username="developer",
                repo_owner="owner",
                repo_name="repo",
                human_score=score,
            )


def test_code_quality_rejects_non_positive_pull_request_numbers():
    with pytest.raises(ValidationError):
        AnalyzeRequest(repository_id="owner/repo", pr_number=0)
