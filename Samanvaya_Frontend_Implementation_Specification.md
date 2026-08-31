# Samanvaya Frontend — Complete Implementation Specification

**Document:** Frontend Product & Technical Specification  
**Project:** Agentic-AI Samanvaya  
**Status:** Frontend implementation blueprint  
**Frontend:** React + Vite  
**Backend:** Existing FastAPI backend  
**Database:** Existing MongoDB backend  
**Audience:** Developer implementing the Samanvaya frontend

---

## 1. Purpose

Samanvaya is an intelligent software engineering and performance platform. The frontend is the operational interface through which organizational roles manage work, inspect engineering quality, provide human feedback, and consume AI-generated insights.

The frontend must:

- authenticate users;
- enforce role-aware navigation and UI access;
- consume the existing FastAPI backend;
- provide project/team/workflow management;
- display GitHub and CI/CD information;
- display code-quality evidence and risk;
- display AI evaluations and recommendations;
- collect role-specific human feedback;
- display developer/team/project/organization performance;
- provide reports, notifications and history;
- never become the authoritative source for permissions, scores, risk, or AI results.

The backend remains authoritative for security, business rules, scoring, persistence and AI results.

---

# 2. Core Product Philosophy

Samanvaya must feel like one platform, not seven unrelated dashboards.

```text
                    SAMANVAYA
                        |
          +-------------+-------------+
          |             |             |
       WORKFLOW      QUALITY       PEOPLE
          |             |             |
      Projects      Code Quality   Performance
      Teams         Security       Feedback
      Sprints       Testing        Growth
      Stories       Risk
      Tasks         AI
      Kanban
          |             |             |
          +-------------+-------------+
                        |
                    INSIGHTS
                        |
                 Decisions / Action
```

The frontend should distinguish:

- measured evidence;
- backend-calculated scores;
- human feedback;
- AI interpretation;
- recommendations;
- user actions.

AI must never silently modify important organizational or engineering data.

---

# 3. Organizational Roles

The system has exactly seven application roles:

1. `DEVELOPER`
2. `LEAD`
3. `PM`
4. `QA`
5. `DEVOPS`
6. `HR`
7. `CEO`

Do not introduce `MANAGER`, `SUPER_ADMIN`, or `HR_ADMIN` into the frontend role model.

---

# 4. Role Responsibilities

## 4.1 DEVELOPER

### Primary objective

Build software, complete assigned work, understand personal performance and improve engineering quality.

### Main access

- own dashboard;
- own tasks;
- own board;
- assigned projects;
- assigned sprints;
- own pull requests;
- own/relevant code-quality results;
- own performance;
- received feedback;
- notifications;
- profile.

### Can create/modify

- own task progress/status where backend permits;
- comments;
- work updates.

### Cannot

- view other developers' private performance;
- manage employees;
- create teams;
- create projects;
- assign organizational members;
- trigger arbitrary performance evaluations;
- modify AI scores;
- modify historical evaluations.

---

## 4.2 LEAD

### Primary objective

Technical leadership and team execution.

### Main access

- own dashboard;
- team dashboard;
- team members;
- team tasks;
- sprints;
- stories;
- board;
- pull requests;
- team code quality;
- technical risks;
- team performance;
- technical feedback;
- relevant reports.

### Can create/modify

- technical/team workflow actions allowed by backend;
- team task assignments where permitted;
- technical feedback;
- technical workflow information.

### Cannot

- manage organization-wide employee records;
- change HR data;
- modify AI scores;
- modify historical performance;
- manage another team's members;
- change project ownership outside responsibility.

---

## 4.3 PM

### Primary objective

Project delivery, planning and project health.

### Main access

- dashboard;
- projects;
- project members;
- teams relevant to projects;
- sprints;
- stories;
- tasks;
- board;
- project analytics;
- project code-quality summaries;
- risks;
- performance;
- PM feedback;
- reports.

### Can create/modify

- projects;
- project details;
- project membership;
- project/team assignment;
- sprints;
- stories;
- tasks;
- delivery information;
- PM feedback.

### Cannot

- manage organization-wide employee administration;
- modify HR information;
- modify AI scores;
- modify historical evaluations;
- manage unrelated projects.

---

## 4.4 QA

### Primary objective

Software quality, testing and defect management.

### Main access

- QA dashboard;
- assigned projects;
- relevant developers;
- test runs;
- bugs;
- pull requests;
- code quality;
- quality risks;
- performance relevant to quality;
- QA feedback;
- quality reports.

