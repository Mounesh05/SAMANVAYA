"""
Vulnerable dependencies: manifest parsing, CVSS 3.1 scoring, audit-report
parsing and an optional OSV lookup.

Manifests            requirements*.txt, pyproject.toml (PEP 621 and Poetry),
                     package-lock.json (npm lockfile v1, v2, v3)
Audit reports        pip-audit --format=json (2.x object and older list form),
                     npm audit --json (npm 7+)
CVSS 3.1 base score  implemented from FIRST's specification (section 7.1 and
                     Appendix A "Roundup"); severity bands: 0.1-3.9 low,
                     4.0-6.9 medium, 7.0-8.9 high, 9.0-10.0 critical
OSV lookup           https://osv.dev (the database pip-audit can also use).
                     It sends package names and versions to an external
                     service, so nothing here calls it on its own: the caller
                     decides (SAMANVAYA: setting OSV_LOOKUP_ENABLED, off by default).
"""

from __future__ import annotations

import json
import math
import re
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]


@dataclass(frozen=True)
class Dependency:
    name: str                 # normalized (PEP 503 for PyPI)
    version: Optional[str]    # exact pinned version, or None when only a range is given
    ecosystem: str            # "PyPI" | "npm"
    specifier: str = ""       # e.g. ">=2.0,<3"
    source: str = ""          # manifest file
    dev: bool = False


@dataclass(frozen=True)
class DependencyVulnerability:
    package: str
    version: Optional[str]
    ecosystem: str
    vuln_id: str
    severity: str                       # critical | high | medium | low | unknown
    cvss_score: Optional[float] = None
    aliases: Tuple[str, ...] = ()
    fixed_versions: Tuple[str, ...] = ()
    summary: str = ""
    source: str = ""                    # pip-audit | npm-audit | osv

    @property
    def fix_available(self) -> bool:
        return bool(self.fixed_versions)

    def to_dict(self) -> Dict[str, object]:
        data = dict(self.__dict__)
        data["aliases"] = list(self.aliases)
        data["fixed_versions"] = list(self.fixed_versions)
        data["fix_available"] = self.fix_available
        return data


# ── manifests ─────────────────────────────────────────────────────

def normalize_pypi_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


_REQ = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(\[[^\]]*\])?\s*([^;]*)")
_PIN = re.compile(r"^===?\s*([A-Za-z0-9][A-Za-z0-9.+!*_-]*)$")


def _requirement(line: str, source: str) -> Optional[Dependency]:
    match = _REQ.match(line)
    if not match:
        return None
    name, _extras, spec = match.groups()
    spec = spec.strip().replace(" ", "")
    pin = _PIN.match(spec)
    version = pin.group(1) if pin and "*" not in pin.group(1) else None
    return Dependency(normalize_pypi_name(name), version, "PyPI", spec, source)


def parse_requirements(text: str, source: str = "requirements.txt") -> List[Dependency]:
    """pip requirements file -> dependencies (options, includes, URLs and editables skipped)."""
    deps: List[Dependency] = []
    joined = re.sub(r"\\\s*\n", " ", text)  # line continuations
    for raw in joined.splitlines():
        line = re.split(r"\s+#|^#", raw, maxsplit=1)[0].strip()
        if not line or line.startswith("-") or "://" in line or line.startswith((".", "/")):
            continue
        line = re.sub(r"\s--hash=\S+", "", line)
        dep = _requirement(line, source)
        if dep:
            deps.append(dep)
    return deps


