"""Exit successfully only for a matching affirmative production gate response."""

import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate field in gate response.")
        result[key] = value
    return result


def check(env, transport):
    api_url = env["SAMANVAYA_API_URL"]
    base = urlsplit(api_url)
    if (base.scheme != "https" or not base.hostname or base.username is not None or base.password is not None
            or base.query or base.fragment or re.search(r"[\s\x00-\x1f\\]", api_url)):
        raise ValueError("Configure an HTTPS server URL.")
    payload = {
        "repository": env["GITHUB_REPOSITORY"], "revision": env["SAMANVAYA_RELEASE_SHA"],
        "project_id": env["SAMANVAYA_PROJECT_ID"], "environment": env.get("SAMANVAYA_ENVIRONMENT", "production"),
    }
    token = env["SAMANVAYA_RELEASE_GATE_TOKEN"]
    if (not re.fullmatch(r"[0-9a-f]{40}", payload["revision"]) or not token
            or not all(payload.values()) or payload["environment"] != "production"):
        raise ValueError("Provide the project, repository, production environment, credential and exact commit.")
    task_id = env.get("SAMANVAYA_TASK_ID", "")
    release_id = env.get("SAMANVAYA_RELEASE_ID", "")
    artifact_id = env.get("SAMANVAYA_ARTIFACT_ID", "")
    artifact_digest = env.get("SAMANVAYA_ARTIFACT_DIGEST", "")
    if task_id and not any((release_id, artifact_id, artifact_digest)):
        payload["task_id"] = task_id
    elif (not task_id and re.fullmatch(r"RL-[0-9a-f]{32}", release_id)
          and re.fullmatch(r"[1-9][0-9]{0,18}", artifact_id) and int(artifact_id) < 2**63
          and re.fullmatch(r"[0-9a-f]{64}", artifact_digest)):
        payload.update(release_id=release_id, artifact_id=int(artifact_id), artifact_digest=artifact_digest)
    else:
        raise ValueError("Provide either a task ID or a release ID with its artifact ID and SHA-256 digest.")
    req = Request(base.geturl().rstrip("/") + "/api/release-gates/check",
                  data=json.dumps(payload).encode(), headers={"Content-Type": "application/json",
                  "Accept": "application/json", "X-Release-Gate-Token": token}, method="POST")
    with transport.open(req, timeout=15) as response:
        raw = response.read(8193)
        if response.status != 200 or len(raw) > 8192:
            raise ValueError("Invalid gate response.")
        result = json.loads(raw, object_pairs_hook=unique_fields)
    if (not isinstance(result, dict) or result.get("allowed") is not True
            or any(type(result.get(key)) is not type(value) or result[key] != value for key, value in payload.items())):
        raise ValueError("Release approval does not match this deployment.")


if __name__ == "__main__":
    try:
        check(os.environ, build_opener(NoRedirect()))
    except HTTPError as error:
        sys.exit(f"Release gate denied the check (HTTP {error.code}). Review the candidate in Samanvaya.")
    except (URLError, KeyError, ValueError, OSError):
        sys.exit("Release gate unavailable or response invalid. Check the configuration and candidate evidence.")
    print("Samanvaya confirmed QA verification and DevOps approval for the requested production commit.")