### Can create/modify

- bugs;
- test-related records where backend permits;
- QA feedback.

### Cannot

- manage employees;
- create teams;
- change project ownership;
- modify AI scores;
- modify performance history;
- manage CI/CD infrastructure.

---

## 4.5 DEVOPS

### Primary objective

Build, deployment, reliability and operational health.

### Main access

- DevOps dashboard;
- assigned projects;
- repositories;
- pipelines;
- deployments;
- incidents;
- code-quality/security information relevant to delivery;
- operational risks;
- performance relevant to operations;
- DevOps feedback;
- operational reports.

### Can create/modify

- incidents;
- deployment/pipeline information where backend permits;
- DevOps feedback.

### Cannot

- manage employees;
- create teams;
- modify performance scores;
- modify AI results;
- manage project planning.

---

## 4.6 HR

### Primary objective

People, organizational structure and performance oversight.

### Main access

- HR dashboard;
- employees;
- teams;
- projects;
- organization performance;
- individual performance;
- performance trends;
- feedback;
- reports;
- organizational information.

### Can create/modify

- employee records;
- employee status/details;
- teams;
- team details;
- team membership;
- Team Lead assignment;
- HR feedback;
- evaluation re-runs where authorized.

### Cannot

- modify AI scores;
- modify code-quality findings;
- modify technical evidence;
- manage GitHub code;
- manage CI/CD.

---

## 4.7 CEO

### Primary objective

Executive oversight and strategic decision-making.

### Main access

- executive dashboard;
- organization;
- projects;
- teams;
- organization performance;
- quality summary;
- risk;
- delivery;
- reports;
- notifications;
- profile.

### Can

- view organization-wide information;
- view individual performance;
- view project/team performance;
- provide CEO feedback;
- request/re-run authorized evaluations;
- perform executive-level management actions supported by backend.

### Cannot

- modify AI-generated scores;
- modify historical performance records;
- edit technical findings;
- directly manage individual engineering tasks as a normal workflow.

---

# 5. Ownership Model

## People and organization

**HR owns organizational structure.**

HR manages:

- employees;
- teams;
- Team Lead assignment;
- team membership;
- employee information.

CEO has oversight.

## Projects

**PM owns project delivery.**

PM manages:

- projects;
- project membership;
- project/team assignment;
- sprints;
- stories;
- tasks;
- project analytics.

## Technical execution

**LEAD owns technical team execution.**

## Quality

**QA owns testing and defect quality workflows.**

## Operations

**DEVOPS owns operational workflows.**

## Software execution

**DEVELOPER owns assigned engineering work.**

## Strategy

**CEO owns executive oversight.**

---

# 6. Final Permission Model

The frontend uses permissions for UX and route visibility. The backend remains the security boundary.

| Capability | Developer | Lead | PM | QA | DevOps | HR | CEO |
|---|---:|---:|---:|---:|---:|---:|---:|
| Own dashboard | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Own performance | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Team performance | — | ✓ | Relevant | Quality | Ops | ✓ | ✓ |
| Project performance | Assigned | Relevant | ✓ | Relevant | Relevant | ✓ | ✓ |
| Organization performance | — | — | — | — | — | ✓ | ✓ |
| Own tasks | ✓ | ✓ | ✓ | Relevant | Relevant | — | — |
| Team workflow | — | ✓ | Relevant | — | — | — | — |
| Create project | — | — | ✓ | — | — | — | Executive |
| Manage project | — | Relevant | ✓ | — | — | View | View |
| Create/manage sprint | — | Technical | ✓ | View | View | View | View |
| Create/manage stories | Own/relevant | Team | ✓ | View | View | View | View |
| Create/manage tasks | Own | Team | ✓ | Relevant | Relevant | — | View |
| Manage employees | — | — | — | — | — | ✓ | Oversight |
| Manage teams | — | — | — | — | — | ✓ | Oversight |
| Assign Team Lead | — | — | — | — | — | ✓ | Oversight |
| Assign project members | — | Technical | ✓ | — | — | — | Oversight |
| Code quality | Own | Team | Project | Quality | Relevant | Summary | Summary |
| Pull requests | Own | Team | Project | Relevant | Relevant | Summary | Summary |
| Testing | View own | Team | Project | ✓ | Relevant | Summary | Summary |
| Bugs | Own/relevant | Team | Project | ✓ | Relevant | Summary | Summary |
| CI/CD | Relevant | Team | Project | View | ✓ | Summary | Summary |
| Deployments | — | View | Project | View | ✓ | Summary | Summary |
| Incidents | — | View | Project | View | ✓ | Summary | Summary |
| Submit role feedback | — | Lead | PM | QA | DevOps | HR | CEO |
| Trigger/re-run evaluation | — | Team | Project | — | — | ✓ | ✓ |
| Modify AI score | — | — | — | — | — | — | — |
| Modify historical score | — | — | — | — | — | — | — |

