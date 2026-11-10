"""
Integration of the security metrics with the evidence package, the secrets
scanner, the Python analyzer, the evidence merger and the QualityEngine.
"""

import asyncio
import json
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest

from domain.models.risk_configuration import QualityDimensionWeights
from intelligence.analyzers.common.secrets_scanner import scan_secrets
from intelligence.analyzers.common.security_checks import apply_security_metrics, merge_findings
from intelligence.analyzers.python.analyzer import PythonAnalyzer
from intelligence.evidence.merger import EvidenceMerger
from intelligence.evidence.models import CodeQualityEvidence, Finding, SecurityEvidence, SeverityEnum
from intelligence.metrics.dependencies import DependencyVulnerability
from intelligence.quality_engine import QualityEngine

VULNERABLE = textwrap.dedent('''
    from fastapi import APIRouter
    router = APIRouter()

    @router.get("/users")
    async def find(name: str):
        cursor.execute(f"SELECT * FROM users WHERE name = '{name}'")

    def load(raw):
        return yaml.load(raw)
''')  # SQL injection on line 7, yaml.load on line 10

SAFE = "def add(a, b):\n    return a + b\n"


def evidence(**overrides) -> CodeQualityEvidence:
    data = {"repository_id": "repo-1", "primary_language": "python"}
    data.update(overrides)
    return CodeQualityEvidence(**data)


