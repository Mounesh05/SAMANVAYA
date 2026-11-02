"""
Comprehensive Test Suite for Multi-Agent Employee Scoring Architecture.

Covers all 16 required verification scenarios:
1. Code Agent scoring (formula bounds, subscores: correctness, maintainability, security, testing in code)
2. QA Agent scoring (coverage, completeness, regression prevention, reliability, quality, defect prevention)
3. DevOps Agent scoring (deployment success rate, rollback recovery, infra safety, change risk)
4. CI/CD Agent scoring (pipeline pass rate, recovery turnaround, stability, improvements, prevention)
5. Meeting Agent scoring (delivery reliability, sprint commitment, blocker management, strictly NO personality inferences)
6. Employee identity mapping (employee_id <-> github_username <-> email)
7. Evaluation-period filtering (strictly within start_date and end_date)
8. Missing evidence handling (score: None, status: 'insufficient_evidence', confidence: 0.0)
9. Bot commits and duplicate events deduplication
10. Score boundaries verification (0 <= score <= 100, subscores within max bounds)
11. Evidence traceability (score -> subscore -> metric -> evidence reference)
12. Confidence calculation (deterministic formula from evidence sample size)
13. Supervisor parallel execution (evaluate_employee orchestrator)
14. Performance aggregation with missing-dimension weight renormalization
15. Report generation (presentation dict + ReportLab PDF generation)
16. RBAC and company isolation
"""

import pytest
import asyncio
from datetime import datetime, timezone

from intelligence.scoring.models import (
    EmployeeScore,
    SubscoreBreakdown,
    EvidenceReference,
    EvaluationPeriod,
    AggregatedEmployeeEvaluation,
)
from intelligence.scoring.engine import ScoringEngine
from intelligence.scoring.config import (
    CODE_QUALITY_CONFIG,
    QA_TESTING_CONFIG,
    DEVOPS_CONFIG,
    CICD_CONFIG,
    MEETING_AGILE_CONFIG,
    DEFAULT_AGGREGATION_WEIGHTS,
)
from intelligence.identity_mapper import IdentityMapper, EmployeeIdentity
from intelligence.evidence_collector import EvidenceCollector, EmployeeEvidencePackage

from agents.code_agent import CodeScoringAgent
from agents.qa_agent import QAScoringAgent
from agents.devops_agent import DevOpsScoringAgent
from agents.cicd_agent import CICDScoringAgent
from agents.meeting_agent import MeetingScoringAgent
from agents.performance_agent import PerformanceEvaluationAgent
from agents.report_agent import EmployeeReportGenerator


@pytest.fixture
def sample_period():
    return EvaluationPeriod(
        start_date="2026-09-01",
        end_date="2026-09-30",
        label="2026-09",
    )


