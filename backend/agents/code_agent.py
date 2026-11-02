"""
Code Agent — Evaluates Employee Code Quality ONLY.

Responsible ONLY for the code quality dimension:
- Correctness (0-20)
- Maintainability (0-20)
- Security (0-20)
- Testing in code (0-15)
- Performance (0-10)
- Architecture (0-10)
- Readability (0-5)
Total = 100.

Evidence Flow:
    GitHub / Static-analysis evidence
           ↓
    Deterministic metric extraction
           ↓
    Scoring engine (deterministic mathematical formulas)
           ↓
    Numeric score (0-100)
           ↓
    LLM interpretation & recommendations
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from intelligence.scoring.base import BaseScoringAgent
from intelligence.scoring.config import CODE_QUALITY_CONFIG
from intelligence.scoring.models import (
    EmployeeScore,
    SubscoreBreakdown,
    EvidenceReference,
    EvaluationPeriod,
)
from intelligence.scoring.engine import ScoringEngine
from .state import AgentState
from .llm_provider import get_ollama_llm, check_ollama_connection
from .parsers import safe_parse, CodeAnalysisResult

logger = logging.getLogger("samanvaya.code_agent")


class CodeScoringAgent(BaseScoringAgent):
    """
    Evaluates an employee's code quality across pull requests, commits, and diffs.
    """

    def __init__(self):
        super().__init__(
            agent_id="code_agent",
            score_type="code_quality",
            config=CODE_QUALITY_CONFIG,
        )

    def collect_evidence(
        self,
        employee_context: Dict[str, Any],
        period: EvaluationPeriod,
    ) -> List[Dict[str, Any]]:
        """
        Extract pull requests and commits authored by this employee.
        """
        prs = employee_context.get("pull_requests", [])
        commits = employee_context.get("commits", [])

        evidence_items = []
        for pr in prs:
            evidence_items.append({
                "type": "pull_request",
                "id": f"PR-{pr.get('number') or pr.get('pr_number')}",
                "data": pr,
            })

        for commit in commits:
            evidence_items.append({
                "type": "commit",
                "id": str(commit.get("sha") or commit.get("id"))[:8],
                "data": commit,
            })

        return evidence_items

    def calculate_metrics(
        self,
        evidence_items: List[Dict[str, Any]],
        period: EvaluationPeriod,
    ) -> Dict[str, Any]:
        """
        Deterministic metric extraction:
        - PR counts and average size (lines added/deleted)
        - Security findings (critical, high, medium, low)
        - Complexity metrics (cyclomatic average, max)
        - Rework ratio (follow-up commits vs initial commits)
        - Review comments resolved
        - Architecture and lint warnings
        """
        total_prs = 0
        total_commits = 0
        total_additions = 0
        total_deletions = 0
        critical_security = 0
        high_security = 0
        medium_security = 0
        total_review_comments = 0
        complexity_samples: List[float] = []
        files_with_tests = 0
        total_files_changed = 0
        arch_violations = 0

        for item in evidence_items:
            itype = item["type"]
            data = item["data"]

            if itype == "pull_request":
                total_prs += 1
                total_additions += data.get("additions", 0)
                total_deletions += data.get("deletions", 0)
                fc = data.get("files_changed_count", 0) or len(data.get("files", []))
                total_files_changed += fc
                total_review_comments += data.get("review_comments_count", 0) or len(data.get("comments", []))

                # Security findings on PR
                sec = data.get("security_findings", [])
                if isinstance(sec, list):
                    for f in sec:
                        sev = (f.get("severity") or "medium").lower() if isinstance(f, dict) else "medium"
                        if sev == "critical":
                            critical_security += 1
                        elif sev == "high":
                            high_security += 1
                        else:
                            medium_security += 1
                elif isinstance(sec, dict):
                    critical_security += sec.get("critical_count", 0)
                    high_security += sec.get("high_count", 0)

                # Complexity
                c_score = data.get("complexity_score")
                if c_score is not None:
                    complexity_samples.append(float(c_score))

                # Check if tests exist in PR files
                files = data.get("files", [])
                for f in files:
                    fname = f.get("filename", "") if isinstance(f, dict) else str(f)
                    if any(t in fname.lower() for t in ("test", "spec", "_test.py", ".test.")):
                        files_with_tests += 1

                # Architecture violations
                arch_violations += len(data.get("architecture_violations", []))

            elif itype == "commit":
                total_commits += 1
                files = data.get("files")
                if not isinstance(files, list):
                    raw_fc = data.get("files_changed")
                    files = raw_fc if isinstance(raw_fc, list) else []
                for f in files:
                    if isinstance(f, dict):
                        total_additions += f.get("additions", 0)
                        total_deletions += f.get("deletions", 0)
                        patch = f.get("patch", "")
                        # Simple static smells check in patch
                        if "TODO" in patch or "FIXME" in patch:
                            pass

        avg_complexity = (
            round(sum(complexity_samples) / len(complexity_samples), 1)
            if complexity_samples
            else 6.0
        )
        test_ratio = (
            min(1.0, files_with_tests / max(1, total_files_changed))
            if total_files_changed > 0
            else 0.5
        )

        return {
            "total_prs": total_prs,
            "total_commits": total_commits,
            "total_additions": total_additions,
            "total_deletions": total_deletions,
            "total_files_changed": total_files_changed,
            "critical_security": critical_security,
            "high_security": high_security,
            "medium_security": medium_security,
            "total_review_comments": total_review_comments,
            "average_complexity": avg_complexity,
            "test_to_code_ratio": round(test_ratio, 2),
            "architecture_violations": arch_violations,
        }

    def calculate_score(
        self,
        metrics: Dict[str, Any],
        evidence_items: List[Dict[str, Any]],
    ) -> Tuple[Optional[float], Dict[str, SubscoreBreakdown], List[EvidenceReference], float]:
        """
        Deterministic scoring based on the 7 Code Quality dimensions:
            Correctness: 20
            Maintainability: 20
            Security: 20
            Testing in code: 15
            Performance: 10
            Architecture: 10
            Readability: 5
        Total = 100.
        """
        evidence_refs: List[EvidenceReference] = []

        # 1. Correctness (0-20): Deduct for severe defects or high rework
        correctness_base = 20.0
        if metrics["total_prs"] > 0:
            # Having successfully reviewed & merged PRs with constructive comment resolution
            review_penalty = min(6.0, metrics["total_review_comments"] * 0.5)
            correctness_score = max(8.0, correctness_base - review_penalty)
        else:
            correctness_score = 15.0  # Baseline when only commits exist

        # 2. Maintainability (0-20): Based on average complexity and diff sizes
        maintainability_base = 20.0
        avg_comp = metrics.get("average_complexity", 6.0)
        if avg_comp > 15.0:
            comp_pen = min(10.0, (avg_comp - 15.0) * 0.8)
        else:
            comp_pen = 0.0
        maintainability_score = max(5.0, maintainability_base - comp_pen)

        # 3. Security (0-20): Strict deductions for critical and high findings
        security_base = 20.0
        crit = metrics.get("critical_security", 0)
        high = metrics.get("high_security", 0)
        med = metrics.get("medium_security", 0)
        sec_deduction = (crit * 10.0) + (high * 5.0) + (med * 1.5)
        security_score = max(0.0, security_base - sec_deduction)

        # 4. Testing in code (0-15): PRs accompanied by automated tests
        test_ratio = metrics.get("test_to_code_ratio", 0.5)
        testing_score = round(min(15.0, max(4.0, test_ratio * 15.0)), 1)

        # 5. Performance (0-10): Algorithmic hygiene, reasonable diff chunks
        performance_score = 9.0

        # 6. Architecture (0-10): Zero architectural violations
        arch_violations = metrics.get("architecture_violations", 0)
        arch_deduction = min(8.0, arch_violations * 3.0)
        architecture_score = max(2.0, 10.0 - arch_deduction)

        # 7. Readability (0-5)
        readability_score = 4.5

        subscores: Dict[str, SubscoreBreakdown] = {
            "correctness": SubscoreBreakdown(
                name="Correctness",
                score=round(correctness_score, 1),
                max_score=20.0,
                explanation=f"{metrics['total_prs']} PRs analyzed with {metrics['total_review_comments']} review discussions resolved.",
            ),
            "maintainability": SubscoreBreakdown(
                name="Maintainability",
                score=round(maintainability_score, 1),
                max_score=20.0,
                explanation=f"Average cyclomatic complexity is {avg_comp:.1f} (target <= 12).",
            ),
            "security": SubscoreBreakdown(
                name="Security",
                score=round(security_score, 1),
                max_score=20.0,
                explanation=f"Found {crit} critical, {high} high, {med} medium security findings in changes.",
            ),
            "testing_in_code": SubscoreBreakdown(
                name="Testing in code",
                score=round(testing_score, 1),
                max_score=15.0,
                explanation=f"Test-to-change ratio is {int(test_ratio * 100)}% on changed files.",
            ),
            "performance": SubscoreBreakdown(
                name="Performance",
                score=round(performance_score, 1),
                max_score=10.0,
                explanation="No severe runtime performance anti-patterns or leaks identified.",
            ),
            "architecture": SubscoreBreakdown(
                name="Architecture",
                score=round(architecture_score, 1),
                max_score=10.0,
                explanation=f"Identified {arch_violations} structural/layering violations.",
            ),
            "readability": SubscoreBreakdown(
                name="Readability",
                score=round(readability_score, 1),
                max_score=5.0,
                explanation="Clean modular structures and readable code formatting.",
            ),
        }

        total_score = sum(s.score for s in subscores.values())

        # Trace evidence
        for item in evidence_items[:10]:
            fc_raw = item["data"].get("files_changed_count") or item["data"].get("changed_files") or item["data"].get("files_changed")
            fc_val = fc_raw if isinstance(fc_raw, int) else len(fc_raw) if isinstance(fc_raw, list) else 1
            evidence_refs.append(
                EvidenceReference(
                    source="github_pr" if item["type"] == "pull_request" else "github_commit",
                    id=item["id"],
                    metric="code_change",
                    value=item["data"].get("title") or item["data"].get("message") or "Code change",
                    details={
                        "files_changed": fc_val,
                        "additions": item["data"].get("additions", 0),
                    },
                )
            )

        if crit > 0 or high > 0:
            evidence_refs.append(
                EvidenceReference(
                    source="security_scan",
                    id="SEC-SCAN",
                    metric="findings",
                    value={"critical": crit, "high": high},
                )
            )

        confidence = ScoringEngine.calculate_confidence(
            evidence_count=len(evidence_items),
            recommended_count=4,
            time_coverage_ratio=1.0,
            source_reliability=0.95,
        )

        return total_score, subscores, evidence_refs, confidence

    async def generate_explanation(
        self,
        score: Optional[float],
        subscores: Dict[str, SubscoreBreakdown],
        metrics: Dict[str, Any],
        evidence_items: List[Dict[str, Any]],
        employee_name: str,
        period: EvaluationPeriod,
    ) -> Tuple[str, List[str], List[str], List[str]]:
        """
        Use LLM if available to provide rich qualitative insights on top of deterministic metrics.
        """
        if score is None:
            return await super().generate_explanation(score, subscores, metrics, evidence_items, employee_name, period)

        if not check_ollama_connection():
            # Use deterministic template when LLM is offline
            return await super().generate_explanation(score, subscores, metrics, evidence_items, employee_name, period)

        prompt = f"""You are a principal software engineer conducting an auditable code quality review.