def finding(severity=SeverityEnum.CRITICAL, category="security", **kw) -> Finding:
    data = dict(file_path="a.py", line_number=1, rule_id="R", category=category, severity=severity,
                source_tool="t", message="m")
    data.update(kw)
    return Finding(**data)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    (root / "api").mkdir(parents=True)
    (root / "api" / "users.py").write_text(VULNERABLE, encoding="utf-8")
    (root / "api" / "math.py").write_text(SAFE, encoding="utf-8")
    (root / "settings.py").write_text('API_TOKEN = "Zx8Kq2LmP9vR4tYw7Nb3Hj6Fd1Sa5Ge0"\n', encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_auth.py").write_text('password = "hunter2hunter2"\n', encoding="utf-8")
    (tmp_path / "outside.py").write_text('SECRET_KEY = "Qm9vX2Fq7Lz3Rt8Yp1Wc5Nv6Hb4Kd2Gs"\n', encoding="utf-8")
    return root


@pytest.fixture
def engine():
    eng = QualityEngine()

    async def defaults(project_id=None):
        return SimpleNamespace(quality_weights=QualityDimensionWeights())

    eng._config_service = SimpleNamespace(get_configuration=defaults)
    return eng


# ── counting: each finding once ───────────────────────────────────

def test_secret_in_static_findings_and_counts_is_counted_once():
    secret = finding()
    ev = evidence(static_findings=[secret], security=SecurityEvidence(critical_count=1, findings=[secret]))
    assert ev.total_critical_findings == 1          # was 2 before the fix


def test_count_only_tool_results_still_count():
    # C/C++/Java analyzers report some security tools as counts without listed findings
    ev = evidence(static_findings=[finding()], security=SecurityEvidence(critical_count=3))
    assert ev.total_critical_findings == 3           # 1 listed secret + 2 count-only


@pytest.mark.asyncio
async def test_engine_penalty_counts_a_secret_once(engine):
    secret = finding()
    ev = evidence(static_findings=[secret], security=SecurityEvidence(critical_count=1))
    result = await engine.calculate(ev)
    assert result["penalties"]["static_security"] == 10.0   # one critical = 10 (was 20)
    assert "security" not in result                          # no SAMANVAYA security metrics computed


# ── secrets scanner adapter ───────────────────────────────────────

def test_scan_secrets_format_paths_and_test_files(repo):
    found = scan_secrets(["settings.py", "tests/test_auth.py", "../outside.py", "api/math.py"], str(repo))
    by_file = {f.file_path: f for f in found}
    assert set(by_file) == {"settings.py", "tests/test_auth.py"}       # outside.py rejected
    token = by_file["settings.py"]
    assert token.rule_id == "SEC-SECRET-API_KEY_GENERIC" and token.category == "security"
    assert token.severity == SeverityEnum.HIGH and token.cwe == 798 and token.source_tool == "secrets-scanner"
    assert "Zx8Kq2LmP9vR4tYw7Nb3Hj6Fd1Sa5Ge0" not in token.code_snippet
    test_pw = by_file["tests/test_auth.py"]
    assert test_pw.severity == SeverityEnum.LOW and test_pw.message.endswith("(test file)")


# ── merging with bandit ───────────────────────────────────────────

def test_merge_keeps_ours_on_same_file_line_cwe():
    ours = [finding(file_path="api/users.py", line_number=7, cwe=89, source_tool="samanvaya-security")]
    bandit_same = finding(file_path="api\\users.py", line_number=7, cwe=89, source_tool="bandit")
    bandit_other = finding(file_path="api/users.py", line_number=9, cwe=502, source_tool="bandit")
    bandit_no_cwe = finding(file_path="api/users.py", line_number=7, cwe=None, source_tool="bandit")
    merged = merge_findings(ours, [bandit_same, bandit_other, bandit_no_cwe])
    assert [f.source_tool for f in merged] == ["samanvaya-security", "bandit", "bandit"]
    assert bandit_same not in merged


# ── apply_security_metrics ────────────────────────────────────────

def test_apply_security_metrics(repo):
    secret = scan_secrets(["settings.py"], str(repo))[0]
    bandit_dup = finding(file_path="api/users.py", line_number=10, cwe=502, severity=SeverityEnum.MEDIUM,
                         source_tool="bandit", rule_id="BANDIT-B506")
    ev = evidence(static_findings=[secret], security=SecurityEvidence(findings=[bandit_dup], dependency_vulnerabilities=[
        {"package": "django", "version": "3.2.0", "ecosystem": "PyPI", "id": "PYSEC-1", "severity": "high",
         "fix_versions": ["3.2.1"]}]))
    apply_security_metrics(ev, ["api/users.py", "api/math.py", "../outside.py"], str(repo))
    sec = ev.security
    rules = sorted(f.rule_id for f in sec.findings)
    assert rules == ["SAM-S104", "SAM-S201", "SEC-SECRET-API_KEY_GENERIC"]   # bandit duplicate dropped
    sql = next(f for f in sec.findings if f.rule_id == "SAM-S201")
    assert sql.cwe == 89 and sql.line_number == 7 and "confirmed by taint analysis" in sql.message
    assert sql.suggested_fix.startswith("Use a parameterized query")
    assert (sec.critical_count, sec.high_count, sec.medium_count) == (0, 3, 0)
    assert sec.rating == "D"
    assert sec.by_cwe == {"CWE-89 SQL injection": 1, "CWE-502 Deserialization of untrusted data": 1,
                          "CWE-798 Hard-coded credentials": 1}
    assert sec.vulnerability_density > 0
    assert sec.dependency_summary["vulnerabilities"] == 1 and sec.dependency_summary["fixable"] == 1
    assert "samanvaya-security" in ev.tools_executed
    assert ev.total_high_findings == 3                                      # secret counted once


def test_apply_security_metrics_clean_code_rates_a(repo):
    ev = evidence()
    apply_security_metrics(ev, ["api/math.py"], str(repo))
    assert ev.security.rating == "A" and ev.security.findings == [] and ev.security.vulnerability_density == 0.0


@pytest.mark.asyncio
async def test_engine_reports_security_section(engine, repo):
    ev = evidence()
    apply_security_metrics(ev, ["api/users.py"], str(repo))
    result = await engine.calculate(ev)
    section = result["security"]
    assert section["rating"] == "D" and section["high"] == 2
    assert "CWE-89 SQL injection" in section["by_cwe"]
    assert result["penalties"]["static_security"] == 10.0                   # 2 high x 5


def test_merger_keeps_worst_rating_and_sums_cwe_counts():
    a = evidence(security=SecurityEvidence(rating="B", by_cwe={"CWE-89 SQL injection": 1}, vulnerability_density=1.0))
    b = evidence(primary_language="javascript",
                 security=SecurityEvidence(rating="D", by_cwe={"CWE-89 SQL injection": 2}))
    merged = EvidenceMerger.merge([a, b])
    assert merged.security.rating == "D" and merged.security.by_cwe == {"CWE-89 SQL injection": 3}


# ── Python analyzer end to end ────────────────────────────────────

def test_python_analyzer_end_to_end(repo, monkeypatch):
    monkeypatch.setattr(PythonAnalyzer, "_tool_available", lambda self, tool: False)   # no external tools
    files = ["api/users.py", "api/math.py", "settings.py", "../outside.py"]
    ev = asyncio.run(PythonAnalyzer().analyze(files, str(repo), {"project_id": "p"}))
    rules = {f.rule_id for f in ev.security.findings}
    assert {"SAM-S201", "SAM-S104", "SEC-SECRET-API_KEY_GENERIC"} <= rules
    assert ev.security.rating == "D"
    assert {"samanvaya-metrics", "samanvaya-security"} <= set(ev.tools_executed)
    assert not any("outside" in f.file_path for f in ev.security.findings)


def test_pip_audit_2x_now_parsed():
    out = json.dumps({"dependencies": [{"name": "Django", "version": "3.2.0", "vulns": [
        {"id": "PYSEC-2021-98", "fix_versions": ["3.2.1"], "aliases": ["CVE-2021-31542"], "description": "x"}]}]})
    [v] = PythonAnalyzer._parse_dep_vulns(out)
    assert (v["package"], v["cve"], v["fix_versions"]) == ("django", "CVE-2021-31542", ["3.2.1"])
    assert PythonAnalyzer._parse_dep_vulns("not json") == []


def test_osv_lookup_is_opt_in_and_uses_requirements(repo, monkeypatch):
    from core.config import settings
    import intelligence.analyzers.python.analyzer as analyzer_module
    assert settings.OSV_LOOKUP_ENABLED is False          # off by default: no external calls
    (repo / "requirements.txt").write_text("django==3.2.0\nflask>=2\n", encoding="utf-8")
    sent = []

    def fake_query(deps):
        sent.extend(deps)
        return [DependencyVulnerability("django", "3.2.0", "PyPI", "GHSA-1", "critical", 9.8, ("CVE-1",), ("3.2.4",), "RCE", "osv")]

    monkeypatch.setattr(analyzer_module, "query_osv", fake_query)
    ev = evidence()
    [v] = PythonAnalyzer._osv_dependencies(str(repo), ev)
    assert (v["package"], v["severity"], v["cve"], v["source"]) == ("django", "critical", "CVE-1", "osv")
    assert [d.name for d in sent] == ["django", "flask"] and "osv" in ev.tools_executed