`✓` means normal access. `Relevant`, `View`, `Summary`, `Oversight`, and similar entries must map to the actual backend permissions/endpoints.

---

# 7. Frontend Technical Stack

Use:

- React
- Vite
- React Router
- Axios
- Zustand
- TanStack Query
- React Hook Form
- Zod
- Recharts
- `@dnd-kit`

Recommended responsibility:

```text
Zustand
    -> client/UI state

TanStack Query
    -> server/API state

React Hook Form + Zod
    -> forms and client validation

Axios
    -> HTTP transport

React Router
    -> routing

Recharts
    -> analytics

dnd-kit
    -> Kanban interactions
```

Do not place all server data into Zustand.

---

# 8. Frontend Folder Architecture

```text
frontend/
│
├── public/
│
├── src/
│   │
│   ├── api/
│   │   ├── client.js
│   │   ├── auth.api.js
│   │   ├── users.api.js
│   │   ├── employees.api.js
│   │   ├── teams.api.js
│   │   ├── projects.api.js
│   │   ├── sprints.api.js
│   │   ├── stories.api.js
│   │   ├── tasks.api.js
│   │   ├── board.api.js
│   │   ├── github.api.js
│   │   ├── codeQuality.api.js
│   │   ├── evaluation.api.js
│   │   ├── feedback.api.js
│   │   ├── reports.api.js
│   │   ├── notifications.api.js
│   │   └── activity.api.js
│   │
│   ├── auth/
│   │   ├── AuthContext.jsx
│   │   ├── ProtectedRoute.jsx
│   │   ├── RoleGuard.jsx
│   │   ├── PermissionGuard.jsx
│   │   └── permissions.js
│   │
│   ├── components/
│   │   ├── common/
│   │   ├── layout/
│   │   ├── charts/
│   │   ├── performance/
│   │   ├── code-quality/
│   │   ├── projects/
│   │   ├── teams/
│   │   ├── sprints/
│   │   ├── tasks/
│   │   ├── kanban/
│   │   ├── feedback/
│   │   └── notifications/
│   │
│   ├── pages/
│   │   ├── auth/
│   │   ├── developer/
│   │   ├── lead/
│   │   ├── pm/
│   │   ├── qa/
│   │   ├── devops/
│   │   ├── hr/
│   │   ├── ceo/
│   │   ├── projects/
│   │   ├── teams/
│   │   ├── sprints/
│   │   ├── stories/
│   │   ├── tasks/
│   │   ├── board/
│   │   ├── code-quality/
│   │   ├── evaluation/
│   │   ├── feedback/
│   │   ├── reports/
│   │   ├── notifications/
│   │   ├── profile/
│   │   └── shared/
│   │
│   ├── hooks/
│   │   ├── useAuth.js
│   │   ├── useApi.js
│   │   └── usePermissions.js
│   │
│   ├── context/
│   │
│   ├── routes/
│   │   └── routes.jsx
│   │
│   ├── store/
│   │
│   ├── utils/
│   │   ├── formatters.js
│   │   ├── dates.js
│   │   ├── constants.js
│   │   └── permissions.js
│   │
│   ├── App.jsx
│   ├── main.jsx
│   └── index.css
│
├── .env
├── .env.example
├── package.json
└── vite.config.js
```

---

# 9. Authentication

## Login page

Route:

```text
/login
```

Contains:

- email/identifier;
- password;
- login button;
- validation;
- loading state;
- authentication error;
- session handling.

Flow:

```text
Login
  ↓
POST backend authentication endpoint
  ↓
JWT/session returned
  ↓
Store authenticated user state
  ↓
Load current-user information
  ↓
Redirect to role dashboard
```

Logout must:

- clear authentication state;
- clear sensitive cached client data;
- redirect to login.

---

# 10. RBAC Architecture

Three levels:

```text
ProtectedRoute
    ↓
Is user authenticated?

RoleGuard
    ↓
Is the user's role allowed?

PermissionGuard
    ↓
Does the user have the specific permission?
```

