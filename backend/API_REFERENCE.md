# Samanvaya API Reference

Complete API documentation for all endpoints organized by feature and role.

## 🔐 Authentication

### Register
```http
POST /api/auth/register
Content-Type: application/json

{
  "employee_id": "E001",
  "name": "John Doe",
  "email": "john@company.com",
  "role": "DEVELOPER",
  "dept": "Engineering",
  "organisation_password": "org123",
  "employee_password": "emp123",
  "github_username": "johndoe",
  "team_id": "TEAM001"
}
```

### Login
```http
POST /api/auth/login
Content-Type: application/json

{
  "employee_id": "E001",
  "organisation_password": "org123",
  "employee_password": "emp123"
}

Response:
{
  "access_token": "eyJhbGc...",
  "token_type": "bearer",
  "user": { ... }
}
```

### Get Current User
```http
GET /api/auth/me
Authorization: Bearer {token}
```

---

## 📁 Projects

### Create Project (CEO/PM/HR only)
```http
POST /api/projects
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "Mobile App Redesign",
  "description": "Complete UI overhaul",
  "org_id": "ORG001",
  "team_id": "TEAM001",
  "start_date": "2026-08-01",
  "end_date": "2026-12-31",
  "main_module": "mobile-app"
}
```

### Get Project
```http
GET /api/projects/{project_id}
Authorization: Bearer {token}
```

### List Organization Projects
```http
GET /api/projects?org_id=ORG001
Authorization: Bearer {token}
```

### List Team Projects
```http
GET /api/projects/team/{team_id}
Authorization: Bearer {token}
```

---

## 🏃 Sprints

### Create Sprint (PM/LEAD only)
```http
POST /api/sprints
Authorization: Bearer {token}
Content-Type: application/json

{
  "name": "Sprint 12",
  "project_id": "PRJ-ABC123",
  "goal": "Complete authentication module",
  "start_date": "2026-08-10",
  "end_date": "2026-08-24"
}
```

### Get Sprint
```http
GET /api/sprints/{sprint_id}
Authorization: Bearer {token}
```

### Get Active Sprint
```http
GET /api/sprints/project/{project_id}/active
Authorization: Bearer {token}
```

### Get Sprint Health (Plan vs Reality) ⭐
```http
GET /api/sprints/{sprint_id}/health
Authorization: Bearer {token}

Response:
{
  "sprint_id": "SPR-ABC123",
  "total_stories": 15,
  "completed_stories": 8,
  "completion_pct": 53.33,
  "risk_score": 45,
  "risk_level": "MEDIUM",
  "risk_factors": [
    "Behind schedule: 12.0% behind",
    "2 stories blocked"
  ]
}
```

---

## 📖 Stories

### Create Story (PM/LEAD only)
```http
POST /api/stories
Authorization: Bearer {token}
Content-Type: application/json

{
  "title": "Implement OAuth login",
  "description": "Add Google and GitHub OAuth",
  "sprint_id": "SPR-ABC123",
  "project_id": "PRJ-ABC123",
  "assignee_id": "E001",
  "points": 5,
  "priority": "high"
}
```

### Get Story
```http
GET /api/stories/{story_id}
Authorization: Bearer {token}
```

### List Sprint Stories
```http
GET /api/stories/sprint/{sprint_id}
Authorization: Bearer {token}
```

### List My Stories
```http
GET /api/stories/assignee/{employee_id}
Authorization: Bearer {token}
```

### Update Story Status
```http
PATCH /api/stories/{story_id}/status?status=in_progress
Authorization: Bearer {token}
```

---

## ✅ Tasks

### Create Task
```http
POST /api/tasks
Authorization: Bearer {token}
Content-Type: application/json

{
  "title": "Write unit tests for OAuth",
  "project_id": "PRJ-ABC123",
  "assignee_id": "E001",
  "story_id": "STY-XYZ456",
  "type": "feature",
  "priority": "high",
  "due_date": "2026-08-20"
}
```

### Get Task
```http
GET /api/tasks/{task_id}
Authorization: Bearer {token}
```

### List My Tasks
```http
GET /api/tasks/assignee/{employee_id}
Authorization: Bearer {token}
```

### Update Task Status
```http
PATCH /api/tasks/{task_id}/status?status=done
Authorization: Bearer {token}
```

---

## 🧠 Intelligence Engine (Layer 5)

### Analyze PR Risk ⭐
```http
POST /api/intelligence/analyze-pr/{pr_id}
Authorization: Bearer {token}
Content-Type: application/json

{
  "files_changed": 15,
  "lines_added": 300,
  "lines_deleted": 50,
  "changed_files": ["src/auth/login.py", "config/secrets.yml"],
  "commit_count": 8,
  "tests_failed": 2,
  "previous_coverage": 85.0,
  "current_coverage": 78.0
}

Response:
{
  "risk_score": 68,
  "risk_level": "HIGH",
  "risk_factors": [...],
  "recommended_actions": [...]
}
```