def parse_pyproject(text: str, source: str = "pyproject.toml") -> List[Dependency]:
    """PEP 621 [project] dependencies and Poetry [tool.poetry.*dependencies]."""
    if tomllib is None:  # pragma: no cover
        return []
    data = tomllib.loads(text)
    deps: List[Dependency] = []
    project = data.get("project", {})
    for line in project.get("dependencies", []):
        dep = _requirement(line, source)
        if dep:
            deps.append(dep)
    for group in project.get("optional-dependencies", {}).values():
        for line in group:
            dep = _requirement(line, source)
            if dep:
                deps.append(Dependency(dep.name, dep.version, dep.ecosystem, dep.specifier, source, dev=True))
    poetry = data.get("tool", {}).get("poetry", {})
    sections = [("dependencies", False), ("dev-dependencies", True)]
    sections += [(f"group.{g}", True) for g in poetry.get("group", {})]
    for key, dev in sections:
        table = poetry
        for part in key.split("."):
            table = table.get(part, {}) if isinstance(table, dict) else {}
        if key.startswith("group."):
            table = table.get("dependencies", {})
        for name, spec in (table or {}).items():
            if name.lower() == "python":
                continue
            version_spec = spec.get("version", "") if isinstance(spec, dict) else str(spec)
            exact = version_spec if re.fullmatch(r"[0-9][A-Za-z0-9.+!_-]*", version_spec or "") else None
            deps.append(Dependency(normalize_pypi_name(name), exact, "PyPI", version_spec, source, dev))
    return deps


def parse_package_lock(text: str, source: str = "package-lock.json") -> List[Dependency]:
    """npm package-lock.json, lockfile versions 1, 2 and 3 (exact versions)."""
    data = json.loads(text)
    deps: Dict[Tuple[str, str], Dependency] = {}
    packages = data.get("packages")
    if isinstance(packages, dict):  # v2 / v3
        for path, info in packages.items():
            if not path or "node_modules/" not in path or info.get("link"):
                continue
            name = path.rsplit("node_modules/", 1)[1]
            version = info.get("version")
            if version:
                deps[(name, version)] = Dependency(name, version, "npm", version, source, bool(info.get("dev")))
    else:  # v1: nested "dependencies"
        def walk(tree: Mapping[str, Any]) -> None:
            for name, info in tree.items():
                version = info.get("version")
                if version:
                    deps[(name, version)] = Dependency(name, version, "npm", version, source, bool(info.get("dev")))
                walk(info.get("dependencies", {}))
        walk(data.get("dependencies", {}))
    return sorted(deps.values(), key=lambda d: (d.name, d.version or ""))


# ── CVSS 3.1 ──────────────────────────────────────────────────────

_CVSS_WEIGHTS = {
    "AV": {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2},
    "AC": {"L": 0.77, "H": 0.44},
    "UI": {"N": 0.85, "R": 0.62},
    "C": {"H": 0.56, "L": 0.22, "N": 0.0},
    "I": {"H": 0.56, "L": 0.22, "N": 0.0},
    "A": {"H": 0.56, "L": 0.22, "N": 0.0},
}
_PR = {"U": {"N": 0.85, "L": 0.62, "H": 0.27}, "C": {"N": 0.85, "L": 0.68, "H": 0.5}}


def _roundup(value: float) -> float:
    """CVSS 3.1 Appendix A: smallest number with one decimal >= value (float-safe)."""
    integer = round(value * 100000)
    if integer % 10000 == 0:
        return integer / 100000.0
    return (math.floor(integer / 10000) + 1) / 10.0


def cvss31_base_score(vector: str) -> float:
    """Base score of a CVSS v3.0/v3.1 vector, e.g. "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H" -> 9.8."""
    metrics = dict(part.split(":", 1) for part in vector.strip().split("/") if ":" in part and not part.startswith("CVSS"))
    required = ("AV", "AC", "PR", "UI", "S", "C", "I", "A")
    missing = [m for m in required if m not in metrics]
    if missing:
        raise ValueError(f"CVSS vector missing {', '.join(missing)}: {vector}")
    scope = metrics["S"]
    if scope not in ("U", "C"):
        raise ValueError(f"Invalid scope in CVSS vector: {vector}")
    try:
        av, ac, ui = (_CVSS_WEIGHTS[m][metrics[m]] for m in ("AV", "AC", "UI"))
        c, i, a = (_CVSS_WEIGHTS[m][metrics[m]] for m in ("C", "I", "A"))
        pr = _PR[scope][metrics["PR"]]
    except KeyError as exc:
        raise ValueError(f"Invalid value in CVSS vector {vector}: {exc}") from exc

    iss = 1 - (1 - c) * (1 - i) * (1 - a)
    impact = 6.42 * iss if scope == "U" else 7.52 * (iss - 0.029) - 3.25 * (iss - 0.02) ** 15
    exploitability = 8.22 * av * ac * pr * ui
    if impact <= 0:
        return 0.0
    if scope == "U":
        return _roundup(min(impact + exploitability, 10))
    return _roundup(min(1.08 * (impact + exploitability), 10))