Example:

```text
Developer
    ↓
/employees
    ↓
Frontend blocks route
    ↓
Backend would also return 403 if called directly
```

Frontend checks are for UX only.

Backend authorization is authoritative.

---

# 11. Application Shell

Every authenticated user receives:

- Sidebar;
- TopBar;
- page header;
- breadcrumbs where useful;
- notification access;
- profile menu;
- responsive navigation.

The sidebar is dynamically generated from role/permission configuration.

---

# 12. Common Components

Build reusable components first:

- Button
- Input
- Select
- MultiSelect
- DatePicker
- Modal
- Drawer
- Card
- Table
- Tabs
- Badge
- StatusBadge
- RiskBadge
- ScoreCard
- MetricCard
- ProgressBar
- EmptyState
- LoadingState
- ErrorState
- ConfirmDialog
- Toast
- Pagination
- Search
- FilterBar
- DataTable

All important components should be accessible.

---

# 13. Developer Dashboard

Primary question:

> How am I doing and what should I improve?

Sections:

```text
Performance
Work Summary
Sprint Status
GitHub
Code Quality
Risks
AI Recommendations
Recent Activity
```

Metrics:

- overall performance;
- AI evaluation score;
- human feedback score;
- task completion;
- sprint contribution;
- PRs;
- code quality;
- risk;
- test coverage where available.

---

# 14. Lead Dashboard

Primary question:

> How is my team performing technically?

Sections:

- team overview;
- member performance;
- technical risks;
- code quality;
- PR health;
- sprint progress;
- blocked work;
- team trends;
- feedback actions.

Include team comparison and developer drill-down where authorized.

---

# 15. PM Dashboard

Primary question:

> Will my projects deliver successfully?

Sections:

- project portfolio;
- project health;
- sprint progress;
- velocity;
- overdue work;
- blocked tasks;
- delivery risk;
- project performance;
- project quality;
- project trends.

---

# 16. QA Dashboard

Primary question:

> Is the software working correctly?

Sections:

- test coverage;
- pass rate;
- failed tests;
- bugs;
- critical bugs;
- regression risk;
- quality trends;
- PR quality;
- code-quality findings;
- QA feedback.

---

# 17. DevOps Dashboard

Primary question:

> Can we build, deploy and operate reliably?

Sections:

- pipeline health;
- deployment status;
- deployment frequency;
- deployment failures;
- incidents;
- operational risk;
- repository health;
- CI/CD trends;
- DevOps feedback.

---

# 18. HR Dashboard

Primary question:

> How are our people and teams performing?

Sections:

- employee count;
- team health;
- organization performance;
- performance distribution;
- performance trends;
- employees needing attention;
- development areas;
- feedback;
- organizational reports.

HR should not be forced to inspect source-code-level details.

---

# 19. CEO Dashboard

Primary question:

> How healthy is the organization?

Sections:

- organization performance;
- project portfolio health;
- team performance;
- delivery;
- code-quality summary;
- organizational risk;
- trends;
- executive recommendations.

CEO dashboard should be high-level and decision-oriented.

---

# 20. Employee Management

Primarily HR-owned.

Route:

```text
/employees
```

Features:

- employee list;
- search;
- filtering;
- employee details;
- create employee;
- edit employee;
- activate/deactivate;
- assign team;
- assign Team Lead;
- view projects;
- view performance where authorized.

Create employee form:

```text
Employee ID
Name
Email
Role
Department
Team
Team Lead
Projects
Hire Date
Status
```

Do not expose credentials or secrets unnecessarily.

---

# 21. Team Management

Primarily HR-owned.

Route:

```text
/teams
```

Features:

- team list;
- create team;
- edit team;
- Team Lead assignment;
- member management;
- project association;
- team metrics;
- team activity.

Team details:

```text
Team name
Team Lead
Members
Projects
Performance
Code Quality
Risk
Activity
```

---

# 22. Project Management

Primarily PM-owned.

Route:

```text
/projects
```

Project features:

- list;
- create;
- edit;
- archive where backend permits;
- project members;
- team assignment;
- repositories;
- sprints;
- stories;
- tasks;
- board;
- code quality;
- risks;
- analytics;
- activity.

---

# 23. Sprint Management

Features:

- sprint list;
- current sprint;
- create sprint;
- edit sprint;
- sprint goal;
- dates;
- stories;
- tasks;
- velocity;
- completion;
- burndown;
- risks;
- activity.

---

# 24. Story Management

