from contextlib import closing
from io import BytesIO
import json
from pathlib import Path
from runpy import run_path
from unittest.mock import Mock
from urllib.error import URLError

import pytest


action = run_path(str(Path(__file__).resolve().parents[2] / ".github/actions/samanvaya-release-gate/check.py"))
scope = {"project_id": "P", "repository": "owner/repo", "revision": "b" * 40, "task_id": "TSK-1234ABCD",
         "environment": "production"}
env = {"SAMANVAYA_API_URL": "https://example.test", "SAMANVAYA_PROJECT_ID": "P", "GITHUB_REPOSITORY": "owner/repo",
       "SAMANVAYA_RELEASE_SHA": scope["revision"], "SAMANVAYA_TASK_ID": scope["task_id"], "SAMANVAYA_RELEASE_GATE_TOKEN": "fixture"}
candidate = {"project_id": "P", "repository": "owner/repo", "revision": "b" * 40,
             "environment": "production", "release_id": "RL-" + "c" * 32,
             "artifact_id": 5273, "artifact_digest": "d" * 64}
candidate_env = {**env, "SAMANVAYA_TASK_ID": "", "SAMANVAYA_RELEASE_ID": candidate["release_id"],
                 "SAMANVAYA_ARTIFACT_ID": "5273", "SAMANVAYA_ARTIFACT_DIGEST": "d" * 64}


def transport(body):
    return raw_transport(json.dumps(body).encode())


def raw_transport(body, status=200):
    response = BytesIO(body)
    response.status = status
    return Mock(open=Mock(return_value=closing(response)))


def test_exact_approval_for_deployed_commit():
    server = transport({**scope, "allowed": True})
    action["check"](env, server)
    request = server.open.call_args.args[0]
    assert request.full_url == "https://example.test/api/release-gates/check"
    assert json.loads(request.data) == scope
    assert request.get_header("X-release-gate-token") == "fixture"


@pytest.mark.parametrize("override", [{"allowed": False}, {"allowed": 1}, {"revision": "a" * 40},
                                      {"environment": "staging"}, {"repository": "other/repo"}, {"task_id": "different"}])
def test_denies_mismatched_approval(override):
    with pytest.raises(ValueError):
        action["check"](env, transport({**scope, "allowed": True, **override}))


def test_refuses_plaintext_and_redirects():
    server = Mock()
    with pytest.raises(ValueError):
        action["check"]({**env, "SAMANVAYA_API_URL": "http://example.test"}, server)
    server.open.assert_not_called()
    assert action["NoRedirect"]().redirect_request(None) is None


def test_release_mode_checks_exact_manifest_and_artifact():
    server = transport({**candidate, "allowed": True})
    action["check"](candidate_env, server)
    request = server.open.call_args.args[0]
    assert json.loads(request.data) == candidate
    assert server.open.call_args.kwargs["timeout"] == 15


@pytest.mark.parametrize("diff", [
    {"release_id": "RL-" + "e" * 32}, {"artifact_digest": "e" * 64}, {"artifact_id": "5273"},
    {"artifact_id": 5273.0}, {"artifact_id": 5274}, {"artifact_digest": None},
    {"revision": "e" * 40}, {"allowed": False}, {"environment": "staging"},
])
def test_release_mode_denies_inconsistent_approval(diff):
    with pytest.raises(ValueError):
        action["check"](candidate_env, transport({**candidate, "allowed": True, **diff}))


@pytest.mark.parametrize("diff", [
    {"SAMANVAYA_TASK_ID": scope["task_id"]},
    {"SAMANVAYA_RELEASE_ID": ""},
    {"SAMANVAYA_ARTIFACT_ID": "01"},
    {"SAMANVAYA_ARTIFACT_ID": "0"},
    {"SAMANVAYA_ARTIFACT_ID": "9223372036854775808"},
    {"SAMANVAYA_ARTIFACT_DIGEST": "sha256:" + "d" * 64},
    {"SAMANVAYA_ARTIFACT_DIGEST": "D" * 64},
    {"SAMANVAYA_ENVIRONMENT": "staging"},
])
def test_release_mode_rejects_invalid_and_mixed_inputs_before_sending_token(diff):
    server = Mock()
    with pytest.raises(ValueError):
        action["check"]({**candidate_env, **diff}, server)
    server.open.assert_not_called()


def test_legacy_mode_cannot_silently_ignore_artifact_inputs():
    server = Mock()
    with pytest.raises(ValueError):
        action["check"]({**env, "SAMANVAYA_ARTIFACT_ID": "5273"}, server)
    server.open.assert_not_called()


@pytest.mark.parametrize("raw", [b"{}", b"not JSON", b'"approve"', b"x" * 8193])
def test_malformed_release_response_fails_closed(raw):
    with pytest.raises(ValueError):
        action["check"](candidate_env, raw_transport(raw))


def test_release_response_rejects_ambiguous_duplicate_fields():
    body = json.dumps({**candidate, "allowed": True}).encode()[:-1]
    with pytest.raises(ValueError):
        action["check"](candidate_env, raw_transport(b'{"allowed":false,' + body[1:] + b"}"))


def test_cli_fails_closed_when_the_api_is_unavailable(monkeypatch, capsys):
    for key, value in candidate_env.items():
        monkeypatch.setenv(key, value)
    def unavailable(*args, **kwargs):
        raise URLError("private transport detail")
    monkeypatch.setattr("urllib.request.build_opener", lambda *args: Mock(open=unavailable))
    with pytest.raises(SystemExit) as exc:
        run_path(action["__file__"], run_name="__main__")
    assert isinstance(exc.value.code, str)
    assert "fixture" not in exc.value.code and "private transport detail" not in exc.value.code
    assert capsys.readouterr().out == ""