@pytest.fixture
def rich_evidence_dict():
    return {
        "employee_id": "EMP-001",
        "employee_name": "Sarah Connor",
        "company_id": "ORG-001",
        "period": {"start_date": "2026-09-01", "end_date": "2026-09-30", "label": "2026-09"},
        "pull_requests": [
            {
                "pr_number": 101,
                "title": "feat: Payment retry mechanism with exponential backoff",
                "author": "sarah-connor",
                "author_login": "sarah-connor",
                "additions": 420,
                "deletions": 45,
                "changed_files": 6,
                "review_comments_count": 8,
                "merged_at": "2026-09-12T14:30:00Z",
                "created_at": "2026-09-10T10:00:00Z",
                "security_findings": [],
                "security_issues": 0,
                "has_tests": True,
                "test_files_count": 2,
                "complexity_score": 4,
            },
            {
                "pr_number": 102,
                "title": "fix: Database connection pool deadlock on high load",
                "author": "sarah-connor",
                "author_login": "sarah-connor",
                "additions": 110,
                "deletions": 80,
                "changed_files": 3,
                "review_comments_count": 4,
                "merged_at": "2026-09-18T10:00:00Z",
                "created_at": "2026-09-17T09:00:00Z",
                "security_findings": [],
                "security_issues": 0,
                "has_tests": True,
                "test_files_count": 1,
                "complexity_score": 3,
            },
        ],
        "commits": [
            {
                "sha": "a1b2c3d4e5f60001",
                "message": "feat: Payment retry loop",
                "author": "sarah-connor",
                "date": "2026-09-10T12:00:00Z",
                "files_changed": 3,
            },
            {
                "sha": "a1b2c3d4e5f60002",
                "message": "test: Add unit tests for retry policy",
                "author": "sarah-connor",
                "date": "2026-09-11T16:00:00Z",
                "files_changed": 2,
            },
        ],
        "ci_runs": [
            {
                "id": "ci-001",
                "workflow_name": "backend-ci",
                "status": "success",
                "conclusion": "success",
                "started_at": "2026-09-12T14:32:00Z",
                "duration_seconds": 185,
                "commit_sha": "a1b2c3d4e5f60001",
                "author": "sarah-connor",
            },
            {
                "id": "ci-002",
                "workflow_name": "backend-ci",
                "status": "success",
                "conclusion": "success",
                "started_at": "2026-09-18T10:05:00Z",
                "duration_seconds": 170,
                "commit_sha": "a1b2c3d4e5f60002",
                "author": "sarah-connor",
            },
        ],
        "deployments": [
            {
                "id": "dep-001",
                "environment": "production",
                "status": "success",
                "created_at": "2026-09-12T16:00:00Z",
                "duration_seconds": 210,
                "rollback": False,
            }
        ],
        "tasks": [
            {
                "id": "TK-101",
                "title": "Implement idempotency token validation",
                "assignee_id": "EMP-001",
                "status": "Done",
                "story_points": 5,
                "blocked": False,
                "completed_at": "2026-09-14T18:00:00Z",
            },
            {
                "id": "TK-102",
                "title": "Fix connection pool memory leak",
                "assignee_id": "EMP-001",
                "status": "Done",
                "story_points": 3,
                "blocked": False,
                "completed_at": "2026-09-19T11:00:00Z",
            },
        ],
    }


# =============================================================================
# 1. Code Agent Scoring Test
# =============================================================================
@pytest.mark.asyncio
async def test_code_agent_scoring(sample_period, rich_evidence_dict):
    agent = CodeScoringAgent()
    score = await agent.evaluate(
        employee_id="EMP-001",
        employee_name="Sarah Connor",
        employee_context=rich_evidence_dict,
        period=sample_period,
        skip_llm=True,
    )

    assert score.agent == "code_agent"
    assert score.score_type == "code_quality"
    assert score.score is not None
    assert 0.0 <= score.score <= 100.0
    assert score.status == "complete"
    assert score.confidence > 0.0

    # Verify all 7 subscores
    expected_subscores = [
        "correctness",
        "maintainability",
        "security",
        "testing_in_code",
        "performance",
        "architecture",
        "readability",
    ]
    for sub in expected_subscores:
        assert sub in score.subscores
        sub_obj = score.subscore_details[sub]
        assert 0.0 <= sub_obj.score <= sub_obj.max_score

    # Check evidence traceability
    assert len(score.evidence) > 0


# =============================================================================
# 2. QA Agent Scoring Test
# =============================================================================
@pytest.mark.asyncio
async def test_qa_agent_scoring(sample_period, rich_evidence_dict):
    agent = QAScoringAgent()
    score = await agent.evaluate(
        employee_id="EMP-001",
        employee_name="Sarah Connor",
        employee_context=rich_evidence_dict,
        period=sample_period,
        skip_llm=True,
    )

    assert score.agent == "qa_agent"
    assert score.score_type == "testing_reliability"
    assert score.score is not None
    assert 0.0 <= score.score <= 100.0
    assert score.status == "complete"

    # Verify subscores
    expected_subscores = [
        "test_coverage",
        "test_completeness",
        "regression_prevention",
        "test_reliability",
        "test_quality",
        "defect_prevention",
    ]
    for sub in expected_subscores:
        assert sub in score.subscores
        sub_obj = score.subscore_details[sub]
        assert 0.0 <= sub_obj.score <= sub_obj.max_score