### Analyze Sprint Health ⭐
```http
POST /api/intelligence/analyze-sprint/{sprint_id}
Authorization: Bearer {token}
Content-Type: application/json

{
  "total_stories": 15,
  "completed_stories": 6,
  "in_progress_stories": 4,
  "blocked_stories": 2,
  "total_points": 75,
  "completed_points": 30
}
```

### Analyze Deployment Risk
```http
POST /api/intelligence/analyze-deployment/{deployment_id}
Authorization: Bearer {token}
Content-Type: application/json

{
  "ci_data": {
    "builds_total": 20,
    "builds_passed": 18,
    "builds_failed": 2
  },
  "deployment_data": {
    "deployments_total": 10,
    "deployments_successful": 9,
    "deployments_failed": 1
  }
}
```

---

## 👤 Role-Specific Dashboards

### Developer Dashboard
```http
GET /api/role/developer/dashboard
Authorization: Bearer {token}

Response:
{
  "role": "DEVELOPER",
  "summary": {
    "total_tasks": 12,
    "completed_tasks": 5,
    "in_progress_tasks": 3,
    "blocked_tasks": 1,
    "open_prs": 2
  },
  "my_tasks": [...],
  "my_stories": [...],
  "my_prs": [...]
}
```

```http
GET /api/role/developer/my-tasks
GET /api/role/developer/my-prs
```

### Lead Dashboard
```http
GET /api/role/lead/dashboard
Authorization: Bearer {token}

Response:
{
  "role": "LEAD",
  "summary": {
    "team_size": 6,
    "open_prs": 8,
    "high_risk_prs": 2,
    "blocked_tasks": 3
  },
  "team_members": [...],
  "pr_review_queue": [...],
  "blockers": [...]
}
```

```http
GET /api/role/lead/team
GET /api/role/lead/review-queue
```

### PM Dashboard
```http
GET /api/role/pm/dashboard
GET /api/role/pm/projects?org_id=ORG001
GET /api/role/pm/project/{project_id}/health
GET /api/role/pm/risks
```

### CEO Dashboard
```http
GET /api/role/ceo/dashboard
GET /api/role/ceo/execution-health?org_id=ORG001
GET /api/role/ceo/critical-risks?org_id=ORG001
```

### HR Dashboard
```http
GET /api/role/hr/dashboard
GET /api/role/hr/employees
GET /api/role/hr/capacity
```

### QA Dashboard
```http
GET /api/role/qa/dashboard
GET /api/role/qa/test-health
GET /api/role/qa/bugs
```

### DevOps Dashboard
```http
GET /api/role/devops/dashboard
GET /api/role/devops/pipelines
GET /api/role/devops/deployments
```

---

## 📊 API Overview

### Total Endpoints: 50+

| Category | Count | Description |
|----------|-------|-------------|
| Auth | 3 | Registration, login, current user |
| Projects | 4 | CRUD operations |
| Sprints | 5 | CRUD + health analysis |
| Stories | 5 | CRUD + status updates |
| Tasks | 6 | CRUD + filtering |
| Intelligence | 4 | Risk analysis (Layer 5) |
| Developer | 3 | My tasks, PRs, dashboard |
| Lead | 3 | Team health, review queue |
| PM | 4 | Project health, risks |
| CEO | 3 | Org health, critical risks |
| HR | 3 | Employees, capacity |
| QA | 3 | Test health, bugs |
| DevOps | 3 | Pipelines, deployments |

---

## 🔑 Role Permissions

| Endpoint | CEO | HR | PM | LEAD | DEV | QA | DEVOPS |
|----------|-----|----|----|------|-----|-----|--------|
| Create Project | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Create Sprint | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Create Story | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Create Task | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| View Org Health | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| View Team | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| View Own Work | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## 🚀 Quick Start

1. **Register a user:**
   ```bash
   curl -X POST http://127.0.0.1:8000/api/auth/register \
     -H "Content-Type: application/json" \
     -d '{"employee_id":"E001","name":"John","email":"john@co.com","role":"DEVELOPER","dept":"Eng","organisation_password":"org123","employee_password":"emp123"}'
   ```

2. **Login:**
   ```bash
   curl -X POST http://127.0.0.1:8000/api/auth/login \
     -H "Content-Type: application/json" \
     -d '{"employee_id":"E001","organisation_password":"org123","employee_password":"emp123"}'
   ```

3. **Use token in subsequent requests:**
   ```bash
   curl -X GET http://127.0.0.1:8000/api/role/developer/dashboard \
     -H "Authorization: Bearer YOUR_TOKEN"
   ```

---

## 📖 Interactive API Docs

Visit http://127.0.0.1:8000/docs for Swagger UI with all endpoints documented and testable.
