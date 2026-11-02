"""
Samanvaya Complete End-to-End Pipeline & Dashboard Verification
================================================================
1. Full System Health
2. Company & 7 Roles Auth Verification
3. Hiring Pipeline Workflow (Create candidate -> Interview -> Offer -> Hired)
4. Project & Sprint Creation
5. Task Assignment across all 7 Roles
6. Task Progress Workflow (todo -> in_progress -> review)
7. Approval Workflow (review -> done)
8. Dashboard & Panel Section Checks for all 7 Roles
9. AI Agent Direct Invocations (Code Review, QA, DevOps, Meeting)
10. Multi-Agent Evaluation with verbose=True & Per-Agent Metrics Breakdown
11. Feature & Extended Endpoints Verification
"""

import asyncio
import httpx
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"
TIMEOUT = 30.0
AI_TIMEOUT = 120.0

results = []
tokens = {}
user_ids = {}

def record(phase, item, status, detail=""):
    badge = "PASS" if status == "PASS" else "FAIL" if status == "FAIL" else "WARN"
    print(f"[{badge}] [{phase}] {item}" + (f" -> {detail[:150]}" if detail else ""))
    results.append({"phase": phase, "item": item, "status": status, "detail": detail})

class RetryClient:
    def __init__(self, inner):
        self.inner = inner
    async def get(self, *a, **kw):
        for i in range(3):
            try:
                return await self.inner.get(*a, **kw)
            except Exception as e:
                if i == 2: raise
                await asyncio.sleep(1.5)
    async def post(self, *a, **kw):
        for i in range(3):
            try:
                return await self.inner.post(*a, **kw)
            except Exception as e:
                if i == 2: raise
                await asyncio.sleep(1.5)
    async def put(self, *a, **kw):
        for i in range(3):
            try:
                return await self.inner.put(*a, **kw)
            except Exception as e:
                if i == 2: raise
                await asyncio.sleep(1.5)
    async def patch(self, *a, **kw):
        for i in range(3):
            try:
                return await self.inner.patch(*a, **kw)
            except Exception as e:
                if i == 2: raise
                await asyncio.sleep(1.5)

