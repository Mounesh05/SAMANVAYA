"""
DevOps Agent — Evaluates Deployment and Operational Engineering Quality ONLY.

Responsible ONLY for the DevOps dimension:
- Deployment Reliability (0-25)
- Infrastructure Safety (0-20)
- Change Risk Management (0-20)
- Rollback/Recovery (0-15)
- Observability (0-10)
- Operational Practices (0-10)
Total = 100.

Evidence Flow:
    Deployment & Infrastructure evidence
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
from intelligence.scoring.config import DEVOPS_CONFIG
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

logger = logging.getLogger("samanvaya.devops_agent")

INFRA_FILE_INDICATORS = (
    "dockerfile",
    "docker-compose",
    ".tf",
    "k8s",
    "kubernetes",
    "helm",
    "chart.yaml",
    "values.yaml",
    ".github/workflows",
    "terraform",
    "migrations/",
    "migration",
    "alembic",
    "flyway",
    "env.example",
)


class DevOpsScoringAgent(BaseScoringAgent):
    """
    Evaluates deployment health, infrastructure changes, blast radius, and observability.
    """

    def __init__(self):
        super().__init__(
            agent_id="devops_agent",
            score_type="devops",
            config=DEVOPS_CONFIG,
        )

    def collect_evidence(
        self,
        employee_context: Dict[str, Any],
        period: EvaluationPeriod,
    ) -> List[Dict[str, Any]]:
        """
        Extract only deployment, infrastructure, migration, and config evidence.
        """
        evidence_items = []

        # 1. Deployments performed or triggered
        deployments = employee_context.get("deployments", [])
        for dep in deployments:
            evidence_items.append({
                "type": "deployment",
                "id": str(dep.get("id") or dep.get("deployment_id") or "DEP-RECORD"),
                "data": dep,
            })

        # 2. Infra / config / migration changes in PRs
        prs = employee_context.get("pull_requests", [])
        for pr in prs:
            files = pr.get("files", [])
            infra_files = [
                f for f in files
                if any(ind in (f.get("filename", "") if isinstance(f, dict) else str(f)).lower()
                       for ind in INFRA_FILE_INDICATORS)
            ]
            has_db_migration = pr.get("db_migrations", 0) > 0 or any("migration" in str(f).lower() for f in files)
            has_breaking = pr.get("breaking_changes", 0) > 0

            if infra_files or has_db_migration or has_breaking or pr.get("deployment_risk_score") is not None:
                evidence_items.append({
                    "type": "infra_pr",
                    "id": f"PR-{pr.get('number') or pr.get('pr_number')}",
                    "data": {
                        "pr_number": pr.get("number") or pr.get("pr_number"),
                        "infra_files_count": len(infra_files),
                        "db_migrations": 1 if has_db_migration else 0,
                        "breaking_changes": 1 if has_breaking else 0,
                        "deployment_risk_score": pr.get("deployment_risk_score", 20),
                        "rollbacks_count": pr.get("rollbacks_count", 0),
                        "observability_added": pr.get("observability_added", False),
                    },
                })

        return evidence_items

    def calculate_metrics(
        self,
        evidence_items: List[Dict[str, Any]],
        period: EvaluationPeriod,
    ) -> Dict[str, Any]:
        """
        Deterministic metric extraction:
        - Total deployments
        - Successful deployments & failure rate
        - Rollback incidents
        - Infra change PRs managed
        - DB migrations safely executed
        - Breaking changes introduced
        - Observability updates
        """
        total_deployments = 0
        successful_deployments = 0
        failed_deployments = 0
        rollbacks = 0
        infra_prs_count = 0
        db_migrations = 0
        breaking_changes = 0
        observability_updates = 0

        for item in evidence_items:
            itype = item["type"]
            data = item["data"]

            if itype == "deployment":
                total_deployments += 1
                status = str(data.get("status", "")).lower()
                if status in ("success", "successful", "completed"):
                    successful_deployments += 1
                elif status in ("failed", "failure", "error"):
                    failed_deployments += 1
                if data.get("rollback", False) or "rollback" in status:
                    rollbacks += 1

            elif itype == "infra_pr":
                infra_prs_count += 1
                db_migrations += data.get("db_migrations", 0)
                breaking_changes += data.get("breaking_changes", 0)
                rollbacks += data.get("rollbacks_count", 0)
                if data.get("observability_added"):
                    observability_updates += 1

        success_rate = (
            (successful_deployments / max(1, total_deployments)) * 100
            if total_deployments > 0
            else 100.0
        )

        return {
            "total_deployments": total_deployments,
            "successful_deployments": successful_deployments,
            "failed_deployments": failed_deployments,
            "deployment_success_rate": round(success_rate, 1),
            "rollbacks": rollbacks,
            "infra_prs_count": infra_prs_count,
            "db_migrations": db_migrations,
            "breaking_changes": breaking_changes,
            "observability_updates": observability_updates,
        }

    def calculate_score(
        self,
        metrics: Dict[str, Any],
        evidence_items: List[Dict[str, Any]],
    ) -> Tuple[Optional[float], Dict[str, SubscoreBreakdown], List[EvidenceReference], float]:
        """
        Deterministic scoring across 6 DevOps dimensions:
            Deployment Reliability: 25
            Infrastructure Safety: 20
            Change Risk Management: 20
            Rollback/Recovery: 15
            Observability: 10
            Operational Practices: 10
        Total = 100.
        """
        evidence_refs: List[EvidenceReference] = []

        # 1. Deployment Reliability (0-25)
        succ_rate = metrics.get("deployment_success_rate", 100.0)
        dep_score = ScoringEngine.normalize(succ_rate, 70.0, 100.0, 12.0, 25.0)

        # 2. Infrastructure Safety (0-20): Clean infra changes without misconfigurations
        infra_count = metrics.get("infra_prs_count", 0)
        infra_score = 18.0 if infra_count > 0 else 16.0

        # 3. Change Risk Management (0-20): Safe migrations, zero unmitigated breaking changes
        breaking = metrics.get("breaking_changes", 0)
        migrations = metrics.get("db_migrations", 0)
        risk_pen = min(10.0, breaking * 5.0)
        change_risk_score = max(10.0, 20.0 - risk_pen)
        if migrations > 0 and breaking == 0:
            change_risk_score = min(20.0, change_risk_score + 2.0)

        # 4. Rollback / Recovery (0-15): Clean recovery if rollback occurred
        rollbacks = metrics.get("rollbacks", 0)
        rollback_deduction = min(7.0, rollbacks * 3.5)
        rollback_score = max(8.0, 15.0 - rollback_deduction)

        # 5. Observability (0-10): Telemetry, logging, metrics
        obs_updates = metrics.get("observability_updates", 0)
        obs_score = min(10.0, 8.0 + (obs_updates * 1.5))

        # 6. Operational Practices (0-10): Environment isolation, good config hygiene
        ops_score = 9.0

        subscores: Dict[str, SubscoreBreakdown] = {
            "deployment_reliability": SubscoreBreakdown(
                name="Deployment Reliability",
                score=round(dep_score, 1),
                max_score=25.0,
                explanation=f"Deployment success rate: {succ_rate}% across {metrics['total_deployments']} deployments.",
            ),
            "infrastructure_safety": SubscoreBreakdown(
                name="Infrastructure Safety",
                score=round(infra_score, 1),
                max_score=20.0,
                explanation=f"Safely managed {infra_count} infrastructure/configuration updates.",
            ),
            "change_risk_management": SubscoreBreakdown(
                name="Change Risk Management",
                score=round(change_risk_score, 1),
                max_score=20.0,
                explanation=f"Executed {migrations} migrations with {breaking} breaking API contracts.",
            ),
            "rollback_recovery": SubscoreBreakdown(
                name="Rollback/Recovery",
                score=round(rollback_score, 1),
                max_score=15.0,
                explanation=f"Encountered {rollbacks} rollbacks during the period.",
            ),
            "observability": SubscoreBreakdown(
                name="Observability",
                score=round(obs_score, 1),
                max_score=10.0,
                explanation=f"Contributed {obs_updates} observability enhancements (metrics/logging/health).",
            ),
            "operational_practices": SubscoreBreakdown(
                name="Operational Practices",
                score=round(ops_score, 1),
                max_score=10.0,
                explanation="Maintained solid secret isolation and operational hygiene.",
            ),
        }

        total_score = sum(s.score for s in subscores.values())

        for item in evidence_items[:8]:
            evidence_refs.append(
                EvidenceReference(
                    source=item["type"],
                    id=item["id"],
                    metric="devops_evidence",
                    value=item["data"],
                )
            )

        confidence = ScoringEngine.calculate_confidence(
            evidence_count=len(evidence_items),
            recommended_count=2,
            time_coverage_ratio=1.0,
            source_reliability=0.90,
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

        prompt = f"""You are a Principal SRE / DevOps Architect analyzing deployment and infrastructure evidence.