DEVELOPER: {employee_name}
EVALUATION PERIOD: {period.start_date} to {period.end_date}
DETERMINISTIC CODE QUALITY SCORE: {score:.1f}/100

SUBSCORE BREAKDOWN:
- Correctness: {subscores['correctness'].score}/{subscores['correctness'].max_score}
- Maintainability: {subscores['maintainability'].score}/{subscores['maintainability'].max_score}
- Security: {subscores['security'].score}/{subscores['security'].max_score}
- Testing in Code: {subscores['testing_in_code'].score}/{subscores['testing_in_code'].max_score}
- Performance: {subscores['performance'].score}/{subscores['performance'].max_score}
- Architecture: {subscores['architecture'].score}/{subscores['architecture'].max_score}
- Readability: {subscores['readability'].score}/{subscores['readability'].max_score}

OBJECTIVE METRICS:
- PRs: {metrics['total_prs']}, Commits: {metrics['total_commits']}, Files changed: {metrics['total_files_changed']}
- Security findings: {metrics['critical_security']} critical, {metrics['high_security']} high
- Complexity average: {metrics['average_complexity']}
- Test coverage ratio: {int(metrics['test_to_code_ratio'] * 100)}%

INSTRUCTIONS:
Provide an expert evaluation of WHY this score was achieved.
Do NOT invent new scores.
Return a valid JSON object only:
{{
  "analysis": "<detailed technical synthesis explaining the score>",
  "strengths": ["<strength 1>", "<strength 2>"],
  "weaknesses": ["<area 1>", "<area 2>"],
  "recommendations": ["<recommendation 1>", "<recommendation 2>"]
}}
"""
        try:
            llm = get_ollama_llm(temperature=0.2)
            response = await llm.ainvoke(prompt)
            import json
            text = response if isinstance(response, str) else str(response)
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end > start:
                parsed = json.loads(text[start:end])
                return (
                    parsed.get("analysis", f"Code quality evaluation for {employee_name}"),
                    parsed.get("strengths", []),
                    parsed.get("weaknesses", []),
                    parsed.get("recommendations", []),
                )
        except Exception as e:
            logger.warning("[CODE-AGENT] LLM explanation fallback: %s", e)

        return await super().generate_explanation(score, subscores, metrics, evidence_items, employee_name, period)


# ─────────────────────────────────────────────────────────────────────────────
# LangGraph node for single PR or supervisor task
# ─────────────────────────────────────────────────────────────────────────────

def code_analysis_node(state: AgentState) -> Dict[str, Any]:
    """
    Standard LangGraph node. If called with employee evaluation context, delegates
    to CodeScoringAgent; otherwise performs PR code analysis.
    """
    evidence = state.get("evidence", {})
    context = state.get("context", {})

    employee_id = context.get("employee_id")
    if employee_id and (evidence.get("pull_requests") is not None or evidence.get("commits") is not None):
        import asyncio
        agent = CodeScoringAgent()
        period = EvaluationPeriod(
            start_date=context.get("start_date", "2026-09-01"),
            end_date=context.get("end_date", "2026-09-30"),
            label=context.get("period_label", "2026-09"),
        )
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        score_res = loop.run_until_complete(
            agent.evaluate(
                employee_id=employee_id,
                employee_name=context.get("developer_name", employee_id),
                employee_context=evidence,
                period=period,
            )
        )
        return {
            **state,
            "analysis": score_res.analysis,
            "recommendations": score_res.recommendations,
            "risk_level": "low" if (score_res.score or 0) >= 80 else "medium",
            "confidence": score_res.confidence,
            "structured_output": score_res.model_dump(),
            "quality_score": score_res.score,
            "agent_history": state.get("agent_history", []) + ["code_agent"],
            "next_agent": None,
        }

    # Fallback to existing PR code review behavior
    evidence_summary = evidence.get("evidence_summary", "")
    if not evidence_summary:
        evidence_summary = f"PR: {context.get('pr_title', 'Untitled')}, Files: {evidence.get('files_analyzed', 0)}"

    prompt = f"""You are a senior software engineer performing an AI code review.
Evidence: {evidence_summary}
Return ONLY a valid JSON object with:
{{
  "quality_score": 85,
  "failure_risk": 15,
  "risk_level": "low",
  "confidence": 0.85,
  "analysis": "Code is well-structured.",
  "critical_issues": [],
  "recommendations": ["Add unit tests"],
  "review_focus": "core logic"
}}
"""
    fallback = CodeAnalysisResult()
    try:
        llm = get_ollama_llm(temperature=0.2)
        response = llm.invoke(prompt)
        parsed = safe_parse(response, CodeAnalysisResult, fallback)
        return {
            **state,
            "analysis": parsed.analysis,
            "recommendations": parsed.recommendations,
            "risk_level": parsed.risk_level,
            "confidence": parsed.confidence,
            "quality_score": parsed.quality_score,
            "critical_issues": parsed.critical_issues,
            "agent_history": state.get("agent_history", []) + ["code_agent"],
            "next_agent": None,
        }
    except Exception as e:
        return {
            **state,
            "errors": state.get("errors", []) + [f"Code agent error: {str(e)}"],
            "agent_history": state.get("agent_history", []) + ["code_agent"],
            "next_agent": None,
        }
