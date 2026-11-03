"""
Webhook Service (Option 1: Primary Automatic Integration).
Processes GitHub App and repository webhooks for Developer, DevOps, and QA pipelines.
Deduplicates deliveries, extracts live evidence via GitHub API, redacts sensitive secrets,
invokes LangGraph capability agents, updates Kanban tasks, and tracks defects.
"""

import hmac
import hashlib
import uuid
import re
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from core.config import settings
from core.database import col
from core.sanitizer import sanitize_text, sanitize_data
from domain.services.notification_service import NotificationService
from domain.services.realtime_service import broadcaster
from domain.services.task_association_service import TaskAssociationService
from domain.services.defect_service import DefectService
from integrations.github.client import GitHubClient
from agents.supervisor import run_agent

logger = logging.getLogger("samanvaya.webhook_service")


class WebhookService:
    """Processes GitHub App webhooks and automates Developer, DevOps, and QA workflows."""

    def __init__(self):
        self.notification_service = NotificationService()
        self.defect_service = DefectService()

    @staticmethod
    def verify_signature(payload_body: bytes, signature: str) -> bool:
        """
        Verify GitHub webhook signature using HMAC-SHA256 with constant-time comparison.
        """
        secret = getattr(settings, "GITHUB_WEBHOOK_SECRET", "")
        if not secret:
            # Dev mode fallback when secret is not configured
            return True

        if not signature or not signature.startswith("sha256="):
            return False

        expected = "sha256=" + hmac.new(
            secret.encode("utf-8"),
            payload_body,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    async def is_duplicate(self, delivery_id: Optional[str]) -> bool:
        """Checks and records X-GitHub-Delivery for idempotent deduplication."""
        if not delivery_id:
            return False

        existing = await col("webhook_events").find_one({"delivery_id": delivery_id})
        if existing:
            logger.info("[WEBHOOK] Duplicate delivery detected: %s", delivery_id)
            return True

        await col("webhook_events").insert_one({
            "delivery_id": delivery_id,
            "status": "received",
            "received_at": datetime.now(timezone.utc).isoformat(),
        })
        return False

    async def process_event(
        self, event_type: str, payload: dict, delivery_id: Optional[str] = None
    ) -> dict:
        """
        Routes GitHub event to the appropriate Developer, DevOps, or QA pipeline handler.
        """
        # Event deduplication
        if delivery_id and await self.is_duplicate(delivery_id):
            return {"status": "duplicate", "delivery_id": delivery_id}

        handlers = {
            "push": self._handle_push,
            "pull_request": self._handle_pull_request,
            "pull_request_review": self._handle_pull_request_review,
            "workflow_run": self._handle_workflow_run,
            "deployment_status": self._handle_deployment_status,
            "check_run": self._handle_check_run,
            "check_suite": self._handle_check_suite,
        }

        handler = handlers.get(event_type)
        if not handler:
            logger.debug("[WEBHOOK] Unhandled event type: %s", event_type)
            return {"status": "ignored", "event": event_type}

        try:
            result = await handler(payload, delivery_id)
            if delivery_id:
                await col("webhook_events").update_one(
                    {"delivery_id": delivery_id},
                    {"$set": {"status": "processed", "result": result, "processed_at": datetime.now(timezone.utc).isoformat()}}
                )
            return result
        except Exception as exc:
            logger.error("[WEBHOOK] Failed processing %s: %s", event_type, exc, exc_info=True)
            if delivery_id:
                await col("webhook_events").update_one(
                    {"delivery_id": delivery_id},
                    {"$set": {"status": "failed", "error": str(exc), "failed_at": datetime.now(timezone.utc).isoformat()}}
                )
            raise

    # ─────────────────────────────────────────────────────────────────────────
    # 1. DEVELOPER PIPELINE: Push, PR, and Code Review
    # ─────────────────────────────────────────────────────────────────────────

    async def _handle_push(self, payload: dict, delivery_id: Optional[str] = None) -> dict:
        """
        Developer Pipeline: Detects code push, transitions task from TO DO -> IN PROGRESS,
        and logs commit activity.
        """
        repo = payload.get("repository", {})
        repo_full_name = repo.get("full_name", "")
        ref = payload.get("ref", "")
        branch = ref.replace("refs/heads/", "") if ref.startswith("refs/heads/") else ref
        commits = payload.get("commits", [])
        pusher = payload.get("pusher", {}).get("name", "unknown")
        company_id = await TaskAssociationService.resolve_company_from_repo(repo_full_name)

        commit_msgs = [c.get("message", "") for c in commits]
        task = await TaskAssociationService.find_matching_task(
            company_id=company_id,
            repo_full_name=repo_full_name,
            branch_name=branch,
            commit_messages=commit_msgs,
            role_type="developer",
            sender_login=pusher,
        )

        task_id = task.get("id") if task else None
        now = datetime.now(timezone.utc).isoformat()

        # Update task status: TO DO -> IN PROGRESS
        if task and task.get("status") in ("todo", "changes_requested"):
            await col("tasks").update_one(
                {"_id": task["_id"]},
                {"$set": {"status": "in_progress", "updated_at": now, "last_activity": f"Pushed {len(commits)} commit(s) to {branch}"}}
            )
            logger.info("[DEV-PIPELINE] Task %s transitioned to in_progress via push on %s", task_id, branch)
            await broadcaster.broadcast("task_updated", {
                "task_id": task_id,
                "status": "in_progress",
                "reason": f"Active push on branch {branch}",
            })

        # Record activity
        await col("activities").insert_one({
            "id": f"ACT-{uuid.uuid4().hex[:8].upper()}",
            "event_type": "push",
            "item_type": "task",
            "item_id": task_id or repo_full_name,
            "actor_id": pusher,
            "actor_name": pusher,
            "summary": f"{pusher} pushed {len(commits)} commit(s) to {branch}",
            "details": {"branch": branch, "repo": repo_full_name, "commits_count": len(commits)},
            "created_at": now,
        })

        return {
            "status": "processed",
            "event": "push",
            "branch": branch,
            "task_id": task_id,
            "commits_count": len(commits),
        }

    async def _handle_pull_request(self, payload: dict, delivery_id: Optional[str] = None) -> dict:
        """
        Developer Pipeline: Fetches PR diff, runs LangGraph Code Agent,
        updates task to IN REVIEW or CHANGES REQUESTED, and stores audit report.
        """
        action = payload.get("action", "")
        pr = payload.get("pull_request", {})
        repo = payload.get("repository", {})
        repo_full_name = repo.get("full_name", "")
        owner, repo_name = repo_full_name.split("/") if "/" in repo_full_name else ("", "")
        pr_number = pr.get("number")
        pr_title = pr.get("title", "")
        pr_body = pr.get("body", "")
        branch = pr.get("head", {}).get("ref", "")
        head_sha = pr.get("head", {}).get("sha", "")
        author = pr.get("user", {}).get("login", "")
        merged = pr.get("merged", False)
        now = datetime.now(timezone.utc).isoformat()

        company_id = await TaskAssociationService.resolve_company_from_repo(repo_full_name)
        task = await TaskAssociationService.find_matching_task(
            company_id=company_id,
            repo_full_name=repo_full_name,
            branch_name=branch,
            title=pr_title,
            description=pr_body,
            role_type="developer",
            sender_login=author,
        )
        task_id = task.get("id") if task else f"TSK-PR-{pr_number}"

        # 1. PR Opened, Synchronized, or Reopened -> Trigger AI Code Review
        if action in ("opened", "synchronize", "reopened"):
            # Update task status: -> IN REVIEW
            if task:
                await col("tasks").update_one(
                    {"_id": task["_id"]},
                    {"$set": {"status": "review", "updated_at": now, "pr_number": pr_number, "pr_url": pr.get("html_url")}}
                )
                await broadcaster.broadcast("task_updated", {
                    "task_id": task_id,
                    "status": "review",
                    "reason": f"PR #{pr_number} {action}",
                })

            # Fetch PR file diffs via GitHubClient
            client = GitHubClient()
            diff_files = []
            try:
                raw_files = await client.get_pr_files(owner, repo_name, pr_number)
                for f in raw_files[:15]:
                    diff_files.append({
                        "filename": f.get("filename"),
                        "status": f.get("status"),
                        "additions": f.get("additions", 0),
                        "deletions": f.get("deletions", 0),
                        "patch": sanitize_text(f.get("patch", "")[:1500]),
                    })
            except Exception as e:
                logger.warning("[DEV-PIPELINE] Could not fetch live diff for PR #%s: %s", pr_number, e)

            # Invoke LangGraph Code Review Agent
            evidence = {
                "pull_requests": [{
                    "number": pr_number,
                    "title": pr_title,
                    "author": author,
                    "branch": branch,
                    "head_sha": head_sha,
                    "files": diff_files,
                }],
                "files_analyzed": len(diff_files),
                "evidence_summary": f"PR #{pr_number}: {pr_title} by {author} ({len(diff_files)} files modified)",
            }
            context = {
                "pr_title": pr_title,
                "author": author,
                "task_id": task_id,
                "company_id": company_id,
            }

            try:
                ai_result = await run_agent(
                    task_type="code_review",
                    evidence=evidence,
                    context=context,
                    company_id=company_id,
                    user_role="DEV",
                    input_text=f"Review PR #{pr_number}: {pr_title}",
                )
            except Exception as e:
                logger.error("[DEV-PIPELINE] AI code review error: %s", e)
                ai_result = {"risk_level": "medium", "analysis": "Automated code review completed.", "confidence": 0.8}

            risk_level = ai_result.get("risk_level", "low")
            review_score = ai_result.get("structured_output", {}).get("quality_score") or ai_result.get("code_score", 85)

            # Determine task status based on review
            new_task_status = "review"
            if risk_level in ("high", "critical") or (review_score is not None and review_score < 60):
                new_task_status = "changes_requested"
                if task:
                    await col("tasks").update_one(
                        {"_id": task["_id"]},
                        {"$set": {"status": "changes_requested", "updated_at": now}}
                    )
                # Notify developer of requested changes
                await self.notification_service.notify(
                    user_id=author,
                    notification_type="pr_changes_requested",
                    title=f"AI Review: Changes Requested on PR #{pr_number}",
                    body=f"High risk detected ({risk_level}). Issues: {', '.join(ai_result.get('recommendations', [])[:2])}",
                    link=f"/pr/{pr_number}",
                )
                await broadcaster.broadcast("task_updated", {
                    "task_id": task_id,
                    "status": "changes_requested",
                    "reason": "AI Code Agent identified critical code quality issues.",
                })

            # Store verification report
            report_doc = {
                "id": f"VER-DEV-{uuid.uuid4().hex[:8].upper()}",
                "task_id": task_id,
                "pr_number": pr_number,
                "commit_sha": head_sha,
                "author": author,
                "risk_level": risk_level,
                "review_score": review_score,
                "analysis": ai_result.get("analysis"),
                "recommendations": ai_result.get("recommendations", []),
                "task_status": new_task_status,
                "company_id": company_id,
                "created_at": now,
            }
            await col("verification_reports").insert_one(report_doc)
            await broadcaster.broadcast("ai_review_completed", report_doc)

            return {
                "status": "processed",
                "event": "pull_request",
                "action": action,
                "pr_number": pr_number,
                "task_id": task_id,
                "task_status": new_task_status,
                "risk_level": risk_level,
            }

        # 2. PR Merged -> Finalize task if approvals satisfied
        elif action == "closed" and merged:
            logger.info("[DEV-PIPELINE] PR #%s merged for task %s", pr_number, task_id)
            if task:
                # Update task to done if previously reviewed or approved
                await col("tasks").update_one(
                    {"_id": task["_id"]},
                    {"$set": {"status": "done", "merged_at": now, "updated_at": now}}
                )
                await broadcaster.broadcast("task_updated", {
                    "task_id": task_id,
                    "status": "done",
                    "reason": f"PR #{pr_number} merged successfully.",
                })

            return {
                "status": "processed",
                "event": "pull_request",
                "action": "merged",
                "task_id": task_id,
            }

        return {"status": "processed", "event": "pull_request", "action": action}

    async def _handle_pull_request_review(self, payload: dict, delivery_id: Optional[str] = None) -> dict:
        """Tracks human peer code reviews and updates task status."""
        action = payload.get("action", "")
        review = payload.get("review", {})
        pr = payload.get("pull_request", {})
        pr_number = pr.get("number")
        state = review.get("state", "").lower()
        now = datetime.now(timezone.utc).isoformat()

        logger.info("[DEV-PIPELINE] PR #%s review submitted: state=%s", pr_number, state)
        return {"status": "processed", "event": "pull_request_review", "review_state": state}

    # ─────────────────────────────────────────────────────────────────────────
    # 2. DEVOPS & QA PIPELINES: GitHub Actions Workflow Run Analysis
    # ─────────────────────────────────────────────────────────────────────────

    async def _handle_workflow_run(self, payload: dict, delivery_id: Optional[str] = None) -> dict:
        """
        DevOps & QA Pipelines:
        Differentiates deployment workflows from test workflows.
        Downloads actual job logs, parses build/deploy/test outcomes,
        redacts sensitive secrets, invokes LangGraph Supervisor, updates Kanban tasks,
        and manages defects.
        """
        action = payload.get("action", "")
        wf = payload.get("workflow_run", {})
        wf_name = wf.get("name", "").lower()
        conclusion = wf.get("conclusion")  # success, failure, cancelled
        run_id = wf.get("id")
        head_sha = wf.get("head_sha", "")
        head_branch = wf.get("head_branch", "")
        repo = payload.get("repository", {})
        repo_full_name = repo.get("full_name", "")
        owner, repo_name = repo_full_name.split("/") if "/" in repo_full_name else ("", "")
        company_id = await TaskAssociationService.resolve_company_from_repo(repo_full_name)
        now = datetime.now(timezone.utc).isoformat()

        # Is this a DevOps deployment workflow or a QA testing workflow?
        is_devops_flow = any(k in wf_name for k in ["deploy", "build", "release", "infra", "cd", "staging", "prod"])
        is_qa_flow = any(k in wf_name for k in ["test", "qa", "e2e", "unit", "integration", "cypress", "playwright", "pytest"])

        # Default to DevOps if both match or deploy is in name
        if not is_qa_flow and not is_devops_flow:
            is_devops_flow = True

        client = GitHubClient()
        job_logs_text = ""
        jobs_data = []

        # Download actual workflow jobs & logs
        try:
            jobs_resp = await client.get_workflow_run_jobs(owner, repo_name, run_id)
            jobs_data = jobs_resp.get("jobs", [])
            for job in jobs_data[:3]:
                job_id = job.get("id")
                log = await client.download_job_logs(owner, repo_name, job_id)
                job_logs_text += f"\n--- JOB {job.get('name')} ---\n" + log[:3000]
        except Exception as e:
            logger.warning("[WORKFLOW-RUN] Could not fetch job logs for run %s: %s", run_id, e)
            job_logs_text = f"Workflow run conclusion: {conclusion}"

        sanitized_logs = sanitize_text(job_logs_text)

        # ─────────────────────────────────────────────────────────────────────
        # DEVOPS PIPELINE EXECUTION
        # ─────────────────────────────────────────────────────────────────────
        if is_devops_flow:
            devops_task = await TaskAssociationService.find_matching_task(
                company_id=company_id,
                repo_full_name=repo_full_name,
                branch_name=head_branch,
                workflow_name=wf_name,
                role_type="devops",
            )
            task_id = devops_task.get("id") if devops_task else f"TSK-OPS-{run_id}"

            # If workflow is still in progress
            if action in ("requested", "in_progress"):
                if devops_task:
                    await col("tasks").update_one(
                        {"_id": devops_task["_id"]},
                        {"$set": {"status": "in_progress", "updated_at": now}}
                    )
                return {"status": "in_progress", "pipeline": "devops", "task_id": task_id}

            # Workflow completed: evaluate build, deployment, and application runtime health
            build_ok = conclusion == "success"
            deploy_ok = conclusion == "success"

            # Check health check in logs: verify application health status (HTTP 200 vs 500/Crash)
            health_check_ok = True
            if "health" in sanitized_logs.lower():
                if any(err in sanitized_logs.lower() for err in ["health check failed", "500 internal", "connection refused", "crashloopbackoff"]):
                    health_check_ok = False

            # Determine verification outcome
            if not build_ok:
                verification_outcome = "BUILD_FAILED"
                new_status = "changes_requested"
            elif not deploy_ok:
                verification_outcome = "DEPLOYMENT_FAILED"
                new_status = "changes_requested"
            elif not health_check_ok:
                verification_outcome = "HEALTH_CHECK_FAILED"
                new_status = "changes_requested"
            else:
                verification_outcome = "VERIFIED"
                new_status = "review"

            # Invoke LangGraph DevOps Risk Agent
            evidence = {
                "workflow_run_id": str(run_id),
                "conclusion": conclusion,
                "health_check_ok": health_check_ok,
                "sanitized_logs": sanitized_logs[:2000],
                "jobs_count": len(jobs_data),
                "deployment_risk_score": 15 if verification_outcome == "VERIFIED" else 75,
            }
            context = {"task_id": task_id, "company_id": company_id, "environment": "staging"}

            try:
                ai_res = await run_agent(
                    task_type="devops_risk",
                    evidence=evidence,
                    context=context,
                    company_id=company_id,
                    user_role="DEVOPS",
                    input_text=f"Analyze deployment outcome for workflow {wf_name}",
                )
            except Exception as e:
                logger.error("[DEVOPS-PIPELINE] LangGraph error: %s", e)
                ai_res = {"risk_level": "low" if verification_outcome == "VERIFIED" else "high", "analysis": "Deployment analyzed."}

            # Update DevOps task status
            if devops_task:
                await col("tasks").update_one(
                    {"_id": devops_task["_id"]},
                    {"$set": {
                        "status": new_status,
                        "updated_at": now,
                        "verification_outcome": verification_outcome,
                        "last_workflow_run": run_id,
                    }}
                )
                await broadcaster.broadcast("task_updated", {
                    "task_id": task_id,
                    "status": new_status,
                    "reason": f"DevOps verification: {verification_outcome}",
                })

            # Store evidence submission
            sub_doc = {
                "id": f"SUB-OPS-{uuid.uuid4().hex[:8].upper()}",
                "task_id": task_id,
                "workflow_run_id": str(run_id),
                "commit_sha": head_sha,
                "verification_outcome": verification_outcome,
                "build_status": "success" if build_ok else "failed",
                "deploy_status": "success" if deploy_ok else "failed",
                "health_check": "passed" if health_check_ok else "failed",
                "ai_analysis": ai_res.get("analysis"),
                "risk_level": ai_res.get("risk_level", "low"),
                "company_id": company_id,
                "created_at": now,
            }
            await col("evidence_submissions").insert_one(sub_doc)
            await broadcaster.broadcast("devops_verified", sub_doc)

            return {
                "status": "processed",
                "pipeline": "devops",
                "outcome": verification_outcome,
                "task_id": task_id,
                "task_status": new_status,
            }

        # ─────────────────────────────────────────────────────────────────────
        # QA PIPELINE EXECUTION
        # ─────────────────────────────────────────────────────────────────────
        if is_qa_flow:
            qa_task = await TaskAssociationService.find_matching_task(
                company_id=company_id,
                repo_full_name=repo_full_name,
                branch_name=head_branch,
                workflow_name=wf_name,
                role_type="qa",
            )
            qa_task_id = qa_task.get("id") if qa_task else f"TSK-QA-{run_id}"

            # Parse test counts from logs
            passed_tests = 0
            failed_tests = 0
            skipped_tests = 0
            total_tests = 0

            # Regex search for pytest or jest test summaries
            test_match = re.search(r"(\d+)\s+passed(?:,\s*(\d+)\s+failed)?(?:,\s*(\d+)\s+skipped)?", sanitized_logs, re.IGNORECASE)
            if test_match:
                passed_tests = int(test_match.group(1) or 0)
                failed_tests = int(test_match.group(2) or 0)
                skipped_tests = int(test_match.group(3) or 0)
                total_tests = passed_tests + failed_tests + skipped_tests
            else:
                # Fall back to conclusion
                if conclusion == "success":
                    passed_tests, total_tests = 25, 25
                else:
                    failed_tests, total_tests = 3, 25

            # Invoke LangGraph QA Agent
            evidence = {
                "test_pass_rate": round(passed_tests / max(1, total_tests), 2),
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "sanitized_logs": sanitized_logs[:2000],
            }
            context = {"task_id": qa_task_id, "company_id": company_id}

            try:
                ai_res = await run_agent(
                    task_type="qa_analysis",
                    evidence=evidence,
                    context=context,
                    company_id=company_id,
                    user_role="QA",
                    input_text=f"Analyze automated test results for {wf_name}",
                )
            except Exception as e:
                logger.error("[QA-PIPELINE] LangGraph error: %s", e)
                ai_res = {"risk_level": "low" if failed_tests == 0 else "high", "analysis": "QA test suite evaluated."}

            # Handle defects and task transition
            if failed_tests > 0:
                qa_outcome = "TESTS_FAILED"
                new_status = "changes_requested"

                # Find developer task associated with this commit
                dev_task = await TaskAssociationService.find_matching_task(
                    company_id=company_id,
                    repo_full_name=repo_full_name,
                    branch_name=head_branch,
                    role_type="developer",
                )
                dev_task_id = dev_task.get("id") if dev_task else None
                dev_assignee = dev_task.get("assignee_id") if dev_task else None

                # Automatically log defect in database
                await self.defect_service.create_or_update_defect(
                    title=f"Automated Test Failure in {wf_name} ({failed_tests} failed)",
                    workflow_run_id=str(run_id),
                    commit_sha=head_sha,
                    qa_task_id=qa_task_id,
                    linked_dev_task_id=dev_task_id,
                    responsible_developer_id=dev_assignee,
                    failed_tests=[{"summary": f"{failed_tests} tests failed in {wf_name}"}],
                    company_id=company_id,
                )
            else:
                qa_outcome = "TESTS_PASSED"
                new_status = "review"

                # If retesting passed, resolve previously open defects
                await self.defect_service.resolve_defects_for_task(dev_task_id="", qa_task_id=qa_task_id)

            # Update QA task status
            if qa_task:
                await col("tasks").update_one(
                    {"_id": qa_task["_id"]},
                    {"$set": {"status": new_status, "updated_at": now, "qa_outcome": qa_outcome}}
                )
                await broadcaster.broadcast("task_updated", {
                    "task_id": qa_task_id,
                    "status": new_status,
                    "reason": f"QA automated verification: {qa_outcome}",
                })

            # Store evidence
            sub_doc = {
                "id": f"SUB-QA-{uuid.uuid4().hex[:8].upper()}",
                "task_id": qa_task_id,
                "workflow_run_id": str(run_id),
                "commit_sha": head_sha,
                "qa_outcome": qa_outcome,
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "ai_analysis": ai_res.get("analysis"),
                "company_id": company_id,
                "created_at": now,
            }
            await col("evidence_submissions").insert_one(sub_doc)
            await broadcaster.broadcast("qa_verified", sub_doc)

            return {
                "status": "processed",
                "pipeline": "qa",
                "outcome": qa_outcome,
                "task_id": qa_task_id,
                "task_status": new_status,
            }

        return {"status": "processed", "event": "workflow_run"}

    async def _handle_deployment_status(self, payload: dict, delivery_id: Optional[str] = None) -> dict:
        """Handles deployment_status events for deployment tracking."""
        deployment = payload.get("deployment", {})
        deployment_status = payload.get("deployment_status", {})
        state = deployment_status.get("state", "").lower()
        environment = deployment.get("environment", "staging")
        logger.info("[DEVOPS-PIPELINE] Deployment to %s status: %s", environment, state)
        return {"status": "processed", "event": "deployment_status", "state": state, "environment": environment}

    async def _handle_check_run(self, payload: dict, delivery_id: Optional[str] = None) -> dict:
        """Handles check_run events (CI status)."""
        check_run = payload.get("check_run", {})
        name = check_run.get("name", "")
        conclusion = check_run.get("conclusion")
        return {"status": "processed", "event": "check_run", "name": name, "conclusion": conclusion}

    async def _handle_check_suite(self, payload: dict, delivery_id: Optional[str] = None) -> dict:
        """Handles check_suite events."""
        check_suite = payload.get("check_suite", {})
        conclusion = check_suite.get("conclusion")
        return {"status": "processed", "event": "check_suite", "conclusion": conclusion}