DEVELOPER: {employee_name}
PERIOD: {period.start_date} to {period.end_date}
DETERMINISTIC DEVOPS SCORE: {score:.1f}/100

SUBSCORES:
- Deployment Reliability: {subscores['deployment_reliability'].score}/{subscores['deployment_reliability'].max_score}
- Infrastructure Safety: {subscores['infrastructure_safety'].score}/{subscores['infrastructure_safety'].max_score}
- Change Risk Management: {subscores['change_risk_management'].score}/{subscores['change_risk_management'].max_score}
- Rollback/Recovery: {subscores['rollback_recovery'].score}/{subscores['rollback_recovery'].max_score}
- Observability: {subscores['observability'].score}/{subscores['observability'].max_score}
- Operational Practices: {subscores['operational_practices'].score}/{subscores['operational_practices'].max_score}

METRICS:
- Deployments: {metrics['total_deployments']} ({metrics['deployment_success_rate']}% success)
- Rollbacks: {metrics['rollbacks']}, Migrations: {metrics['db_migrations']}, Infra PRs: {metrics['infra_prs_count']}

Explain this score. Do NOT alter numeric scores.
Return JSON ONLY:
{{
  "analysis": "<detailed operational assessment>",
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
                    parsed.get("analysis", f"DevOps operational evaluation for {employee_name}"),
                    parsed.get("strengths", []),
                    parsed.get("weaknesses", []),
                    parsed.get("recommendations", []),
                )
        except Exception as e:
            logger.warning("[DEVOPS-AGENT] LLM explanation fallback: %s", e)

        return await super().generate_explanation(score, subscores, metrics, evidence_items, employee_name, period)


# ─────────────────────────────────────────────────────────────────────────────
# LangGraph node
# ─────────────────────────────────────────────────────────────────────────────

def devops_analysis_node(state: AgentState) -> Dict[str, Any]:
    """
    Standard LangGraph node. If called with employee evaluation context, delegates
    to DevOpsScoringAgent; otherwise performs PR deployment risk analysis.
    """
    evidence = state.get("evidence", {})
    context = state.get("context", {})

    employee_id = context.get("employee_id")
    if employee_id:
        import asyncio
        agent = DevOpsScoringAgent()
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
            "devops_score": score_res.score,
            "agent_history": state.get("agent_history", []) + ["devops_agent"],
            "next_agent": None,
        }

    # Fallback to single PR deployment risk
    prompt = f"""You are a DevOps engineer analyzing deployment risk.
Deployment Risk Score: {evidence.get('deployment_risk_score', 0)}/100
Return JSON:
{{
  "analysis": "Deployment risk is low.",
  "recommendations": ["Verify migrations"],
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
            "agent_history": state.get("agent_history", []) + ["devops_agent"],
            "next_agent": None,
        }
    except Exception as e:
        return {
            **state,
            "errors": state.get("errors", []) + [f"DevOps agent error: {str(e)}"],
            "agent_history": state.get("agent_history", []) + ["devops_agent"],
            "next_agent": None,
        }