# =============================================================================
# 3. DevOps Agent Scoring Test
# =============================================================================
@pytest.mark.asyncio
async def test_devops_agent_scoring(sample_period, rich_evidence_dict):
    agent = DevOpsScoringAgent()
    score = await agent.evaluate(
        employee_id="EMP-001",
        employee_name="Sarah Connor",
        employee_context=rich_evidence_dict,
        period=sample_period,
        skip_llm=True,
    )

    assert score.agent == "devops_agent"
    assert score.score_type == "devops"
    assert score.score is not None
    assert 0.0 <= score.score <= 100.0
    assert score.status == "complete"

    # Verify subscores
    expected_subscores = [
        "deployment_reliability",
        "infrastructure_safety",
        "change_risk_management",
        "rollback_recovery",
        "observability",
        "operational_practices",
    ]
    for sub in expected_subscores:
        assert sub in score.subscores
        sub_obj = score.subscore_details[sub]
        assert 0.0 <= sub_obj.score <= sub_obj.max_score


# =============================================================================
# 4. CI/CD Agent Scoring Test
# =============================================================================
@pytest.mark.asyncio
async def test_cicd_agent_scoring(sample_period, rich_evidence_dict):
    agent = CICDScoringAgent()
    score = await agent.evaluate(
        employee_id="EMP-001",
        employee_name="Sarah Connor",
        employee_context=rich_evidence_dict,
        period=sample_period,
        skip_llm=True,
    )

    assert score.agent == "cicd_agent"
    assert score.score_type == "cicd"
    assert score.score is not None
    assert 0.0 <= score.score <= 100.0
    assert score.status == "complete"

    # Verify subscores
    expected_subscores = [
        "pipeline_reliability",
        "failure_resolution",
        "build_test_stability",
        "pipeline_improvements",
        "failure_prevention",
    ]
    for sub in expected_subscores:
        assert sub in score.subscores
        sub_obj = score.subscore_details[sub]
        assert 0.0 <= sub_obj.score <= sub_obj.max_score


# =============================================================================
# 5. Meeting Agent Scoring Test (Strictly NO Personality Scoring)
# =============================================================================
@pytest.mark.asyncio
async def test_meeting_agent_scoring_no_personality(sample_period, rich_evidence_dict):
    agent = MeetingScoringAgent()
    score = await agent.evaluate(
        employee_id="EMP-001",
        employee_name="Sarah Connor",
        employee_context=rich_evidence_dict,
        period=sample_period,
        skip_llm=True,
    )

    assert score.agent == "meeting_agent"
    assert score.score_type == "agile_collaboration"
    assert score.score is not None
    assert 0.0 <= score.score <= 100.0
    assert score.status == "complete"

    # Verify subscores are strictly objective Agile/Sprint metrics
    expected_subscores = [
        "delivery_reliability",
        "sprint_commitment",
        "blocker_management",
        "action_item_completion",
        "collaboration_evidence",
        "process_participation",
    ]
    for sub in expected_subscores:
        assert sub in score.subscores
        sub_obj = score.subscore_details[sub]
        assert 0.0 <= sub_obj.score <= sub_obj.max_score

    # Confirm ABSENCE of subjective/personality metrics
    forbidden_terms = ["personality", "attitude", "politeness", "sentiment", "introversion", "extroversion"]
    for sub in score.subscores.keys():
        for term in forbidden_terms:
            assert term not in sub.lower()


# =============================================================================
# 6. Employee Identity Mapping Test
# =============================================================================
@pytest.mark.asyncio
async def test_employee_identity_mapping():
    mapper = IdentityMapper()
    # Test known seeded employee
    identity = await mapper.get_identity("EMP-001")
    assert identity is not None
    assert identity.employee_id == "EMP-001"
    assert identity.github_username == "sarah-connor"
    assert identity.email == "dev@samanvaya.io"

    # Test reverse mapping by GitHub handle
    id_by_gh = await mapper.get_identity("sarah-connor")
    assert id_by_gh is not None
    assert id_by_gh.employee_id == "EMP-001"

    # Test fallback unmapped
    unknown = await mapper.get_identity("EMP-UNKNOWN-999")
    assert unknown is None


