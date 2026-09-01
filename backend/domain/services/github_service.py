"""
GitHub Service.
Orchestrates GitHub API client, data normalization, and integration with Samanvaya.
"""

from typing import Optional, List, Dict, Any
from integrations.github.client import GitHubClient
from integrations.github.normalizer import GitHubNormalizer
from repositories.pr_repository import PRRepository
from repositories.ai_run_repository import AIRunRepository
from intelligence.risk_engine import RiskEngine
from domain.models.ai_run import AIRun
from core.database import db


class GitHubService:
    """Service for GitHub integration operations."""

    def __init__(self, github_token: Optional[str] = None):
        """
        Initialize GitHub service.
        
        Args:
            github_token: GitHub PAT (uses config if not provided)
        """
        self.client = GitHubClient(token=github_token)
        self.normalizer = GitHubNormalizer()
        self.pr_repo = PRRepository()
        self.ai_run_repo = AIRunRepository(db)
        self.risk_engine = RiskEngine()

    async def sync_pull_request(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        project_id: str,
        use_ai: bool = True,
        use_deep_analysis: bool = False,
        triggered_by: str = "system",
    ) -> Dict[str, Any]:
        """
        Fetch PR from GitHub, normalize it, analyze risk, and store in database.
        
        This is the main entry point for PR synchronization.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: PR number
            project_id: Samanvaya project ID
            use_ai: Whether to invoke AI agent for analysis
            use_deep_analysis: Whether to run comprehensive deep analysis (static analysis, security, etc.)
            triggered_by: User who triggered the sync
        
        Returns:
            Complete PR data with risk analysis and optional AI insights
        """
        # Fetch PR from GitHub
        github_pr = await self.client.get_pull_request(owner, repo, pr_number)
        
        # Fetch additional PR data
        files = await self.client.get_pr_files(owner, repo, pr_number)
        commits = await self.client.get_pr_commits(owner, repo, pr_number)
        
        # Get CI status
        head_sha = github_pr["head"]["sha"]
        try:
            check_runs = await self.client.get_commit_check_runs(owner, repo, head_sha)
            ci_data = self.normalizer.normalize_check_runs(check_runs)
        except Exception:
            ci_data = {"ci_status": None}
        
        # Normalize PR data
        repo_id = f"{owner}/{repo}"
        normalized_pr = self.normalizer.normalize_pull_request(
            github_pr, project_id, repo_id
        )
        
        # Normalize file changes
        file_stats = self.normalizer.normalize_pr_files(files)
        
        # Calculate PR age
        pr_age_hours = self.normalizer.calculate_pr_age_hours(github_pr["created_at"])
        
        # Update PR with file stats and CI status
        normalized_pr.update({
            "files_changed_count": file_stats["files_changed"],
            "ci_status": ci_data["ci_status"],
        })
        
        # Analyze risk using Intelligence Engine
        risk_evidence = await self.risk_engine.analyze_pull_request(
            pr_id=normalized_pr["id"],
            files_changed=file_stats["files_changed"],
            lines_added=file_stats["lines_added"],
            lines_deleted=file_stats["lines_deleted"],
            changed_files=file_stats["changed_files"],
            commit_count=len(commits),
            pr_age_hours=pr_age_hours,
        )
        
        # Add risk analysis to PR
        normalized_pr.update({
            "risk_score": risk_evidence["risk_score"],
            "risk_level": risk_evidence["risk_level"],
        })
        
        # Store in database
        existing_pr = await self.pr_repo.find_by_pr_number(repo_id, pr_number)
        
        if existing_pr:
            # Update existing PR
            await self.pr_repo.update(
                {"id": existing_pr["id"]},
                normalized_pr
            )
            normalized_pr["id"] = existing_pr["id"]
        else:
            # Insert new PR
            await self.pr_repo.insert(normalized_pr)
        
        # Layer 6: AI Agent Analysis (Optional)
        ai_analysis = None
        ai_run_id = None
        code_quality_report = None
        
        if use_ai:
            try:
                from agents.llm_provider import check_ollama_connection
                
                # Check if Ollama is available
                if not check_ollama_connection():
                    ai_analysis = {"error": "Ollama not available"}
                else:
                    # Decide which analysis to use
                    if use_deep_analysis:
                        # NEW: Use comprehensive deep analysis
                        from intelligence.evidence_builder import EvidenceBuilder
                        from agents.code_agent import code_analysis_node
                        from domain.models.code_quality_report import CodeQualityReport, QualityBreakdown
                        import time
                        import tempfile
                        import os
                        
                        start_time = time.time()
                        
                        # Use platform-appropriate temp directory for evidence building
                        temp_dir = tempfile.gettempdir()
                        repo_work_dir = os.path.join(temp_dir, f"samanvaya-repo-{owner}-{repo}")
                        
                        # Build comprehensive evidence package
                        evidence_builder = EvidenceBuilder(repo_work_dir)
                        
                        pr_context = {
                            "pr_title": github_pr.get("title", ""),
                            "author": github_pr.get("user", {}).get("login", ""),
                            "pr_number": pr_number,
                            "repo": f"{owner}/{repo}",
                            "project_id": project_id,
                        }
                        
                        changed_file_paths = [f["filename"] for f in files]
                        
                        # Run all analyzers and build evidence
                        evidence = await evidence_builder.build_evidence(
                            changed_files=changed_file_paths,
                            pr_context=pr_context,
                            deep_analysis=True
                        )
                        
                        # Prepare state for enhanced AI agent
                        agent_state = {
                            "task_type": "code_review",
                            "evidence": evidence,
                            "context": pr_context,
                            "agent_history": [],
                            "errors": [],
                        }
                        
                        # Invoke enhanced code agent
                        ai_result = code_analysis_node(agent_state)
                        
                        # Build CodeQualityReport
                        quality_breakdown = QualityBreakdown(
                            correctness=ai_result.get("quality_breakdown", {}).get("correctness", 0),
                            maintainability=ai_result.get("quality_breakdown", {}).get("maintainability", 0),
                            security=ai_result.get("quality_breakdown", {}).get("security", 0),
                            testing=ai_result.get("quality_breakdown", {}).get("testing", 0),
                            performance=ai_result.get("quality_breakdown", {}).get("performance", 0),
                            architecture=ai_result.get("quality_breakdown", {}).get("architecture", 0),
                            readability=ai_result.get("quality_breakdown", {}).get("readability", 0),
                        )
                        
                        code_quality_report = CodeQualityReport(
                            pr_id=normalized_pr["id"],
                            pr_number=pr_number,
                            pr_title=github_pr.get("title", ""),
                            author=github_pr.get("user", {}).get("login", ""),
                            quality_score=ai_result.get("quality_score", evidence.get("quality_score", 0)),
                            quality_breakdown=quality_breakdown,
                            quality_factors=evidence.get("quality_factors", []),
                            failure_risk=ai_result.get("failure_risk", evidence.get("overall_risk_score", 0)),
                            risk_level=ai_result.get("risk_level", "medium"),
                            risk_factors=evidence.get("risk_factors", []),
                            static_analysis=evidence.get("static_analysis", {}),
                            complexity_metrics=evidence.get("complexity", {}),
                            security_findings=evidence.get("security", {}),
                            test_metrics=evidence.get("tests", {}),
                            dependency_changes=evidence.get("dependencies", {}),
                            historical_data=evidence.get("history", {}),
                            architecture_analysis=evidence.get("architecture", {}),
                            ai_analysis=ai_result.get("analysis"),
                            critical_issues=ai_result.get("critical_issues", []),
                            recommendations=ai_result.get("recommendations", []),
                            review_focus=ai_result.get("review_focus"),
                            confidence=ai_result.get("confidence", 0.7),
                            tools_used=evidence.get("static_analysis", {}).get("tools_used", []),
                            analysis_duration_ms=(time.time() - start_time) * 1000,
                        )
                        
                        ai_analysis = {
                            "analysis": ai_result.get("analysis"),
                            "recommendations": ai_result.get("recommendations", []),
                            "risk_level": ai_result.get("risk_level"),
                            "confidence": ai_result.get("confidence"),
                            "quality_score": ai_result.get("quality_score"),
                            "failure_risk": ai_result.get("failure_risk"),
                            "critical_issues": ai_result.get("critical_issues", []),
                        }
                        
                        # Save AI run to database
                        from domain.models.ai_run import AIRun
                        ai_run = AIRun(
                            agent_type="code_review_deep",
                            input_data={
                                "evidence": evidence,
                                "context": pr_context,
                            },
                            output_data=ai_analysis,
                            status="completed",
                            model_name="ollama",
                            triggered_by=triggered_by,
                        )
                        ai_run_id = await self.ai_run_repo.create(ai_run)
                    
                    else:
                        # Original simple AI analysis (backward compatible)
                        from agents.code_agent import code_analysis_node
                        
                        agent_state = {
                            "task_type": "code_review",
                            "evidence": risk_evidence,
                            "context": {
                                "pr_title": github_pr.get("title", ""),
                                "author": github_pr.get("user", {}).get("login", ""),
                                "pr_number": pr_number,
                                "repo": f"{owner}/{repo}",
                            },
                            "agent_history": [],
                            "errors": [],
                        }
                        
                        # Invoke code agent
                        ai_result = code_analysis_node(agent_state)
                        
                        # Extract AI insights
                        ai_analysis = {
                            "analysis": ai_result.get("analysis"),
                            "recommendations": ai_result.get("recommendations", []),
                            "risk_level": ai_result.get("risk_level"),
                            "confidence": ai_result.get("confidence"),
                        }
                        
                        # Save AI run to database
                        from domain.models.ai_run import AIRun
                        ai_run = AIRun(
                            agent_type="code_review",
                            input_data={
                                "evidence": risk_evidence,
                                "context": agent_state["context"],
                            },
                            output_data=ai_analysis,
                            status="completed",
                            model_name="ollama",
                            triggered_by=triggered_by,
                        )
                        ai_run_id = await self.ai_run_repo.create(ai_run)
                    
            except Exception as e:
                # AI analysis failed, but continue with Layer 5 results
                ai_analysis = {"error": f"AI analysis failed: {str(e)}"}
        
        return {
            "pr": normalized_pr,
            "file_stats": file_stats,
            "risk_analysis": risk_evidence,
            "ai_analysis": ai_analysis,
            "ai_run_id": ai_run_id,
            "code_quality_report": code_quality_report.dict() if code_quality_report else None,
            "ci_data": ci_data,
            "commit_count": len(commits),
        }

    async def sync_repository_prs(
        self,
        owner: str,
        repo: str,
        project_id: str,
        state: str = "open",
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Sync multiple PRs from a repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            project_id: Samanvaya project ID
            state: PR state (open|closed|all)
            limit: Max PRs to sync
        
        Returns:
            List of synced PRs with analysis
        """
        # Fetch PRs from GitHub
        github_prs = await self.client.list_pull_requests(
            owner, repo, state=state, per_page=limit
        )
        
        synced_prs = []
        
        for github_pr in github_prs[:limit]:
            try:
                result = await self.sync_pull_request(
                    owner, repo, github_pr["number"], project_id
                )
                synced_prs.append(result)
            except Exception as e:
                # Log error but continue with other PRs
                synced_prs.append({
                    "pr_number": github_pr["number"],
                    "error": str(e),
                    "status": "failed"
                })
        
        return synced_prs

    async def get_repository_info(
        self, owner: str, repo: str
    ) -> Dict[str, Any]:
        """
        Get repository information from GitHub.
        
        Args:
            owner: Repository owner
            repo: Repository name
        
        Returns:
            Normalized repository data
        """
        github_repo = await self.client.get_repository(owner, repo)
        return self.normalizer.normalize_repository(github_repo)

    async def list_repositories(
        self, org: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List GitHub repositories.
        
        Args:
            org: Organization name (user repos if None)
        
        Returns:
            List of normalized repositories
        """
        github_repos = await self.client.list_repositories(org)
        return [
            self.normalizer.normalize_repository(repo)
            for repo in github_repos
        ]
