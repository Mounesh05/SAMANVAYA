"""Phase 1 CQ-W5: the Code Quality AI advisory contract and composite report status.

The model's free text is never published as is. ``advisory_v1`` turns a validated
interpretation into ``code-quality-advisory-v1``:

* ``summary`` (<= 300 chars): the model's summary only when every number in it is a
  measured fact and it claims nothing unmeasured (e.g. passing tests); otherwise a
  server-written factual summary.
* ``suggestions`` (<= 3): each bound to exactly one real, eligible finding ID by its
  exact ``[file:line rule]`` citation. ``why`` is the analyzer's own message
  (<= 180), ``action`` the model's advice (<= 240). Unsafe or empty advice is dropped.
* ``limitations`` (<= 3, <= 160 chars each): server-written from measured gaps.

Model text that inflates a finding's severity, echoes injected instructions or looks
like a credential is withheld (CQ-31..34).

No score, severity or confidence field is part of the contract.
"""
import re

SCHEMA_VERSION = "code-quality-advisory-v1"
MAX_SUMMARY, MAX_SUGGESTIONS, MAX_WHY, MAX_ACTION = 300, 3, 180, 240
MAX_LIMITATIONS, MAX_LIMITATION = 3, 160
# Skips that are expected in the isolated worker and disclosed separately; they do
# not by themselves make the static evidence partial (documented decision).
DISCLOSED_ENVIRONMENT_SKIPS = frozenset({"dependency-advisories-offline", "pytest", "coverage",
                                         "tsc:configuration-unavailable",
                                         "npm-audit:package-manifest-unavailable"})

_UNMEASURED_CLAIMS = re.compile(
    r"\b(tests?\s+(?:all\s+)?pass(?:ed|es)?|fully\s+tested|100\s*%\s*coverage|bug[- ]free|no\s+vulnerabilit)",
    re.IGNORECASE)
_UNSAFE_ACTIONS = re.compile(
    r"(curl[^\n|]*\|\s*(?:ba)?sh|rm\s+-rf|chmod\s+777|disable\s+(?:the\s+)?(?:linter|security|bandit|eslint|checks?)"
    r"|#\s*nosec|eslint-disable|noqa|type:\s*ignore|eval\()", re.IGNORECASE)
_NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?![\w.])")
# Model text that echoes injected instructions or looks like a credential is withheld.
_INJECTION_ECHO = re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions|system\s+prompt"
                             r"|you\s+are\s+now\b", re.IGNORECASE)
_SECRET_LIKE = re.compile(r"AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{20,}|xox[abpr]-[A-Za-z0-9-]{10,}"
                          r"|-----BEGIN [A-Z ]*PRIVATE KEY|\b(?:password|passwd|secret|api[_-]?key|token)\s*[=:]\s*\S{4,}",
                          re.IGNORECASE)
_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
_SEVERITY_CLAIM = re.compile(r"\b(critical|high[- ]severity|severe)\b", re.IGNORECASE)


def _claimed_rank(text):
    """Most severe level the text asserts (None when it asserts none)."""
    ranks = [0 if m.lower() == "critical" else 1 for m in _SEVERITY_CLAIM.findall(text)]
    return min(ranks) if ranks else None


def _withheld(text):
    return bool(_INJECTION_ECHO.search(text) or _SECRET_LIKE.search(text))


def _citation(finding):
    return f"[{finding.get('file')}:{finding.get('line')} {finding.get('rule_id')}]"


def _allowed_numbers(evidence, findings):
    numbers = {len(findings), evidence.get("files_analyzed")}
    for finding in findings:
        numbers.add(finding.get("line"))
    severities = {}
    for finding in findings:
        severities[finding.get("severity")] = severities.get(finding.get("severity"), 0) + 1
    numbers.update(severities.values())
    comparison = evidence.get("pr_comparison") or {}
    for key in ("base_score", "head_score", "delta"):
        numbers.add(comparison.get(key))
    numbers.update(((comparison.get("finding_changes") or {}).get("counts") or {}).values())
    for value in (evidence.get("quality_score"), evidence.get("risk_score")):
        numbers.add(value)
    coverage = ((evidence.get("tests") or {}).get("coverage") or {}).get("line_coverage")
    numbers.add(coverage)
    return {str(n) for n in numbers if isinstance(n, (int, float))} | {str(int(n)) for n in numbers
                                                                       if isinstance(n, float) and n.is_integer()}


def server_summary(evidence, findings):
    if not findings:
        return ("Static analysis reported no findings in the analysed files, so there is nothing to fix "
                "from static analysis.")
    order = ["critical", "high", "medium", "low", "info"]
    counts = {}
    for finding in findings:
        counts[finding.get("severity") or "unknown"] = counts.get(finding.get("severity") or "unknown", 0) + 1
    parts = [f"{counts[s]} {s}" for s in order if counts.get(s)]
    files = evidence.get("files_analyzed")
    where = f" in {files} analysed file(s)" if isinstance(files, int) else ""
    return f"{len(findings)} finding(s){where}: " + ", ".join(parts) + "."


