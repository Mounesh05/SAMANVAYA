"""
Master Automated Verification Suite for Developer, DevOps, and QA Webhook Integration.
Tests all 3 employee pipelines through live GitHub App webhook simulation with
real HMAC-SHA256 signatures, task state machine validation, LangGraph AI verification,
defect tracking, and failure edge cases.
"""

import asyncio
import hmac
import hashlib
import json
import uuid
import httpx
from datetime import datetime, timezone

BASE_URL = "http://127.0.0.1:8000"
WEBHOOK_SECRET = "test-webhook-secret-2026"

scorecard = []

def record(category: str, test_name: str, status: str, details: str = ""):
    scorecard.append({
        "category": category,
        "test": test_name,
        "status": status,
        "details": details,
    })
    badge = f"[{status}]"
    print(f"  {badge:<8} {category:<18} | {test_name:<42} -> {details}")


def make_signature(payload_bytes: bytes, secret: str = WEBHOOK_SECRET) -> str:
    """Generates a valid GitHub X-Hub-Signature-256 header."""
    return "sha256=" + hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()


async def run_master_webhook_tests():
    print("=" * 85)
    print("  SAMANVAYA: GITHUB WEBHOOK PIPELINES AUTOMATION AUDIT & TEST SUITE")
    print("  Testing Developer, DevOps, and QA Workflows (Option 1: Primary Integration)")
    print("=" * 85)

    from core.config import settings
    settings.GITHUB_WEBHOOK_SECRET = WEBHOOK_SECRET
    from core.database import col

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0) as client:
        # =====================================================================
        # 1. SETUP TEST ENTITIES & TASKS IN MONGODB
        # =====================================================================
        print("\n--- 1. PROVISIONING DEDICATED TEST ENTITIES ---")
        now = datetime.now(timezone.utc).isoformat()
        company_id = "ORG-EIT-TEST"
        repo_name = "eitc-org/execution-platform"

        # Register organization
        await col("organizations").update_one(
            {"id": company_id},
            {"$set": {
                "id": company_id,
                "company_id": company_id,
                "name": "Execution Intelligence Testing Company",
                "code": "EITC",
                "repositories": [repo_name],
            }},
            upsert=True
        )

        # Developer User & Task
        dev_user_id = "EMP-DEV-AUTO-01"
        dev_task_id = "TSK-DEV-AUTO-101"
        await col("users").update_one(
            {"id": dev_user_id},
            {"$set": {"id": dev_user_id, "name": "Sarah Connor", "github_username": "sarah-connor", "company_id": company_id}},
            upsert=True
        )
        await col("tasks").update_one(
            {"id": dev_task_id},
            {"$set": {
                "id": dev_task_id,
                "title": f"{dev_task_id}: Implement OAuth2 Authentication System",
                "status": "todo",
                "assignee_id": dev_user_id,
                "type": "feature",
                "company_id": company_id,
                "created_at": now,
            }},
            upsert=True
        )

        # DevOps User & Task
        ops_user_id = "EMP-OPS-AUTO-02"
        ops_task_id = "TSK-OPS-AUTO-201"
        await col("users").update_one(
            {"id": ops_user_id},
            {"$set": {"id": ops_user_id, "name": "Jordan Hayes", "github_username": "jordan-hayes", "company_id": company_id}},
            upsert=True
        )
        await col("tasks").update_one(
            {"id": ops_task_id},
            {"$set": {
                "id": ops_task_id,
                "title": f"{ops_task_id}: Deploy Ingress & Staging Environment",
                "status": "todo",
                "assignee_id": ops_user_id,
                "type": "devops",
                "company_id": company_id,
                "created_at": now,
            }},
            upsert=True
        )

        # QA User & Task
        qa_user_id = "EMP-QA-AUTO-03"
        qa_task_id = "TSK-QA-AUTO-301"
        await col("users").update_one(
            {"id": qa_user_id},
            {"$set": {"id": qa_user_id, "name": "Maya Lin", "github_username": "maya-lin", "company_id": company_id}},
            upsert=True
        )
        await col("tasks").update_one(
            {"id": qa_task_id},
            {"$set": {
                "id": qa_task_id,
                "title": f"{qa_task_id}: Automated End-to-End Test Suite",
                "status": "todo",
                "assignee_id": qa_user_id,
                "type": "qa",
                "company_id": company_id,
                "created_at": now,
            }},
            upsert=True
        )
        record("PROVISIONING", "Seed Test Entities & Tasks", "PASS", "Dev, DevOps, QA tasks seeded in TO DO")

        # =====================================================================
        # 2. SECURITY, SIGNATURE & DEDUPLICATION TESTS
        # =====================================================================
        print("\n--- 2. SECURITY & WEBHOOK INTEGRITY VERIFICATION ---")
        test_payload = {"test": "ping", "repository": {"full_name": repo_name}}
        body_bytes = json.dumps(test_payload).encode("utf-8")

        # 2.1 Invalid Signature Rejected
        bad_sig_res = await client.post(
            "/api/webhooks/github",
            content=body_bytes,
            headers={
                "X-GitHub-Event": "ping",
                "X-Hub-Signature-256": "sha256=badbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadb",
                "Content-Type": "application/json",
            }
        )
        record("SECURITY", "Invalid Signature Rejected", "PASS" if bad_sig_res.status_code == 401 else "FAIL", f"HTTP {bad_sig_res.status_code}")

        # 2.2 Valid Signature Accepted
        valid_sig = make_signature(body_bytes)
        good_sig_res = await client.post(
            "/api/webhooks/github",
            content=body_bytes,
            headers={
                "X-GitHub-Event": "ping",
                "X-Hub-Signature-256": valid_sig,
                "Content-Type": "application/json",
            }
        )
        record("SECURITY", "Valid HMAC-SHA256 Accepted", "PASS" if good_sig_res.status_code == 200 else "FAIL", f"HTTP {good_sig_res.status_code}")

        # 2.3 Delivery Deduplication via X-GitHub-Delivery
        deliv_id = f"delivery-{uuid.uuid4().hex}"
        d1_res = await client.post(
            "/api/webhooks/github",
            content=body_bytes,
            headers={
                "X-GitHub-Event": "ping",
                "X-Hub-Signature-256": make_signature(body_bytes),
                "X-GitHub-Delivery": deliv_id,
                "Content-Type": "application/json",
            }
        )
        d2_res = await client.post(
            "/api/webhooks/github",
            content=body_bytes,
            headers={
                "X-GitHub-Event": "ping",
                "X-Hub-Signature-256": make_signature(body_bytes),
                "X-GitHub-Delivery": deliv_id,
                "Content-Type": "application/json",
            }
        )
        is_dedup = d2_res.status_code == 200 and d2_res.json().get("status") == "duplicate"
        record("SECURITY", "Delivery Deduplication (X-GitHub-Delivery)", "PASS" if is_dedup else "FAIL", f"First: {d1_res.json().get('status')} | Second: {d2_res.json().get('status')}")

        # =====================================================================
        # 3. DEVELOPER PIPELINE VERIFICATION
        # =====================================================================
        print("\n--- 3. DEVELOPER PIPELINE (PUSH -> PR -> AI CODE AGENT -> KANBAN) ---")
        
        # 3.1 Push Webhook -> Task moves from TO DO to IN PROGRESS
        push_payload = {
            "ref": f"refs/heads/feature/{dev_task_id}-auth",
            "repository": {"full_name": repo_name},
            "pusher": {"name": "sarah-connor"},
            "commits": [
                {"id": "a1b2c3d4e5", "message": f"{dev_task_id}: Implement token verification logic", "author": {"name": "Sarah Connor"}},
            ],
        }
        push_bytes = json.dumps(push_payload).encode("utf-8")
        push_res = await client.post(
            "/api/webhooks/github",
            content=push_bytes,
            headers={
                "X-GitHub-Event": "push",
                "X-Hub-Signature-256": make_signature(push_bytes),
                "X-GitHub-Delivery": str(uuid.uuid4()),
                "Content-Type": "application/json",
            }
        )
        task_after_push = await col("tasks").find_one({"id": dev_task_id})
        push_ok = push_res.status_code == 200 and task_after_push.get("status") == "in_progress"
        record("DEVELOPER", "Push Webhook -> IN PROGRESS", "PASS" if push_ok else "FAIL", f"Status: {task_after_push.get('status')}")

        # 3.2 PR Opened Webhook -> Triggers LangGraph Code Review Agent -> IN REVIEW
        pr_open_payload = {
            "action": "opened",
            "pull_request": {
                "number": 104,
                "title": f"{dev_task_id}: Complete OAuth2 Login Endpoint",
                "body": "Implements JWT bearer authentication and unit tests.",
                "user": {"login": "sarah-connor"},
                "head": {"ref": f"feature/{dev_task_id}-auth", "sha": "c0ffee123456"},
                "state": "open",
            },
            "repository": {"full_name": repo_name},
        }
        pr_bytes = json.dumps(pr_open_payload).encode("utf-8")
        pr_res = await client.post(
            "/api/webhooks/github",
            content=pr_bytes,
            headers={
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": make_signature(pr_bytes),
                "X-GitHub-Delivery": str(uuid.uuid4()),
                "Content-Type": "application/json",
            }
        )
        task_after_pr = await col("tasks").find_one({"id": dev_task_id})
        pr_report = await col("verification_reports").find_one({"task_id": dev_task_id})
        pr_ok = pr_res.status_code == 200 and task_after_pr.get("status") in ("review", "changes_requested") and pr_report is not None
        record("DEVELOPER", "PR Opened -> Code Agent Verification", "PASS" if pr_ok else "FAIL", f"Task: {task_after_pr.get('status')} | Score: {pr_report.get('review_score') if pr_report else None}")

        # 3.3 PR Merged -> Task Finalized
        pr_merge_payload = {
            "action": "closed",
            "pull_request": {
                "number": 104,
                "title": f"{dev_task_id}: Complete OAuth2 Login Endpoint",
                "merged": True,
                "user": {"login": "sarah-connor"},
                "head": {"ref": f"feature/{dev_task_id}-auth", "sha": "c0ffee123456"},
                "state": "closed",
            },
            "repository": {"full_name": repo_name},
        }
        merge_bytes = json.dumps(pr_merge_payload).encode("utf-8")
        await client.post(
            "/api/webhooks/github",
            content=merge_bytes,
            headers={
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": make_signature(merge_bytes),
                "X-GitHub-Delivery": str(uuid.uuid4()),
                "Content-Type": "application/json",
            }
        )
        task_after_merge = await col("tasks").find_one({"id": dev_task_id})
        record("DEVELOPER", "PR Merged -> Task DONE", "PASS" if task_after_merge.get("status") == "done" else "FAIL", f"Status: {task_after_merge.get('status')}")

        # =====================================================================
        # 4. DEVOPS PIPELINE VERIFICATION
        # =====================================================================
        print("\n--- 4. DEVOPS PIPELINE (GITHUB ACTIONS DEPLOYMENT -> VERIFICATION) ---")
        
        # 4.1 Successful Deployment with HTTP 200 Health Check -> VERIFIED & IN REVIEW
        ops_payload = {
            "action": "completed",
            "workflow_run": {
                "id": 982101,
                "name": f"Deploy Staging ({ops_task_id})",
                "conclusion": "success",
                "head_sha": "deploy9821sha",
                "head_branch": f"ops/{ops_task_id}",
            },
            "repository": {"full_name": repo_name},
        }
        ops_bytes = json.dumps(ops_payload).encode("utf-8")
        ops_res = await client.post(
            "/api/webhooks/github",
            content=ops_bytes,
            headers={
                "X-GitHub-Event": "workflow_run",
                "X-Hub-Signature-256": make_signature(ops_bytes),
                "X-GitHub-Delivery": str(uuid.uuid4()),
                "Content-Type": "application/json",
            }
        )
        task_after_ops = await col("tasks").find_one({"id": ops_task_id})
        ops_ev = await col("evidence_submissions").find_one({"task_id": ops_task_id})
        ops_ok = ops_res.status_code == 200 and task_after_ops.get("status") == "review" and ops_ev.get("verification_outcome") == "VERIFIED"
        record("DEVOPS", "Deployment Completed -> VERIFIED", "PASS" if ops_ok else "FAIL", f"Task: {task_after_ops.get('status')} | Outcome: {ops_ev.get('verification_outcome') if ops_ev else None}")

        # 4.2 Failed Build / Deploy -> CHANGES REQUESTED
        ops_fail_payload = {
            "action": "completed",
            "workflow_run": {
                "id": 982102,
                "name": f"Deploy Production ({ops_task_id})",
                "conclusion": "failure",
                "head_sha": "deploybadsha",
                "head_branch": f"ops/{ops_task_id}",
            },
            "repository": {"full_name": repo_name},
        }
        ops_fail_bytes = json.dumps(ops_fail_payload).encode("utf-8")
        await client.post(
            "/api/webhooks/github",
            content=ops_fail_bytes,
            headers={
                "X-GitHub-Event": "workflow_run",
                "X-Hub-Signature-256": make_signature(ops_fail_bytes),
                "X-GitHub-Delivery": str(uuid.uuid4()),
                "Content-Type": "application/json",
            }
        )
        task_after_ops_fail = await col("tasks").find_one({"id": ops_task_id})
        record("DEVOPS", "Failed Deployment -> CHANGES REQUESTED", "PASS" if task_after_ops_fail.get("status") == "changes_requested" else "FAIL", f"Status: {task_after_ops_fail.get('status')}")

        # =====================================================================
        # 5. QA PIPELINE VERIFICATION
        # =====================================================================
        print("\n--- 5. QA PIPELINE (TEST SUITE RUNS -> DEFECT TRACKING) ---")
        
        # 5.1 Test Failure -> CHANGES REQUESTED & Defect Created for Developer
        qa_fail_payload = {
            "action": "completed",
            "workflow_run": {
                "id": 771101,
                "name": f"E2E Integration Tests ({qa_task_id})",
                "conclusion": "failure",
                "head_sha": "c0ffee123456",
                "head_branch": f"qa/{qa_task_id}",
            },
            "repository": {"full_name": repo_name},
        }
        qa_fail_bytes = json.dumps(qa_fail_payload).encode("utf-8")
        await client.post(
            "/api/webhooks/github",
            content=qa_fail_bytes,
            headers={
                "X-GitHub-Event": "workflow_run",
                "X-Hub-Signature-256": make_signature(qa_fail_bytes),
                "X-GitHub-Delivery": str(uuid.uuid4()),
                "Content-Type": "application/json",
            }
        )
        task_after_qa_fail = await col("tasks").find_one({"id": qa_task_id})
        defect = await col("defects").find_one({"qa_task_id": qa_task_id})
        qa_fail_ok = task_after_qa_fail.get("status") == "changes_requested" and defect is not None
        record("QA", "Test Failure -> Defect Created & Changes Req", "PASS" if qa_fail_ok else "FAIL", f"Task: {task_after_qa_fail.get('status')} | Defect ID: {defect.get('id') if defect else None}")

        # 5.2 Retest Passed -> Defect Resolved & IN REVIEW
        qa_pass_payload = {
            "action": "completed",
            "workflow_run": {
                "id": 771102,
                "name": f"E2E Integration Tests ({qa_task_id})",
                "conclusion": "success",
                "head_sha": "c0ffee123456",
                "head_branch": f"qa/{qa_task_id}",
            },
            "repository": {"full_name": repo_name},
        }
        qa_pass_bytes = json.dumps(qa_pass_payload).encode("utf-8")
        await client.post(
            "/api/webhooks/github",
            content=qa_pass_bytes,
            headers={
                "X-GitHub-Event": "workflow_run",
                "X-Hub-Signature-256": make_signature(qa_pass_bytes),
                "X-GitHub-Delivery": str(uuid.uuid4()),
                "Content-Type": "application/json",
            }
        )
        task_after_qa_pass = await col("tasks").find_one({"id": qa_task_id})
        resolved_defect = await col("defects").find_one({"qa_task_id": qa_task_id, "status": "resolved"})
        qa_pass_ok = task_after_qa_pass.get("status") == "review" and resolved_defect is not None
        record("QA", "Retest Succeeded -> Defect Resolved & IN REVIEW", "PASS" if qa_pass_ok else "FAIL", f"Task: {task_after_qa_pass.get('status')} | Defect: {resolved_defect.get('status') if resolved_defect else None}")

        # =====================================================================
        # 6. SENSITIVE CREDENTIAL REDACTION TEST
        # =====================================================================
        print("\n--- 6. SENSITIVE DATA REDACTION AUDIT ---")
        from core.sanitizer import sanitize_text
        dirty_log = "Error connecting with ghp_1234567890abcdefghijklmnopqrstuvwxyz and password=SuperSecretPassword123 at mongodb://admin:mysecretpass@localhost:27017"
        clean_log = sanitize_text(dirty_log)
        redact_ok = "[REDACTED" in clean_log and "SuperSecretPassword123" not in clean_log and "mysecretpass" not in clean_log
        record("SECURITY", "Secret Redaction (Tokens, Passwords, URIs)", "PASS" if redact_ok else "FAIL", f"Cleaned log: {clean_log[:60]}...")

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 85)
    print("  WEBHOOK AUTOMATION TEST SCORECARD")
    print("=" * 85)
    total = len(scorecard)
    passed = sum(1 for s in scorecard if s["status"] == "PASS")
    failed = total - passed
    print(f"  TOTAL CHECKS: {total} | PASSED: {passed} | FAILED: {failed} | SUCCESS RATE: {(passed/total)*100:.1f}%\n")
    return failed == 0

if __name__ == "__main__":
    success = asyncio.run(run_master_webhook_tests())
    exit(0 if success else 1)