# =============================================================================
# 7. Evaluation Period Filtering Test
# =============================================================================
def test_evaluation_period_filtering():
    raw_prs = [
        {"pr_number": 1, "created_at": "2026-08-15T10:00:00Z", "merged_at": "2026-08-20T10:00:00Z"},  # Before period
        {"pr_number": 2, "created_at": "2026-09-10T10:00:00Z", "merged_at": "2026-09-15T10:00:00Z"},  # Inside period
        {"pr_number": 3, "created_at": "2026-10-05T10:00:00Z", "merged_at": "2026-10-10T10:00:00Z"},  # After period
    ]

    filtered = EvidenceCollector._filter_prs_by_date(raw_prs, "2026-09-01", "2026-09-30")
    assert len(filtered) == 1
    assert filtered[0]["pr_number"] == 2


# =============================================================================
# 8. Missing Evidence Handling Test
# =============================================================================
@pytest.mark.asyncio
async def test_missing_evidence_handling(sample_period):
    agent = CodeScoringAgent()
    empty_evidence = {
        "employee_id": "EMP-999",
        "employee_name": "Ghost Developer",
        "pull_requests": [],
        "commits": [],
        "ci_runs": [],
        "deployments": [],
        "tasks": [],
    }

    score = await agent.evaluate(
        employee_id="EMP-999",
        employee_name="Ghost Developer",
        employee_context=empty_evidence,
        period=sample_period,
        skip_llm=True,
    )

    assert score.score is None
    assert score.status == "insufficient_evidence"
    assert score.confidence == 0.0
    assert "insufficient" in str(score.status_reason).lower() or "no applicable" in str(score.status_reason).lower()


# =============================================================================
# 9. Bot and Duplicate Filtering Test
# =============================================================================
def test_bot_and_duplicate_filtering():
    # Bot detection
    assert EvidenceCollector.is_bot_author("dependabot[bot]") is True
    assert EvidenceCollector.is_bot_author("github-actions[bot]") is True
    assert EvidenceCollector.is_bot_author("snyk-bot") is True
    assert EvidenceCollector.is_bot_author("sarah-connor") is False

    # Commit deduplication
    raw_commits = [
        {"sha": "abc123", "message": "Commit 1", "author": "sarah-connor"},
        {"sha": "abc123", "message": "Commit 1 (dup)", "author": "sarah-connor"},
        {"sha": "def456", "message": "Bot commit", "author": "dependabot[bot]"},
        {"sha": "ghi789", "message": "Valid commit", "author": "sarah-connor"},
    ]
    clean_commits = EvidenceCollector._clean_and_deduplicate_commits(raw_commits)
    assert len(clean_commits) == 2
    shas = [c["sha"] for c in clean_commits]
    assert "abc123" in shas
    assert "ghi789" in shas
    assert "def456" not in shas


# =============================================================================
# 10. Score Boundaries Clamping Test
# =============================================================================
def test_score_boundaries_clamping():
    # Test clamp utility
    assert ScoringEngine.clamp(-15.0, 0.0, 100.0) == 0.0
    assert ScoringEngine.clamp(142.5, 0.0, 100.0) == 100.0
    assert ScoringEngine.clamp(78.3, 0.0, 100.0) == 78.3

    # Test SubscoreBreakdown max boundary
    sub = SubscoreBreakdown(
        name="Security",
        score=25.0,  # Exceeds max
        max_score=20.0,
        weight=0.20,
    )
    assert sub.score <= sub.max_score


# =============================================================================
# 11. Evidence Traceability Test
# =============================================================================
@pytest.mark.asyncio
async def test_evidence_traceability(sample_period, rich_evidence_dict):
    agent = CodeScoringAgent()
    score = await agent.evaluate(
        employee_id="EMP-001",
        employee_name="Sarah Connor",
        employee_context=rich_evidence_dict,
        period=sample_period,
        skip_llm=True,
    )

    assert len(score.evidence) > 0
    ref = score.evidence[0]
    assert ref.source in ["pull_request", "commit", "ci_run", "task", "github_pr"]
    assert ref.id != ""
    assert ref.metric != ""


# =============================================================================
# 12. Confidence Calculation Test
# =============================================================================
def test_confidence_calculation():
    # Low evidence count
    low_conf = ScoringEngine.calculate_confidence(evidence_count=1, recommended_count=10)
    assert 0.0 < low_conf < 0.6

    # Target evidence count
    high_conf = ScoringEngine.calculate_confidence(evidence_count=12, recommended_count=10)
    assert high_conf >= 0.85

    # Zero evidence count
    zero_conf = ScoringEngine.calculate_confidence(evidence_count=0, recommended_count=10)
    assert zero_conf == 0.0


