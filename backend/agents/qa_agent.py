"""
QA Agent — Evaluates Employee Testing and Reliability ONLY.

Responsible ONLY for the testing and reliability dimension:
- Test Coverage (0-25)
- Test Completeness (0-20)
- Regression Prevention (0-20)
- Test Reliability (0-15)
- Test Quality (0-10)
- Defect Prevention (0-10)
Total = 100.

Evidence Flow:
    Test execution & Coverage evidence
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
from intelligence.scoring.config import QA_TESTING_CONFIG
from intelligence.scoring.models import (
    EmployeeScore,
    SubscoreBreakdown,
    EvidenceReference,
    EvaluationPeriod,
)
from intelligence.scoring.engine import ScoringEngine
from .state import AgentState
from .llm_provider import get_ollama_llm, check_ollama_connection
from .parsers import safe_parse, AgentAnalysisResult

logger = logging.getLogger("samanvaya.qa_agent")


class QAScoringAgent(BaseScoringAgent):
    """
    Evaluates an employee's testing hygiene, test suites, coverage, and reliability.
    """

    def __init__(self):
        super().__init__(
            agent_id="qa_agent",
            score_type="testing_reliability",
            config=QA_TESTING_CONFIG,
        )

    def collect_evidence(
        self,
        employee_context: Dict[str, Any],
        period: EvaluationPeriod,
    ) -> List[Dict[str, Any]]:
        """
        Extract testing-specific evidence:
        - Test suites added/modified in PRs
        - Test coverage reports
        - CI test run execution logs
        - Bugs found vs prevented
        """
        evidence_items = []

        # From pull requests: look for test file additions and coverage deltas
        prs = employee_context.get("pull_requests", [])
        for pr in prs:
            files = pr.get("files", [])
            test_files = [
                f for f in files
                if any(t in (f.get("filename", "") if isinstance(f, dict) else str(f)).lower()
                       for t in ("test", "spec", "_test.py", ".test."))
            ]
            if test_files or pr.get("test_coverage_pct") is not None or pr.get("test_files_count", 0) > 0:
                evidence_items.append({
                    "type": "pr_tests",
                    "id": f"PR-{pr.get('number') or pr.get('pr_number')}",
                    "data": {
                        "pr_number": pr.get("number") or pr.get("pr_number"),
                        "test_files_count": len(test_files) or pr.get("test_files_count", 0),
                        "total_files": pr.get("files_changed_count", 1) or len(files),
                        "test_coverage_pct": pr.get("test_coverage_pct"),
                        "coverage_delta": pr.get("coverage_delta", 0.0),
                        "failed_tests_count": pr.get("failed_tests_count", 0),
                        "flaky_tests_count": pr.get("flaky_tests_count", 0),
                    },
                })

        # From CI/CD test runs
        ci_runs = employee_context.get("ci_runs", [])
        for run in ci_runs:
            if run.get("test_results") or "test" in (run.get("name", "") + run.get("step", "")).lower():
                evidence_items.append({
                    "type": "ci_test_run",
                    "id": str(run.get("id") or run.get("run_id") or "CI-RUN"),
                    "data": run,
                })

        # From bug reports
        bugs = employee_context.get("bugs", [])
        if isinstance(bugs, dict):
            bugs_fixed = bugs.get("bugs_fixed_count", 0)
            bugs_intro = bugs.get("bugs_introduced_count", 0)
            if bugs_fixed > 0 or bugs_intro > 0:
                evidence_items.append({
                    "type": "bug_evidence",
                    "id": "BUGS-SUMMARY",
                    "data": bugs,
                })
        elif isinstance(bugs, list) and bugs:
            evidence_items.append({
                "type": "bug_evidence",
                "id": "BUGS-LIST",
                "data": {"count": len(bugs), "items": bugs},
            })

        return evidence_items

    def calculate_metrics(
        self,
        evidence_items: List[Dict[str, Any]],
        period: EvaluationPeriod,
    ) -> Dict[str, Any]:
        """
        Deterministic metric extraction:
        - Average test coverage %
        - Coverage delta %
        - Total tests added/modified
        - Untested PR count
        - Flaky test occurrences
        - Regressions caught prior to prod
        """
        coverage_samples: List[float] = []
        coverage_deltas: List[float] = []
        total_test_files = 0
        total_prs = 0
        untested_prs = 0
        failed_tests = 0
        flaky_tests = 0
        bugs_introduced = 0
        bugs_fixed = 0

        for item in evidence_items:
            itype = item["type"]
            data = item["data"]

            if itype == "pr_tests":
                total_prs += 1
                t_count = data.get("test_files_count", 0)
                total_test_files += t_count
                if t_count == 0:
                    untested_prs += 1

                cov = data.get("test_coverage_pct")
                if cov is not None:
                    coverage_samples.append(float(cov))

                delta = data.get("coverage_delta")
                if delta is not None:
                    coverage_deltas.append(float(delta))

                failed_tests += data.get("failed_tests_count", 0)
                flaky_tests += data.get("flaky_tests_count", 0)

            elif itype == "ci_test_run":
                tr = data.get("test_results", {})
                if isinstance(tr, dict):
                    failed_tests += tr.get("failed", 0)
                    flaky_tests += tr.get("flaky", 0)

            elif itype == "bug_evidence":
                bugs_introduced += data.get("bugs_introduced_count", 0)
                bugs_fixed += data.get("bugs_fixed_count", 0)

        avg_cov = (
            round(sum(coverage_samples) / len(coverage_samples), 1)
            if coverage_samples
            else 82.0
        )
        avg_delta = (
            round(sum(coverage_deltas) / len(coverage_deltas), 2)
            if coverage_deltas
            else 0.5
        )

        return {
            "average_coverage_pct": avg_cov,
            "average_coverage_delta": avg_delta,
            "total_test_files": total_test_files,
            "total_prs_evaluated": total_prs,
            "untested_prs": untested_prs,
            "failed_tests_count": failed_tests,
            "flaky_tests_count": flaky_tests,
            "bugs_introduced": bugs_introduced,
            "bugs_fixed": bugs_fixed,
        }

    def calculate_score(
        self,
        metrics: Dict[str, Any],
        evidence_items: List[Dict[str, Any]],
    ) -> Tuple[Optional[float], Dict[str, SubscoreBreakdown], List[EvidenceReference], float]:
        """
        Deterministic QA scoring across 6 dimensions:
            Test Coverage: 25
            Test Completeness: 20
            Regression Prevention: 20
            Test Reliability: 15
            Test Quality: 10
            Defect Prevention: 10
        Total = 100.
        """
        evidence_refs: List[EvidenceReference] = []

        # 1. Test Coverage (0-25): Target 80%+
        avg_cov = metrics.get("average_coverage_pct", 80.0)
        cov_score = ScoringEngine.normalize(avg_cov, 50.0, 95.0, 10.0, 25.0)

        # 2. Test Completeness (0-20): Penalize untested PRs
        untested = metrics.get("untested_prs", 0)
        completeness_deduction = min(12.0, untested * 4.0)
        completeness_score = max(6.0, 20.0 - completeness_deduction)

        # 3. Regression Prevention (0-20): Zero regressions introduced
        bugs_intro = metrics.get("bugs_introduced", 0)
        reg_deduction = min(15.0, bugs_intro * 5.0)
        regression_score = max(5.0, 20.0 - reg_deduction)

        # 4. Test Reliability (0-15): Absence of flaky tests
        flaky = metrics.get("flaky_tests_count", 0)
        flaky_deduction = min(10.0, flaky * 3.0)
        reliability_score = max(5.0, 15.0 - flaky_deduction)

        # 5. Test Quality (0-10): Positive coverage delta and test file updates
        delta = metrics.get("average_coverage_delta", 0.0)
        quality_score = 9.0 if delta >= 0 else max(4.0, 9.0 + (delta * 2.0))

        # 6. Defect Prevention (0-10): Bugs fixed
        fixed = metrics.get("bugs_fixed", 0)
        defect_score = min(10.0, 8.0 + (fixed * 1.0))

        subscores: Dict[str, SubscoreBreakdown] = {
            "test_coverage": SubscoreBreakdown(
                name="Test Coverage",
                score=round(cov_score, 1),
                max_score=25.0,
                explanation=f"Achieved average line coverage of {avg_cov}%.",
            ),
            "test_completeness": SubscoreBreakdown(
                name="Test Completeness",
                score=round(completeness_score, 1),
                max_score=20.0,
                explanation=f"Evaluated {metrics['total_prs_evaluated']} PRs, {untested} lacked test modifications.",
            ),
            "regression_prevention": SubscoreBreakdown(
                name="Regression Prevention",
                score=round(regression_score, 1),
                max_score=20.0,
                explanation=f"{bugs_intro} regressions traced to changes during evaluation window.",
            ),
            "test_reliability": SubscoreBreakdown(
                name="Test Reliability",
                score=round(reliability_score, 1),
                max_score=15.0,
                explanation=f"{flaky} flaky test executions detected.",
            ),
            "test_quality": SubscoreBreakdown(
                name="Test Quality",
                score=round(quality_score, 1),
                max_score=10.0,
                explanation=f"Coverage delta trajectory: {delta:+.2f}%.",
            ),
            "defect_prevention": SubscoreBreakdown(
                name="Defect Prevention",
                score=round(defect_score, 1),
                max_score=10.0,
                explanation=f"{fixed} defects successfully addressed with verified tests.",
            ),
        }

        total_score = sum(s.score for s in subscores.values())

        for item in evidence_items[:8]:
            evidence_refs.append(
                EvidenceReference(
                    source=item["type"],
                    id=item["id"],
                    metric="test_metric",
                    value=item["data"],
                )
            )

        confidence = ScoringEngine.calculate_confidence(
            evidence_count=len(evidence_items),
            recommended_count=3,
            time_coverage_ratio=1.0,
            source_reliability=0.92,
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
        if score is None:
            return await super().generate_explanation(score, subscores, metrics, evidence_items, employee_name, period)

        if not check_ollama_connection():
            return await super().generate_explanation(score, subscores, metrics, evidence_items, employee_name, period)

        prompt = f"""You are a QA Lead analyzing testing and reliability engineering evidence.

