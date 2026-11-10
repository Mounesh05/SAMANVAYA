"""
Tests for intelligence.metrics.security, .secrets and .dependencies.
"""

import json
import textwrap

import pytest

from evaluation.security_corpus import CASES
from intelligence.metrics.dependencies import (
    Dependency,
    DependencyVulnerability,
    cvss31_base_score,
    cvss_severity,
    parse_npm_audit,
    parse_package_lock,
    parse_pip_audit,
    parse_pyproject,
    parse_requirements,
    query_osv,
    summarize_dependencies,
)
from intelligence.metrics.secrets import (
    detect_secrets,
    is_high_entropy,
    is_placeholder,
    is_test_path,
    shannon_entropy,
)
from intelligence.metrics.security import analyze_file, analyze_source, security_rating, summarize

ROUTE = "from fastapi import APIRouter\nrouter = APIRouter()\n"


def findings(source):
    result = analyze_source(textwrap.dedent(source))
    assert result.parse_error is None, result.parse_error
    return result.findings


# ── labelled corpus ───────────────────────────────────────────────

@pytest.mark.parametrize("case_id, cwe, source", CASES, ids=[c[0] for c in CASES])
def test_labelled_corpus(case_id, cwe, source):
    found = analyze_source(source, case_id).findings
    if cwe is None:
        assert found == [], f"false alarm: {[(f.rule, f.cwe, f.line) for f in found]}"
    else:
        assert cwe in {f.cwe for f in found}, f"missed CWE-{cwe}: got {[(f.rule, f.cwe) for f in found]}"


def test_corpus_has_both_vulnerable_and_safe_samples():
    vulnerable = sum(1 for _, cwe, _ in CASES if cwe is not None)
    safe = sum(1 for _, cwe, _ in CASES if cwe is None)
    assert vulnerable >= 30 and safe >= 15


# ── taint analysis details ────────────────────────────────────────

def test_taint_message_names_source_and_sink():
    [f] = findings(ROUTE + '''
@router.get("/u")
async def u(name: str):
    cursor.execute(f"SELECT * FROM t WHERE n = '{name}'")
''')
    assert f.rule == "SAM-S201" and f.confidence == "high" and f.line == 6  # 2 header lines + blank line
    assert "request parameter `name`" in f.message and "cursor.execute" in f.message
    assert f.fix.startswith("Use a parameterized query")


def test_taint_confirmed_finding_replaces_pattern_finding_on_same_line():
    found = findings(ROUTE + '''
@router.get("/u")
async def u(name: str):
    cursor.execute(f"SELECT * FROM t WHERE n = '{name}'")
''')
    assert [(f.rule, f.confidence) for f in found] == [("SAM-S201", "high")]   # not also SAM-S113


def test_non_route_function_parameters_are_not_sources():
    # one function at a time: a helper's parameters are not known to be user input
    assert findings('''
def helper(path):
    with open(path) as fh:
        return fh.read()
''') == []


def test_nested_function_does_not_inherit_taint():
    found = findings(ROUTE + '''
@router.get("/u")
async def u(name: str):
    def inner():
        return open(name)
    return inner
''')
    assert found == []


def test_taint_survives_try_and_while():
    found = findings(ROUTE + '''
@router.get("/u")
async def u(cmd: str):
    attempts = 0
    while attempts < 3:
        try:
            current = cmd
        except ValueError:
            current = "true"
        attempts += 1
    os.system(current)
''')
    assert {f.cwe for f in found} == {78}


def test_parse_error_and_file_reading(tmp_path):
    assert analyze_source("def broken(:\n").parse_error is not None
    assert analyze_file(tmp_path / "missing.py").parse_error is not None
    good = tmp_path / "a.py"
    good.write_bytes(b"\xef\xbb\xbfimport yaml\nyaml.load(x)\n")
    result = analyze_file(good, display_path="pkg/a.py")
    assert result.findings[0].path == "pkg/a.py" and result.findings[0].cwe == 502


# ── rating and summary ────────────────────────────────────────────

@pytest.mark.parametrize("severities, rating", [
    ([], "A"), (["low"], "B"), (["low", "medium"], "C"), (["high", "low"], "D"), (["critical", "low"], "E"),
])
def test_security_rating(severities, rating):
    assert security_rating(severities) == rating