def cvss_severity(score: Optional[float]) -> str:
    if score is None:
        return "unknown"
    if score >= 9.0:
        return "critical"
    if score >= 7.0:
        return "high"
    if score >= 4.0:
        return "medium"
    if score > 0:
        return "low"
    return "none"


_LABELS = {"critical": "critical", "high": "high", "moderate": "medium", "medium": "medium", "low": "low", "info": "low"}


# ── audit reports ─────────────────────────────────────────────────

def parse_pip_audit(output: str) -> List[DependencyVulnerability]:
    """pip-audit --format=json. 2.x prints {"dependencies": [{name, version, vulns: [...]}]};
    older output and some wrappers print a list. pip-audit gives no severity."""
    data = json.loads(output)
    entries = data.get("dependencies", []) if isinstance(data, dict) else data
    vulns: List[DependencyVulnerability] = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        name = normalize_pypi_name(str(entry.get("name", "")))
        version = entry.get("version")
        items = entry.get("vulns")
        if items is None and entry.get("id"):  # flat legacy item
            items = [entry]
        for v in items or []:
            vulns.append(DependencyVulnerability(
                package=name, version=version, ecosystem="PyPI", vuln_id=str(v.get("id", "")),
                severity=_LABELS.get(str(v.get("severity", "")).lower(), "unknown"),
                aliases=tuple(v.get("aliases", []) or ()),
                fixed_versions=tuple(v.get("fix_versions", []) or ()),
                summary=str(v.get("description", ""))[:300], source="pip-audit",
            ))
    return vulns


def parse_npm_audit(output: str) -> List[DependencyVulnerability]:
    """npm audit --json (npm 7+): one entry per advisory reaching each package."""
    data = json.loads(output)
    vulns: List[DependencyVulnerability] = []
    for name, info in (data.get("vulnerabilities") or {}).items():
        fix = info.get("fixAvailable")
        fixed = (str(fix.get("version")),) if isinstance(fix, dict) and fix.get("version") else ()
        for via in info.get("via", []):
            if not isinstance(via, dict):  # a string means "vulnerable through another package"
                continue
            cvss = via.get("cvss") or {}
            score = cvss.get("score") if cvss.get("score") else None
            vulns.append(DependencyVulnerability(
                package=name, version=None, ecosystem="npm",
                vuln_id=str(via.get("url") or via.get("source") or ""),
                severity=_LABELS.get(str(via.get("severity", info.get("severity", ""))).lower(), "unknown"),
                cvss_score=float(score) if score is not None else None,
                fixed_versions=fixed, summary=str(via.get("title", ""))[:300], source="npm-audit",
            ))
    return vulns


# ── OSV (optional, external) ──────────────────────────────────────

OSV_API = "https://api.osv.dev/v1"
PostJson = Callable[[str, Dict[str, Any]], Dict[str, Any]]
GetJson = Callable[[str], Dict[str, Any]]


def _http_post(url: str, body: Dict[str, Any]) -> Dict[str, Any]:  # pragma: no cover - network
    request = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode())


def _http_get(url: str) -> Dict[str, Any]:  # pragma: no cover - network
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode())


def _osv_severity(detail: Mapping[str, Any]) -> Tuple[str, Optional[float]]:
    for item in detail.get("severity", []) or []:
        if str(item.get("type", "")).startswith("CVSS_V3"):
            try:
                score = cvss31_base_score(item.get("score", ""))
                return cvss_severity(score), score
            except ValueError:
                continue
    for affected in detail.get("affected", []) or []:
        label = str((affected.get("database_specific") or {}).get("severity", "")).lower()
        if label in _LABELS:
            return _LABELS[label], None
    label = str((detail.get("database_specific") or {}).get("severity", "")).lower()
    return _LABELS.get(label, "unknown"), None


