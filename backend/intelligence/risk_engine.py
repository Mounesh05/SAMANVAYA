"""
Risk Engine (Main Interface for Intelligence Layer).
Central coordinator for all risk calculations and evidence building.

This is the main entry point for Layer 5 (Intelligence Engine).
NO LLM - pure computation and rule-based analysis.

NOTE: This is the SIMPLE risk engine for basic metrics.
For DEEP ANALYSIS, use EvidenceBuilder + CodeAgent directly (see github_service.py)
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone
from intelligence.rules.risk_rules import (
    RiskRules,
    PR_SIZE_LARGE_THRESHOLD, PR_SIZE_MEDIUM_THRESHOLD, PR_SIZE_SMALL_THRESHOLD,
    PR_SIZE_LARGE_RISK, PR_SIZE_MEDIUM_RISK, PR_SIZE_SMALL_RISK,
    CHURN_HIGH_THRESHOLD, CHURN_MEDIUM_THRESHOLD, CHURN_HIGH_RISK, CHURN_MEDIUM_RISK,
    TEST_FAILURE_RISK, TEST_NONE_PASSING_RISK,
    COVERAGE_DECREASE_RISK,
    PR_STALE_THRESHOLD_HOURS, PR_STALE_RISK,
    SPRINT_BLOCKED_HIGH_PCT, SPRINT_BLOCKED_HIGH_RISK, SPRINT_BLOCKED_LOW_RISK,
    SPRINT_BEHIND_SCHEDULE_RISK, SPRINT_SLIGHT_BEHIND_RISK,
    SPRINT_SCOPE_CREEP_HIGH_PCT, SPRINT_SCOPE_CREEP_HIGH_RISK, SPRINT_SCOPE_CREEP_LOW_RISK,
    SPRINT_LOW_COMPLETION_RISK, SPRINT_LOW_COMPLETION_PCT, SPRINT_TIME_ELAPSED_PCT,
    DEPLOY_BUILD_FAILURE_HIGH_PCT, DEPLOY_BUILD_FAILURE_LOW_PCT,
    DEPLOY_BUILD_FAILURE_HIGH_RISK, DEPLOY_BUILD_FAILURE_LOW_RISK,
    DEPLOY_DEPLOY_FAILURE_HIGH_PCT, DEPLOY_DEPLOY_FAILURE_LOW_PCT,
    DEPLOY_DEPLOY_FAILURE_HIGH_RISK, DEPLOY_DEPLOY_FAILURE_LOW_RISK,
    DEPLOY_ROLLBACK_HIGH_PCT, DEPLOY_ROLLBACK_HIGH_RISK, DEPLOY_ROLLBACK_LOW_RISK,
)
from repositories.pr_repository import PRRepository
from repositories.sprint_repository import SprintRepository
from repositories.story_repository import StoryRepository
from domain.services.risk_config_service import get_risk_config_service


class RiskEngine:
    """
    Central risk calculation engine for SIMPLE analysis.
    Coordinates all metrics calculators using formulas (NO AI, NO TOOLS).
    
    For DEEP analysis with static analyzers and AI, use AnalyzerRegistry directly.
    
    Uses configurable risk weights and thresholds from database (with fallback to defaults).
    """

    def __init__(self):
        self.pr_repo = PRRepository()
        self.sprint_repo = SprintRepository()
        self.story_repo = StoryRepository()
        self._config_service = get_risk_config_service()
    
    async def _classify_risk_level(
        self,
        risk_score: int,
        project_id: Optional[str] = None
    ) -> str:
        """
        Classify risk score using configurable thresholds.
        
        Args:
            risk_score: Integer 0-100
            project_id: Optional project ID for project-specific thresholds
        
        Returns:
            Risk level: CRITICAL|HIGH|MEDIUM|LOW
        """
        config = await self._config_service.get_configuration(project_id)
        thresholds = config.risk_thresholds
        
        if risk_score >= thresholds.critical:
            return "CRITICAL"
        elif risk_score >= thresholds.high:
            return "HIGH"
        elif risk_score >= thresholds.medium:
            return "MEDIUM"
        else:
            return "LOW"

    async def analyze_pull_request(
        self,
        pr_id: str,
        files_changed: int = None,
        lines_added: int = None,
        lines_deleted: int = None,
        changed_files: list[str] = None,
        commit_count: int = None,
        pr_age_hours: float = None,
        tests_passed: int = 0,
        tests_failed: int = 0,
        previous_coverage: float = None,
        current_coverage: float = None,
    ) -> Dict[str, Any]:
        """
        Analyze a pull request and return risk evidence.
        
        If data is not provided, attempts to fetch from database.
        
        Args:
            pr_id: Pull request ID
            ... (metrics - if None, fetched from DB)
        
        Returns:
            Evidence package with risk score and factors
        """
        # Fetch PR data if not provided
        if files_changed is None:
            pr_data = await self.pr_repo.find_by_id(pr_id)
            if pr_data:
                files_changed = pr_data.get("files_changed_count")  # Preserve None
                commit_count = pr_data.get("commit_count")  # Preserve None
                # Other fields would come from GitHub integration
        
        # For simple formula path: use 0 as fallback ONLY if still None
        # This is OK because simple path doesn't distinguish missing from zero
        # Real evidence path (analyze_evidence) handles None properly
        files_changed = files_changed if files_changed is not None else 0
        lines_added = lines_added if lines_added is not None else 0
        lines_deleted = lines_deleted if lines_deleted is not None else 0
        changed_files = changed_files if changed_files is not None else []
        commit_count = commit_count if commit_count is not None else 1
        
        # Build evidence using SIMPLE formulas (not deep analysis)
        evidence = await self._build_simple_pr_evidence(
            pr_id=pr_id,
            files_changed=files_changed,
            lines_added=lines_added,
            lines_deleted=lines_deleted,
            commit_count=commit_count,
            pr_age_hours=pr_age_hours,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            previous_coverage=previous_coverage,
            current_coverage=current_coverage,
        )
        
        return evidence
    
    async def _build_simple_pr_evidence(
        self,
        pr_id: str,
        files_changed: int,
        lines_added: int,
        lines_deleted: int,
        commit_count: int,
        pr_age_hours: float = None,
        tests_passed: int = 0,
        tests_failed: int = 0,
        previous_coverage: float = None,
        current_coverage: float = None,
    ) -> Dict[str, Any]:
        """Build simple PR evidence using formulas (no tools)."""
        risk_score = 0
        risk_factors = []
        
        # Factor 1: Size (max 30 points)
        if files_changed > PR_SIZE_LARGE_THRESHOLD:
            risk_score += PR_SIZE_LARGE_RISK
            risk_factors.append(f"Large PR (>{PR_SIZE_LARGE_THRESHOLD} files)")
        elif files_changed > PR_SIZE_MEDIUM_THRESHOLD:
            risk_score += PR_SIZE_MEDIUM_RISK
            risk_factors.append(f"Medium PR ({PR_SIZE_MEDIUM_THRESHOLD}-{PR_SIZE_LARGE_THRESHOLD} files)")
        elif files_changed > PR_SIZE_SMALL_THRESHOLD:
            risk_score += PR_SIZE_SMALL_RISK
        
        # Factor 2: Churn (max 20 points)
        # Measures volume of code change (lines added + deleted)
        # High churn = more surface area for bugs
        lines_total = lines_added + lines_deleted
        if lines_total > CHURN_HIGH_THRESHOLD:
            risk_score += CHURN_HIGH_RISK
            risk_factors.append(f"High code churn (>{CHURN_HIGH_THRESHOLD} lines)")
        elif lines_total > CHURN_MEDIUM_THRESHOLD:
            risk_score += CHURN_MEDIUM_RISK
        
        # Factor 3: Tests (max 25 points)
        if tests_failed > 0:
            risk_score += TEST_FAILURE_RISK
            risk_factors.append(f"{tests_failed} failing tests")
        elif tests_passed == 0:
            risk_score += TEST_NONE_PASSING_RISK
            risk_factors.append("No passing tests")
        
        # Factor 4: Coverage (max 15 points)
        if current_coverage is not None and previous_coverage is not None:
            if current_coverage < previous_coverage:
                risk_score += COVERAGE_DECREASE_RISK
                risk_factors.append("Coverage decreased")
        
        # Factor 5: PR age (max 10 points)
        if pr_age_hours and pr_age_hours > PR_STALE_THRESHOLD_HOURS:
            risk_score += PR_STALE_RISK
            risk_factors.append(f"PR is stale (>{PR_STALE_THRESHOLD_HOURS // 24} week)")
        
        # Cap at 100
        risk_score = min(risk_score, 100)
        risk_level = await self._classify_risk_level(risk_score)
        
        return {
            "pr_id": pr_id,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "metrics": {
                "files_changed": files_changed,
                "lines_added": lines_added,
                "lines_deleted": lines_deleted,
                "commit_count": commit_count,
                "tests_passed": tests_passed,
                "tests_failed": tests_failed,
            }
        }

    async def analyze_sprint(
        self,
        sprint_id: str,
        stories_data: Dict = None,
    ) -> Dict[str, Any]:
        """
        Analyze a sprint and return Plan vs Reality evidence.
        
        This is the core intelligence for sprint health.
        
        Args:
            sprint_id: Sprint ID
            stories_data: Optional dict with pre-calculated story metrics
        
        Returns:
            Evidence package with sprint health and delivery risk
        """
        # Fetch sprint data
        sprint = await self.sprint_repo.find_by_id(sprint_id)
        if not sprint:
            return {"error": "Sprint not found"}
        
        # Use provided data or query from stories in the database
        if stories_data:
            total_stories = stories_data.get("total_stories") or 0
            completed_stories = stories_data.get("completed_stories") or 0
            in_progress_stories = stories_data.get("in_progress_stories") or 0
            blocked_stories = stories_data.get("blocked_stories") or 0
            total_points = stories_data.get("total_points") or 0
            completed_points = stories_data.get("completed_points") or 0
            original_points = stories_data.get("original_points") or total_points
        else:
            # Query actual stories from the database
            all_stories = await self.story_repo.find_all({"sprint_id": sprint_id})
            total_stories = len(all_stories)
            completed_stories = sum(1 for s in all_stories if s.get("status") == "completed")
            in_progress_stories = sum(1 for s in all_stories if s.get("status") == "in_progress")
            blocked_stories = sum(1 for s in all_stories if s.get("status") == "blocked")
            total_points = sum(s.get("story_points") or 0 for s in all_stories)
            completed_points = sum(s.get("story_points") or 0 for s in all_stories if s.get("status") == "completed")
            original_points = sprint.get("original_points") or total_points
        
        # Calculate elapsed days from sprint start_date
        start_date_str = sprint.get("start_date")
        end_date_str = sprint.get("end_date")
        now = datetime.now(timezone.utc)
        
        if start_date_str and end_date_str:
            start_dt = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
            days_elapsed = max(0, (now - start_dt).days)
            sprint_duration_days = max(1, (end_dt - start_dt).days)
        else:
            # Fallback: use sprint duration_days field or sensible minimum
            sprint_duration_days = sprint.get("duration_days", 14)
            days_elapsed = sprint_duration_days // 2  # assume midpoint if dates missing
        
        evidence = await self._build_simple_sprint_evidence(
            sprint_id=sprint_id,
            total_stories=total_stories,
            completed_stories=completed_stories,
            in_progress_stories=in_progress_stories,
            blocked_stories=blocked_stories,
            total_points=total_points,
            completed_points=completed_points,
            original_points=original_points,
            days_elapsed=days_elapsed,
            sprint_duration_days=sprint_duration_days,
        )
        
        return evidence
    
    async def _build_simple_sprint_evidence(
        self,
        sprint_id: str,
        total_stories: int,
        completed_stories: int,
        in_progress_stories: int,
        blocked_stories: int,
        total_points: int,
        completed_points: int,
        original_points: int,
        days_elapsed: int,
        sprint_duration_days: int,
    ) -> Dict[str, Any]:
        """Build simple sprint evidence using formulas."""
        risk_score = 0
        risk_factors = []
        
        # Factor 1: Blocked stories (max 30 points)
        if blocked_stories > 0:
            blocked_pct = (blocked_stories / total_stories) * 100
            if blocked_pct > SPRINT_BLOCKED_HIGH_PCT:
                risk_score += SPRINT_BLOCKED_HIGH_RISK
                risk_factors.append(f"{blocked_pct:.0f}% stories blocked")
            else:
                risk_score += SPRINT_BLOCKED_LOW_RISK
                risk_factors.append(f"{blocked_stories} blocked stories")
        
        # Factor 2: Progress vs time (max 40 points)
        time_pct = (days_elapsed / sprint_duration_days) * 100
        progress_pct = (completed_points / total_points) * 100 if total_points > 0 else 0
        
        if progress_pct < (time_pct - 20):
            risk_score += SPRINT_BEHIND_SCHEDULE_RISK
            risk_factors.append(f"Behind schedule ({progress_pct:.0f}% vs {time_pct:.0f}% time)")
        elif progress_pct < time_pct:
            risk_score += SPRINT_SLIGHT_BEHIND_RISK
        
        # Factor 3: Scope creep (max 20 points)
        if total_points > original_points:
            scope_increase = ((total_points - original_points) / original_points) * 100
            if scope_increase > SPRINT_SCOPE_CREEP_HIGH_PCT:
                risk_score += SPRINT_SCOPE_CREEP_HIGH_RISK
                risk_factors.append(f"Scope increased {scope_increase:.0f}%")
            else:
                risk_score += SPRINT_SCOPE_CREEP_LOW_RISK
        
        # Factor 4: Completion rate (max 10 points)
        completion_rate = (completed_stories / total_stories) * 100 if total_stories > 0 else 0
        if completion_rate < SPRINT_LOW_COMPLETION_PCT and time_pct > SPRINT_TIME_ELAPSED_PCT:
            risk_score += SPRINT_LOW_COMPLETION_RISK
            risk_factors.append("Low completion rate")
        
        risk_score = min(risk_score, 100)
        risk_level = await self._classify_risk_level(risk_score)
        
        return {
            "sprint_id": sprint_id,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "metrics": {
                "total_stories": total_stories,
                "completed_stories": completed_stories,
                "blocked_stories": blocked_stories,
                "total_points": total_points,
                "completed_points": completed_points,
                "progress_pct": progress_pct,
                "time_pct": time_pct,
            }
        }

    async def analyze_deployment(
        self,
        deployment_id: str,
        ci_data: Dict = None,
        deployment_data: Dict = None,
    ) -> Dict[str, Any]:
        """
        Analyze a deployment and return CI/CD health evidence.
        
        Args:
            deployment_id: Deployment ID
            ci_data: CI/CD metrics
            deployment_data: Deployment history metrics
        
        Returns:
            Evidence package with deployment risk
            
        Note:
            Returns risk_score=None (not 0) when data is insufficient.
            None = unavailable, 0 = measured zero risk.
        """
        # Require actual data — do not use hardcoded defaults
        if not ci_data or not deployment_data:
            return {
                "error": "ci_data and deployment_data are required for deployment analysis",
                "deployment_id": deployment_id,
                "risk_score": None,  # None = unavailable, not 0
                "risk_level": "unknown",
                "risk_factors": ["Insufficient data for analysis"],
                "metrics": {},
            }
        
        evidence = await self._build_simple_deployment_evidence(
            deployment_id=deployment_id,
            **ci_data,
            **deployment_data,
        )
        
        return evidence
    
    async def _build_simple_deployment_evidence(
        self,
        deployment_id: str,
        builds_total: int,
        builds_passed: int,
        builds_failed: int,
        deployments_total: int,
        deployments_successful: int,
        deployments_failed: int,
        rollbacks: int,
    ) -> Dict[str, Any]:
        """
        Build simple deployment evidence using formulas.
        
        Returns risk_score=None when deployments_total=0 (no data).
        None = unavailable, 0 = measured zero risk.
        """
        # Check for insufficient data
        if deployments_total == 0:
            return {
                "deployment_id": deployment_id,
                "risk_score": None,  # None = no data available
                "risk_level": "unknown",
                "risk_factors": ["No deployment history available"],
                "metrics": {
                    "builds_total": builds_total,
                    "builds_passed": builds_passed,
                    "builds_failed": builds_failed,
                    "build_failure_rate": None,
                    "deployments_total": 0,
                    "deployments_successful": 0,
                    "deployments_failed": 0,
                    "deploy_failure_rate": None,
                    "rollbacks": 0,
                }
            }
        
        risk_score = 0
        risk_factors = []
        
        # Factor 1: Build failures (max 30 points)
        build_failure_rate = (builds_failed / builds_total) * 100 if builds_total > 0 else 0
        if build_failure_rate > DEPLOY_BUILD_FAILURE_HIGH_PCT:
            risk_score += DEPLOY_BUILD_FAILURE_HIGH_RISK
            risk_factors.append(f"High build failure rate ({build_failure_rate:.0f}%)")
        elif build_failure_rate > DEPLOY_BUILD_FAILURE_LOW_PCT:
            risk_score += DEPLOY_BUILD_FAILURE_LOW_RISK
        
        # Factor 2: Deployment failures (max 40 points)
        deploy_failure_rate = (deployments_failed / deployments_total) * 100 if deployments_total > 0 else 0
        if deploy_failure_rate > DEPLOY_DEPLOY_FAILURE_HIGH_PCT:
            risk_score += DEPLOY_DEPLOY_FAILURE_HIGH_RISK
            risk_factors.append(f"High deployment failure rate ({deploy_failure_rate:.0f}%)")
        elif deploy_failure_rate > DEPLOY_DEPLOY_FAILURE_LOW_PCT:
            risk_score += DEPLOY_DEPLOY_FAILURE_LOW_RISK
        
        # Factor 3: Rollbacks (max 30 points)
        if rollbacks > 0:
            rollback_rate = (rollbacks / deployments_total) * 100 if deployments_total > 0 else 0
            if rollback_rate > DEPLOY_ROLLBACK_HIGH_PCT:
                risk_score += DEPLOY_ROLLBACK_HIGH_RISK
                risk_factors.append(f"{rollbacks} rollbacks ({rollback_rate:.0f}%)")
            else:
                risk_score += DEPLOY_ROLLBACK_LOW_RISK
                risk_factors.append(f"{rollbacks} rollbacks")
        
        risk_score = min(risk_score, 100)
        risk_level = await self._classify_risk_level(risk_score)
        
        return {
            "deployment_id": deployment_id,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "metrics": {
                "builds_total": builds_total,
                "builds_passed": builds_passed,
                "builds_failed": builds_failed,
                "build_failure_rate": build_failure_rate,
                "deployments_total": deployments_total,
                "deployments_successful": deployments_successful,
                "deployments_failed": deployments_failed,
                "deploy_failure_rate": deploy_failure_rate,
                "rollbacks": rollbacks,
            }
        }

    async def classify_risk(self, risk_score: int) -> str:
        """
        Classify a numeric risk score into a risk level.
        
        Args:
            risk_score: Integer 0-100
        
        Returns:
            Risk level: CRITICAL|HIGH|MEDIUM|LOW
        """
        return await self._classify_risk_level(risk_score)

    async def analyze_evidence(
        self,
        evidence: "CodeQualityEvidence",
        baseline: "RepositoryBaseline | None" = None,
    ) -> dict:
        """
        Phase 4 — Compute multi-dimensional risk from a CodeQualityEvidence package.

        NOTE: References to RISK_DIMENSION_WEIGHTS and Z-score system are legacy.
        baseline=None always, so this falls back to threshold-based risk calculation.
        Preserves all existing analyze_pull_request / analyze_sprint methods.

        Args:
            evidence: Normalized CodeQualityEvidence from any language analyzer
            baseline: Optional RepositoryBaseline for Z-score calculation;
                      falls back to default thresholds if None

        Returns:
            {
                "risk_score": int (0-100),
                "risk_level": str,
                "risk_factors": list[str],
                "dimension_scores": dict,
            }
        """
        from domain.services.risk_config_service import get_risk_config_service
        
        # Load configurable weights (DB or fallback to hardcoded)
        config_service = get_risk_config_service()
        config = await config_service.get_configuration(
            project_id=evidence.repository_id
        )
        
        # Extract weights from configuration
        weights = {
            "alpha_size_zscore": config.risk_weights.alpha_size_zscore,
            "beta_hotspot": config.risk_weights.beta_hotspot,
            "gamma_dependency": config.risk_weights.gamma_dependency,
            "delta_missing_tests": config.risk_weights.delta_missing_tests,
            "epsilon_security": config.risk_weights.epsilon_security,
            "zeta_complexity": config.risk_weights.zeta_complexity,
        }
        BASE_RISK = config.base_risk
        risk_factors: list[str] = []
        dimension_scores: dict = {}

        # ── 1. Size Z-score (alpha) ───────────────────────────────────────────
        z_size = 0.0
        if baseline:
            lines_changed = evidence.lines_added + evidence.lines_deleted
            z_size = await baseline.compute_zscore(
                evidence.repository_id, "lines_changed", lines_changed
            )
        else:
            # Fallback: simple threshold-based score
            lines_changed = evidence.lines_added + evidence.lines_deleted
            z_size = min(3.0, lines_changed / 500.0)

        alpha_score = min(100.0, max(0.0, z_size * 20))
        dimension_scores["size_deviation"] = round(alpha_score, 1)
        if z_size > 2.0:
            risk_factors.append(
                f"PR is {z_size:.1f}x larger than this repo's normal size"
            )

        # ── 2. Hotspot weight (beta) ──────────────────────────────────────────
        hotspot_count = len(evidence.change_context.hot_paths_touched)
        beta_score = min(100.0, hotspot_count * 25.0)
        dimension_scores["hotspot_files"] = round(beta_score, 1)
        if hotspot_count > 0:
            risk_factors.append(
                f"{hotspot_count} historically incident-prone file(s) modified"
            )

        # ── 3. Dependency risk (gamma) ────────────────────────────────────────
        dep_count = len(evidence.security.dependency_vulnerabilities)
        gamma_score = min(100.0, dep_count * 20.0)
        dimension_scores["dependency_vulnerabilities"] = round(gamma_score, 1)
        if dep_count > 0:
            risk_factors.append(f"{dep_count} vulnerable dependency/dependencies detected")

        # ── 4. Missing test weight (delta) ────────────────────────────────────
        coverage = evidence.testing.coverage_percentage
        if coverage is None:
            delta_score = 70.0
            risk_factors.append("No test coverage data available")
        elif coverage < 60.0:
            delta_score = 100.0
            risk_factors.append(f"Critical test coverage gap: {coverage:.0f}%")
        elif coverage < 80.0:
            delta_score = (80.0 - coverage) / 20.0 * 60.0
            risk_factors.append(f"Test coverage below threshold: {coverage:.0f}%")
        else:
            delta_score = 0.0
        dimension_scores["test_coverage_gap"] = round(delta_score, 1)

        # ── 5. Security score (epsilon) ───────────────────────────────────────
        sec = evidence.security
        epsilon_score = min(
            100.0,
            (sec.critical_count * 40.0) +
            (sec.high_count * 15.0) +
            (sec.medium_count * 5.0)
        )
        dimension_scores["security_findings"] = round(epsilon_score, 1)
        if sec.critical_count > 0:
            risk_factors.append(f"{sec.critical_count} CRITICAL security finding(s)")
        if sec.hardcoded_secrets:
            risk_factors.append(f"{len(sec.hardcoded_secrets)} hardcoded secret(s) detected")

        # ── 6. Complexity spike (zeta) ────────────────────────────────────────
        avg_complexity = evidence.complexity.average_complexity
        zeta_score = 0.0
        if avg_complexity > 15:
            zeta_score = min(100.0, (avg_complexity - 15) * 5.0)
            risk_factors.append(
                f"Average cyclomatic complexity is high: {avg_complexity:.1f}"
            )
        dimension_scores["complexity_spike"] = round(zeta_score, 1)

        # ── Special signals ───────────────────────────────────────────────────
        ctx = evidence.change_context
        bonus = 0.0
        if ctx.db_migrations_changed:
            bonus += 15.0
            risk_factors.append("Database migration detected — schema change risk")
        if ctx.public_api_changed:
            bonus += 10.0
            risk_factors.append("Public API change — potential breaking change")
        if ctx.config_files_changed:
            bonus += 5.0

        # ── CI/CD history ─────────────────────────────────────────────────────
        cicd_bonus = 0.0
        if evidence.ci_cd.historical_failure_rate > 0.3:
            cicd_bonus = min(15.0, evidence.ci_cd.historical_failure_rate * 30)
            risk_factors.append(
                f"CI/CD has {evidence.ci_cd.historical_failure_rate*100:.0f}% historical failure rate"
            )

        # ── Weighted final score ──────────────────────────────────────────────
        weighted = (
            weights["alpha_size_zscore"]   * (alpha_score   / 100) +
            weights["beta_hotspot"]        * (beta_score    / 100) +
            weights["gamma_dependency"]    * (gamma_score   / 100) +
            weights["delta_missing_tests"] * (delta_score   / 100) +
            weights["epsilon_security"]    * (epsilon_score / 100) +
            weights["zeta_complexity"]     * (zeta_score    / 100)
        )

        risk_score = int(min(100, max(0, BASE_RISK + weighted + bonus + cicd_bonus)))
        risk_level = RiskRules.classify_risk_level(risk_score)

        # Confidence adjustment — if evidence is degraded, widen uncertainty
        confidence_note = ""
        if evidence.analysis_quality.confidence < 0.7:
            risk_score = min(100, risk_score + 5)  # slight conservative bump
            confidence_note = f" (confidence: {evidence.analysis_quality.confidence:.1f})"

        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "dimension_scores": dimension_scores,
            "confidence_note": confidence_note,
        }