def test_summary():
    found = []
    for _, _, source in CASES[:5]:
        found += analyze_source(source).findings
    summary = summarize(found, code_lines=2000)
    data = summary.to_dict()
    assert data["vulnerabilities"] == 5 and data["density"] == 2.5
    assert data["by_cwe"] == {"CWE-89 SQL injection": 5}
    assert data["rating"] == "D" and data["taint_confirmed"] == 5


# ── secrets ───────────────────────────────────────────────────────

def test_entropy_values():
    assert shannon_entropy("aaaa") == 0.0
    assert shannon_entropy("abcd") == 2.0
    assert is_high_entropy("Zx8Kq2LmP9vR4tYw7Nb3Hj6Fd1Sa5Ge0")       # random base64-ish
    assert is_high_entropy("f3a9c0d17b2e4e8a9c6d5b4a3f2e1d0c")       # random hex
    assert not is_high_entropy("created_at_timestamp_field")
    assert not is_high_entropy("short9Xq")                            # under 16 characters


@pytest.mark.parametrize("value", [
    "CHANGE_ME_TO_A_RANDOM_32_BYTE_HEX_STRING", "your-api-key-here", "<token>", "${GITHUB_TOKEN}", "{{ secret }}",
    "xxxxxxxx", "********", "example-key-123", "SECRET_KEY", "$2b$12$abcdefghijklmnopqrstuv", "/etc/ssl/key.pem",
    "https://api.example.com/v1", "null", "test",
])
def test_placeholders(value):
    assert is_placeholder(value)


# Vendor-format fake secrets are assembled from pieces so this file never contains a
# complete secret-shaped string (secret scanners such as GitHub push protection block those).
FAKE_AWS_KEY = "AKIA" + "ABCDEFGHIJKLMNOP"
FAKE_DB_URL = "mongo" + "db://admin:s3cr3tPass@db:27017/app"


@pytest.mark.parametrize("value", ["Zx8Kq2LmP9vR4tYw7Nb3Hj6Fd1Sa5Ge0", "Sup3rS3cret!", "post" + "gres://u:p4ssw0rd@db/app"])
def test_real_values_are_not_placeholders(value):
    assert not is_placeholder(value)


def test_test_paths():
    assert is_test_path("backend/tests/test_x.py") and is_test_path("src/app.spec.ts") and is_test_path("x_test.py")
    assert not is_test_path("backend/core/security.py")


def test_detectors_in_code():
    code = textwrap.dedent('''
        AWS = "@AWS@"
        INTERNAL_TOKEN = "f3a9c0d17b2e4e8a9c6d5b4a3f2e1d0c9b8a7f6e"
        client = Client(token="Zx8Kq2LmP9vR4tYw7Nb3Hj6Fd1Sa5Ge0")
        signing = {"session_key": "Qm9vX2Fq7Lz3Rt8Yp1Wc5Nv6Hb4Kd2Gs"}
        DATABASE_PASSWORD = "CHANGE_ME_PLEASE"
        sort_key = "created_at"
        hint = "Password must contain 12 characters"
        password_hash = hash_password(raw)
    ''').replace("@AWS@", FAKE_AWS_KEY)
    found = {(f.line, f.rule, f.detector) for f in detect_secrets(code, "app/config.py")}
    assert found == {
        (2, "aws_access_key", "known"),
        (3, "api_key_generic", "keyword"),
        (4, "api_key_generic", "keyword"),
        (5, "high_entropy_string", "entropy"),
    }


def test_secret_value_never_stored():
    secret = "Zx8Kq2LmP9vR4tYw7Nb3Hj6Fd1Sa5Ge0"
    [f] = detect_secrets(f'token = "{secret}"\n', "a.py")
    assert secret not in f.snippet and f.snippet.startswith('token = "Zx8')


def test_test_files_are_downgraded_not_dropped():
    [f] = detect_secrets('password = "hunter2hunter2"\n', "backend/tests/test_auth.py")
    assert f.in_test and f.severity == "low" and f.rule == "password_assignment" and f.cwe == 259