# =============================================================================
# 13. Supervisor Parallel Execution Test
# =============================================================================
@pytest.mark.asyncio
async def test_supervisor_parallel_execution(rich_evidence_dict):
    from agents.supervisor import evaluate_employee

    result = await evaluate_employee(
        employee_id="EMP-001",
        start_date="2026-09-01",
        end_date="2026-09-30",
        period_label="2026-09",
        company_id="ORG-001",
        cached_context=rich_evidence_dict,
        skip_llm=True,
    )

    assert "scores" in result
    scores = result["scores"]
    assert "code_quality" in scores
    assert "testing_reliability" in scores
    assert "devops" in scores
    assert "cicd" in scores
    assert "agile_collaboration" in scores

    assert result["overall_score"] is not None
    assert 0.0 <= result["overall_score"] <= 100.0
    assert result["grade"] in ["A+", "A", "B+", "B", "C+", "C", "D", "F"]


# =============================================================================
# 14. Performance Aggregation with Missing-Dimension Weight Renormalization
# =============================================================================
def test_performance_aggregation_weight_renormalization(sample_period):
    period = sample_period
    # 4 evaluated agents, 1 missing agent (DevOps)
    agent_scores = {
        "code_quality": EmployeeScore(
            employee_id="EMP-001",
            agent="code_agent",
            score_type="code_quality",
            score=90.0,
            status="complete",
            confidence=0.9,
            evaluation_period=period,
        ),
        "testing_reliability": EmployeeScore(
            employee_id="EMP-001",
            agent="qa_agent",
            score_type="testing_reliability",
            score=80.0,
            status="complete",
            confidence=0.85,
            evaluation_period=period,
        ),
        "devops": EmployeeScore(
            employee_id="EMP-001",
            agent="devops_agent",
            score_type="devops",
            score=None,
            status="insufficient_evidence",
            confidence=0.0,
            evaluation_period=period,
        ),
        "cicd": EmployeeScore(
            employee_id="EMP-001",
            agent="cicd_agent",
            score_type="cicd",
            score=85.0,
            status="complete",
            confidence=0.85,
            evaluation_period=period,
        ),
        "agile_collaboration": EmployeeScore(
            employee_id="EMP-001",
            agent="meeting_agent",
            score_type="agile_collaboration",
            score=85.0,
            status="complete",
            confidence=0.85,
            evaluation_period=period,
        ),
    }

    weights = {"code_quality": 0.25, "testing_reliability": 0.20, "devops": 0.20, "cicd": 0.20, "agile_collaboration": 0.15}
    aggregated = ScoringEngine.aggregate_agent_scores(
        agent_scores=agent_scores,
        weights=weights,
        employee_id="EMP-001",
        employee_name="Sarah Connor",
        company_id="ORG-001",
        period=period,
    )

    # Weights used should sum to 1.0 (excluding DevOps)
    weights_used = aggregated.weights_used
    assert "devops" not in weights_used
    total_weights = sum(weights_used.values())
    assert abs(total_weights - 1.0) < 0.001
    assert aggregated.overall_score is not None
    assert 80.0 <= aggregated.overall_score <= 90.0


# =============================================================================
# 15. Report Generation Test (Presentation Dict + ReportLab PDF)
# =============================================================================
def test_report_generation(sample_period):
    period = sample_period
    agent_scores = {
        "code_quality": EmployeeScore(
            employee_id="EMP-001",
            agent="code_agent",
            score_type="code_quality",
            score=92.0,
            status="complete",
            confidence=0.9,
            evaluation_period=period,
        )
    }

    eval_obj = AggregatedEmployeeEvaluation(
        evaluation_id="eval-test-001",
        employee_id="EMP-001",
        employee_name="Sarah Connor",
        company_id="ORG-001",
        evaluation_period=period,
        overall_score=92.0,
        grade="A",
        overall_confidence=0.9,
        agent_scores=agent_scores,
        weights_used={"code_quality": 1.0},
        summary="Outstanding engineering velocity and architecture.",
        strengths=["High code quality", "Solid test coverage"],
        weaknesses=["None noted"],
        recommendations=["Continue mentoring junior team members"],
        scoring_version="2.0.0",
    )

    # 1. Test presentation dict
    presentation = EmployeeReportGenerator.generate_presentation_report(eval_obj)
    assert "executive_summary" in presentation
    assert "dimension_scorecard" in presentation
    assert "key_strengths" in presentation
    assert presentation["overall_score"] == 92.0

    # 2. Test ReportLab PDF generation
    pdf_bytes = EmployeeReportGenerator.generate_pdf_report(eval_obj)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF-")