async def main():
    print("=" * 80)
    print("  SAMANVAYA FULL PIPELINE & DASHBOARDS AUDIT")
    print(f"  Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as raw_c:
        c = RetryClient(raw_c)

        # -------------------------------------------------------------
        # 1. HEALTH CHECKS
        # -------------------------------------------------------------
        print("\n--- 1. SYSTEM HEALTH CHECKS ---")
        r = await c.get("/")
        record("HEALTH", "Root API", "PASS" if r.status_code == 200 else "FAIL", f"status={r.status_code}")

        r = await c.get("/health")
        if r.status_code == 200:
            h = r.json()
            deps = h.get("dependencies", {})
            record("HEALTH", "Core Dependencies", "PASS", f"DB: {deps.get('database')} | Ollama: {deps.get('ollama')}")
        else:
            record("HEALTH", "Core Dependencies", "FAIL", f"status={r.status_code}")

        r = await c.get("/api/ai/health")
        if r.status_code == 200:
            record("HEALTH", "AI Engine Health", "PASS", f"status={r.json().get('status')}")
        else:
            record("HEALTH", "AI Engine Health", "FAIL", f"status={r.status_code}")

        # -------------------------------------------------------------
        # 2. AUTHENTICATION FOR ALL 7 ROLES
        # -------------------------------------------------------------
        print("\n--- 2. ROLE AUTHENTICATION ---")
        users_def = [
            ("EMP-007", "CEO", "Alexander Sterling"),
            ("EMP-006", "HR", "Priya Sharma"),
            ("EMP-003", "PM", "Rachel Zane"),
            ("EMP-002", "LEAD", "Marcus Vance"),
            ("EMP-001", "DEVELOPER", "Sarah Connor"),
            ("EMP-005", "DEVOPS", "Jordan Hayes"),
            ("EMP-004", "QA", "Elena Rostova"),
        ]

        for emp_id, role, expected_name in users_def:
            res = await c.post("/api/auth/login", json={
                "employee_id": emp_id,
                "organisation_password": "Samanvaya@Org2024",
                "employee_password": "Samanvaya@Emp2024"
            })
            if res.status_code == 200:
                tok = res.json().get("token")
                tokens[role] = tok
                user_ids[role] = emp_id
                record("AUTH", f"Login {role} ({emp_id})", "PASS", f"Name: {expected_name}")
            else:
                record("AUTH", f"Login {role} ({emp_id})", "FAIL", f"HTTP {res.status_code}")

        ceo_token = tokens.get("CEO")
        hr_token = tokens.get("HR")
        ceo_h = {"Authorization": f"Bearer {ceo_token}"}
        hr_h = {"Authorization": f"Bearer {hr_token}"}

        # -------------------------------------------------------------
        # 3. HIRING PIPELINE WORKFLOW
        # -------------------------------------------------------------
        print("\n--- 3. HIRING PIPELINE WORKFLOW ---")
        cand_id = f"CAND-{datetime.now().strftime('%M%S')}"
        cand_payload = {
            "id": cand_id,
            "name": "Alex Mercer",
            "email": f"alex.mercer.{cand_id}@example.com",
            "role": "Developer",
            "dept": "Engineering",
            "experience": "5 years",
            "status": "Screening",
            "appliedDate": datetime.now().strftime("%b %d, %Y"),
            "company_id": "ORG-001"
        }

        # 3.1 Create candidate
        r = await c.post("/api/candidates", json=cand_payload, headers=hr_h)
        if r.status_code in (200, 201):
            record("HIRING", "Create Candidate", "PASS", f"Alex Mercer ({cand_id}) in Screening")
        else:
            record("HIRING", "Create Candidate", "FAIL", f"HTTP {r.status_code}: {r.text[:100]}")

        # 3.2 Progress to Interview
        r = await c.put(f"/api/candidates/{cand_id}", json={"status": "Interview"}, headers=hr_h)
        if r.status_code == 200:
            record("HIRING", "Progress to Interview", "PASS", f"Candidate {cand_id} -> Interview")
        else:
            record("HIRING", "Progress to Interview", "FAIL", f"HTTP {r.status_code}")

        # 3.3 Progress to Offer Sent
        r = await c.put(f"/api/candidates/{cand_id}", json={"status": "Offer Sent"}, headers=hr_h)
        if r.status_code == 200:
            record("HIRING", "Progress to Offer Sent", "PASS", f"Candidate {cand_id} -> Offer Sent")
        else:
            record("HIRING", "Progress to Offer Sent", "FAIL", f"HTTP {r.status_code}")

        # 3.4 Progress to Hired
        r = await c.put(f"/api/candidates/{cand_id}", json={"status": "Hired"}, headers=hr_h)
        if r.status_code == 200:
            record("HIRING", "Complete Hiring (Hired)", "PASS", f"Candidate {cand_id} -> Hired")
        else:
            record("HIRING", "Complete Hiring (Hired)", "FAIL", f"HTTP {r.status_code}")

        # 3.5 Query candidate list
        r = await c.get("/api/candidates", headers=hr_h)
        if r.status_code == 200:
            cands = r.json()
            record("HIRING", "List Candidates", "PASS", f"Total candidates count: {len(cands)}")
        else:
            record("HIRING", "List Candidates", "FAIL", f"HTTP {r.status_code}")

        # -------------------------------------------------------------
        # 4. PROJECT & SPRINT MANAGEMENT
        # -------------------------------------------------------------
        print("\n--- 4. PROJECT & SPRINT SETUP ---")
        proj_res = await c.post("/api/projects", json={
            "name": f"Enterprise Cloud Suite v{datetime.now().strftime('%M%S')}",
            "description": "Multi-agent integrated workflow test project",
            "status": "active"
        }, headers=ceo_h)
        project_id = None
        if proj_res.status_code in (200, 201):
            project_id = proj_res.json().get("_id") or proj_res.json().get("id")
            record("PROJECT", "Create Project", "PASS", f"Project ID: {project_id}")
        else:
            record("PROJECT", "Create Project", "FAIL", f"HTTP {proj_res.status_code}")

        sprint_id = None
        if project_id:
            sprint_res = await c.post("/api/sprints", json={
                "name": "Sprint Alpha - Full Cycle",
                "project_id": project_id,
                "goal": "Verify all role workflows and agent intelligence",
                "start_date": "2026-10-01",
                "end_date": "2026-10-15",
                "status": "active"
            }, headers=ceo_h)
            if sprint_res.status_code in (200, 201):
                sprint_id = sprint_res.json().get("_id") or sprint_res.json().get("id")
                record("SPRINT", "Create Sprint", "PASS", f"Sprint ID: {sprint_id}")
            else:
                record("SPRINT", "Create Sprint", "FAIL", f"HTTP {sprint_res.status_code}")

        # -------------------------------------------------------------
        # 5. ASSIGN TASKS TO ALL 7 ROLES
        # -------------------------------------------------------------
        print("\n--- 5. TASK CREATION & ASSIGNMENT ---")
        task_specs = [
            ("CEO", "Define Q4 Corporate Strategy", "high"),
            ("HR", "Execute Q4 Talent Acquisition", "medium"),
            ("PM", "Align Roadmap & Epic Deliverables", "high"),
            ("LEAD", "Architecture Review & Tech Debt Audit", "high"),
            ("DEVELOPER", "Implement OAuth2 & Token Rotation", "high"),
            ("DEVOPS", "Deploy K8s Ingress & Auto-Scaler", "high"),
            ("QA", "Automate End-to-End Regression Suite", "high"),
        ]

        assigned_tasks = {}
        for role, title, priority in task_specs:
            assignee = user_ids.get(role)
            r = await c.post("/api/tasks", json={
                "title": title,
                "description": f"Core deliverable for {role}",
                "priority": priority,
                "status": "todo",
                "project_id": project_id,
                "sprint_id": sprint_id,
                "assignee_id": assignee
            }, headers=ceo_h)
            if r.status_code in (200, 201):
                tid = r.json().get("_id") or r.json().get("id")
                assigned_tasks[role] = tid
                record("TASK", f"Assign task to {role}", "PASS", f"Task ID: {tid} | Title: {title}")
            else:
                record("TASK", f"Assign task to {role}", "FAIL", f"HTTP {r.status_code}")

        # -------------------------------------------------------------
        # 6. WORKFLOW EXECUTION (todo -> in_progress -> review)
        # -------------------------------------------------------------
        print("\n--- 6. TASK EXECUTION WORKFLOW ---")
        for role, tid in assigned_tasks.items():
            tok = tokens.get(role)
            h = {"Authorization": f"Bearer {tok}"}
            # Start task
            r1 = await c.patch(f"/api/tasks/{tid}/status?status=in_progress", headers=h)
            if r1.status_code == 200:
                record("WORKFLOW", f"{role}: todo -> in_progress", "PASS", f"Task: {tid}")
            else:
                record("WORKFLOW", f"{role}: todo -> in_progress", "FAIL", f"HTTP {r1.status_code}")

            # Mark ready for review
            r2 = await c.post(f"/api/tasks/{tid}/mark-done", json={}, headers=h)
            if r2.status_code == 200:
                record("WORKFLOW", f"{role}: in_progress -> review", "PASS", f"Task: {tid}")
            else:
                record("WORKFLOW", f"{role}: in_progress -> review", "FAIL", f"HTTP {r2.status_code}")

        # -------------------------------------------------------------
        # 7. APPROVAL WORKFLOW (review -> done)
        # -------------------------------------------------------------
        print("\n--- 7. TASK APPROVAL WORKFLOW ---")
        for role, tid in assigned_tasks.items():
            r = await c.post(f"/api/tasks/{tid}/approve", json={}, headers=ceo_h)
            if r.status_code == 200:
                record("APPROVAL", f"CEO approves {role} task -> done", "PASS", f"Task: {tid}")
            else:
                record("APPROVAL", f"CEO approves {role} task", "FAIL", f"HTTP {r.status_code}")

        # -------------------------------------------------------------
        # 8. ROLE DASHBOARDS & PANEL SECTIONS AUDIT
        # -------------------------------------------------------------
        print("\n--- 8. ROLE DASHBOARDS & PANELS AUDIT ---")
        dashboard_tests = {
            "CEO": [
                ("/api/role/ceo/dashboard", "CEO Overview Dashboard"),
                ("/api/role/ceo/execution-health", "CEO Execution Health"),
                ("/api/role/ceo/critical-risks", "CEO Critical Risks"),
            ],
            "HR": [
                ("/api/role/hr/dashboard", "HR Overview Dashboard"),
                ("/api/role/hr/employees", "HR Employee Directory"),
                ("/api/role/hr/teams", "HR Teams Management"),
            ],
            "PM": [
                ("/api/role/pm/dashboard", "PM Overview Dashboard"),
                ("/api/role/pm/projects", "PM Projects View"),
                ("/api/role/pm/risks", "PM Risk Matrix"),
            ],
            "LEAD": [
                ("/api/role/lead/dashboard", "Lead Overview Dashboard"),
                ("/api/role/lead/team", "Lead Team Workload"),
                ("/api/role/lead/review-queue", "Lead Review Queue"),
            ],
            "DEVELOPER": [
                ("/api/role/developer/dashboard", "Developer Overview Dashboard"),
                ("/api/role/developer/my-tasks", "Developer Assigned Tasks"),
                ("/api/role/developer/my-prs", "Developer Pull Requests"),
            ],
            "DEVOPS": [
                ("/api/role/devops/dashboard", "DevOps Overview Dashboard"),
                ("/api/role/devops/pipelines", "DevOps CI/CD Pipelines"),
                ("/api/role/devops/deployments", "DevOps Deployments"),
            ],
            "QA": [
                ("/api/role/qa/dashboard", "QA Overview Dashboard"),
                ("/api/role/qa/bugs", "QA Bug Tracking"),
                ("/api/role/qa/test-health", "QA Test Suite Health"),
            ]
        }

        for role, endpoints in dashboard_tests.items():
            tok = tokens.get(role)
            h = {"Authorization": f"Bearer {tok}"}
            for ep, label in endpoints:
                r = await c.get(ep, headers=h)
                if r.status_code == 200:
                    record("PANEL", f"{role}: {label}", "PASS", f"HTTP 200")
                else:
                    record("PANEL", f"{role}: {label}", "FAIL", f"HTTP {r.status_code}")

        # -------------------------------------------------------------
        # 9. AI SPECIALIST AGENTS DIRECT INVOCATION
        # -------------------------------------------------------------
        print("\n--- 9. AI SPECIALIST AGENT INVOCATION ---")
        agent_invocations = [
            ("code_review", {
                "complexity_score": 42, "risk_level": "medium",
                "files_changed": 5, "test_coverage": 78.5
            }, {"pr_title": "Implement OAuth2 & Token Rotation", "author": "sarah.connor"}),
            ("qa_analysis", {
                "test_pass_rate": 0.94, "bugs_found": 2,
                "critical_bugs": 0, "regression_coverage": 0.88
            }, {"sprint": "Sprint Alpha", "module": "Security"}),
            ("devops_risk", {
                "failed_deployments": 0, "pipeline_success_rate": 0.98,
                "infra_alerts": 1, "uptime": 0.999
            }, {"env": "production"}),
            ("meeting_insights", {
                "standups_attended": 10, "total_standups": 10,
                "prs_reviewed": 5, "blockers_resolved": 3
            }, {"sprint": "Sprint Alpha"}),
        ]

        for task_type, ev, ctx in agent_invocations:
            r = await c.post("/api/ai/invoke", json={
                "task_type": task_type,
                "evidence": ev,
                "context": ctx,
                "save_run": True
            }, headers=ceo_h, timeout=AI_TIMEOUT)
            if r.status_code == 200:
                res = r.json()
                record("AI_AGENT", f"Agent: {task_type}", "PASS",
                       f"Risk: {res.get('risk_level')} | Confidence: {res.get('confidence')} | Exec: {round(res.get('execution_time_ms', 0), 1)}ms")
            else:
                record("AI_AGENT", f"Agent: {task_type}", "FAIL", f"HTTP {r.status_code}")

        # -------------------------------------------------------------
        # 10. MULTI-AGENT EVALUATION WITH VERBOSE=TRUE
        # -------------------------------------------------------------
        print("\n--- 10. MULTI-AGENT EVALUATION (verbose=True) ---")
        eval_roles = ["DEVELOPER", "LEAD", "DEVOPS", "QA"]
        for role in eval_roles:
            emp_id = user_ids.get(role)
            r = await c.post("/api/evaluation/run", json={
                "employee_id": emp_id,
                "start_date": "2026-09-01",
                "end_date": "2026-09-30",
                "period_label": "2026-09",
                "company_id": "ORG-001",
                "skip_llm": True,
                "verbose": True
            }, headers=ceo_h, timeout=AI_TIMEOUT)

            if r.status_code == 200:
                data = r.json()
                overall = data.get("overall_score") or data.get("final_score")
                grade = data.get("grade", "N/A")
                conf = data.get("confidence", "N/A")
                lat = data.get("evaluation_latency_ms", 0)
                record("EVAL", f"Evaluate {role} ({emp_id})", "PASS",
                       f"Score: {overall} | Grade: {grade} | Conf: {conf} | Latency: {lat}ms")

                # Print Detailed Agent Metrics Breakdown
                agent_metrics = data.get("agent_metrics", {})
                if agent_metrics:
                    print(f"\n      >>> AGENT EVALUATION METRICS BREAKDOWN for {data.get('employee_name', role)}:")
                    print(f"      {'Specialist Agent':<25} {'Score':>7} {'Confidence':>12} {'Risk':<10} Recommendation")
                    print(f"      {'-'*75}")
                    for dim, m in agent_metrics.items():
                        score_str = f"{m.get('score'):.1f}" if m.get('score') is not None else "N/A"
                        conf_val = m.get('confidence', 0.0)
                        risk_val = m.get('risk_level') or "nominal"
                        recs = m.get('recommendations') or []
                        first_rec = str(recs[0])[:35] if recs else "Dimension within normal limits"
                        print(f"      {m.get('agent', dim):<25} {score_str:>7} {conf_val:>12.2f} {risk_val:<10} {first_rec}")
                    print(f"      Dimension Weights: {data.get('weights_used', {})}\n")
            else:
                record("EVAL", f"Evaluate {role} ({emp_id})", "FAIL", f"HTTP {r.status_code}: {r.text[:100]}")

        # -------------------------------------------------------------
        # 11. FEATURE & EXTENDED PLATFORM ENDPOINTS
        # -------------------------------------------------------------
        print("\n--- 11. FEATURE & EXTENDED PLATFORM ENDPOINTS ---")
        feature_checks = [
            ("All Evaluations Feed", "/api/evaluation", ceo_h),
            ("Intelligence Engine Health", "/api/intelligence/health", ceo_h),
            ("Notifications Center", "/api/notifications/", ceo_h),
            ("Code Quality Languages", "/api/code-quality/languages", ceo_h),
            ("CI/CD Log Patterns", "/api/cicd-logs/patterns", ceo_h),
            ("Activity Feed (Me)", "/api/activity/me", ceo_h),
            ("Kanban Board (Project)", f"/api/boards/project/{project_id}", ceo_h),
            ("Developer Performance Trend", f"/api/performance/developer/{user_ids['DEVELOPER']}/trend", ceo_h),
            ("Developer Dashboard API", f"/api/performance/dashboard/{user_ids['DEVELOPER']}", ceo_h),
            ("Organization Users", "/api/users", ceo_h),
            ("Organization Teams", "/api/teams", ceo_h),
            ("Organization Pipelines", "/api/pipelines", ceo_h),
            ("Platform Reports", "/api/reports", ceo_h),
        ]

        for label, path, auth_h in feature_checks:
            r = await c.get(path, headers=auth_h)
            if r.status_code == 200:
                record("FEATURES", label, "PASS", f"HTTP 200")
            else:
                record("FEATURES", label, "FAIL", f"HTTP {r.status_code}")

        # -------------------------------------------------------------
        # SUMMARY SCORECARD
        # -------------------------------------------------------------
        print("\n" + "=" * 80)
        print("  FINAL EXECUTION SCORECARD")
        print("=" * 80)
        phases = {}
        for item in results:
            p = item["phase"]
            if p not in phases:
                phases[p] = {"PASS": 0, "FAIL": 0, "WARN": 0}
            phases[p][item["status"]] += 1

        for p, counts in phases.items():
            tot = sum(counts.values())
            res_str = "PASS" if counts["FAIL"] == 0 else "FAIL"
            print(f"  [{res_str:<4}] {p:<15} — PASS: {counts['PASS']:<3} FAIL: {counts['FAIL']:<3} (Total: {tot})")

        total = len(results)
        passes = sum(1 for x in results if x["status"] == "PASS")
        fails = sum(1 for x in results if x["status"] == "FAIL")
        rate = round((passes / total) * 100, 1)

        print("-" * 80)
        print(f"  TOTAL CHECKS: {total} | PASSED: {passes} | FAILED: {fails} | SUCCESS RATE: {rate}%")
        print("=" * 80)

asyncio.run(main())