Features:

- title;
- description;
- project;
- sprint;
- assignee;
- points;
- priority;
- status;
- risk;
- activity;
- comments.

Potential AI display:

- story clarity;
- ambiguity;
- estimated risk;
- dependency suggestions.

AI recommendations must require human action before changing the story.

---

# 25. Task Management

Features:

- create;
- edit;
- assign;
- priority;
- due date;
- type;
- status;
- story;
- sprint;
- comments;
- activity.

The UI must enforce the user's visible permissions.

---

# 26. Kanban Board

Columns:

```text
TODO
IN PROGRESS
REVIEW
DONE
```

Features:

- drag/drop;
- task cards;
- assignee;
- priority;
- due date;
- risk;
- quick view;
- filters;
- search.

Use `@dnd-kit`.

Workflow:

```text
Drag
 ↓
Optimistic UI
 ↓
Backend mutation
 ↓
Success → keep
Failure → rollback + error
```

---

# 27. GitHub / Engineering Pages

Provide:

```text
Repositories
Branches
Commits
Pull Requests
Reviews
CI
```

Repository page:

- repository metadata;
- languages;
- branches;
- recent commits;
- PRs;
- CI status;
- code-quality summary.

---

# 28. Pull Request Page

Display:

```text
PR metadata
Author
Branch
Base branch
Files changed
Commits
Reviews
CI status
Quality Score
Risk Score
Findings
AI Review
```

Example structure:

```text
PR #184

Quality: 88
Risk: HIGH

Build       PASS
Tests       WARNING
Security    PASS
Complexity  WARNING
Architecture WARNING

AI Assessment
...
```

---

# 29. Code Quality Module

This is a major Samanvaya feature.

Routes should support:

```text
/code-quality
/code-quality/repositories/:id
/code-quality/pr/:id
/code-quality/runs/:id
/code-quality/findings/:id
```

Main sections:

- overview;
- repositories;
- pull requests;
- analysis runs;
- findings;
- security;
- testing;
- complexity;
- architecture;
- dependencies;
- history.

---

# 30. Multi-language UI

The frontend must be language-independent.

It should display detected languages dynamically:

```text
Java          62%
TypeScript    28%
C++           10%
```

Do not create separate frontend applications for Java, C, C++, Python, etc.

The backend normalizes language-specific analysis into common evidence.

---

# 31. Code Quality Evidence

Display findings using a common model:

```text
Severity
Category
File
Line
Tool
Description
Recommendation
Confidence where available
```

Example:

```text
HIGH
Complexity

PaymentService.java
Line 184

Detected by static analyzer

Description
...

Recommendation
...
```

---

# 32. Code Quality vs Risk vs Performance

These must remain separate.

```text
Performance
    = developer/work contribution

Code Quality
    = quality of software

Risk
    = likelihood/impact of failure
```

A user may have:

```text
Performance: 92
Code Quality: 78
Risk: 64
```

These are not interchangeable metrics.

---

# 33. AI Review UX

AI should be presented as an interpretation layer over evidence.

Preferred flow:

```text
Evidence
  ↓
Finding
  ↓
Risk
  ↓
AI interpretation
  ↓
Recommendation
```

Show:

- AI assessment;
- supporting evidence;
- risk explanation;
- recommendations;
- confidence if available;
- analysis timestamp;
- model information if backend exposes it.

Never present AI output as an unexplained absolute truth.

---

# 34. AI Analysis Progress

For long-running analysis:

```text
Collecting evidence       ✓
Running analyzers         ✓
Calculating quality       ✓
Calculating risk          ●
AI reasoning              ○
Saving results            ○
```

The frontend must not freeze while an asynchronous analysis is running.

Allow users to navigate away and return later.

---

# 35. Performance Module

Sections:

```text
Overall Performance
AI Evaluation
Human Feedback
Delivery
Quality
Reliability
Collaboration
Trends
Strengths
Weaknesses
Recommendations
History
```

Example:

```text
Overall Score       87%

AI Evaluation       90%
Human Evaluation    82%

Delivery             88
Quality              91
Reliability          86
Collaboration        84
```

The backend calculates the authoritative score.

The frontend only displays it.

---

# 36. Performance Scoring

Current product concept:

```text
AI evaluation = 90% weight
Human combined evaluation = 10% weight
```

The frontend should visualize the breakdown, for example:

```text
AI Evaluation       90%
Human Evaluation    10%
-------------------------
Final Score          87%
```