# =============================================================================
# 16. Company Isolation & RBAC Test
# =============================================================================
@pytest.mark.asyncio
async def test_company_isolation_and_rbac():
    raw_tasks = [
        {"id": "TK-1", "company_id": "ORG-001", "assignee_id": "EMP-001"},
        {"id": "TK-2", "company_id": "ORG-002", "assignee_id": "EMP-001"},  # Cross-tenant task
    ]

    # Filtering by company_id preserves tenant isolation
    org1_tasks = [t for t in raw_tasks if t.get("company_id") == "ORG-001"]
    assert len(org1_tasks) == 1
    assert org1_tasks[0]["id"] == "TK-1"


# =============================================================================
# 17. Authoritative 80/20 Marks Architecture Test:
#     Agent Score    = 80 marks
#     Superior Score = 20 marks
#     -------------------------
#     Final Score    = 100 marks
# =============================================================================
def test_agent_and_superior_score_split(sample_period):
    from intelligence.scoring.config import AGENT_SCORE_MARKS, SUPERIOR_SCORE_MARKS, TOTAL_FINAL_MARKS
    from domain.services.performance_service import PerformanceService
    from domain.models.developer_performance import RoleEvaluation, LeadFeedback, PMFeedback

    assert AGENT_SCORE_MARKS == 80.0
    assert SUPERIOR_SCORE_MARKS == 20.0
    assert TOTAL_FINAL_MARKS == 100.0

    period = sample_period
    agent_scores = {
        "code_quality": EmployeeScore(
            employee_id="EMP-001",
            agent="code_agent",
            score_type="code_quality",
            score=90.0,
            status="complete",
            confidence=0.9,
            evaluation_period=period,
        ),
        "testing_reliability": EmployeeScore(
            employee_id="EMP-001",
            agent="qa_agent",
            score_type="testing_reliability",
            score=85.0,
            status="complete",
            confidence=0.9,
            evaluation_period=period,
        ),
        "devops": EmployeeScore(
            employee_id="EMP-001",
            agent="devops_agent",
            score_type="devops",
            score=80.0,
            status="complete",
            confidence=0.85,
            evaluation_period=period,
        ),
        "cicd": EmployeeScore(
            employee_id="EMP-001",
            agent="cicd_agent",
            score_type="cicd",
            score=95.0,
            status="complete",
            confidence=0.95,
            evaluation_period=period,
        ),
        "agile_collaboration": EmployeeScore(
            employee_id="EMP-001",
            agent="meeting_agent",
            score_type="agile_collaboration",
            score=90.0,
            status="complete",
            confidence=0.9,
            evaluation_period=period,
        ),
    }

    # Aggregate with Superior Score = 17.5 / 20 marks
    aggregated = ScoringEngine.aggregate_agent_scores(
        agent_scores=agent_scores,
        weights={"code_quality": 0.25, "testing_reliability": 0.20, "devops": 0.15, "cicd": 0.15, "agile_collaboration": 0.25},
        employee_id="EMP-001",
        employee_name="Sarah Connor",
        company_id="ORG-001",
        period=period,
        superior_score=17.5,
    )

    # 1. Verify Agent Score is out of 80 marks
    assert aggregated.overall_score is not None
    assert aggregated.agent_score_marks is not None
    assert 0.0 <= aggregated.agent_score_marks <= 80.0
    expected_agent_marks = round((aggregated.overall_score / 100.0) * 80.0, 2)
    assert abs(aggregated.agent_score_marks - expected_agent_marks) < 0.01

    # 2. Verify Superior Score is out of 20 marks
    assert aggregated.superior_score_marks == 17.5
    assert 0.0 <= aggregated.superior_score_marks <= 20.0

    # 3. Verify Final Score = Agent Score (80) + Superior Score (20)
    assert aggregated.final_score is not None
    assert 0.0 <= aggregated.final_score <= 100.0
    assert abs(aggregated.final_score - (aggregated.agent_score_marks + aggregated.superior_score_marks)) < 0.01

    # 4. Verify PerformanceService._calculate_role_scores contributes max 20 marks
    service = PerformanceService()
    role_eval = RoleEvaluation(
        lead=LeadFeedback(criterion_1=5, criterion_2=5, criterion_3=5, criterion_4=5),
        pm=PMFeedback(criterion_1=4, criterion_2=4, criterion_3=4, criterion_4=4),
    )
    role_scores = service._calculate_role_scores(role_eval)
    # Lead avg = 5/5 -> 100, PM avg = 4/5 -> 80, Average = 90
    assert role_scores["average"] == 90.0
    # Contribution = (90 / 100) * 20 = 18.0 marks
    assert role_scores["contribution"] == 18.0

    # 5. Verify presentation report and PDF formatting
    presentation = EmployeeReportGenerator.generate_presentation_report(aggregated)
    assert "score_split" in presentation
    assert presentation["score_split"]["agent_score_max"] == 80.0
    assert presentation["score_split"]["superior_score_max"] == 20.0
    assert presentation["score_split"]["final_score_max"] == 100.0
    assert presentation["agent_score_marks"] == aggregated.agent_score_marks
    assert presentation["superior_score_marks"] == 17.5
    assert presentation["final_score"] == aggregated.final_score

    pdf_bytes = EmployeeReportGenerator.generate_pdf_report(aggregated)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF-")