DEVELOPER: {employee_name}
PERIOD: {period.start_date} to {period.end_date}
DETERMINISTIC TESTING & RELIABILITY SCORE: {score:.1f}/100

SUBSCORES:
- Test Coverage: {subscores['test_coverage'].score}/{subscores['test_coverage'].max_score}
- Test Completeness: {subscores['test_completeness'].score}/{subscores['test_completeness'].max_score}
- Regression Prevention: {subscores['regression_prevention'].score}/{subscores['regression_prevention'].max_score}
- Test Reliability: {subscores['test_reliability'].score}/{subscores['test_reliability'].max_score}
- Test Quality: {subscores['test_quality'].score}/{subscores['test_quality'].max_score}
- Defect Prevention: {subscores['defect_prevention'].score}/{subscores['defect_prevention'].max_score}

METRICS:
- Coverage: {metrics['average_coverage_pct']}%, Delta: {metrics['average_coverage_delta']}%
- Untested PRs: {metrics['untested_prs']}, Flaky tests: {metrics['flaky_tests_count']}

Explain the score strictly based on the objective evidence. Do not change numeric values.
Return JSON ONLY:
{{
  "analysis": "<detailed QA assessment>",
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
                    parsed.get("analysis", f"QA testing evaluation for {employee_name}"),
                    parsed.get("strengths", []),
                    parsed.get("weaknesses", []),
                    parsed.get("recommendations", []),
                )
        except Exception as e:
            logger.warning("[QA-AGENT] LLM explanation fallback: %s", e)

        return await super().generate_explanation(score, subscores, metrics, evidence_items, employee_name, period)


# ─────────────────────────────────────────────────────────────────────────────
# LangGraph node
# ─────────────────────────────────────────────────────────────────────────────

def qa_analysis_node(state: AgentState) -> Dict[str, Any]:
    """
    Standard LangGraph node. If called with employee evaluation context, delegates
    to QAScoringAgent; otherwise handles PR test coverage analysis.
    """
    evidence = state.get("evidence", {})
    context = state.get("context", {})

    employee_id = context.get("employee_id")
    if employee_id:
        import asyncio
        agent = QAScoringAgent()
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
            "qa_score": score_res.score,
            "agent_history": state.get("agent_history", []) + ["qa_agent"],
            "next_agent": None,
        }

    # Fallback to single PR test coverage review
    prompt = f"""You are a QA engineer analyzing test coverage.
Coverage: {evidence.get('test_coverage_pct', 'N/A')}%
Tests Added: {evidence.get('tests_added', 0)}
Return JSON:
{{
  "analysis": "Test coverage is adequate.",
  "recommendations": ["Add edge case tests"],
  "risk_level": "low",
  "confidence": 0.8
}}
"""
    fallback = AgentAnalysisResult()
    try:
        llm = get_ollama_llm(temperature=0.3)
        response = llm.invoke(prompt)
        parsed = safe_parse(response, AgentAnalysisResult, fallback)
        return {
            **state,
            "analysis": parsed.analysis,
            "recommendations": parsed.recommendations,
            "risk_level": parsed.risk_level,
            "confidence": parsed.confidence,
            "agent_history": state.get("agent_history", []) + ["qa_agent"],
            "next_agent": None,
        }
    except Exception as e:
        return {
            **state,
            "errors": state.get("errors", []) + [f"QA agent error: {str(e)}"],
            "agent_history": state.get("agent_history", []) + ["qa_agent"],
            "next_agent": None,
        }
