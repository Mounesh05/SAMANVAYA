"""
Bridge from SAMANVAYA's security metrics (intelligence/metrics/security.py,
secrets.py, dependencies.py) to the evidence package.

For the analyzed Python files it:
    - runs the pattern rules and taint analysis (CWE-mapped findings)
    - merges them with bandit's findings: one finding per (file, line, CWE),
      SAMANVAYA's kept when both report the same issue (it carries the taint
      path and a fix)
    - rebuilds the security counts from the merged list (secrets included)
    - sets the security rating (A-E), vulnerabilities per 1,000 code lines,
      counts per CWE and a dependency-vulnerability summary

Only files that resolve inside the repository are read (see code_metrics).
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from intelligence.analyzers.common.code_metrics import resolve_inside
from intelligence.evidence.models import CodeQualityEvidence, Finding, SeverityEnum
from intelligence.metrics.dependencies import DependencyVulnerability, summarize_dependencies
from intelligence.metrics.security import CWE_TITLES, SecurityFinding, analyze_file, security_rating
from intelligence.metrics.size import measure_file

_SEVERITY = {
    "critical": SeverityEnum.CRITICAL,
    "high": SeverityEnum.HIGH,
    "medium": SeverityEnum.MEDIUM,
    "low": SeverityEnum.LOW,
}
_SEVERITY_NAME = {v: k for k, v in _SEVERITY.items()}
_SEVERITY_NAME[SeverityEnum.INFO] = "low"


def to_finding(f: SecurityFinding) -> Finding:
    title = CWE_TITLES.get(f.cwe, f"CWE-{f.cwe}")
    certainty = "confirmed by taint analysis" if f.confidence == "high" else "pattern match"
    return Finding(
        file_path=f.path,
        line_number=f.line,
        rule_id=f.rule,
        category="security",
        severity=_SEVERITY.get(f.severity, SeverityEnum.MEDIUM),
        source_tool=f.source,
        message=f"CWE-{f.cwe} {title}: {f.message} ({certainty})",
        suggested_fix=f.fix,
        cwe=f.cwe,
    )


def _key(f: Finding) -> Tuple[str, Optional[int], Optional[int]]:
    return f.file_path.replace("\\", "/"), f.line_number, f.cwe


def merge_findings(ours: Sequence[Finding], others: Sequence[Finding]) -> List[Finding]:
    """Ours first; another tool's finding is dropped when it matches one of
    ours on (file, line, CWE). Findings without a CWE are always kept."""
    taken = {_key(f) for f in ours}
    merged = list(ours)
    for f in others:
        if f.cwe is not None and _key(f) in taken:
            continue
        merged.append(f)
    return merged


def _dependency_vulns(evidence: CodeQualityEvidence) -> List[DependencyVulnerability]:
    vulns = []
    for d in evidence.security.dependency_vulnerabilities:
        vulns.append(DependencyVulnerability(
            package=str(d.get("package", "")), version=d.get("version"), ecosystem=str(d.get("ecosystem", "")),
            vuln_id=str(d.get("id") or d.get("cve") or ""), severity=str(d.get("severity") or "unknown"),
            fixed_versions=tuple(d.get("fix_versions") or ()),
        ))
    return vulns


def apply_security_metrics(evidence: CodeQualityEvidence, files: Sequence[str], repo_path: str) -> None:
    """Add SAMANVAYA's code security findings and metrics to `evidence` (mutates it)."""
    python_files = [f for f in files if Path(f).suffix == ".py"]
    inside, _rejected = resolve_inside(python_files, repo_path)
    root = Path(repo_path).resolve()

    ours: List[Finding] = []
    code_lines = 0
    for path in inside:
        rel = path.relative_to(root).as_posix()
        ours.extend(to_finding(f) for f in analyze_file(path, display_path=rel).findings)
        if evidence.metrics is None:
            code_lines += measure_file(path).code_lines
    if evidence.metrics is not None:
        code_lines = evidence.metrics.code_lines

    security = evidence.security
    security.findings = merge_findings(ours, security.findings)
    listed_ids = {f.id for f in security.findings}
    # secrets live in static_findings; include them in the security list once
    for f in evidence.static_findings:
        if f.category == "security" and f.id not in listed_ids:
            security.findings.append(f)
            listed_ids.add(f.id)

    counts = Counter(f.severity for f in security.findings)
    security.critical_count = counts.get(SeverityEnum.CRITICAL, 0)
    security.high_count = counts.get(SeverityEnum.HIGH, 0)
    security.medium_count = counts.get(SeverityEnum.MEDIUM, 0)
    security.low_count = counts.get(SeverityEnum.LOW, 0)

    security.rating = security_rating(_SEVERITY_NAME.get(f.severity, "low") for f in security.findings)
    security.vulnerability_density = (
        round(len(security.findings) / (code_lines / 1000), 2) if code_lines else 0.0
    )
    by_cwe: Dict[str, int] = {}
    for f in security.findings:
        if f.cwe is not None:
            label = f"CWE-{f.cwe} {CWE_TITLES.get(f.cwe, '')}".strip()
            by_cwe[label] = by_cwe.get(label, 0) + 1
    security.by_cwe = dict(sorted(by_cwe.items(), key=lambda kv: -kv[1]))
    security.dependency_summary = summarize_dependencies(_dependency_vulns(evidence)).to_dict()

    if ours and "samanvaya-security" not in evidence.tools_executed:
        evidence.tools_executed.append("samanvaya-security")