If individual human evaluator contributions are returned by the backend, display them by role:

```text
Lead
PM
QA
DevOps
HR
CEO
```

Do not calculate the final score in React.

---

# 37. Feedback Module

Role-specific forms:

```text
LEAD
    Technical feedback

PM
    Project/delivery feedback

QA
    Quality feedback

DEVOPS
    Reliability/operations feedback

HR
    People/development feedback

CEO
    Executive feedback
```

Each feedback record should display:

- target employee;
- evaluator;
- evaluator role;
- evaluation period;
- submitted date;
- score/categories;
- comments;
- status.

Historical feedback should not be casually editable unless the backend supports controlled editing.

---

# 38. Reports Module

Reports:

```text
Sprint Velocity
Sprint Completion
Project Delivery
Developer Performance
Team Performance
Code Quality Trend
Risk Summary
QA Quality
CI/CD Health
Organization Performance
```

Role visibility:

### Developer

- own performance;
- own code quality;
- own sprint/task history.

### Lead

- team performance;
- team code quality;
- sprint performance;
- team risk.

### PM

- project delivery;
- sprint velocity;
- project risk;
- project performance.

### QA

- quality trends;
- bug trends;
- test results;
- regression.

### DevOps

- pipeline health;
- deployment success;
- incident trends;
- reliability.

### HR

- employee performance;
- team performance;
- organizational people metrics.

### CEO

- organization performance;
- project health;
- team performance;
- risk;
- quality;
- delivery.

---

# 39. Export

Support:

- CSV for tabular data;
- PDF for formal reports.

Prefer backend-generated reports when backend endpoints exist so calculations remain authoritative.

Frontend flow:

```text
Request report
 ↓
Backend generates
 ↓
Frontend receives file
 ↓
User downloads
```

---

# 40. Notifications

TopBar must show:

- unread count;
- notification list;
- read/unread state;
- timestamp;
- deep link.

Examples:

```text
PR approved
Task assigned
Sprint deadline approaching
Pipeline failed
Deployment completed
AI analysis completed
Feedback received
Risk increased
```

Notification click should open the related entity.

---

# 41. Real-time Strategy

## Initial implementation

Polling.

Use approximately 30-second polling only for appropriate live information:

- notifications;
- active AI analysis;
- pipeline status;
- deployment status.

Do not poll every API continuously.

## Future

Add WebSocket support for:

- notifications;
- PR state;
- pipeline completion;
- deployment events;
- AI analysis completion;
- task changes;
- comments;
- risk updates.

---

# 42. Global Search

Search entities:

```text
Employees
Teams
Projects
Sprints
Stories
Tasks
Repositories
Pull Requests
Risks
```

Search results must be permission-aware.

A developer must not discover restricted employee data through search.

---

# 43. Profile

All roles:

```text
Profile
Personal information
Role
Department
Team
Projects
GitHub account
Account information
Notification preferences
```

Editable fields depend on backend permissions.

---

# 44. Settings

Keep settings intentionally limited.

## Personal

- profile;
- notification preferences;
- display preferences;
- account/password controls supported by backend.

## Project

For authorized PMs:

- project configuration;
- members;
- repositories;
- project information.

## Organization

For authorized HR/CEO functionality:

- organizational information;
- teams;
- employees.

Do not expose backend infrastructure secrets or system-level configuration through the normal frontend.

---

# 45. Error Handling

Every API-driven page needs:

## Loading

```text
Loading project data...
```

## Empty

```text
No active projects found.
```

## Error

```text
Unable to load project data.
[Retry]
```

## Unauthorized

```text
You do not have permission to access this page.
```

## Session expiration

```text
Your session has expired.
Please log in again.
```

Errors should be human-readable and should not expose stack traces or secrets.

---

# 46. Accessibility

Target WCAG 2.1 AA-level practices.

Requirements:

- keyboard navigation;
- visible focus;
- semantic HTML;
- accessible labels;
- ARIA where required;
- accessible dialogs;
- correct focus management;
- form error association;
- non-color-only status indicators;
- sufficient contrast;
- keyboard-accessible drag/drop alternatives.

Example:

```text
HIGH
```

not merely a red-colored dot.

---

# 47. Responsive Design

Desktop is the primary experience.

Support:

- desktop;
- tablet;
- mobile.

Mobile priority:

```text
Dashboard
Tasks
Notifications
Performance
Critical Risks
```

Large analytics tables should become:

- scrollable;
- responsive cards;
- or condensed views.

---