def _osv_fixed(detail: Mapping[str, Any], name: str) -> Tuple[str, ...]:
    fixed: List[str] = []
    for affected in detail.get("affected", []) or []:
        package = (affected.get("package") or {}).get("name", "")
        if package and normalize_pypi_name(package) != normalize_pypi_name(name) and package != name:
            continue
        for rng in affected.get("ranges", []) or []:
            for event in rng.get("events", []) or []:
                if "fixed" in event:
                    fixed.append(str(event["fixed"]))
    return tuple(dict.fromkeys(fixed))


def query_osv(
    dependencies: Sequence[Dependency],
    post_json: Optional[PostJson] = None,
    get_json: Optional[GetJson] = None,
    batch_size: int = 500,
) -> List[DependencyVulnerability]:
    """Look up pinned dependencies in OSV. Sends names and versions to osv.dev
    unless other functions are passed in (tests pass fakes)."""
    post = post_json or _http_post
    get = get_json or _http_get
    pinned = [d for d in dependencies if d.version]
    details: Dict[str, Dict[str, Any]] = {}
    found: List[Tuple[Dependency, str]] = []
    for start in range(0, len(pinned), batch_size):
        batch = pinned[start:start + batch_size]
        body = {"queries": [{"version": d.version, "package": {"name": d.name, "ecosystem": d.ecosystem}} for d in batch]}
        response = post(f"{OSV_API}/querybatch", body)
        for dep, result in zip(batch, response.get("results", [])):
            for vuln in result.get("vulns", []) or []:
                found.append((dep, vuln["id"]))
    out: List[DependencyVulnerability] = []
    for dep, vuln_id in found:
        if vuln_id not in details:
            details[vuln_id] = get(f"{OSV_API}/vulns/{vuln_id}")
        detail = details[vuln_id]
        severity, score = _osv_severity(detail)
        out.append(DependencyVulnerability(
            package=dep.name, version=dep.version, ecosystem=dep.ecosystem, vuln_id=vuln_id,
            severity=severity, cvss_score=score, aliases=tuple(detail.get("aliases", []) or ()),
            fixed_versions=_osv_fixed(detail, dep.name), summary=str(detail.get("summary", ""))[:300], source="osv",
        ))
    return out


# ── summary ───────────────────────────────────────────────────────

_ORDER = {"unknown": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


@dataclass
class DependencySummary:
    vulnerabilities: List[DependencyVulnerability] = field(default_factory=list)

    @property
    def by_severity(self) -> Dict[str, int]:
        counts = {s: 0 for s in ("critical", "high", "medium", "low", "unknown")}
        for v in self.vulnerabilities:
            counts[v.severity if v.severity in counts else "unknown"] += 1
        return counts

    @property
    def packages_affected(self) -> int:
        return len({(v.ecosystem, v.package) for v in self.vulnerabilities})

    @property
    def fixable(self) -> int:
        return sum(1 for v in self.vulnerabilities if v.fix_available)

    @property
    def worst_severity(self) -> Optional[str]:
        if not self.vulnerabilities:
            return None
        return max((v.severity for v in self.vulnerabilities), key=lambda s: _ORDER.get(s, 0))

    def to_dict(self) -> Dict[str, object]:
        return {
            "vulnerabilities": len(self.vulnerabilities),
            "packages_affected": self.packages_affected,
            "fixable": self.fixable,
            "by_severity": self.by_severity,
            "worst_severity": self.worst_severity,
        }


def summarize_dependencies(vulnerabilities: Iterable[DependencyVulnerability]) -> DependencySummary:
    """One entry per (package, version, vulnerability id), deduplicated across sources."""
    unique: Dict[Tuple[str, str, Optional[str], str], DependencyVulnerability] = {}
    for v in vulnerabilities:
        key = (v.ecosystem, v.package, v.version, v.vuln_id)
        current = unique.get(key)
        if current is None or (current.severity == "unknown" and v.severity != "unknown"):
            unique[key] = v
    return DependencySummary(list(unique.values()))