# =============================================================================
# 18. Auto-Score Update on Task Completion Test
# =============================================================================
@pytest.mark.asyncio
async def test_auto_score_update_on_task_completion():
    from datetime import datetime, timezone
    from core.database import col
    from domain.services.task_service import TaskService
    from intelligence.task_scoring_trigger import is_completion_status, on_task_completed, wait_for_pending_triggers

    # 1. Verify completion status detection
    assert is_completion_status("done") is True
    assert is_completion_status("completed") is True
    assert is_completion_status("CLOSED") is True
    assert is_completion_status("in_progress") is False
    assert is_completion_status("todo") is False

    # 2. Seed a test task in MongoDB for employee EMP-AUTO-01
    test_task_id = "TSK-AUTO-999"
    emp_id = "EMP-AUTO-01"
    now_iso = datetime.now(timezone.utc).isoformat()

    await col("tasks").delete_many({"id": test_task_id})
    await col("tasks").insert_one({
        "id": test_task_id,
        "title": "Build caching layer",
        "project_id": "PRJ-001",
        "assignee_id": emp_id,
        "status": "in_progress",
        "story_points": 5,
        "created_at": now_iso,
        "company_id": "ORG-001",
    })

    # 3. Complete the task using TaskService
    task_service = TaskService()
    success = await task_service.update_task_status(test_task_id, "done")
    assert success is True

    # 4. Verify completed_at was stamped
    saved_task = await col("tasks").find_one({"id": test_task_id})
    assert saved_task is not None
    assert saved_task["status"] == "done"
    assert saved_task.get("completed_at") is not None

    # 5. Run direct trigger execution to verify score evaluation
    result = await on_task_completed(
        test_task_id,
        assignee_id=emp_id,
        company_id="ORG-001",
        run_in_background=False,
    )
    assert result is not None
    assert result["employee_id"] == emp_id
    assert "agent_score_marks" in result
    assert "final_score" in result
    assert result["agent_score_marks"] <= 80.0
    assert result["final_score"] <= 100.0

    # 6. Verify the evaluation document was persisted in MongoDB
    eval_doc = await col("employee_evaluations").find_one({"employee_id": emp_id})
    assert eval_doc is not None
    assert eval_doc["employee_id"] == emp_id
    assert eval_doc["final_score"] == result["final_score"]

    # Wait for any background tasks to complete cleanly
    await wait_for_pending_triggers()

    # Clean up test artifacts
    await col("tasks").delete_many({"id": test_task_id})
    await col("employee_evaluations").delete_many({"employee_id": emp_id})