def limitations(evidence, omitted=0):
    out = []
    comparison = evidence.get("pr_comparison")
    if isinstance(comparison, dict) and (comparison.get("finding_changes") or {}).get("status") != "available":
        out.append("Introduced and resolved findings are not shown: the two revisions were not measured alike.")
    if ((evidence.get("tests") or {}).get("coverage") or {}).get("line_coverage") is None:
        out.append("Test coverage was not measured.")
    if evidence.get("dependency_audit") in ("not_checked_offline", "not_checked"):
        out.append("Dependency vulnerabilities were not checked.")
    if omitted:
        out.append(f"{omitted} lower-priority finding(s) were not given to the AI.")
    return [text[:MAX_LIMITATION] for text in out[:MAX_LIMITATIONS]]


def advisory_v1(interpretation, evidence):
    """Contract view of a completed interpretation; ``None`` for anything else."""
    if interpretation.get("status") != "completed":
        return None
    findings = [f for f in ((evidence.get("static_analysis") or {}).get("findings") or []) if isinstance(f, dict)]
    by_citation = {_citation(f): f for f in findings if f.get("id")}
    suggestions, used, rejected = [], set(), 0
    for text in [*(interpretation.get("critical_issues") or []), *(interpretation.get("recommendations") or [])]:
        text = str(text)
        cited = [c for c in by_citation if c in text]
        if len(cited) != 1:
            rejected += 1
            continue
        finding = by_citation[cited[0]]
        action = text.replace(cited[0], "").strip(" \t:-–—.")
        claimed = _claimed_rank(action)
        inflated = claimed is not None and claimed < _SEVERITY_RANK.get(finding.get("severity"), 5)
        if (not action or _UNSAFE_ACTIONS.search(action) or _UNMEASURED_CLAIMS.search(action) or _withheld(action)
                or inflated or finding["id"] in used):
            rejected += 1
            continue
        used.add(finding["id"])
        suggestions.append({"finding_id": finding["id"], "why": str(finding.get("message") or "")[:MAX_WHY],
                            "action": action[:MAX_ACTION]})
        if len(suggestions) == MAX_SUGGESTIONS:
            break
    model_summary = str(interpretation.get("analysis") or "").strip()
    numbers_ok = set(_NUMBER.findall(model_summary)) <= _allowed_numbers(evidence, findings)
    worst = min((_SEVERITY_RANK.get(f.get("severity"), 5) for f in findings), default=5)
    claimed = _claimed_rank(model_summary)
    grounded = (bool(findings) and model_summary and numbers_ok and not _UNMEASURED_CLAIMS.search(model_summary)
                and not _withheld(model_summary) and (claimed is None or claimed >= worst))
    summary = model_summary if grounded else server_summary(evidence, findings)
    return {"schema_version": SCHEMA_VERSION, "summary": summary[:MAX_SUMMARY],
            "summary_source": "model" if grounded else "server",
            "suggestions": suggestions, "rejected_suggestions": rejected,
            "limitations": limitations(evidence, evidence.get("omitted_findings") or 0)}


def static_reasons_for_run(result):
    """Why a single-revision report's static evidence is partial (empty = complete)."""
    state = result.get("quality_analysis_status")
    if state in ("failed", "unsupported") or result.get("quality_score") is None:
        return None  # static evidence unavailable: the report failed
    skipped = sorted(set(result.get("tools_skipped") or []) - DISCLOSED_ENVIRONMENT_SKIPS)
    return ["static_tools_skipped:" + ",".join(skipped)] if skipped else []


def static_reasons_for_comparison(summary):
    if summary.get("quality_analysis_status") in ("failed", "unsupported"):
        return None
    reasons = []
    changes = summary.get("finding_changes") or {}
    if changes.get("status") != "available":
        reasons.append("comparison_partial:" + str(changes.get("reason") or "unknown"))
    for side in ("base", "head"):
        if (summary.get("quality_comparison") or {}).get(side + "_status") in ("failed", "unsupported", None):
            reasons.append(f"{side}_revision_not_measured")
    return reasons


def report_state(static_reasons, ai_analysis):
    """Composite report status: complete only with full static evidence and validated AI."""
    if static_reasons is None:
        return "failed", ["static_evidence_unavailable"]
    reasons = list(static_reasons)
    if ai_analysis.get("status") != "completed":
        reasons.append("ai_interpretation_" + str(ai_analysis.get("status")) + ":"
                       + ",".join(ai_analysis.get("errors") or []))
    return ("complete" if not reasons else "partial"), reasons