# 48. UX Rules

1. Do not hide important errors.
2. Do not silently change data.
3. Confirm destructive actions.
4. Show save/loading state on mutations.
5. Disable duplicate submission while a mutation is running.
6. Show optimistic updates only where rollback is safe.
7. Keep filters and pagination consistent.
8. Preserve navigation context.
9. Deep-link notifications to their entities.
10. Never make AI output look like manually verified fact.
11. Show timestamps for AI/evaluation data.
12. Explain score/risk terminology through tooltips or help text.

---

# 49. Security Rules

Frontend must:

- never contain backend secrets;
- never contain Gemini/Ollama/API credentials;
- never assume hidden UI equals authorization;
- clear sensitive client state on logout;
- avoid exposing restricted data in global stores;
- handle 401/403 consistently;
- use HTTPS in production;
- use the configured backend API URL;
- avoid logging tokens or sensitive employee data.

---

# 50. API Architecture

Use:

```text
Page
 ↓
Custom Query/Mutation Hook
 ↓
API Service
 ↓
Axios Client
 ↓
FastAPI
```

Do not place raw Axios calls throughout page components.

Example concept:

```text
DeveloperDashboard
    ↓
useDeveloperPerformance()
    ↓
performanceApi.getDeveloperPerformance()
    ↓
apiClient
    ↓
FastAPI endpoint
```

---

# 51. TanStack Query Conventions

Use query keys consistently.

Examples:

```text
['current-user']

['projects']

['project', projectId]

['project', projectId, 'members']

['team', teamId]

['sprint', sprintId]

['tasks', filters]

['pull-request', prId]

['code-quality', repositoryId]

['code-quality-run', runId]

['performance', employeeId]

['notifications']
```

After mutations, invalidate the relevant queries.

---

# 52. State Separation

## Zustand

Use for:

- authentication client state if desired;
- UI preferences;
- sidebar;
- selected global filters;
- transient UI state.

## TanStack Query

Use for:

- employees;
- teams;
- projects;
- tasks;
- PRs;
- code quality;
- performance;
- feedback;
- reports;
- notifications.

---

# 53. Form Standards

Every create/edit form must have:

- schema validation;
- required field indication;
- inline errors;
- loading state;
- server error handling;
- successful submission feedback;
- cancel behavior;
- dirty-form handling where appropriate.

Forms:

```text
Login
Employee
Team
Project
Sprint
Story
Task
Bug
Feedback
```

---

# 54. Data Visualization Standards

Use Recharts consistently.

Charts should include:

- meaningful labels;
- legends where needed;
- tooltips;
- accessible text alternatives;
- appropriate time ranges;
- empty states;
- loading states.

Do not create decorative charts that don't support a decision.

---

# 55. Audit and Activity

Where backend activity/audit APIs are available, show:

```text
Who
What
When
Entity
```

Examples:

```text
HR added employee Alice
PM assigned John to Project A
Lead submitted technical feedback
AI evaluation completed
Risk changed from LOW to HIGH
```

---

# 56. Page Inventory

## Authentication

```text
/login
```

## Developer

```text
/developer/dashboard
/developer/tasks
/developer/board
/developer/projects
/developer/sprints
/developer/pull-requests
/developer/code-quality
/developer/performance
```

## Lead

```text
/lead/dashboard
/lead/team
/lead/performance
/lead/code-quality
/lead/feedback
```

## PM

```text
/pm/dashboard
/pm/projects
/pm/analytics
/pm/performance
/pm/feedback
```

## QA

```text
/qa/dashboard
/qa/tests
/qa/bugs
/qa/code-quality
/qa/feedback
```

## DevOps

```text
/devops/dashboard
/devops/pipelines
/devops/deployments
/devops/incidents
/devops/code-quality
/devops/feedback
```

## HR

```text
/hr/dashboard
/hr/employees
/hr/teams
/hr/performance
/hr/feedback
/hr/reports
```

## CEO

```text
/ceo/dashboard
/ceo/organization
/ceo/projects
/ceo/teams
/ceo/performance
/ceo/risk
/ceo/reports
```

## Shared domains

```text
/projects
/teams
/sprints
/stories
/tasks
/board
/code-quality
/evaluation
/feedback
/reports
/notifications
/profile
```

The actual final route ownership should follow the backend's available endpoints and authorization.

---

# 57. Implementation Order

Do not build all pages simultaneously.

## Phase 1 — Project foundation

Build:

