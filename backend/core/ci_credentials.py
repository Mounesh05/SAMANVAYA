"""Credentials for a project's QA result uploader."""

import hmac
import json

from core.config import settings


def project_ci_token(project_id: str, repository: str) -> str:
    # Legacy repository secrets may contain QA_TEST_RESULTS_TOKEN. Only the
    # application holds the signing key used to derive scoped credentials.
    scope = json.dumps(["qa-upload-v1", settings.QA_TEST_RESULTS_TOKEN, project_id, repository.casefold()])
    return "qa1." + hmac.digest(settings.SECRET_KEY.encode(), scope.encode(), "sha256").hex()