def test_config_files_allow_unquoted_values():
    env = "SECRET_KEY=9f2c7a1e5b8d4f6a0c3e9b7d1a5f8c2e\nDB_PASSWORD=Sup3rS3cret!\nGITHUB_TOKEN=\nALGORITHM=HS256\n"
    assert [(f.line, f.rule) for f in detect_secrets(env, "backend/.env")] == [
        (1, "secret_key_generic"), (2, "password_assignment")]
    example = "SECRET_KEY=CHANGE_ME_TO_A_RANDOM_32_BYTE_HEX_STRING\nGITHUB_TOKEN=\n"
    assert detect_secrets(example, "backend/.env.example") == []
    yaml = "db:\n  password: Sup3rS3cret!\n  token: ${{ secrets.TOKEN }}\n  key: !vault abc\n"
    assert [(f.line, f.rule) for f in detect_secrets(yaml, "deploy/values.yaml")] == [(2, "password_assignment")]


def test_code_files_ignore_unquoted_assignments():
    assert detect_secrets("password = get_password()\ntoken = create_token(user)\n", "auth.py") == []


def test_database_url_with_password():
    [f] = detect_secrets(f'MONGO_URI = "{FAKE_DB_URL}"\n', "settings.py")
    assert f.rule == "db_conn_string" and f.severity == "critical"


# ── dependencies: manifests ───────────────────────────────────────

def test_parse_requirements():
    text = textwrap.dedent("""\
        # comment
        Django==4.2.1
        requests[socks] == 2.31.0 ; python_version >= "3.8"
        flask>=2.0,<3
        Some_Package.Name===1.0.0
        pinned-with-hash==1.2.3 \\
            --hash=sha256:abc
        -r other.txt
        -e git+https://github.com/x/y.git#egg=y
        ./local/package
        wild==1.*
    """)
    deps = {d.name: d for d in parse_requirements(text)}
    assert set(deps) == {"django", "requests", "flask", "some-package-name", "pinned-with-hash", "wild"}
    assert deps["django"].version == "4.2.1" and deps["requests"].version == "2.31.0"
    assert deps["flask"].version is None and deps["flask"].specifier == ">=2.0,<3"
    assert deps["some-package-name"].version == "1.0.0" and deps["pinned-with-hash"].version == "1.2.3"
    assert deps["wild"].version is None


def test_parse_pyproject_pep621_and_poetry():
    text = textwrap.dedent("""\
        [project]
        dependencies = ["fastapi==0.110.0", "pydantic>=2"]
        [project.optional-dependencies]
        dev = ["pytest==8.0.0"]
        [tool.poetry.dependencies]
        python = "^3.12"
        httpx = "0.27.0"
        rich = {version = "^13.0"}
        [tool.poetry.group.test.dependencies]
        faker = "30.0.0"
    """)
    deps = {(d.name, d.version, d.dev) for d in parse_pyproject(text)}
    assert ("fastapi", "0.110.0", False) in deps and ("pydantic", None, False) in deps
    assert ("pytest", "8.0.0", True) in deps and ("httpx", "0.27.0", False) in deps
    assert ("rich", None, False) in deps and ("faker", "30.0.0", True) in deps
    assert not any(name == "python" for name, _, _ in deps)


def test_parse_package_lock_v3_and_v1():
    v3 = {"lockfileVersion": 3, "packages": {
        "": {"name": "app"},
        "node_modules/lodash": {"version": "4.17.20"},
        "node_modules/@scope/pkg": {"version": "1.0.0", "dev": True},
        "node_modules/a/node_modules/lodash": {"version": "3.10.1"},
        "node_modules/linked": {"link": True},
    }}
    deps = {(d.name, d.version, d.dev) for d in parse_package_lock(json.dumps(v3))}
    assert deps == {("lodash", "4.17.20", False), ("@scope/pkg", "1.0.0", True), ("lodash", "3.10.1", False)}
    v1 = {"lockfileVersion": 1, "dependencies": {"express": {"version": "4.17.1", "dependencies": {"qs": {"version": "6.7.0"}}}}}
    assert {(d.name, d.version) for d in parse_package_lock(json.dumps(v1))} == {("express", "4.17.1"), ("qs", "6.7.0")}


# ── dependencies: CVSS ────────────────────────────────────────────

@pytest.mark.parametrize("vector, score", [
    ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", 9.8),
    ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H", 10.0),
    ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N", 7.5),
    ("CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N", 6.1),
    ("CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H", 7.8),
    ("CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:H", 9.9),
    ("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N", 0.0),
])
def test_cvss31_reference_scores(vector, score):
    assert cvss31_base_score(vector) == score


@pytest.mark.parametrize("vector", ["CVSS:3.1/AV:N/AC:L", "CVSS:3.1/AV:X/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", "garbage"])
def test_cvss_invalid_vectors(vector):
    with pytest.raises(ValueError):
        cvss31_base_score(vector)