- Vite project;
- React;
- dependencies;
- environment configuration;
- global CSS;
- routing foundation.

## Phase 2 — API layer

Build:

- Axios client;
- API service organization;
- error normalization;
- 401/403 handling.

## Phase 3 — Authentication

Build:

- login;
- authentication state;
- current-user loading;
- logout;
- protected routes;
- session handling.

## Phase 4 — RBAC

Build:

- role constants;
- permission constants;
- ProtectedRoute;
- RoleGuard;
- PermissionGuard;
- role-aware navigation.

## Phase 5 — Design system

Build reusable:

- buttons;
- forms;
- cards;
- tables;
- modals;
- badges;
- loading/error states;
- toast;
- confirmation dialogs.

## Phase 6 — Application shell

Build:

- Sidebar;
- TopBar;
- profile;
- notification UI;
- responsive layout.

## Phase 7 — Developer experience

Build first complete role:

- Developer dashboard;
- tasks;
- board;
- projects;
- sprints;
- PRs;
- code quality;
- performance.

This establishes the reusable patterns.

## Phase 8 — Lead

Build:

- team dashboard;
- team members;
- team performance;
- technical feedback;
- team code quality.

## Phase 9 — PM

Build:

- project management;
- project analytics;
- sprint/story/task management;
- PM feedback.

## Phase 10 — QA

Build:

- testing;
- bugs;
- quality dashboard;
- QA feedback.

## Phase 11 — DevOps

Build:

- pipelines;
- deployments;
- incidents;
- operational dashboard.

## Phase 12 — HR

Build:

- employee management;
- team management;
- people performance;
- HR feedback.

## Phase 13 — CEO

Build:

- executive dashboard;
- organization;
- organization performance;
- risk;
- executive reports.

## Phase 14 — Intelligence

Build:

- GitHub;
- PR analysis;
- code quality;
- findings;
- risk;
- AI analysis;
- evaluation.

## Phase 15 — Reports/notifications

Build:

- reports;
- exports;
- notification center;
- polling.

## Phase 16 — Quality

Finish:

- accessibility;
- responsive design;
- error handling;
- performance;
- security review;
- frontend tests;
- end-to-end testing.

---

# 58. Definition of Done

The frontend is not complete merely because pages render.

A feature is complete when:

- route works;
- backend API is connected;
- loading state exists;
- empty state exists;
- error state exists;
- permissions are handled;
- forms validate;
- mutations show feedback;
- unauthorized actions are blocked in UI;
- backend remains authoritative;
- responsive behavior works;
- accessibility is reasonable;
- data refreshes correctly;
- no secrets are exposed;
- tests exist for important behavior.

---

# 59. Final Product Flow

The complete user experience should be:

```text
LOGIN
  ↓
AUTHENTICATED USER
  ↓
ROLE + PERMISSIONS
  ↓
ROLE-SPECIFIC DASHBOARD
  ↓
WORK
  ├── Projects
  ├── Teams
  ├── Sprints
  ├── Stories
  ├── Tasks
  └── Kanban
  ↓
ENGINEERING DATA
  ├── GitHub
  ├── PRs
  ├── CI/CD
  └── Deployments
  ↓
INTELLIGENCE
  ├── Code Quality
  ├── Testing
  ├── Security
  ├── Architecture
  └── Risk
  ↓
AI
  ├── Analysis
  ├── Explanation
  └── Recommendations
  ↓
PERFORMANCE
  ├── AI Evaluation
  ├── Human Feedback
  ├── Trends
  └── Recommendations
  ↓
REPORTS + DECISIONS
```

---

# 60. Final Frontend Principle

The frontend should make each role's job obvious within seconds.

```text
DEVELOPER
"What should I work on and how am I improving?"

LEAD
"How is my team performing technically?"

PM
"Will my projects deliver?"

QA
"Is the software reliable?"

DEVOPS
"Can we safely deploy and operate?"

HR
"How are our people and teams performing?"

CEO
"How healthy is the organization?"
```

Samanvaya's frontend should connect those questions to a common evidence-driven platform without duplicating backend business logic.

---

## Final build target

```text
React/Vite
   ↓
Accessible UI
   ↓
Role-aware experience
   ↓
API services
   ↓
TanStack Query
   ↓
Existing FastAPI backend
   ↓
MongoDB + GitHub + intelligence + AI
```

This document is the implementation blueprint. Build incrementally, verify each frontend feature against the existing backend API contract, and do not invent frontend-only business rules where the backend already owns the logic.