@pytest.mark.parametrize("score, severity", [(9.0, "critical"), (8.9, "high"), (7.0, "high"), (6.9, "medium"),
                                             (4.0, "medium"), (3.9, "low"), (0.1, "low"), (0.0, "none"), (None, "unknown")])
def test_cvss_severity_bands(score, severity):
    assert cvss_severity(score) == severity


# ── dependencies: audit reports ───────────────────────────────────

PIP_AUDIT_2X = json.dumps({"dependencies": [
    {"name": "Django", "version": "3.2.0", "vulns": [
        {"id": "PYSEC-2021-98", "fix_versions": ["3.2.1"], "aliases": ["CVE-2021-31542"], "description": "Path traversal"}]},
    {"name": "requests", "version": "2.31.0", "vulns": []},
    {"name": "local-pkg", "skip_reason": "not on PyPI"},
], "fixes": []})


def test_pip_audit_2x_format():
    [v] = parse_pip_audit(PIP_AUDIT_2X)
    assert (v.package, v.version, v.vuln_id, v.fixed_versions, v.aliases) == (
        "django", "3.2.0", "PYSEC-2021-98", ("3.2.1",), ("CVE-2021-31542",))
    assert v.severity == "unknown" and v.fix_available


def test_pip_audit_legacy_list_format():
    legacy = json.dumps([{"name": "flask", "version": "0.12", "id": "PYSEC-2018-66", "severity": "high"}])
    [v] = parse_pip_audit(legacy)
    assert (v.package, v.vuln_id, v.severity) == ("flask", "PYSEC-2018-66", "high")


def test_npm_audit():
    report = {"auditReportVersion": 2, "vulnerabilities": {
        "lodash": {"severity": "high", "fixAvailable": {"name": "lodash", "version": "4.17.21"}, "via": [
            {"source": 1065, "url": "https://github.com/advisories/GHSA-35jh-r3h4-6jhm", "title": "Command injection",
             "severity": "high", "cvss": {"score": 7.2, "vectorString": "CVSS:3.1/AV:N/AC:L/PR:H/UI:N/S:U/C:H/I:H/A:H"}}]},
        "express": {"severity": "moderate", "fixAvailable": True, "via": ["qs"]},
    }}
    [v] = parse_npm_audit(json.dumps(report))
    assert (v.package, v.severity, v.cvss_score, v.fixed_versions) == ("lodash", "high", 7.2, ("4.17.21",))


# ── dependencies: OSV (fakes only, no network) ────────────────────

def test_query_osv_with_fake_api():
    posted, fetched = [], []

    def post(url, body):
        posted.append((url, body))
        return {"results": [{"vulns": [{"id": "GHSA-1"}]}, {}]}

    def get(url):
        fetched.append(url)
        return {"id": "GHSA-1", "summary": "RCE", "aliases": ["CVE-2024-1"],
                "severity": [{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"}],
                "affected": [{"package": {"name": "django", "ecosystem": "PyPI"},
                              "ranges": [{"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": "3.2.4"}]}]}]}

    deps = [Dependency("django", "3.2.0", "PyPI"), Dependency("flask", "2.0.0", "PyPI"), Dependency("rich", None, "PyPI")]
    [v] = query_osv(deps, post_json=post, get_json=get)
    assert (v.package, v.severity, v.cvss_score, v.fixed_versions) == ("django", "critical", 9.8, ("3.2.4",))
    assert len(posted[0][1]["queries"]) == 2          # unpinned "rich" is not sent
    assert fetched == ["https://api.osv.dev/v1/vulns/GHSA-1"]


def test_dependency_summary_deduplicates_sources():
    a = DependencyVulnerability("django", "3.2.0", "PyPI", "PYSEC-1", "unknown", source="pip-audit", fixed_versions=("3.2.1",))
    b = DependencyVulnerability("django", "3.2.0", "PyPI", "PYSEC-1", "high", source="osv")
    c = DependencyVulnerability("lodash", None, "npm", "GHSA-2", "medium", source="npm-audit")
    summary = summarize_dependencies([a, b, c])
    data = summary.to_dict()
    assert data["vulnerabilities"] == 2 and data["packages_affected"] == 2
    assert data["by_severity"]["high"] == 1 and data["worst_severity"] == "high"
    assert summarize_dependencies([]).worst_severity is None
