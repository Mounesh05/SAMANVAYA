"""
Seed script to populate initial users, teams, projects, sprints, stories, tasks,
companies, company settings, HR reports, HR performance metrics, and audit logs.
Run: ..\venv\Scripts\python seed_data.py
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone

backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from core.database import col
from core.security import hash_password

COMPANIES = [
    {
        "id": "ORG-001",
        "code": "SMV",
        "name": "Samanvaya Inc.",
        "domain": "samanvaya.io",
        "industry": "Enterprise AI & Developer Intelligence",
        "location": "Bengaluru HQ (Whitefield), Karnataka, India",
        "employee_count": 580,
        "project_count": 6,
        "status": "Active",
        "created_by": "Alexander Sterling (CEO)",
        "created_at": "Jan 10, 2025",
        "roles_configured": ["CEO", "HR", "PM", "LEAD", "DEVELOPER", "DEVOPS", "QA"],
        "description": "Flagship engineering execution governance and developer telemetry center."
    },
    {
        "id": "ORG-002",
        "code": "TNL",
        "name": "TechNova Labs",
        "domain": "technova.io",
        "industry": "Cloud Infrastructure & SRE",
        "location": "HITEC City, Hyderabad, Telangana, India",
        "employee_count": 380,
        "project_count": 4,
        "status": "Active",
        "created_by": "Alexander Sterling (CEO)",
        "created_at": "May 18, 2025",
        "roles_configured": ["CEO", "HR", "PM", "LEAD", "DEVELOPER", "DEVOPS"],
        "description": "High-throughput cloud systems, distributed databases and deployment platform division."
    },
    {
        "id": "ORG-003",
        "code": "AGD",
        "name": "Apex Global Dynamics",
        "domain": "apexgd.com",
        "industry": "FinTech & Banking Infrastructure",
        "location": "BKC, Bandra East, Mumbai, Maharashtra, India",
        "employee_count": 180,
        "project_count": 3,
        "status": "Active",
        "created_by": "Priya Sharma (HR)",
        "created_at": "Sep 04, 2025",
        "roles_configured": ["CEO", "HR", "PM", "DEVELOPER", "QA"],
        "description": "PCI-DSS compliant fintech transaction pipelines and banking microservices."
    },
    {
        "id": "ORG-004",
        "code": "VAL",
        "name": "Valence Autonomous Systems",
        "domain": "valence.io",
        "industry": "Autonomous Robotics & AI Control",
        "location": "Bengaluru HQ (Whitefield), Karnataka, India",
        "employee_count": 240,
        "project_count": 3,
        "status": "Active",
        "created_by": "SuperAdmin (Platform Administrator)",
        "created_at": "Nov 02, 2026",
        "assigned_ceo": {
            "employee_id": "EMP-CEO-VAL-001",
            "name": "Dr. Vikram Malhotra",
            "email": "ceo@valence.io",
            "phone": "+91 98450 11223"
        },
        "assigned_hr": {
            "employee_id": "EMP-HR-VAL-001",
            "name": "Ananya Sen",
            "email": "hr@valence.io",
            "phone": "+91 98450 44556"
        },
        "roles_configured": ["CEO", "HR", "PM", "LEAD", "DEVELOPER", "DEVOPS", "QA"],
        "description": "Autonomous drone navigation, robotics intelligence, and industrial IoT platform."
    }
]

TEAMS = [
    {
        "team_id": "team-01",
        "name": "Core Engineering Squad",
        "dept": "Engineering",
        "org_id": "ORG-001",
        "company_id": "ORG-001",
        "description": "Primary product execution, backend APIs, and developer intelligence platform",
        "team_lead_id": "EMP-002",
        "team_lead_name": "Marcus Vance",
        "project_ids": ["PRJ-01", "PRJ-02"],
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "team_id": "team-02",
        "name": "Platform & Infrastructure",
        "dept": "Infrastructure & SRE",
        "org_id": "ORG-001",
        "company_id": "ORG-001",
        "description": "Cloud infra, CI/CD pipelines, container clusters and SRE observability",
        "team_lead_id": "EMP-005",
        "team_lead_name": "Jordan Hayes",
        "project_ids": ["PRJ-01"],
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "team_id": "team-03",
        "name": "Quality & Verification",
        "dept": "Quality Assurance",
        "org_id": "ORG-001",
        "company_id": "ORG-001",
        "description": "Automated regression testing, release sign-offs, and compliance verification",
        "team_lead_id": "EMP-004",
        "team_lead_name": "Elena Rostova",
        "project_ids": ["PRJ-01", "PRJ-02", "PRJ-03"],
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "team_id": "team-04",
        "name": "FinTech Payment Squad",
        "dept": "Engineering",
        "org_id": "ORG-001",
        "company_id": "ORG-001",
        "description": "Secure payment gateways, ledger synchronization, and checkout pipelines",
        "team_lead_id": "EMP-001",
        "team_lead_name": "Sarah Connor",
        "project_ids": ["PRJ-02"],
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "team_id": "team-05",
        "name": "Mobile Client Experience",
        "dept": "Mobile",
        "org_id": "ORG-002",
        "company_id": "ORG-002",
        "description": "Cross-platform iOS and Android developer analytics application",
        "team_lead_id": "EMP-002",
        "team_lead_name": "Marcus Vance",
        "project_ids": ["PRJ-03"],
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
]

ROLES_USERS = [
    {
        "employee_id": "EMP-001",
        "name": "Sarah Connor",
        "email": "dev@samanvaya.io",
        "role": "DEVELOPER",
        "dept": "Engineering",
        "github_username": "sarah-connor",
        "team_id": "team-01",
        "team_name": "Core Engineering Squad",
        "org_id": "ORG-001",
        "company_id": "ORG-001",
        "perfScore": 89.2,
        "behaviour": 8.5,
        "risk": "Low",
        "sprintContrib": "24 SP",
        "projects": ["Samanvaya AI Platform", "FinTech Payment Gateway v2"],
        "status": "Active",
        "is_active": True,
        "avatar": "SC",
    },
    {
        "employee_id": "EMP-002",
        "name": "Marcus Vance",
        "email": "lead@samanvaya.io",
        "role": "LEAD",
        "dept": "Engineering",
        "github_username": "marcus-vance",
        "team_id": "team-01",
        "team_name": "Core Engineering Squad",
        "org_id": "ORG-001",
        "company_id": "ORG-001",
        "perfScore": 94.0,
        "behaviour": 9.2,
        "risk": "Low",
        "sprintContrib": "28 SP",
        "projects": ["Samanvaya AI Platform"],
        "status": "Active",
        "is_active": True,
        "avatar": "MV",
    },
    {
        "employee_id": "EMP-003",
        "name": "Rachel Zane",
        "email": "pm@samanvaya.io",
        "role": "PM",
        "dept": "Product",
        "github_username": "rachel-pm",
        "team_id": "team-01",
        "team_name": "Core Engineering Squad",
        "org_id": "ORG-001",
        "company_id": "ORG-001",
        "perfScore": 91.5,
        "behaviour": 9.0,
        "risk": "Low",
        "sprintContrib": "30 SP",
        "projects": ["Samanvaya AI Platform", "FinTech Payment Gateway v2"],
        "status": "Active",
        "is_active": True,
        "avatar": "RZ",
    },
    {
        "employee_id": "EMP-004",
        "name": "Elena Rostova",
        "email": "qa@samanvaya.io",
        "role": "QA",
        "dept": "Quality Assurance",
        "github_username": "elena-qa",
        "team_id": "team-03",
        "team_name": "Quality & Verification",
        "org_id": "ORG-001",
        "company_id": "ORG-001",
        "perfScore": 88.0,
        "behaviour": 8.8,
        "risk": "Low",
        "sprintContrib": "20 SP",
        "projects": ["Samanvaya AI Platform", "Mobile Client Suite"],
        "status": "Active",
        "is_active": True,
        "avatar": "ER",
    },
    {
        "employee_id": "EMP-005",
        "name": "Jordan Hayes",
        "email": "devops@samanvaya.io",
        "role": "DEVOPS",
        "dept": "Infrastructure & SRE",
        "github_username": "jordan-ops",
        "team_id": "team-02",
        "team_name": "Platform & Infrastructure",
        "org_id": "ORG-001",
        "company_id": "ORG-001",
        "perfScore": 89.8,
        "behaviour": 8.7,
        "risk": "Low",
        "sprintContrib": "22 SP",
        "projects": ["Samanvaya AI Platform"],
        "status": "Active",
        "is_active": True,
        "avatar": "JH",
    },
    {
        "employee_id": "EMP-006",
        "name": "Priya Sharma",
        "email": "hr@samanvaya.io",
        "role": "HR",
        "dept": "Human Resources",
        "github_username": "priya-hr",
        "team_id": "team-01",
        "team_name": "Core Engineering Squad",
        "org_id": "ORG-001",
        "company_id": "ORG-001",
        "perfScore": 95.0,
        "behaviour": 9.6,
        "risk": "Low",
        "sprintContrib": "18 SP",
        "projects": ["People Operations", "Talent Growth"],
        "status": "Active",
        "is_active": True,
        "avatar": "PS",
    },
    {
        "employee_id": "EMP-007",
        "name": "Alexander Sterling",
        "email": "ceo@samanvaya.io",
        "role": "CEO",
        "dept": "Executive",
        "github_username": "alex-ceo",
        "team_id": "team-01",
        "team_name": "Core Engineering Squad",
        "org_id": "ORG-001",
        "company_id": "ORG-001",
        "perfScore": 98.0,
        "behaviour": 9.9,
        "risk": "Low",
        "sprintContrib": "35 SP",
        "projects": ["Samanvaya AI Platform", "FinTech Payment Gateway v2"],
        "status": "Active",
        "is_active": True,
        "avatar": "AS",
    },
    {
        "employee_id": "EMP-008",
        "name": "Vikram Singh",
        "email": "vikram.singh@samanvaya.io",
        "role": "DEVELOPER",
        "dept": "Engineering",
        "github_username": "vikram-dev",
        "team_id": "team-01",
        "team_name": "Core Engineering Squad",
        "org_id": "ORG-001",
        "company_id": "ORG-001",
        "perfScore": 96.0,
        "behaviour": 9.4,
        "risk": "Low",
        "sprintContrib": "26 SP",
        "projects": ["Samanvaya AI Platform"],
        "status": "Active",
        "is_active": True,
        "avatar": "VS",
    },
    {
        "employee_id": "EMP-009",
        "name": "Sneha Iyer",
        "email": "sneha.iyer@samanvaya.io",
        "role": "LEAD",
        "dept": "Engineering",
        "github_username": "sneha-sm",
        "team_id": "team-01",
        "team_name": "Core Engineering Squad",
        "org_id": "ORG-001",
        "company_id": "ORG-001",
        "perfScore": 94.0,
        "behaviour": 9.1,
        "risk": "Low",
        "sprintContrib": "24 SP",
        "projects": ["Samanvaya AI Platform"],
        "status": "Active",
        "is_active": True,
        "avatar": "SI",
    },
    {
        "employee_id": "EMP-010",
        "name": "Ananya Reddy",
        "email": "ananya.reddy@samanvaya.io",
        "role": "DEVOPS",
        "dept": "Infrastructure & SRE",
        "github_username": "ananya-ops",
        "team_id": "team-02",
        "team_name": "Platform & Infrastructure",
        "org_id": "ORG-001",
        "company_id": "ORG-001",
        "perfScore": 76.5,
        "behaviour": 7.8,
        "risk": "High",
        "sprintContrib": "21 SP",
        "projects": ["Platform Observability"],
        "status": "Active",
        "is_active": True,
        "avatar": "AR",
    },
    {
        "employee_id": "EMP-011",
        "name": "David Kim",
        "email": "david.kim@samanvaya.io",
        "role": "DEVELOPER",
        "dept": "Engineering",
        "github_username": "david-kim",
        "team_id": "team-04",
        "team_name": "FinTech Payment Squad",
        "org_id": "ORG-001",
        "company_id": "ORG-001",
        "perfScore": 62.0,
        "behaviour": 6.8,
        "risk": "High",
        "sprintContrib": "12 SP",
        "projects": ["FinTech Payment Gateway v2"],
        "status": "Probation",
        "is_active": True,
        "avatar": "DK",
    },
    {
        "employee_id": "EMP-012",
        "name": "Anita Patel",
        "email": "anita.patel@samanvaya.io",
        "role": "QA",
        "dept": "Quality Assurance",
        "github_username": "anita-qa",
        "team_id": "team-03",
        "team_name": "Quality & Verification",
        "org_id": "ORG-001",
        "company_id": "ORG-001",
        "perfScore": 68.0,
        "behaviour": 7.2,
        "risk": "High",
        "sprintContrib": "14 SP",
        "projects": ["Quality Automation"],
        "status": "Active",
        "is_active": True,
        "avatar": "AP",
    },
    # Dedicated demo role credentials
    {
        "employee_id": "EMP-CEO-001",
        "name": "Alexander Sterling",
        "email": "ceo@samanvaya.io",
        "role": "CEO",
        "dept": "Executive",
        "github_username": "ceo-admin",
        "team_id": "team-01",
        "team_name": "Core Engineering Squad",
        "org_id": "ORG-001",
        "company_id": "ORG-001",
        "perfScore": 98.0,
        "behaviour": 9.9,
        "risk": "Low",
        "sprintContrib": "35 SP",
        "projects": ["Samanvaya AI Platform"],
        "status": "Active",
        "is_active": True,
        "avatar": "AS",
    },
    {
        "employee_id": "EMP-HR-001",
        "name": "Priya Sharma",
        "email": "hr@samanvaya.io",
        "role": "HR",
        "dept": "Human Resources",
        "github_username": "hr-admin",
        "team_id": "team-01",
        "team_name": "Core Engineering Squad",
        "org_id": "ORG-001",
        "company_id": "ORG-001",
        "perfScore": 95.0,
        "behaviour": 9.6,
        "risk": "Low",
        "sprintContrib": "18 SP",
        "projects": ["People Operations"],
        "status": "Active",
        "is_active": True,
        "avatar": "PS",
    },
    {
        "employee_id": "EMP-PM-001",
        "name": "Rachel Zane",
        "email": "pm@samanvaya.io",
        "role": "PM",
        "dept": "Product",
        "github_username": "pm-admin",
        "team_id": "team-01",
        "team_name": "Core Engineering Squad",
        "org_id": "ORG-001",
        "company_id": "ORG-001",
        "perfScore": 91.5,
        "behaviour": 9.0,
        "risk": "Low",
        "sprintContrib": "30 SP",
        "projects": ["Samanvaya AI Platform"],
        "status": "Active",
        "is_active": True,
        "avatar": "RZ",
    },
    {
        "employee_id": "EMP-LEAD-001",
        "name": "Marcus Vance",
        "email": "lead@samanvaya.io",
        "role": "LEAD",
        "dept": "Engineering",
        "github_username": "lead-admin",
        "team_id": "team-01",
        "team_name": "Core Engineering Squad",
        "org_id": "ORG-001",
        "company_id": "ORG-001",
        "perfScore": 94.0,
        "behaviour": 9.2,
        "risk": "Low",
        "sprintContrib": "28 SP",
        "projects": ["Samanvaya AI Platform"],
        "status": "Active",
        "is_active": True,
        "avatar": "MV",
    },
    {
        "employee_id": "EMP-DEV-001",
        "name": "Sarah Connor",
        "email": "dev@samanvaya.io",
        "role": "DEVELOPER",
        "dept": "Engineering",
        "github_username": "dev-admin",
        "team_id": "team-01",
        "team_name": "Core Engineering Squad",
        "org_id": "ORG-001",
        "company_id": "ORG-001",
        "perfScore": 89.2,
        "behaviour": 8.5,
        "risk": "Low",
        "sprintContrib": "24 SP",
        "projects": ["Samanvaya AI Platform"],
        "status": "Active",
        "is_active": True,
        "avatar": "SC",
    },
    {
        "employee_id": "EMP-OPS-001",
        "name": "Jordan Hayes",
        "email": "ops@samanvaya.io",
        "role": "DEVOPS",
        "dept": "Infrastructure & SRE",
        "github_username": "ops-admin",
        "team_id": "team-02",
        "team_name": "Platform & Infrastructure",
        "org_id": "ORG-001",
        "company_id": "ORG-001",
        "perfScore": 89.8,
        "behaviour": 8.7,
        "risk": "Low",
        "sprintContrib": "22 SP",
        "projects": ["Samanvaya AI Platform"],
        "status": "Active",
        "is_active": True,
        "avatar": "JH",
    },
    {
        "employee_id": "EMP-QA-001",
        "name": "Elena Rostova",
        "email": "qa@samanvaya.io",
        "role": "QA",
        "dept": "Quality Assurance",
        "github_username": "qa-admin",
        "team_id": "team-03",
        "team_name": "Quality & Verification",
        "org_id": "ORG-001",
        "company_id": "ORG-001",
        "perfScore": 88.0,
        "behaviour": 8.8,
        "risk": "Low",
        "sprintContrib": "20 SP",
        "projects": ["Samanvaya AI Platform"],
        "status": "Active",
        "is_active": True,
        "avatar": "ER",
    },
    {
        "employee_id": "EMP-CEO-VAL-001",
        "name": "Dr. Vikram Malhotra",
        "email": "ceo@valence.io",
        "role": "CEO",
        "dept": "Executive",
        "github_username": "vikram-ceo",
        "team_id": "team-01",
        "team_name": "Executive Leadership",
        "org_id": "ORG-004",
        "company_id": "ORG-004",
        "company_name": "Valence Autonomous Systems",
        "perfScore": 98.5,
        "behaviour": 9.8,
        "risk": "Low",
        "sprintContrib": "35 SP",
        "projects": ["Autonomous Fleet Control"],
        "status": "Active",
        "is_active": True,
        "is_admin": True,
        "avatar": "VM",
    },
    {
        "employee_id": "EMP-HR-VAL-001",
        "name": "Ananya Sen",
        "email": "hr@valence.io",
        "role": "HR",
        "dept": "Human Resources",
        "github_username": "ananya-hr",
        "team_id": "team-01",
        "team_name": "People Operations",
        "org_id": "ORG-004",
        "company_id": "ORG-004",
        "company_name": "Valence Autonomous Systems",
        "perfScore": 95.5,
        "behaviour": 9.7,
        "risk": "Low",
        "sprintContrib": "20 SP",
        "projects": ["Robotics Talent Acquisition"],
        "status": "Active",
        "is_active": True,
        "is_admin": False,
        "avatar": "AS",
    },
]

PROJECTS = [
    {
        "id": "PRJ-01",
        "name": "Samanvaya AI Platform",
        "key": "SMV",
        "description": "AI-powered software project execution and engineering intelligence platform with real-time velocity tracking.",
        "client": "Samanvaya Internal",
        "org_id": "ORG-001",
        "company_id": "ORG-001",
        "company_name": "Samanvaya Inc.",
        "sprint": "Sprint 24 - Core Intelligence",
        "assignedPM": "Rachel Zane",
        "team_ids": ["team-01", "team-02", "team-03"],
        "team_names": ["Core Engineering Squad", "Platform & Infrastructure", "Quality & Verification"],
        "members": 14,
        "createdDate": "Jan 15, 2026",
        "status": "Active",
        "created_by": "Alexander Sterling (CEO)",
        "updated_by": "Alexander Sterling (CEO)",
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "id": "PRJ-02",
        "name": "FinTech Payment Gateway v2",
        "key": "PAY",
        "description": "High-throughput compliant payment processing infrastructure with automated fraud mitigation.",
        "client": "Apex Banking Corp",
        "org_id": "ORG-001",
        "company_id": "ORG-001",
        "company_name": "Samanvaya Inc.",
        "sprint": "Sprint 18",
        "assignedPM": "Rachel Zane",
        "team_ids": ["team-01", "team-04"],
        "team_names": ["Core Engineering Squad", "FinTech Payment Squad"],
        "members": 8,
        "createdDate": "Feb 01, 2026",
        "status": "Active",
        "created_by": "Priya Sharma (HR)",
        "updated_by": "Rachel Zane (PM)",
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "id": "PRJ-03",
        "name": "Mobile Client Suite",
        "key": "MOB",
        "description": "Cross-platform iOS and Android developer analytics application with offline sync.",
        "client": "TechNova Labs",
        "org_id": "ORG-002",
        "company_id": "ORG-002",
        "company_name": "TechNova Labs",
        "sprint": "Sprint 12",
        "assignedPM": "Rachel Zane",
        "team_ids": ["team-01", "team-05"],
        "team_names": ["Core Engineering Squad", "Mobile Client Experience"],
        "members": 6,
        "createdDate": "Jan 28, 2026",
        "status": "On Hold",
        "created_by": "Alexander Sterling (CEO)",
        "updated_by": "Rachel Zane (PM)",
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "id": "PRJ-04",
        "name": "Distributed Telemetry Collector",
        "key": "TEL",
        "description": "Ultra low-latency event ingestion engine collecting Git commits and build execution telemetry.",
        "client": "TechNova Labs",
        "org_id": "ORG-002",
        "company_id": "ORG-002",
        "company_name": "TechNova Labs",
        "sprint": "Sprint 08",
        "assignedPM": "Marcus Vance",
        "team_ids": ["team-02"],
        "team_names": ["Platform & Infrastructure"],
        "members": 5,
        "createdDate": "Feb 10, 2026",
        "status": "Active",
        "created_by": "Jordan Hayes (DEVOPS)",
        "updated_by": "Marcus Vance (LEAD)",
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "id": "PRJ-05",
        "name": "Banking Core Microservices",
        "key": "BCM",
        "description": "High-availability financial transaction processing pipeline with ISO 20022 compliance.",
        "client": "Apex Global Dynamics",
        "org_id": "ORG-003",
        "company_id": "ORG-003",
        "company_name": "Apex Global Dynamics",
        "sprint": "Sprint 09",
        "assignedPM": "Marcus Vance",
        "team_ids": ["team-01", "team-04"],
        "team_names": ["Core Engineering Squad", "FinTech Payment Squad"],
        "members": 7,
        "createdDate": "Feb 15, 2026",
        "status": "Active",
        "created_by": "Priya Sharma (HR)",
        "updated_by": "Alexander Sterling (CEO)",
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "id": "PRJ-06",
        "name": "Fraud Detection Neural Engine",
        "key": "FNE",
        "description": "Real-time AI risk evaluation and anomaly detection pipeline for multi-currency transactions.",
        "client": "Apex Global Dynamics",
        "org_id": "ORG-003",
        "company_id": "ORG-003",
        "company_name": "Apex Global Dynamics",
        "sprint": "Sprint 05",
        "assignedPM": "Rachel Zane",
        "team_ids": ["team-01", "team-02"],
        "team_names": ["Core Engineering Squad", "Platform & Infrastructure"],
        "members": 5,
        "createdDate": "Mar 01, 2026",
        "status": "Active",
        "created_by": "Alexander Sterling (CEO)",
        "updated_by": "Alexander Sterling (CEO)",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
]

SPRINTS = [
    {
        "id": "SPR-01",
        "name": "Sprint 24 - Core Intelligence",
        "project_id": "PRJ-01",
        "goal": "Launch real-time intelligence engine and role dashboards",
        "start_date": "2026-09-15",
        "end_date": "2026-09-30",
        "status": "active",
        "completion_pct": 78.5,
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "id": "SPR-02",
        "name": "Sprint 25 - Production Scale",
        "project_id": "PRJ-01",
        "goal": "Infrastructure auto-tuning and real-time WebSocket telemetry",
        "start_date": "2026-10-01",
        "end_date": "2026-10-15",
        "status": "planning",
        "completion_pct": 0.0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
]

STORIES = [
    {
        "id": "STY-01",
        "title": "Build real-time team alignment analytics",
        "description": "Calculate story point completion and blocker distribution across engineering",
        "sprint_id": "SPR-01",
        "project_id": "PRJ-01",
        "assignee_id": "EMP-001",
        "assignee": "Sarah Connor",
        "type": "Dev",
        "points": 8,
        "alignment": 92,
        "priority": "high",
        "status": "in_progress",
        "risk": "Low",
        "reviewStatus": "Pending",
        "dueDate": "2026-09-30",
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "id": "STY-02",
        "title": "Automate CI/CD test failure classification",
        "description": "Classify build failure logs using local LLM inference",
        "sprint_id": "SPR-01",
        "project_id": "PRJ-01",
        "assignee_id": "EMP-005",
        "assignee": "Jordan Hayes",
        "type": "DevOps",
        "points": 5,
        "alignment": 88,
        "priority": "medium",
        "status": "review",
        "risk": "Low",
        "reviewStatus": "In Review",
        "dueDate": "2026-10-02",
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "id": "STY-03",
        "title": "Design CEO executive summary dashboard",
        "description": "Comprehensive portfolio health, critical risks, and delivery confidence views",
        "sprint_id": "SPR-01",
        "project_id": "PRJ-01",
        "assignee_id": "EMP-002",
        "assignee": "Marcus Vance",
        "type": "Dev",
        "points": 5,
        "alignment": 94,
        "priority": "high",
        "status": "done",
        "risk": "Low",
        "reviewStatus": "Approved",
        "dueDate": "2026-09-28",
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "id": "ST-201",
        "title": "Implement OAuth2 Login Flow",
        "description": "Implement OAuth2 Login Flow with PKCE support and refresh tokens",
        "assignee": "Vikram Singh",
        "assignee_id": "EMP-001",
        "project_id": "PRJ-01",
        "sprint_id": "SPR-01",
        "type": "Dev",
        "points": 8,
        "alignment": 94,
        "risk": "Low",
        "reviewStatus": "Approved",
        "dueDate": "Feb 28",
        "status": "Done",
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "id": "ST-202",
        "title": "Write Unit Tests for Payments",
        "description": "Comprehensive unit and integration test coverage for payment gateways",
        "assignee": "Anita Patel",
        "assignee_id": "EMP-004",
        "project_id": "PRJ-01",
        "sprint_id": "SPR-01",
        "type": "QA",
        "points": 5,
        "alignment": 78,
        "risk": "Medium",
        "reviewStatus": "In Review",
        "dueDate": "Mar 02",
        "status": "In Progress",
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "id": "ST-203",
        "title": "Refactor Notification Webhook Service",
        "description": "Refactor webhook delivery pipeline with exponential backoff and jitter",
        "assignee": "Vikram Singh",
        "assignee_id": "EMP-001",
        "project_id": "PRJ-01",
        "sprint_id": "SPR-01",
        "type": "Dev",
        "points": 5,
        "alignment": 88,
        "risk": "Low",
        "reviewStatus": "Approved",
        "dueDate": "Mar 03",
        "status": "In Review",
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "id": "ST-204",
        "title": "Fix Pagination on Dashboard",
        "description": "Fix infinite scroll pagination and cursor serialization in frontend table",
        "assignee": "Sneha Iyer",
        "assignee_id": "EMP-002",
        "project_id": "PRJ-01",
        "sprint_id": "SPR-01",
        "type": "Dev",
        "points": 3,
        "alignment": 96,
        "risk": "Low",
        "reviewStatus": "Approved",
        "dueDate": "Feb 27",
        "status": "Done",
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "id": "ST-205",
        "title": "API Rate Limiting Middleware",
        "description": "Implement token-bucket rate limiting middleware for FastAPI backend",
        "assignee": "Ananya Reddy",
        "assignee_id": "EMP-005",
        "project_id": "PRJ-01",
        "sprint_id": "SPR-01",
        "type": "DevOps",
        "points": 5,
        "alignment": 68,
        "risk": "High",
        "reviewStatus": "Pending",
        "dueDate": "Mar 05",
        "status": "To Do",
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "id": "ST-206",
        "title": "Database Migration Script",
        "description": "Automated MongoDB collection indexes and schema migrations for v2.0",
        "assignee": "Ananya Reddy",
        "assignee_id": "EMP-005",
        "project_id": "PRJ-01",
        "sprint_id": "SPR-01",
        "type": "DevOps",
        "points": 8,
        "alignment": 62,
        "risk": "High",
        "reviewStatus": "Pending",
        "dueDate": "Mar 04",
        "status": "Blocked",
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
]

TASKS = [
    {
        "id": "TSK-01",
        "title": "Implement JWT authorization header in frontend client",
        "project_id": "PRJ-01",
        "assignee_id": "EMP-001",
        "story_id": "STY-01",
        "sprint_id": "SPR-01",
        "type": "feature",
        "priority": "high",
        "status": "done",
        "due_date": "2026-09-28",
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "id": "TSK-02",
        "title": "Optimize MongoDB collection indexes for dashboard queries",
        "project_id": "PRJ-01",
        "assignee_id": "EMP-001",
        "story_id": "STY-01",
        "sprint_id": "SPR-01",
        "type": "task",
        "priority": "medium",
        "status": "in_progress",
        "due_date": "2026-09-30",
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "id": "TSK-03",
        "title": "Setup webhook event handler for GitHub PR actions",
        "project_id": "PRJ-01",
        "assignee_id": "EMP-001",
        "story_id": "STY-02",
        "sprint_id": "SPR-01",
        "type": "feature",
        "priority": "high",
        "status": "todo",
        "due_date": "2026-10-02",
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
    {
        "id": "TSK-04",
        "title": "Execute automated regression test suite for release v2.0",
        "project_id": "PRJ-01",
        "assignee_id": "EMP-004",
        "story_id": "STY-03",
        "sprint_id": "SPR-01",
        "type": "test",
        "priority": "medium",
        "status": "review",
        "due_date": "2026-09-29",
        "created_at": datetime.now(timezone.utc).isoformat(),
    },
]

AUDIT_LOGS = [
    {
        "id": "audit-1",
        "action": "Promotion Approved",
        "name": "Vikram Singh",
        "by": "Alexander Sterling (CEO)",
        "role": "CEO",
        "time": "Feb 15, 2026 10:30 AM",
        "details": "Promoted to Senior Full-Stack Engineer based on 96% performance and 9.4 behaviour rating"
    },
    {
        "id": "audit-2",
        "action": "Sent to Review",
        "name": "Elena Rostova",
        "by": "Priya Sharma (HR)",
        "role": "HR",
        "time": "Feb 12, 2026 03:15 PM",
        "details": "Performance evaluation cycle initiated for Q1"
    },
    {
        "id": "audit-3",
        "action": "Team Transfer",
        "name": "Ananya Reddy",
        "by": "Priya Sharma (HR)",
        "role": "HR",
        "fromTeam": "Core Engineering Squad",
        "toTeam": "Platform & Infrastructure",
        "time": "Feb 10, 2026 11:45 AM",
        "details": "Transferred for SRE reliability focus"
    },
    {
        "id": "audit-4",
        "action": "Project Created",
        "name": "Samanvaya AI Platform",
        "by": "Alexander Sterling (CEO)",
        "role": "CEO",
        "time": "Jan 15, 2026 09:00 AM",
        "details": "Initial platform initialization"
    },
    {
        "id": "audit-5",
        "action": "Company Added",
        "name": "TechNova Labs",
        "by": "Alexander Sterling (CEO)",
        "role": "CEO",
        "time": "Jan 10, 2025 10:00 AM",
        "details": "Added subsidiary organization to multi-tenant directory"
    }
]

COMPANY_SETTINGS = {
    "company_id": "ORG-001",
    "company": {
        "name": "Samanvaya Inc.",
        "domain": "samanvaya.io",
        "industry": "Enterprise AI / DevTools",
        "location": "Bengaluru HQ (Whitefield), Karnataka, India"
    },
    "weights": {
        "sprint": 35,
        "alignment": 25,
        "delivery": 25,
        "behaviour": 15
    },
    "sprintPolicy": {
        "duration": 14,
        "maxSP": 55,
        "approvalSLA": 24
    },
    "behaviourAssign": ["CEO", "HR", "LEAD", "PM"],
    "promotionWeightEdit": ["CEO", "HR"]
}

HR_REPORTS = [
    {
        "id": "REP-01",
        "title": "Monthly Performance Distribution",
        "desc": "Breakdown of developer velocity, sprint goal completion, and bug escape rates across teams.",
        "lastGenerated": "Yesterday at 6:00 PM",
        "icon": "BarChart3",
        "color": "#3b82f6"
    },
    {
        "id": "REP-02",
        "title": "Promotion Eligibility Ledger",
        "desc": "Engineers scoring above 85% with high behavior ratings eligible for role progression.",
        "lastGenerated": "Feb 15, 2026",
        "icon": "Award",
        "color": "#10b981"
    },
    {
        "id": "REP-03",
        "title": "Retention & Burnout Risk Analysis",
        "desc": "Predictive signals identifying high-workload individuals and sustained overtime trends.",
        "lastGenerated": "Feb 10, 2026",
        "icon": "AlertTriangle",
        "color": "#ef4444"
    },
    {
        "id": "REP-04",
        "title": "Talent Acquisition & Candidate Pipeline",
        "desc": "Active candidate interview stages, technical score distribution, and hiring timeline.",
        "lastGenerated": "Today at 9:30 AM",
        "icon": "UserPlus",
        "color": "#8b5cf6"
    },
    {
        "id": "REP-05",
        "title": "Organizational Alignment & Culture",
        "desc": "Company core value alignment and quarterly peer feedback assessment.",
        "lastGenerated": "Feb 01, 2026",
        "icon": "Star",
        "color": "#f59e0b"
    },
]

CEO_REPORTS = [
    {
        "id": "CEO-REP-01",
        "title": "Executive Board Intelligence Briefing",
        "desc": "Comprehensive synthesis of sprint delivery velocity, cross-team blockers, and quarterly AI feature milestones.",
        "icon": "Activity",
        "color": "#3b82f6",
        "lastGenerated": "Today at 9:00 AM",
        "role": "CEO"
    },
    {
        "id": "CEO-REP-02",
        "title": "Engineering Velocity & Output Audit",
        "desc": "Comparative telemetry of PR merge times, review latency, and story point throughput across all 5 engineering squads.",
        "icon": "BarChart3",
        "color": "#10b981",
        "lastGenerated": "Yesterday at 6:30 PM",
        "role": "CEO"
    },
    {
        "id": "CEO-REP-03",
        "title": "Organizational Risk & Burnout Matrix",
        "desc": "Predictive behavioral signals and workload density alerts pinpointing teams at risk of delivery delays.",
        "icon": "Shield",
        "color": "#ef4444",
        "lastGenerated": "Feb 18, 2026",
        "role": "CEO"
    },
    {
        "id": "CEO-REP-04",
        "title": "Cross-Company Tenant Capacity Overview",
        "desc": "Headcount distribution, department allocations, and active project staffing across Samanvaya, TechNova, and Apex.",
        "icon": "Users",
        "color": "#8b5cf6",
        "lastGenerated": "Feb 15, 2026",
        "role": "CEO"
    },
    {
        "id": "CEO-REP-05",
        "title": "AI Advisory & Retrospective Synthesis",
        "desc": "Automated analysis of sprint retrospectives, quality benchmarks, and process bottleneck mitigations.",
        "icon": "MessageSquare",
        "color": "#f59e0b",
        "lastGenerated": "Feb 10, 2026",
        "role": "CEO"
    }
]


HR_PERFORMANCE_METRICS = {
    "departments": [
        {"dept": "Engineering", "score": 88.5},
        {"dept": "Product", "score": 92.0},
        {"dept": "Quality Assurance", "score": 85.2},
        {"dept": "Infrastructure & SRE", "score": 89.8},
        {"dept": "Human Resources", "score": 94.1},
    ],
    "velocity": [
        {"sprint": "Sprint 21", "planned": 45, "completed": 42},
        {"sprint": "Sprint 22", "planned": 50, "completed": 48},
        {"sprint": "Sprint 23", "planned": 52, "completed": 49},
        {"sprint": "Sprint 24", "planned": 55, "completed": 52},
    ],
    "top_performers": [
        {"name": "Vikram Singh", "role": "DEVELOPER", "score": 96},
        {"name": "Sneha Iyer", "role": "LEAD", "score": 94},
        {"name": "Marcus Vance", "role": "LEAD", "score": 93},
        {"name": "Elena Rostova", "role": "QA", "score": 91},
        {"name": "Sarah Connor", "role": "DEVELOPER", "score": 90},
    ],
    "low_performers": [
        {"name": "David Kim", "role": "DEVELOPER", "score": 62, "issue": "PR review bottlenecks and missed sprint deliverable milestones"},
        {"name": "Anita Patel", "role": "QA", "score": 68, "issue": "Regression automation flakiness and delayed story sign-offs"},
        {"name": "Karthik Raja", "role": "DEVELOPER", "score": 71, "issue": "Defect leakage in checkout integration service"},
    ]
}

CANDIDATES = [
    # ORG-001 (Samanvaya Inc.)
    {"id": "CND-01", "name": "Aarav Sharma", "email": "aarav.sharma@example.com", "role": "Developer", "dept": "Engineering", "project": "Samanvaya AI Platform", "status": "Interview", "experience": "6 yrs", "score": 92, "appliedDate": "Sep 15, 2026", "applied_date": "2026-09-15", "org_id": "ORG-001", "company_id": "ORG-001", "company_name": "Samanvaya Inc."},
    {"id": "CND-02", "name": "Meera Nair", "email": "meera.nair@example.com", "role": "DevOps Engineer", "dept": "Operations", "project": "Platform Observability", "status": "Screening", "experience": "4 yrs", "score": 88, "appliedDate": "Sep 18, 2026", "applied_date": "2026-09-18", "org_id": "ORG-001", "company_id": "ORG-001", "company_name": "Samanvaya Inc."},
    {"id": "CND-03", "name": "Rohan Deshmukh", "email": "rohan.deshmukh@example.com", "role": "Developer", "dept": "Engineering", "project": "Samanvaya AI Platform", "status": "Hired", "experience": "5 yrs", "score": 95, "appliedDate": "Sep 10, 2026", "applied_date": "2026-09-10", "org_id": "ORG-001", "company_id": "ORG-001", "company_name": "Samanvaya Inc."},
    {"id": "CND-04", "name": "Kavya Patel", "email": "kavya.patel@example.com", "role": "QA Engineer", "dept": "Quality", "project": "Samanvaya AI Platform", "status": "Offer Sent", "experience": "3 yrs", "score": 90, "appliedDate": "Sep 22, 2026", "applied_date": "2026-09-22", "org_id": "ORG-001", "company_id": "ORG-001", "company_name": "Samanvaya Inc."},

    # ORG-002 (TechNova Labs)
    {"id": "CND-05", "name": "Siddharth Verma", "email": "siddharth.v@technova.io", "role": "DevOps Engineer", "dept": "Engineering", "project": "Distributed Telemetry Collector", "status": "Screening", "experience": "8 yrs", "score": 94, "appliedDate": "Sep 12, 2026", "applied_date": "2026-09-12", "org_id": "ORG-002", "company_id": "ORG-002", "company_name": "TechNova Labs"},
    {"id": "CND-06", "name": "Ananya Roy", "email": "ananya.r@technova.io", "role": "Developer", "dept": "Engineering", "project": "Mobile Client Suite", "status": "Interview", "experience": "4 yrs", "score": 89, "appliedDate": "Sep 19, 2026", "applied_date": "2026-09-19", "org_id": "ORG-002", "company_id": "ORG-002", "company_name": "TechNova Labs"},
    {"id": "CND-07", "name": "Vikram Malhotra", "email": "vikram.m@technova.io", "role": "Project Manager", "dept": "Management", "project": "Distributed Telemetry Collector", "status": "Hired", "experience": "7 yrs", "score": 96, "appliedDate": "Sep 08, 2026", "applied_date": "2026-09-08", "org_id": "ORG-002", "company_id": "ORG-002", "company_name": "TechNova Labs"},

    # ORG-003 (Apex Global Dynamics)
    {"id": "CND-08", "name": "Neha Kulkarni", "email": "neha.k@apexgd.com", "role": "Project Manager", "dept": "Management", "project": "Banking Core Microservices", "status": "Interview", "experience": "7 yrs", "score": 93, "appliedDate": "Sep 20, 2026", "applied_date": "2026-09-20", "org_id": "ORG-003", "company_id": "ORG-003", "company_name": "Apex Global Dynamics"},
    {"id": "CND-09", "name": "Arjun Singhania", "email": "arjun.s@apexgd.com", "role": "Developer", "dept": "Engineering", "project": "Fraud Detection Neural Engine", "status": "Screening", "experience": "6 yrs", "score": 91, "appliedDate": "Sep 25, 2026", "applied_date": "2026-09-25", "org_id": "ORG-003", "company_id": "ORG-003", "company_name": "Apex Global Dynamics"},
    {"id": "CND-10", "name": "Tanvi Joshi", "email": "tanvi.j@apexgd.com", "role": "QA Engineer", "dept": "Quality", "project": "Banking Core Microservices", "status": "Hired", "experience": "5 yrs", "score": 97, "appliedDate": "Sep 05, 2026", "applied_date": "2026-09-05", "org_id": "ORG-003", "company_id": "ORG-003", "company_name": "Apex Global Dynamics"}
]

PULL_REQUESTS = [
    {
        "pr_number": 101,
        "title": "feat(core): implement deterministic multi-agent scoring orchestration",
        "author_login": "sarah-connor",
        "author_name": "Sarah Connor",
        "author_email": "dev@samanvaya.io",
        "user_id": "EMP-001",
        "state": "merged",
        "merged": True,
        "additions": 340,
        "deletions": 65,
        "files_changed_count": 8,
        "files": [
            {"filename": "backend/agents/supervisor.py", "additions": 120, "deletions": 20},
            {"filename": "backend/intelligence/scoring/engine.py", "additions": 140, "deletions": 15},
            {"filename": "backend/tests/test_scoring.py", "additions": 80, "deletions": 30},
        ],
        "test_files_count": 2,
        "test_coverage_pct": 89.5,
        "coverage_delta": 2.4,
        "complexity_score": 6.2,
        "security_findings": [],
        "review_comments_count": 3,
        "db_migrations": 0,
        "breaking_changes": 0,
        "created_at": "2026-09-05T10:15:00Z",
        "merged_at": "2026-09-06T14:30:00Z",
    },
    {
        "pr_number": 102,
        "title": "feat(auth): add RBAC company isolation enforcement",
        "author_login": "sarah-connor",
        "author_name": "Sarah Connor",
        "author_email": "dev@samanvaya.io",
        "user_id": "EMP-001",
        "state": "merged",
        "merged": True,
        "additions": 210,
        "deletions": 40,
        "files_changed_count": 5,
        "files": [
            {"filename": "backend/core/security.py", "additions": 110, "deletions": 20},
            {"filename": "backend/tests/test_rbac.py", "additions": 100, "deletions": 20},
        ],
        "test_files_count": 1,
        "test_coverage_pct": 92.0,
        "coverage_delta": 1.2,
        "complexity_score": 5.0,
        "security_findings": [],
        "review_comments_count": 2,
        "db_migrations": 0,
        "breaking_changes": 0,
        "created_at": "2026-09-12T09:00:00Z",
        "merged_at": "2026-09-13T11:20:00Z",
    },
    {
        "pr_number": 103,
        "title": "refactor(arch): domain service decoupling and hexagonal architecture",
        "author_login": "marcus-vance",
        "author_name": "Marcus Vance",
        "author_email": "lead@samanvaya.io",
        "user_id": "EMP-002",
        "state": "merged",
        "merged": True,
        "additions": 450,
        "deletions": 280,
        "files_changed_count": 12,
        "files": [
            {"filename": "backend/domain/services/lead_service.py", "additions": 200, "deletions": 150},
            {"filename": "backend/tests/test_services.py", "additions": 250, "deletions": 130},
        ],
        "test_files_count": 3,
        "test_coverage_pct": 94.0,
        "coverage_delta": 3.0,
        "complexity_score": 5.5,
        "security_findings": [],
        "review_comments_count": 4,
        "db_migrations": 0,
        "breaking_changes": 0,
        "created_at": "2026-09-08T11:00:00Z",
        "merged_at": "2026-09-10T16:00:00Z",
    },
    {
        "pr_number": 104,
        "title": "test(e2e): automated regression verification for release v2.0",
        "author_login": "elena-qa",
        "author_name": "Elena Rostova",
        "author_email": "qa@samanvaya.io",
        "user_id": "EMP-004",
        "state": "merged",
        "merged": True,
        "additions": 520,
        "deletions": 30,
        "files_changed_count": 9,
        "files": [
            {"filename": "backend/tests/e2e/test_regression_v2.py", "additions": 300, "deletions": 10},
            {"filename": "backend/tests/e2e/test_flaky_guards.py", "additions": 220, "deletions": 20},
        ],
        "test_files_count": 9,
        "test_coverage_pct": 95.5,
        "coverage_delta": 4.5,
        "complexity_score": 4.2,
        "security_findings": [],
        "review_comments_count": 1,
        "db_migrations": 0,
        "breaking_changes": 0,
        "created_at": "2026-09-14T08:30:00Z",
        "merged_at": "2026-09-15T12:00:00Z",
    },
    {
        "pr_number": 105,
        "title": "ci(infra): zero-downtime blue-green deployment pipeline and helm charts",
        "author_login": "jordan-ops",
        "author_name": "Jordan Hayes",
        "author_email": "devops@samanvaya.io",
        "user_id": "EMP-005",
        "state": "merged",
        "merged": True,
        "additions": 280,
        "deletions": 45,
        "files_changed_count": 6,
        "files": [
            {"filename": ".github/workflows/deploy.yml", "additions": 150, "deletions": 30},
            {"filename": "helm/values.yaml", "additions": 130, "deletions": 15},
        ],
        "test_files_count": 1,
        "test_coverage_pct": 86.0,
        "coverage_delta": 0.8,
        "complexity_score": 4.8,
        "security_findings": [],
        "review_comments_count": 2,
        "db_migrations": 1,
        "breaking_changes": 0,
        "deployment_risk_score": 15,
        "observability_added": True,
        "created_at": "2026-09-18T14:00:00Z",
        "merged_at": "2026-09-19T17:30:00Z",
    },
]

CICD_LOGS = [
    {
        "id": "CI-RUN-101",
        "pipeline_name": "backend-ci-cd-master",
        "author": "sarah-connor",
        "employee_id": "EMP-001",
        "status": "success",
        "conclusion": "success",
        "exit_code": 0,
        "duration_seconds": 125,
        "failed_step": None,
        "created_at": "2026-09-06T14:25:00Z",
        "timestamp": "2026-09-06T14:25:00Z",
        "test_results": {"passed": 48, "failed": 0, "flaky": 0},
    },
    {
        "id": "CI-RUN-102",
        "pipeline_name": "security-and-lint",
        "author": "sarah-connor",
        "employee_id": "EMP-001",
        "status": "success",
        "conclusion": "success",
        "exit_code": 0,
        "duration_seconds": 88,
        "failed_step": None,
        "created_at": "2026-09-13T11:15:00Z",
        "timestamp": "2026-09-13T11:15:00Z",
        "test_results": {"passed": 36, "failed": 0, "flaky": 0},
    },
    {
        "id": "CI-RUN-103",
        "pipeline_name": "full-regression-e2e",
        "author": "elena-qa",
        "employee_id": "EMP-004",
        "status": "success",
        "conclusion": "success",
        "exit_code": 0,
        "duration_seconds": 310,
        "failed_step": None,
        "created_at": "2026-09-15T11:50:00Z",
        "timestamp": "2026-09-15T11:50:00Z",
        "test_results": {"passed": 124, "failed": 0, "flaky": 0},
    },
    {
        "id": "CI-RUN-104",
        "pipeline_name": "k8s-cluster-cd",
        "author": "jordan-ops",
        "employee_id": "EMP-005",
        "status": "success",
        "conclusion": "success",
        "exit_code": 0,
        "duration_seconds": 180,
        "failed_step": None,
        "created_at": "2026-09-19T17:20:00Z",
        "timestamp": "2026-09-19T17:20:00Z",
        "test_results": {"passed": 20, "failed": 0, "flaky": 0},
    },
]

BRANCHES = [
    {
        "id": 1, "name": "feature/oauth2-flow", "story": "ST-201 – Implement OAuth2 Login Flow",
        "lastCommit": "30m ago", "commits": 12, "status": "Ahead",
        "mergeReady": True, "aiRelevance": 94, "conflicts": False,
        "aiNote": "All files aligned with Auth Service scope."
    },
    {
        "id": 2, "name": "test/payment-unit-tests", "story": "ST-202 – Write Unit Tests for Payments",
        "lastCommit": "2h ago", "commits": 5, "status": "Up to date",
        "mergeReady": False, "aiRelevance": 78, "conflicts": False,
        "aiNote": "Test coverage at 72%. Needs additional edge cases."
    },
    {
        "id": 3, "name": "refactor/notifications-v2", "story": "ST-203 – Refactor Notification Service",
        "lastCommit": "1d ago", "commits": 8, "status": "Behind",
        "mergeReady": False, "aiRelevance": 85, "conflicts": True,
        "aiNote": "Conflict detected in notification_handler.py with main."
    },
    {
        "id": 4, "name": "fix/pagination-bug", "story": "ST-204 – Fix Pagination on Dashboard",
        "lastCommit": "3d ago", "commits": 3, "status": "Up to date",
        "mergeReady": True, "aiRelevance": 96, "conflicts": False,
        "aiNote": "Clean branch. Ready to merge."
    },
    {
        "id": 5, "name": "feature/rate-limiting", "story": "ST-205 – API Rate Limiting Middleware",
        "lastCommit": "45m ago", "commits": 15, "status": "Ahead",
        "mergeReady": False, "aiRelevance": 68, "conflicts": True,
        "aiNote": "Scope drift: 3 files outside API Gateway modified."
    },
    {
        "id": 6, "name": "migration/user-prefs-v2", "story": "ST-206 – Database Migration Script",
        "lastCommit": "6h ago", "commits": 7, "status": "Behind",
        "mergeReady": False, "aiRelevance": 62, "conflicts": False,
        "aiNote": "Missing rollback script. 4 unrelated tables touched."
    },
]

DEV_PULL_REQUESTS = [
    {
        "id": "PR-342", "pr_number": 342, "story": "ST-201 – Implement OAuth2 Login Flow", "alignment": 91,
        "reviewStatus": "Approved", "ci": "Pass", "reviewer": "Sneha Iyer",
        "comments": [
            {"author": "Sneha Iyer", "text": "LGTM! Clean implementation.", "time": "1h ago"},
            {"author": "AI Review", "text": "High alignment. Consider adding rate limiting on token endpoint.", "time": "2h ago"}
        ],
        "aiRisk": None, "files": 8, "additions": 342, "deletions": 45, "status": "Approved"
    },
    {
        "id": "PR-338", "pr_number": 338, "story": "ST-204 – Fix Pagination on Dashboard", "alignment": 96,
        "reviewStatus": "Approved", "ci": "Pass", "reviewer": "Vikram Singh",
        "comments": [
            {"author": "Vikram Singh", "text": "Quick and clean fix.", "time": "2d ago"}
        ],
        "aiRisk": None, "files": 2, "additions": 28, "deletions": 12, "status": "Approved"
    },
    {
        "id": "PR-345", "pr_number": 345, "story": "ST-205 – API Rate Limiting Middleware", "alignment": 68,
        "reviewStatus": "Changes Requested", "ci": "Fail", "reviewer": "Marcus Vance",
        "comments": [
            {"author": "Marcus Vance", "text": "Redis connection pool config missing. Also fix the failing test.", "time": "3h ago"},
            {"author": "AI Review", "text": "Possible scope drift — Frontend files modified for a backend task.", "time": "2h ago"}
        ],
        "aiRisk": "PR 345 – Possible scope drift (Frontend files modified for backend task)",
        "files": 14, "additions": 580, "deletions": 120, "status": "Changes Requested"
    },
    {
        "id": "PR-341", "pr_number": 341, "story": "ST-203 – Refactor Notification Service", "alignment": 85,
        "reviewStatus": "In Review", "ci": "Pass", "reviewer": "Vikram Singh",
        "comments": [
            {"author": "AI Review", "text": "Good separation of concerns. Retry config should be externalized.", "time": "6h ago"}
        ],
        "aiRisk": None, "files": 6, "additions": 195, "deletions": 88, "status": "In Review"
    },
    {
        "id": "PR-347", "pr_number": 347, "story": "ST-206 – Database Migration Script", "alignment": 62,
        "reviewStatus": "Open", "ci": "Fail", "reviewer": "Sneha Iyer",
        "comments": [
            {"author": "AI Review", "text": "High risk — Migration touches 4 unrelated tables. Rollback script missing.", "time": "5h ago"}
        ],
        "aiRisk": "PR 347 – High scope drift (4 unrelated tables modified, rollback missing)",
        "files": 9, "additions": 410, "deletions": 30, "status": "Open"
    },
    {
        "id": "PR-340", "pr_number": 340, "story": "ST-202 – Write Unit Tests for Payments", "alignment": 78,
        "reviewStatus": "Open", "ci": "Pass", "reviewer": "Marcus Vance",
        "comments": [],
        "aiRisk": "PR 340 – Test coverage at 72%, below 85% threshold",
        "files": 5, "additions": 220, "deletions": 10, "status": "Open"
    }
]

DEV_SUBMISSIONS = [
    {
        "id": "SUB-101", "story": "ST-201 – Implement OAuth2 Login Flow", "status": "Approved",
        "submittedAt": "Feb 18, 10:30 AM", "approvedAt": "Feb 18, 02:15 PM", "approvalTime": "3h 45m",
        "rejectionReason": None,
        "revisions": [
            {"version": "v1", "date": "Feb 17", "action": "Submitted", "note": "Initial implementation"},
            {"version": "v2", "date": "Feb 18", "action": "Revised", "note": "Added error handling for token refresh"},
            {"version": "v3", "date": "Feb 18", "action": "Approved", "note": "Final approval by Sneha Iyer"}
        ]
    },
    {
        "id": "SUB-102", "story": "ST-204 – Fix Pagination on Dashboard", "status": "Approved",
        "submittedAt": "Feb 15, 09:00 AM", "approvedAt": "Feb 15, 10:20 AM", "approvalTime": "1h 20m",
        "rejectionReason": None,
        "revisions": [
            {"version": "v1", "date": "Feb 15", "action": "Submitted", "note": "Quick pagination fix"},
            {"version": "v2", "date": "Feb 15", "action": "Approved", "note": "Approved immediately"}
        ]
    },
    {
        "id": "SUB-103", "story": "ST-203 – Refactor Notification Service", "status": "Pending",
        "submittedAt": "Feb 19, 04:00 PM", "approvedAt": None, "approvalTime": "Awaiting...",
        "rejectionReason": None,
        "revisions": [
            {"version": "v1", "date": "Feb 18", "action": "Submitted", "note": "Initial refactor"},
            {"version": "v2", "date": "Feb 19", "action": "Revised", "note": "Added retry mechanism"}
        ]
    },
    {
        "id": "SUB-104", "story": "ST-206 – Database Migration Script", "status": "Rejected",
        "submittedAt": "Feb 17, 11:00 AM", "approvedAt": None, "approvalTime": "—",
        "rejectionReason": "Missing rollback script. Migration touches 4 unrelated tables which violates scope.",
        "revisions": [
            {"version": "v1", "date": "Feb 16", "action": "Submitted", "note": "Initial migration scripts"},
            {"version": "v2", "date": "Feb 17", "action": "Rejected", "note": "Scope issues — missing rollback"}
        ]
    },
    {
        "id": "SUB-105", "story": "ST-205 – API Rate Limiting Middleware", "status": "Pending",
        "submittedAt": "Feb 20, 08:00 AM", "approvedAt": None, "approvalTime": "Awaiting...",
        "rejectionReason": None,
        "revisions": [
            {"version": "v1", "date": "Feb 19", "action": "Submitted", "note": "Rate limiter with Redis backend"},
            {"version": "v2", "date": "Feb 20", "action": "Revised", "note": "Fixed scope drift, removed unrelated files"}
        ]
    },
    {
        "id": "SUB-106", "story": "ST-202 – Write Unit Tests for Payments", "status": "Rejected",
        "submittedAt": "Feb 19, 02:30 PM", "approvedAt": None, "approvalTime": "—",
        "rejectionReason": "Test coverage at 72%, below the minimum 85% threshold. Missing webhook handler tests.",
        "revisions": [
            {"version": "v1", "date": "Feb 19", "action": "Submitted", "note": "Payment unit tests"},
            {"version": "v2", "date": "Feb 19", "action": "Rejected", "note": "Insufficient coverage"}
        ]
    }
]

BLOCKERS = [
    {"id": "B-01", "story": "ST-205", "title": "API Rate Limiting Middleware", "blockerType": "Rejection Loop", "owner": "Ananya Reddy", "daysBlocked": 3, "risk": "High", "resolved": False},
    {"id": "B-02", "story": "ST-206", "title": "Database Migration Script", "blockerType": "Scope Drift", "owner": "Ananya Reddy", "daysBlocked": 2, "risk": "High", "resolved": False},
    {"id": "B-03", "story": "ST-202", "title": "Write Unit Tests for Payments", "blockerType": "Approval Delay", "owner": "Anita Patel", "daysBlocked": 1, "risk": "Medium", "resolved": False},
    {"id": "B-04", "story": "ST-201", "title": "Implement OAuth2 Login Flow", "blockerType": "Approval Delay", "owner": "Vikram Singh", "daysBlocked": 0, "risk": "Low", "resolved": True},
    {"id": "B-05", "story": "ST-203", "title": "Refactor Notification Webhook Service", "blockerType": "DevOps Failure", "owner": "Vikram Singh", "daysBlocked": 0, "risk": "Medium", "resolved": True},
    {"id": "B-06", "story": "ST-204", "title": "Fix Pagination on Dashboard", "blockerType": "Overload", "owner": "Sneha Iyer", "daysBlocked": 0, "risk": "Low", "resolved": True}
]

RETROSPECTIVES = [
    {
        "id": "RETRO-01",
        "sprint": "Sprint 24",
        "avg_alignment": 92,
        "ai_summary": "Sprint 24 demonstrated robust velocity with 94% story point delivery. Cross-functional PR review latency was cut by 60%.",
        "went_well": [
            "Completed 94% of planned story points on time",
            "Zero critical production bugs reported post-deployment",
            "Improved code review turnaround time"
        ],
        "didnt_go_well": [
            "Better estimation on complex distributed tracing stories needed",
            "Increase automated integration test coverage for webhook notifications"
        ],
        "improvements": [
            {"item": "Implement automatic test runs on pull request draft conversion", "action": "Setup CI automation", "owner": "Ananya Reddy", "impact": "High"},
            {"item": "Schedule backlog refinement session for Sprint 25", "action": "Refinement meeting", "owner": "Sneha Iyer", "impact": "Medium"}
        ]
    }
]

REVIEW_QUEUE = [
    {"id": "REV-01", "pr_id": "#142", "title": "Feature: Add real-time task sync via WebSocket", "author": "dev_admin", "author_name": "Sarah Connor", "repo": "Samanvaya/backend", "risk": "LOW", "status": "Pending", "storyTitle": "Build real-time team alignment analytics", "submittedAt": "2h ago", "alignmentScore": 92},
    {"id": "REV-02", "pr_id": "#143", "title": "Refactor: Redesign execution metrics cards", "author": "dev_admin", "author_name": "Sarah Connor", "repo": "Samanvaya/frontend", "risk": "LOW", "status": "Pending", "storyTitle": "Fix Pagination on Dashboard", "submittedAt": "4h ago", "alignmentScore": 95},
    {"id": "REV-03", "pr_id": "#144", "title": "Security: Update CORS regex and bcrypt salt handler", "author": "lead_admin", "author_name": "Marcus Vance", "repo": "Samanvaya/backend", "risk": "MEDIUM", "status": "Approved", "storyTitle": "Implement OAuth2 Login Flow", "submittedAt": "1d ago", "alignmentScore": 88},
    {"id": "REV-04", "pr_id": "#145", "title": "API Rate Limiting Middleware", "author": "ananya_reddy", "author_name": "Ananya Reddy", "repo": "Samanvaya/backend", "risk": "HIGH", "status": "Changes Requested", "storyTitle": "API Rate Limiting Middleware", "submittedAt": "3h ago", "alignmentScore": 68}
]

ESCALATIONS = [
    {"id": "ESC-01", "title": "Payment gateway compliance audit delay", "level": "HIGH", "project": "Payment Gateway v2", "assigned_to": "lead_admin", "raised_by": "pm_admin", "date": "2026-09-27"},
    {"id": "ESC-02", "title": "Third-party analytics SDK rate limitation", "level": "MEDIUM", "project": "Samanvaya Mobile App", "assigned_to": "dev_admin", "raised_by": "qa_admin", "date": "2026-09-28"},
    {"id": "ESC-03", "title": "Database migration scope drift and missing rollback script", "level": "HIGH", "project": "Samanvaya AI Platform", "assigned_to": "lead_admin", "raised_by": "pm_admin", "date": "2026-09-29"}
]

DEV_PROGRESS = {
    "type": "developer_progress",
    "sprint_contribution": [
        {"sprint": "S7", "points": 12}, {"sprint": "S8", "points": 18}, {"sprint": "S9", "points": 15},
        {"sprint": "S10", "points": 22}, {"sprint": "S11", "points": 20}, {"sprint": "S12", "points": 16}
    ],
    "alignment_trend": [
        {"sprint": "S7", "score": 72}, {"sprint": "S8", "score": 78}, {"sprint": "S9", "score": 75},
        {"sprint": "S10", "score": 82}, {"sprint": "S11", "score": 88}, {"sprint": "S12", "score": 83}
    ],
    "rejection_trend": [
        {"sprint": "S7", "rate": 25}, {"sprint": "S8", "rate": 18}, {"sprint": "S9", "rate": 22},
        {"sprint": "S10", "rate": 12}, {"sprint": "S11", "rate": 8}, {"sprint": "S12", "rate": 15}
    ],
    "approval_delay": [
        {"sprint": "S7", "hours": 18}, {"sprint": "S8", "hours": 14}, {"sprint": "S9", "hours": 16},
        {"sprint": "S10", "hours": 9}, {"sprint": "S11", "hours": 6}, {"sprint": "S12", "hours": 8}
    ],
    "behaviour_snapshot": [
        {"label": "Code Quality", "score": 88, "trend": "up"},
        {"label": "Collaboration", "score": 92, "trend": "up"},
        {"label": "Punctuality", "score": 78, "trend": "down"},
        {"label": "Documentation", "score": 85, "trend": "up"},
        {"label": "Communication", "score": 90, "trend": "up"}
    ]
}

DEV_AI_FEEDBACK = {
    "type": "ai_feedback",
    "alignment_data": [
        {"metric": "Keyword Match", "value": 87, "color": "#3b82f6"},
        {"metric": "File Path Relevance", "value": 79, "color": "#8b5cf6"},
        {"metric": "Semantic Similarity", "value": 83, "color": "#06b6d4"},
        {"metric": "Scope Drift", "value": 14, "color": "#ef4444", "invert": True}
    ],
    "suggestions": [
        {"id": 1, "text": "Consider adding unit tests for token expiry edge case in auth handler.", "priority": "High"},
        {"id": 2, "text": "Separate database schema migrations from service logic into dedicated migration PR.", "priority": "Medium"},
        {"id": 3, "text": "Reduce additions in PR #345 to keep changes atomic and reviewable.", "priority": "Low"}
    ],
    "quality_insights": [
        {"title": "Commit Frequency Pattern", "desc": "Averaging 4.2 commits/day. Pattern indicates steady progress with occasional bursts on Fridays.", "type": "info"},
        {"title": "Large Diff Warning", "desc": "PR #345 has 580+ additions. Consider splitting into smaller PRs for easier review.", "type": "warning"},
        {"title": "Tiny Fake Commit Detection", "desc": "No suspicious micro-commits detected. All commits have meaningful changes (avg 42 lines).", "type": "success"},
        {"title": "Repeated Minor Changes Flag", "desc": "3 commits to config.yaml in the last 2 days with minimal changes. Consider batching config updates.", "type": "warning"}
    ],
    "commit_frequency": [
        {"day": "Mon", "commits": 5}, {"day": "Tue", "commits": 3}, {"day": "Wed", "commits": 4},
        {"day": "Thu", "commits": 6}, {"day": "Fri", "commits": 8}, {"day": "Sat", "commits": 1}, {"day": "Sun", "commits": 0}
    ]
}

TEAM_WORKLOAD = [
    {"name": "Vikram Singh", "role": "Senior Developer", "stories": 5, "points": 26, "capacity": 88, "status": "Overloaded", "risk": "Medium"},
    {"name": "Sneha Iyer", "role": "Scrum Master", "stories": 4, "points": 18, "capacity": 72, "status": "Optimal", "risk": "Low"},
    {"name": "Ananya Reddy", "role": "DevOps Engineer", "stories": 5, "points": 28, "capacity": 92, "status": "Overloaded", "risk": "High"},
    {"name": "Anita Patel", "role": "QA Engineer", "stories": 3, "points": 14, "capacity": 56, "status": "Available", "risk": "Low"},
    {"name": "Sarah Connor", "role": "Developer", "stories": 4, "points": 22, "capacity": 75, "status": "Optimal", "risk": "Low"},
    {"name": "Marcus Vance", "role": "Lead Architect", "stories": 3, "points": 16, "capacity": 62, "status": "Available", "risk": "Low"}
]

WORKLOAD_SUGGESTIONS = [
    {"id": 1, "text": "Rebalance 1 story from Ananya Reddy (92%) to Anita Patel (56%) to relieve release bottleneck.", "type": "rebalance", "target": "Ananya Reddy"},
    {"id": 2, "text": "Vikram Singh capacity is near 88% — defer exploratory tech-debt tickets to next sprint.", "type": "warning", "target": "Vikram Singh"}
]

TEAM_PERFORMANCE_MEMBERS = [
    {"name": "Vikram Singh", "completion": 94, "alignmentAvg": 91, "reviewDelayAvg": "1.2d", "rejectionRate": 5, "behaviourScore": 8.5},
    {"name": "Sneha Iyer", "completion": 92, "alignmentAvg": 89, "reviewDelayAvg": "0.9d", "rejectionRate": 4, "behaviourScore": 9.0},
    {"name": "Ananya Reddy", "completion": 74, "alignmentAvg": 75, "reviewDelayAvg": "3.1d", "rejectionRate": 16, "behaviourScore": 7.5},
    {"name": "Anita Patel", "completion": 88, "alignmentAvg": 84, "reviewDelayAvg": "1.5d", "rejectionRate": 8, "behaviourScore": 8.2},
    {"name": "Marcus Vance", "completion": 96, "alignmentAvg": 93, "reviewDelayAvg": "1.1d", "rejectionRate": 3, "behaviourScore": 9.2},
    {"name": "Sarah Connor", "completion": 90, "alignmentAvg": 92, "reviewDelayAvg": "1.4d", "rejectionRate": 6, "behaviourScore": 8.8}
]

SPRINT_TRENDS = [
    {"sprint": "S1", "completion": 70, "alignment": 74, "rejection": 14},
    {"sprint": "S2", "completion": 74, "alignment": 76, "rejection": 13},
    {"sprint": "S3", "completion": 76, "alignment": 78, "rejection": 11},
    {"sprint": "S4", "completion": 78, "alignment": 75, "rejection": 10},
    {"sprint": "S5", "completion": 80, "alignment": 79, "rejection": 9},
    {"sprint": "S6", "completion": 84, "alignment": 82, "rejection": 7}
]

ALIGNMENT_BREAKDOWN = [
    {"name": "Vikram Singh", "keyword": 92, "filePath": 88, "semantic": 91, "scopeDrift": 4},
    {"name": "Sneha Iyer", "keyword": 94, "filePath": 90, "semantic": 93, "scopeDrift": 3},
    {"name": "Ananya Reddy", "keyword": 75, "filePath": 70, "semantic": 78, "scopeDrift": 18},
    {"name": "Anita Patel", "keyword": 85, "filePath": 82, "semantic": 84, "scopeDrift": 8},
    {"name": "Sarah Connor", "keyword": 93, "filePath": 89, "semantic": 92, "scopeDrift": 5}
]

LOW_ALIGNMENT_STORIES = [
    {"id": "ST-205", "title": "API Rate Limiting Middleware", "developer": "Ananya Reddy", "alignment": 68, "offenses": 2, "note": "Scope drift in backend API gateway layer"},
    {"id": "ST-206", "title": "Database Migration Script", "developer": "Ananya Reddy", "alignment": 62, "offenses": 3, "note": "Missing rollback script and 4 unrelated tables modified"},
    {"id": "ST-202", "title": "Write Unit Tests for Payments", "developer": "Anita Patel", "alignment": 78, "offenses": 1, "note": "Coverage at 72%, below 85% requirement"}
]

ALIGNMENT_TREND = [
    {"sprint": "S1", "avg": 74}, {"sprint": "S2", "avg": 76}, {"sprint": "S3", "avg": 78},
    {"sprint": "S4", "avg": 75}, {"sprint": "S5", "avg": 79}, {"sprint": "S6", "avg": 82}
]

BEHAVIOUR_HISTORY = [
    {"month": "Jan 2026", "member": "Vikram Singh", "score": 8.5, "ratedBy": "Alexander Sterling (CEO)"},
    {"month": "Jan 2026", "member": "Ananya Reddy", "score": 7.5, "ratedBy": "Arjun Patel"},
    {"month": "Dec 2025", "member": "Vikram Singh", "score": 8.2, "ratedBy": "Sneha Iyer"},
    {"month": "Dec 2025", "member": "Sneha Iyer", "score": 9.0, "ratedBy": "Alexander Sterling (CEO)"},
    {"month": "Dec 2025", "member": "Sarah Connor", "score": 8.8, "ratedBy": "Marcus Vance"}
]

CEO_METRICS = {
    "type": "ceo_dashboard",
    "execution_weeks": [
        {"week": "W1", "planned": 90, "actual": 88, "confidence": 92},
        {"week": "W2", "planned": 92, "actual": 91, "confidence": 94},
        {"week": "W3", "planned": 95, "actual": 93, "confidence": 91},
        {"week": "W4", "planned": 98, "actual": 96, "confidence": 95}
    ],
    "sprint_status": [
        {"name": "On Track", "value": 14, "color": "#10b981"},
        {"name": "At Risk", "value": 3, "color": "#f59e0b"},
        {"name": "Delayed", "value": 1, "color": "#ef4444"},
        {"name": "Completed", "value": 18, "color": "#3b82f6"}
    ],
    "health_factors": [
        {"name": "Sprint Goal Alignment", "factor": "Sprint Goal Alignment", "score": 92, "weight": 25, "color": "#10b981", "status": "HEALTHY"},
        {"name": "Code Quality & Testing", "factor": "Code Quality & Testing", "score": 88, "weight": 25, "color": "#3b82f6", "status": "HEALTHY"},
        {"name": "PR Review Cadence", "factor": "PR Review Cadence", "score": 84, "weight": 20, "color": "#8b5cf6", "status": "HEALTHY"},
        {"name": "CI/CD Pipeline Stability", "factor": "CI/CD Pipeline Stability", "score": 95, "weight": 15, "color": "#10b981", "status": "HEALTHY"},
        {"name": "Team Capacity Utilization", "factor": "Team Capacity Utilization", "score": 82, "weight": 15, "color": "#f59e0b", "status": "MONITOR"}
    ],
    "story_risks": [
        {"id": "STY-104", "title": "OAuth 2.0 PKCE Authorization Flow", "developer": "Vikram Singh", "risk": 78, "reason": "Third-party IDP rate limits and pending security sign-off"},
        {"id": "STY-108", "title": "Real-time Telemetry WebSocket Broadcast", "developer": "Neha Sharma", "risk": 64, "reason": "High concurrent memory utilization under synthetic stress testing"},
        {"id": "STY-112", "title": "Stripe Webhook Idempotency Layer", "developer": "Arjun Mehta", "risk": 52, "reason": "Edge case deduplication handling requires distributed Redis lock"},
        {"id": "STY-115", "title": "Audit Log Cold Storage Archival", "developer": "Priya Nair", "risk": 35, "reason": "AWS S3 Glacier life-cycle transition policy validation pending"}
    ],
    "dev_risk": [
        {"name": "Vikram Singh", "riskScore": 45, "storiesAtRisk": 2, "avgDelay": "1.2 days"},
        {"name": "Neha Sharma", "riskScore": 32, "storiesAtRisk": 1, "avgDelay": "0.8 days"},
        {"name": "Arjun Mehta", "riskScore": 24, "storiesAtRisk": 1, "avgDelay": "0.5 days"},
        {"name": "Sneha Iyer", "riskScore": 12, "storiesAtRisk": 0, "avgDelay": "0.2 days"},
        {"name": "Priya Nair", "riskScore": 8, "storiesAtRisk": 0, "avgDelay": "0.1 days"}
    ],
    "active_risks": [
        {"id": "RSK-01", "title": "External OAuth Provider Latency", "category": "Third Party Dependency", "severity": "Medium", "mitigation": "Fallback local cache with JWT validation", "owner": "Vikram Singh"},
        {"id": "RSK-02", "title": "Database Read Replicas Lag under High Load", "category": "Infrastructure", "severity": "High", "mitigation": "Implement Redis read-through cache for dashboard queries", "owner": "Jordan Hayes"}
    ],
    "escalation_events": [
        {
            "id": "EVT-101", "title": "Cypress E2E Flakiness Escalation", "category": "Quality Assurance", "status": "Resolved",
            "impact": "False-positive build failures in PR merge validation queue.", "leadAssigned": "Elena Rostova (QA Engineer)",
            "actionTaken": "Updated selector assertions to explicitly wait for animation completion and state hydration.", "recommendedAction": "Cypress pass rate restored to 99.4%."
        }
    ]
}


QA_TEST_CASES = [
    {"id": "TC-001", "title": "Verify user login with valid credentials", "module": "Authentication", "priority": "High", "status": "Passed", "automated": True, "lastRun": "2h ago"},
    {"id": "TC-002", "title": "Verify password reset email flow", "module": "Authentication", "priority": "High", "status": "Passed", "automated": True, "lastRun": "2h ago"},
    {"id": "TC-003", "title": "Test stripe webhook for subscription renewal", "module": "Payment", "priority": "Critical", "status": "Failed", "automated": True, "lastRun": "2h ago"},
    {"id": "TC-004", "title": "Verify dashboard chart renders on data load", "module": "Dashboard", "priority": "Medium", "status": "Flaky", "automated": True, "lastRun": "4h ago"},
    {"id": "TC-005", "title": "Validate user team assignment flow", "module": "User Management", "priority": "Medium", "status": "Passed", "automated": False, "lastRun": "6h ago"},
    {"id": "TC-006", "title": "Verify sprint board drag-and-drop reordering", "module": "Sprint Board", "priority": "Low", "status": "Passed", "automated": False, "lastRun": "1d ago"},
    {"id": "TC-007", "title": "Test bulk CSV user import with 500 records", "module": "User Management", "priority": "High", "status": "Passed", "automated": True, "lastRun": "1d ago"},
    {"id": "TC-008", "title": "Verify notification email sent on story approval", "module": "Notifications", "priority": "Medium", "status": "Passed", "automated": True, "lastRun": "6h ago"},
]

QA_BUGS = [
    {"id": "BUG-001", "title": "Stripe webhook fails for recurring payments", "summary": "Stripe webhook fails for recurring payments", "severity": "Critical", "status": "Open", "module": "Payment Gateway", "service": "Payment Gateway", "reporter": "elena-qa", "assignee": "Vikram Singh"},
    {"id": "BUG-002", "title": "Memory leak on chart re-render after 10+ refreshes", "summary": "Memory leak on chart re-render after 10+ refreshes", "severity": "High", "status": "In Progress", "module": "Dashboard", "service": "Dashboard", "reporter": "elena-qa", "assignee": "Sarah Connor"},
    {"id": "BUG-003", "title": "Session timeout redirect loop in Safari", "summary": "Session timeout redirect loop in Safari", "severity": "Medium", "status": "In Progress", "module": "Authentication", "service": "Authentication", "reporter": "anita-qa", "assignee": "Marcus Vance"},
    {"id": "BUG-004", "title": "CSV export encoding breaks for non-ASCII names", "summary": "CSV export encoding breaks for non-ASCII names", "severity": "Low", "status": "Resolved", "module": "Reporting", "service": "Reporting", "reporter": "elena-qa", "assignee": "Vikram Singh"},
    {"id": "BUG-005", "title": "Transaction rollback not triggered on timeout", "summary": "Transaction rollback not triggered on timeout", "severity": "Critical", "status": "Open", "module": "Payment Gateway", "service": "Payment Gateway", "reporter": "anita-qa", "assignee": "Sarah Connor"},
    {"id": "BUG-006", "title": "WebSocket disconnects after 5 min idle", "summary": "WebSocket disconnects after 5 min idle", "severity": "High", "status": "Open", "module": "Chat", "service": "Chat", "reporter": "elena-qa", "assignee": "Jordan Hayes"},
    {"id": "BUG-007", "title": "Lazy-loaded charts flash white before render", "summary": "Lazy-loaded charts flash white before render", "severity": "High", "status": "Open", "module": "Dashboard", "service": "Dashboard", "reporter": "anita-qa", "assignee": "Sarah Connor"},
]

QA_REGRESSION = [
    {"id": "REG-001", "module": "Authentication", "cases": 18, "passed": 17, "failed": 1, "flaky": False, "lastRun": "2h ago"},
    {"id": "REG-002", "module": "Payment", "cases": 24, "passed": 16, "failed": 8, "flaky": True, "lastRun": "2h ago"},
    {"id": "REG-003", "module": "Dashboard", "cases": 12, "passed": 10, "failed": 2, "flaky": True, "lastRun": "4h ago"},
    {"id": "REG-004", "module": "User Management", "cases": 15, "passed": 15, "failed": 0, "flaky": False, "lastRun": "6h ago"},
    {"id": "REG-005", "module": "Notifications", "cases": 9, "passed": 8, "failed": 1, "flaky": False, "lastRun": "6h ago"},
    {"id": "REG-006", "module": "Reporting", "cases": 8, "passed": 8, "failed": 0, "flaky": False, "lastRun": "1d ago"},
]

QA_RELEASE_CHECKS = [
    {"label": "Critical Bugs Open", "value": 2, "threshold": 0, "status": "fail"},
    {"label": "High Bugs Open", "value": 3, "threshold": 2, "status": "fail"},
    {"label": "Regression Pass %", "value": 86, "threshold": 90, "status": "fail"},
    {"label": "CI Stability", "value": 95, "threshold": 90, "status": "pass"},
    {"label": "Test Coverage", "value": 82, "threshold": 80, "status": "pass"},
    {"label": "Deployment Risk", "value": "Medium", "threshold": "Low", "status": "warning"},
]

QA_QUALITY_METRICS = {
    "type": "qa_quality_metrics",
    "quality_formula": [
        {"label": "Test Pass Rate", "weight": "40%", "value": 91, "color": "#10b981"},
        {"label": "Defect Density", "weight": "20%", "value": 82, "color": "#3b82f6"},
        {"label": "Reopen Rate", "weight": "15%", "value": 88, "color": "#8b5cf6"},
        {"label": "Regression Stability", "weight": "15%", "value": 78, "color": "#f59e0b"},
        {"label": "Coverage %", "weight": "10%", "value": 82, "color": "#06b6d4"},
    ],
    "sprint_trend": [
        {"sprint": "S7", "score": 72}, {"sprint": "S8", "score": 78}, {"sprint": "S9", "score": 82},
        {"sprint": "S10", "score": 75}, {"sprint": "S11", "score": 80}, {"sprint": "S12", "score": 86},
    ]
}

QA_TEST_RUNS = [
    {"id": 1, "build": "v2.4.1-rc3", "env": "Staging", "total": 86, "passed": 78, "failed": 8, "duration": "12m 34s", "ciStatus": "Passed", "coverage": 82},
    {"id": 2, "build": "v3.1.0-rc1", "env": "Staging", "total": 42, "passed": 36, "failed": 6, "duration": "8m 12s", "ciStatus": "Failed", "coverage": 78},
    {"id": 3, "build": "v2.3.8-hotfix", "env": "Dev", "total": 24, "passed": 20, "failed": 4, "duration": "4m 48s", "ciStatus": "Passed", "coverage": 65},
    {"id": 4, "build": "v1.5.0-beta", "env": "Dev", "total": 18, "passed": 16, "failed": 2, "duration": "3m 22s", "ciStatus": "Passed", "coverage": 88},
    {"id": 5, "build": "v2.4.0-rc2", "env": "Staging", "total": 86, "passed": 82, "failed": 4, "duration": "11m 56s", "ciStatus": "Passed", "coverage": 85},
    {"id": 6, "build": "v1.0.0-alpha", "env": "Dev", "total": 15, "passed": 12, "failed": 3, "duration": "2m 45s", "ciStatus": "Failed", "coverage": 55},
]

QA_REPORTS = [
    {"id": "QA-REP-01", "title": "Sprint 24 Regression Report", "desc": "Full regression pass results across 6 modules for Sprint 24.", "lastGenerated": "Today at 9:00 AM", "status": "Ready"},
    {"id": "QA-REP-02", "title": "Bug Density Analysis Q3 2026", "desc": "Bug density trends per sprint, severity breakdown, and resolution SLA tracking.", "lastGenerated": "Yesterday at 6:00 PM", "status": "Ready"},
    {"id": "QA-REP-03", "title": "Release Readiness Sign-off Report", "desc": "Pre-release checklist, blocking bugs, and deployment risk assessment.", "lastGenerated": "Sep 28, 2026", "status": "Ready"},
]

QA_ASSIGNED_STORIES = [
    {
        "id": 1, "story": "User Login Flow Redesign", "developer": "Vikram Singh", "buildVersion": "v2.4.1",
        "alignment": 92, "testStatus": "Testing", "priority": "High", "deadline": "Feb 22",
        "acceptance": ["Login form validates email format", "Error messages display correctly", "Remember me persists session"],
        "linkedPR": "PR-042", "buildEnv": "Staging",
    },
    {
        "id": 2, "story": "Payment Gateway Integration", "developer": "Rahul Verma", "buildVersion": "v3.1.0",
        "alignment": 88, "testStatus": "Passed", "priority": "Critical", "deadline": "Feb 20",
        "acceptance": ["Stripe and Razorpay supported", "Transaction rollback on failure", "Payment receipt generated"],
        "linkedPR": "PR-039", "buildEnv": "Staging",
    },
    {
        "id": 3, "story": "Dashboard Performance Fix", "developer": "Karan Joshi", "buildVersion": "v2.3.8",
        "alignment": 76, "testStatus": "Failed", "priority": "Medium", "deadline": "Feb 23",
        "acceptance": ["Page load < 2s", "Lazy loading for charts", "No memory leaks on refresh"],
        "linkedPR": "PR-045", "buildEnv": "Dev",
    },
    {
        "id": 4, "story": "Email Notification Service", "developer": "Meera Nair", "buildVersion": "v1.5.0",
        "alignment": 94, "testStatus": "Testing", "priority": "High", "deadline": "Feb 21",
        "acceptance": ["HTML template renders correctly", "Unsubscribe link works", "Retry on SMTP failure"],
        "linkedPR": "PR-047", "buildEnv": "Staging",
    },
    {
        "id": 5, "story": "User Profile Update API", "developer": "Vikram Singh", "buildVersion": "v2.4.2",
        "alignment": 85, "testStatus": "Pending", "priority": "Medium", "deadline": "Feb 24",
        "acceptance": ["Avatar upload max 2MB", "Validation on all fields", "Returns 200 on success"],
        "linkedPR": "PR-050", "buildEnv": "Dev",
    },
    {
        "id": 6, "story": "Real-time Chat Integration", "developer": "Ananya Reddy", "buildVersion": "v1.0.0",
        "alignment": 68, "testStatus": "Pending", "priority": "Low", "deadline": "Feb 26",
        "acceptance": ["WebSocket connection stable", "Message delivery < 500ms", "Typing indicator works"],
        "linkedPR": "PR-052", "buildEnv": "Dev",
    },
]

QA_REPORTS_METRICS = {
    "type": "qa_reports_metrics",
    "bug_trend": [
        {"sprint": "S8", "found": 12, "resolved": 10},
        {"sprint": "S9", "found": 8, "resolved": 12},
        {"sprint": "S10", "found": 14, "resolved": 11},
        {"sprint": "S11", "found": 6, "resolved": 9},
        {"sprint": "S12", "found": 8, "resolved": 14},
    ],
    "quality_trend": [
        {"sprint": "S8", "score": 78},
        {"sprint": "S9", "score": 82},
        {"sprint": "S10", "score": 75},
        {"sprint": "S11", "score": 80},
        {"sprint": "S12", "score": 85},
    ]
}

SHARED_REPORTS = [
    {"id": "REP-01", "title": "Monthly Performance Report", "date": "Feb 2026", "type": "Performance"},
    {"id": "REP-02", "title": "Sprint Velocity Analysis", "date": "Jan 2026", "type": "Engineering"},
    {"id": "REP-03", "title": "Budget Utilization Report", "date": "Jan 2026", "type": "Finance"},
    {"id": "REP-04", "title": "Employee Satisfaction Survey", "date": "Dec 2025", "type": "HR"},
    {"id": "REP-05", "title": "Infrastructure Cost Analysis", "date": "Dec 2025", "type": "DevOps"},
    {"id": "REP-06", "title": "Q4 Executive Summary", "date": "Dec 2025", "type": "Executive"},
]

SHARED_REPORTS_METRICS = {
    "type": "shared_reports_metrics",
    "chart_data": [
        {"month": "Sep", "generated": 12},
        {"month": "Oct", "generated": 15},
        {"month": "Nov", "generated": 10},
        {"month": "Dec", "generated": 18},
        {"month": "Jan", "generated": 14},
        {"month": "Feb", "generated": 8},
    ]
}

PIPELINES = [
    {
        "id": "PL-01", "name": "alpha-backend CI", "branch": "main", "status": "Passed",
        "duration": "3.7m", "last_run": "10 minutes ago", "commit": "7b82f1a", "successRate": 92,
        "author": "Vikram Singh", "stages": ["Lint", "Unit Test", "Integration Test", "Build", "Security Scan"],
        "logs": "All 42 test suites passed in 3m 42s. 0 vulnerabilities found."
    },
    {
        "id": "PL-02", "name": "gamma-frontend CI", "branch": "main", "status": "Passed",
        "duration": "2.3m", "last_run": "25 minutes ago", "commit": "90e4a3b", "successRate": 96,
        "author": "Karan Joshi", "stages": ["Lint", "Type Check", "Vite Build", "E2E Test"],
        "logs": "Production bundle generated in 1m 12s. Bundle size: 482kB."
    },
    {
        "id": "PL-03", "name": "beta-service CD", "branch": "staging", "status": "Running",
        "duration": "5.0m", "last_run": "Just now", "commit": "3c12d4e", "successRate": 68,
        "author": "Rahul Verma", "stages": ["Build Container", "Deploy to Staging", "Smoke Test"],
        "logs": "Deploying image tag v2.4.1-rc3 to k8s namespace staging-beta..."
    },
    {
        "id": "PL-04", "name": "infra-terraform", "branch": "main", "status": "Passed",
        "duration": "1.9m", "last_run": "1 hour ago", "commit": "fa5678b", "successRate": 98,
        "author": "Ananya Reddy", "stages": ["Terraform Plan", "Terraform Apply", "Drift Check"],
        "logs": "Apply complete! Resources: 2 added, 1 modified, 0 destroyed."
    },
    {
        "id": "PL-05", "name": "alpha-backend CD", "branch": "main", "status": "Passed",
        "duration": "4.2m", "last_run": "2 hours ago", "commit": "8a12b3c", "successRate": 88,
        "author": "Sneha Iyer", "stages": ["Blue-Green Deploy", "Health Check", "Traffic Switch"],
        "logs": "Traffic switched to Green deployment. 100% requests routed cleanly."
    },
    {
        "id": "PL-06", "name": "monitoring-deploy", "branch": "main", "status": "Failed",
        "duration": "2.8m", "last_run": "3 hours ago", "commit": "9f34d1e", "successRate": 72,
        "author": "Ananya Reddy", "stages": ["Helm Upgrade", "Pod Readiness"],
        "logs": "Pod Prometheus-server failed liveness check: timed out after 180s."
    }
]

PIPELINE_METRICS = {
    "type": "pipeline_metrics",
    "failure_trend": [
        {"sprint": "S7", "failures": 8},
        {"sprint": "S8", "failures": 5},
        {"sprint": "S9", "failures": 12},
        {"sprint": "S10", "failures": 6},
        {"sprint": "S11", "failures": 4},
        {"sprint": "S12", "failures": 7},
    ],
    "avg_build_time": [
        {"pipeline": "alpha-BE CI", "time": 3.7},
        {"pipeline": "gamma-FE CI", "time": 2.3},
        {"pipeline": "beta-svc CD", "time": 5.0},
        {"pipeline": "infra-TF", "time": 1.9},
        {"pipeline": "alpha-BE CD", "time": 4.2},
        {"pipeline": "monitor", "time": 2.8},
    ],
    "ai_insights": [
        {"text": "Pipeline beta-service CD failed 3 times this sprint. Possible unstable test environment.", "type": "danger"},
        {"text": "monitoring-deploy has a 28% failure rate. Flaky build detected — investigate Docker cache layer.", "type": "warning"},
        {"text": "alpha-backend CI maintains 92% success rate. Stable and healthy.", "type": "success"},
    ]
}

DEPLOYMENTS = [
    {
        "id": "DEP-01", "service": "alpha-backend", "env": "Production", "version": "v2.4.1", "status": "Stable",
        "deployedAt": "Feb 20, 09:30 AM", "deployed_at": "Feb 20, 09:30 AM", "deployedBy": "Ananya Reddy", "by": "Ananya Reddy",
        "commit": "7b82f1a", "canRollback": True, "rollbackVersion": "v2.4.0", "health": "Healthy (99.98% uptime)", "duration": "4m 12s"
    },
    {
        "id": "DEP-02", "service": "API Gateway", "env": "Production", "version": "v1.8.0", "status": "Stable",
        "deployedAt": "Feb 19, 06:15 PM", "deployed_at": "Feb 19, 06:15 PM", "deployedBy": "Ananya Reddy", "by": "Ananya Reddy",
        "commit": "90e4a3b", "canRollback": True, "rollbackVersion": "v1.7.9", "health": "Healthy (All 5 pods running)", "duration": "2m 30s"
    },
    {
        "id": "DEP-03", "service": "beta-service", "env": "Staging", "version": "v3.1.0-rc2", "status": "Warning",
        "deployedAt": "Feb 19, 03:45 PM", "deployed_at": "Feb 19, 03:45 PM", "deployedBy": "Rahul Verma", "by": "Rahul Verma",
        "commit": "3c12d4e", "canRollback": True, "rollbackVersion": "v3.0.9", "health": "Degraded (Memory usage > 85%)", "duration": "5m 45s"
    },
    {
        "id": "DEP-04", "service": "notification-svc", "env": "Production", "version": "v1.5.0", "status": "Stable",
        "deployedAt": "Feb 18, 09:00 AM", "deployed_at": "Feb 18, 09:00 AM", "deployedBy": "Sneha Iyer", "by": "Sneha Iyer",
        "commit": "fa5678b", "canRollback": False, "rollbackVersion": "v1.4.2", "health": "Healthy (Queue latency 12ms)", "duration": "3m 10s"
    },
    {
        "id": "DEP-05", "service": "gamma-frontend", "env": "Production", "version": "v2.3.8", "status": "Failed",
        "deployedAt": "Feb 17, 11:20 PM", "deployed_at": "Feb 17, 11:20 PM", "deployedBy": "Karan Joshi", "by": "Karan Joshi",
        "commit": "8a12b3c", "canRollback": True, "rollbackVersion": "v2.3.7", "health": "Unhealthy (500 errors on dashboard routes)", "duration": "1m 55s"
    },
    {
        "id": "DEP-06", "service": "Cache Redis", "env": "Staging", "version": "v7.2-alpine", "status": "Stable",
        "deployedAt": "Feb 17, 04:30 PM", "deployed_at": "Feb 17, 04:30 PM", "deployedBy": "Ananya Reddy", "by": "Ananya Reddy",
        "commit": "4e18d2a", "canRollback": True, "rollbackVersion": "v7.0", "health": "Healthy (Hit ratio 94.2%)", "duration": "1m 15s"
    }
]

DEPLOY_METRICS = {
    "type": "deploy_metrics",
    "mttr": "1h 45m",
    "deploy_frequency": [
        {"day": "Mon", "deploys": 3},
        {"day": "Tue", "deploys": 5},
        {"day": "Wed", "deploys": 2},
        {"day": "Thu", "deploys": 4},
        {"day": "Fri", "deploys": 6},
        {"day": "Sat", "deploys": 1},
        {"day": "Sun", "deploys": 0},
    ],
    "ai_suggestions": [
        {"text": "Frequent staging failures detected for beta-service. Check Docker image consistency.", "type": "danger"},
        {"text": "notification-svc rolled back twice this month. Investigate dependency conflicts.", "type": "warning"},
        {"text": "alpha-backend and auth-service deployments remain stable across all environments.", "type": "success"}
    ]
}

DEVOPS_SYSTEM_HEALTH = {
    "type": "system_health",
    "services": [
        {"name": "API Gateway", "cpu": 45, "memory": 62, "diskIO": 28, "dbLatency": 12, "apiResponse": 85, "uptime": 99.97},
        {"name": "Auth Service", "cpu": 32, "memory": 48, "diskIO": 15, "dbLatency": 8, "apiResponse": 42, "uptime": 99.99},
        {"name": "DB Primary", "cpu": 68, "memory": 92, "diskIO": 72, "dbLatency": 25, "apiResponse": None, "uptime": 99.95},
        {"name": "Cache Redis", "cpu": 15, "memory": 55, "diskIO": 10, "dbLatency": 2, "apiResponse": None, "uptime": 100},
        {"name": "alpha-backend", "cpu": 52, "memory": 64, "diskIO": 35, "dbLatency": 18, "apiResponse": 120, "uptime": 99.92},
        {"name": "beta-service", "cpu": 78, "memory": 85, "diskIO": 55, "dbLatency": 38, "apiResponse": 245, "uptime": 98.8},
    ],
    "uptime_history": [
        {"week": "W1", "uptime": 99.95},
        {"week": "W2", "uptime": 99.97},
        {"week": "W3", "uptime": 99.80},
        {"week": "W4", "uptime": 99.99},
        {"week": "W5", "uptime": 99.92},
        {"week": "W6", "uptime": 99.96},
    ],
    "sla_breaches": [
        {"service": "beta-service", "breach": "Uptime dropped below 99.9% SLA", "time": "Feb 19, 3:00 PM", "severity": "High"},
        {"service": "DB Primary", "breach": "Memory usage exceeded 90% threshold", "time": "Feb 20, 6:20 AM", "severity": "Medium"},
    ],
    "dependencies": [
        {"from": "API Gateway", "to": "Auth Service", "status": "healthy"},
        {"from": "API Gateway", "to": "alpha-backend", "status": "healthy"},
        {"from": "alpha-backend", "to": "DB Primary", "status": "degraded"},
        {"from": "alpha-backend", "to": "Cache Redis", "status": "healthy"},
        {"from": "beta-service", "to": "DB Primary", "status": "unhealthy"},
        {"from": "beta-service", "to": "Cache Redis", "status": "healthy"},
    ]
}

DEVOPS_TASKS = [
    {
        "id": 1, "story": "Deploy alpha-backend v2.4.1", "type": "Deployment", "env": "Production", "status": "Done",
        "alignment": 94, "ciAligned": True, "deployTriggered": True, "filesCorrect": True,
        "aiNote": "Deployment matched expected CI pipeline. All file changes align with the story scope."
    },
    {
        "id": 2, "story": "Update Redis config for beta-service", "type": "Infra Change", "env": "Staging", "status": "In Progress",
        "alignment": 72, "ciAligned": True, "deployTriggered": False, "filesCorrect": False,
        "aiNote": "Warning: Config changes detected in files outside of task scope. Possible scope drift."
    },
    {
        "id": 3, "story": "Set up Prometheus monitoring for gamma-frontend", "type": "Monitoring Setup", "env": "All", "status": "To Do",
        "alignment": 0, "ciAligned": False, "deployTriggered": False, "filesCorrect": False,
        "aiNote": "No CI activity detected yet for this story."
    },
    {
        "id": 4, "story": "Apply security patch CVE-2025-1234", "type": "Security Patch", "env": "Production", "status": "Done",
        "alignment": 88, "ciAligned": True, "deployTriggered": True, "filesCorrect": True,
        "aiNote": "Security patch applied cleanly. CI logs confirm patched dependencies in lockfile."
    },
    {
        "id": 5, "story": "Scale Kubernetes pods for API Gateway", "type": "Infra Change", "env": "Production", "status": "Done",
        "alignment": 96, "ciAligned": True, "deployTriggered": True, "filesCorrect": True,
        "aiNote": "Infrastructure change fully aligned. Replica count matches HPA thresholds."
    },
    {
        "id": 6, "story": "Rotate SSL certificates for api.example.com", "type": "Security Patch", "env": "Production", "status": "In Progress",
        "alignment": 60, "ciAligned": False, "deployTriggered": False, "filesCorrect": True,
        "aiNote": "Certificate renewal initiated but CI pipeline not triggered. Manual deployment required."
    }
]

DEVOPS_INCIDENTS = [
    {
        "id": "INC-001", "incident": "Production database connection pool exhaustion", "severity": "Critical",
        "service": "DB Primary", "openedAt": "Feb 20, 06:20 AM", "resolvedAt": "Feb 20, 08:05 AM",
        "rootCause": "Leaked connections from beta-service due to missing connection.release() calls",
        "mttd": "8m", "mttr": "1h 45m", "mttrMinutes": 105, "repeat": False,
        "aiSummary": "Incident caused by connection leak in beta-service. Missing connection.release() in 3 API handlers. Recommend adding connection pool monitoring."
    },
    {
        "id": "INC-002", "incident": "Auth service 503 errors during login", "severity": "High",
        "service": "auth-service", "openedAt": "Feb 19, 08:30 AM", "resolvedAt": "Feb 19, 09:15 AM",
        "rootCause": "JWT signing key rotation triggered during peak hours",
        "mttd": "3m", "mttr": "45m", "mttrMinutes": 45, "repeat": False,
        "aiSummary": "Key rotation executed during peak login window (8-9 AM). Recommend scheduling rotations during off-peak hours (2-4 AM)."
    },
    {
        "id": "INC-003", "incident": "Staging deployment failure for beta-service", "severity": "Medium",
        "service": "beta-service", "openedAt": "Feb 18, 02:00 PM", "resolvedAt": "Feb 18, 03:30 PM",
        "rootCause": "Docker image tag mismatch between CI and deployment manifest",
        "mttd": "15m", "mttr": "1h 30m", "mttrMinutes": 90, "repeat": True,
        "aiSummary": "Repeat incident: Docker image tag inconsistency. Same root cause as INC-007 from Sprint 10. Automate image tag pinning in CI pipeline."
    },
    {
        "id": "INC-004", "incident": "SSL certificate expired for staging API", "severity": "High",
        "service": "API Gateway", "openedAt": "Feb 17, 11:00 PM", "resolvedAt": "Feb 18, 01:00 AM",
        "rootCause": "Auto-renewal cron job disabled after infrastructure migration",
        "mttd": "2h", "mttr": "2h", "mttrMinutes": 120, "repeat": False,
        "aiSummary": "SSL auto-renewal was disabled after Terraform migration. Add Certbot renewal to IaC and set up certificate expiry alerts at 30/14/7 day thresholds."
    },
    {
        "id": "INC-005", "incident": "Memory spike causing API Gateway restarts", "severity": "Critical",
        "service": "API Gateway", "openedAt": "Feb 16, 10:00 AM", "resolvedAt": "Feb 16, 12:30 PM",
        "rootCause": "Unbounded in-memory cache for session data",
        "mttd": "5m", "mttr": "2h 30m", "mttrMinutes": 150, "repeat": True,
        "aiSummary": "Repeat incident: Memory leak from session cache. Previously mitigated by increasing RAM, but root fix requires implementing LRU eviction policy."
    }
]

DEVOPS_INFRA_CHANGES = [
    {"id": 1, "type": "Docker Config Update", "service": "alpha-backend", "changedBy": "Vikram Singh", "timestamp": "Feb 20, 07:30 AM", "risk": "Low", "approved": True, "details": "Updated base image from node:18 to node:20-alpine"},
    {"id": 2, "type": "Kubernetes Scaling", "service": "API Gateway", "changedBy": "Ananya Reddy", "timestamp": "Feb 19, 06:15 PM", "risk": "Medium", "approved": True, "details": "Scaled replicas from 3 to 5 for peak traffic"},
    {"id": 3, "type": "Environment Variable", "service": "beta-service", "changedBy": "Karan Joshi", "timestamp": "Feb 19, 03:45 PM", "risk": "High", "approved": False, "details": "Changed DB_HOST without approval — possible unauthorized change"},
    {"id": 4, "type": "Terraform Modification", "service": "Infrastructure", "changedBy": "Meera Nair", "timestamp": "Feb 18, 11:20 AM", "risk": "High", "approved": True, "details": "Modified VPC subnet allocation for staging environment"},
    {"id": 5, "type": "Docker Config Update", "service": "notification-svc", "changedBy": "Rahul Verma", "timestamp": "Feb 18, 09:00 AM", "risk": "Low", "approved": True, "details": "Added health check endpoint to Dockerfile"},
    {"id": 6, "type": "Kubernetes Scaling", "service": "Cache Redis", "changedBy": "System (Auto)", "timestamp": "Feb 17, 11:55 PM", "risk": "Low", "approved": True, "details": "Auto-scale triggered: memory usage exceeded 85%"},
    {"id": 7, "type": "Environment Variable", "service": "auth-service", "changedBy": "Vikram Singh", "timestamp": "Feb 17, 04:30 PM", "risk": "Medium", "approved": True, "details": "Rotated JWT_SECRET key across all environments"},
    {"id": 8, "type": "Terraform Modification", "service": "Infrastructure", "changedBy": "Unknown", "timestamp": "Feb 16, 02:00 AM", "risk": "High", "approved": False, "details": "Security group rules modified — drift detected from IaC state"},
]

DEVOPS_LOGS = [
    {"id": 1, "category": "Error", "severity": "Critical", "service": "beta-service", "message": "NullPointerException in PaymentProcessor.java:142", "timestamp": "Feb 20, 08:12 AM", "count": 48},
    {"id": 2, "category": "Error", "severity": "High", "service": "alpha-backend", "message": "Connection refused: Redis cluster unreachable on port 6379", "timestamp": "Feb 20, 07:55 AM", "count": 12},
    {"id": 3, "category": "Warning", "severity": "Medium", "service": "API Gateway", "message": "Rate limit threshold reached for /api/v2/users endpoint", "timestamp": "Feb 20, 07:30 AM", "count": 156},
    {"id": 4, "category": "Security", "severity": "Critical", "service": "auth-service", "message": "Suspicious login attempt: 15 failed logins from IP 192.168.1.45", "timestamp": "Feb 20, 06:45 AM", "count": 15},
    {"id": 5, "category": "Memory", "severity": "High", "service": "DB Primary", "message": "Memory usage at 92% — approaching OOM threshold", "timestamp": "Feb 20, 06:20 AM", "count": 1},
    {"id": 6, "category": "Warning", "severity": "Low", "service": "notification-svc", "message": "Deprecated API call to /v1/push — migration to v2 recommended", "timestamp": "Feb 19, 11:30 PM", "count": 89},
    {"id": 7, "category": "Security", "severity": "Medium", "service": "Infrastructure", "message": "SSL certificate for api.example.com expires in 7 days", "timestamp": "Feb 19, 10:00 PM", "count": 1},
    {"id": 8, "category": "Error", "severity": "High", "service": "gamma-frontend", "message": "Webpack build failed: Module not found @components/Chart", "timestamp": "Feb 19, 08:15 PM", "count": 3},
    {"id": 9, "category": "Memory", "severity": "Medium", "service": "Cache Redis", "message": "Eviction rate spiked to 450 keys/sec — consider increasing maxmemory", "timestamp": "Feb 19, 06:00 PM", "count": 1},
    {"id": 10, "category": "Warning", "severity": "Low", "service": "alpha-backend", "message": "Slow query detected: SELECT * FROM analytics_events took 4.2s", "timestamp": "Feb 19, 04:30 PM", "count": 7},
]

DEVOPS_LOGS_METRICS = {
    "type": "logs_metrics",
    "ai_analysis": [
        {"text": "Memory spike pattern detected before backend crash. Recommend increasing RAM allocation for DB Primary to 16GB.", "type": "danger"},
        {"text": "Redis connection failures correlate with high traffic periods (8-9 AM). Implement connection pooling.", "type": "warning"},
        {"text": "SSL certificate expiry alert — auto-renewal should be configured via Certbot or AWS ACM.", "type": "warning"},
        {"text": "Suspicious login pattern from IP 192.168.1.45 matches known brute-force signature. Consider IP blocking.", "type": "danger"},
    ]
}

DEVOPS_REPORTS = [
    {"id": "OPS-REP-01", "title": "SRE Incident & Root Cause Review", "desc": "Sprint 24 MTTR analysis, recurrence breakdown, and post-mortem tracking.", "lastGenerated": "Today at 8:00 AM", "status": "Ready"},
    {"id": "OPS-REP-02", "title": "CI/CD Pipeline Reliability Audit", "desc": "Build durations, stage bottlenecks, and flaky test impact across all squads.", "lastGenerated": "Yesterday at 5:00 PM", "status": "Ready"},
    {"id": "OPS-REP-03", "title": "Cloud Infrastructure Cost & Drift Report", "desc": "Resource utilization, idle instances, and IaC Terraform drift detection.", "lastGenerated": "Sep 28, 2026", "status": "Ready"},
]

DEVOPS_REPORTS_CHARTS = {
    "type": "charts",
    "incident_by_severity": [
        {"name": "Critical", "value": 2, "color": "#ef4444"},
        {"name": "High", "value": 2, "color": "#f97316"},
        {"name": "Medium", "value": 1, "color": "#f59e0b"},
    ],
    "pipeline_success": [
        {"name": "alpha-BE CI", "rate": 92},
        {"name": "gamma-FE CI", "rate": 96},
        {"name": "beta-svc CD", "rate": 68},
        {"name": "infra-TF", "rate": 98},
        {"name": "alpha-BE CD", "rate": 88},
        {"name": "monitor", "rate": 72},
    ]
}

BUGS = [
    {
        "id": "BUG-101",
        "title": "JWT Token Expiration does not trigger automatic silent refresh on Kanban board",
        "description": "When session reaches 60 minutes, dragging a task in board silently fails without refreshing token.",
        "severity": "HIGH",
        "status": "OPEN",
        "component": "frontend/auth",
        "project_name": "Core Platform",
        "assignee": "dev_admin",
        "reported_by": "QA Engineer",
        "service": "Frontend Web",
        "created_at": "2026-02-18T10:00:00Z"
    },
    {
        "id": "BUG-102",
        "title": "Null pointer exception when calculating code quality score with 0 findings",
        "description": "Backend returns 500 error instead of default score 100 when repository has clean analysis run.",
        "severity": "CRITICAL",
        "status": "IN_PROGRESS",
        "component": "backend/code_quality",
        "project_name": "Intelligence Engine",
        "assignee": "lead_admin",
        "reported_by": "Lead Architect",
        "service": "Backend API",
        "created_at": "2026-02-19T14:30:00Z"
    },
    {
        "id": "BUG-103",
        "title": "Avatar initial letter lowercase on profile view with single name",
        "description": "Single word usernames display in lowercase instead of capitalized initials.",
        "severity": "LOW",
        "status": "RESOLVED",
        "component": "frontend/profile",
        "project_name": "Core Platform",
        "assignee": "dev_admin",
        "reported_by": "QA Lead",
        "service": "Core UI",
        "created_at": "2026-02-19T16:45:00Z"
    },
    {
        "id": "BUG-104",
        "title": "Payment rollback error on card failure",
        "description": "Transactions fail to rollback cleanly on card decline.",
        "severity": "CRITICAL",
        "status": "OPEN",
        "component": "backend/payments",
        "project_name": "FinTech Core",
        "assignee": "dev_admin",
        "reported_by": "qa_admin",
        "service": "Payment Gateway",
        "created_at": "2026-02-20T09:15:00Z"
    },
]

ALERTS = [
    {"id": "ALT-01", "type": "warning", "message": "High memory allocation detected on worker node-2", "timestamp": "12 mins ago"},
    {"id": "ALT-02", "type": "info", "message": "Daily automated backup completed successfully", "timestamp": "3 hours ago"},
    {"id": "ALT-03", "type": "error", "message": "Database replica sync latency reached 450ms", "timestamp": "5 hours ago"},
]

OFFENSE_BREAKDOWN = [
    {"type": "Unplanned Scope Additions", "count": 4, "severity": "Medium"},
    {"type": "Ticket Re-estimation Drift", "count": 2, "severity": "Low"},
    {"type": "Context Switching Between Squads", "count": 3, "severity": "Medium"},
    {"type": "Blocked Dependencies", "count": 1, "severity": "High"}
]

SCOPE_DRIFT = [
    {"sprint": "Sprint 20", "planned": 40, "actual": 42, "drift": "+5.0%"},
    {"sprint": "Sprint 21", "planned": 45, "actual": 47, "drift": "+4.4%"},
    {"sprint": "Sprint 22", "planned": 50, "actual": 51, "drift": "+2.0%"},
    {"sprint": "Sprint 23", "planned": 48, "actual": 50, "drift": "+4.1%"},
    {"sprint": "Sprint 24", "planned": 52, "actual": 53, "drift": "+1.9%"}
]

# ── Dynamic Collections for CEO, PM, QA, DevOps, Developer & Landing ──

CEO_RISK_PATTERNS = [
    {
        "id": "CRP-01",
        "title": "Sprint End Testing Crunch",
        "color": "#ef4444",
        "occurrences": 4,
        "sprints": "Sprint 20, 21, 22, 23",
        "impact": "28% of stories tested on final 2 sprint days",
        "recommendation": "Enforce mid-sprint WIP limits and introduce progressive story sign-off gates."
    },
    {
        "id": "CRP-02",
        "title": "Third-Party Dependency Latency",
        "color": "#f59e0b",
        "occurrences": 3,
        "sprints": "Sprint 21, 22, 23",
        "impact": "Average 1.8 days delay per dependent story",
        "recommendation": "Create mock integration environments during sprint kickoff to prevent blocking."
    },
    {
        "id": "CRP-03",
        "title": "PR Review Asymmetry",
        "color": "#8b5cf6",
        "occurrences": 5,
        "sprints": "Sprint 19, 20, 21, 22, 23",
        "impact": "70% of code reviews concentrated on 2 tech leads",
        "recommendation": "Establish peer rotation program for code reviews to distribute knowledge and velocity."
    }
]

RETRO_IMPROVEMENTS = [
    {"id": "IMP-01", "category": "went_well", "text": "All 4 high-priority epic deliverables released on schedule for Sprint 23."},
    {"id": "IMP-02", "category": "went_well", "text": "Zero production downtime during database indexing migrations."},
    {"id": "IMP-03", "category": "went_well", "text": "Continuous integration test execution time reduced by 34% with caching."},
    {"id": "IMP-04", "category": "didnt_go_well", "text": "PR turnaround time averaged 16 hours during the middle sprint cycle."},
    {"id": "IMP-05", "category": "didnt_go_well", "text": "Frontend story STY-108 required architectural re-scoping midway through."},
    {"id": "IMP-06", "category": "improvement", "action": "Enforce strict WIP limits of maximum 2 active stories per engineer", "impact": "High", "owner": "PM & Tech Lead"},
    {"id": "IMP-07", "category": "improvement", "action": "Automate contract testing for microservices to catch breaking changes early", "impact": "High", "owner": "DevOps"},
    {"id": "IMP-08", "category": "improvement", "action": "Conduct asynchronous 5-minute standup summaries to save meeting overhead", "impact": "Medium", "owner": "Scrum Master"},
]

CEO_BEHAVIOUR_FEEDBACK = [
    {
        "id": "CBF-01",
        "aiSummary": "Engineering velocity remains resilient at 94% sprint goal alignment. Cross-functional collaboration across frontend and backend squads is at an all-time peak.",
        "member": "Vikram Singh",
        "role": "Senior Full-Stack Engineer",
        "ownership": 9.2,
        "velocity": 9.5,
        "quality": 9.0,
        "feedback": "Outstanding architectural leadership during the high-load telemetry refactor.",
        "score": 9.2
    },
    {
        "id": "CBF-02",
        "aiSummary": "Engineering velocity remains resilient at 94% sprint goal alignment.",
        "member": "Neha Sharma",
        "role": "Backend Engineer",
        "ownership": 8.8,
        "velocity": 9.0,
        "quality": 9.3,
        "feedback": "High attention to detail on database query optimization and error logging.",
        "score": 9.0
    },
    {
        "id": "CBF-03",
        "aiSummary": "Engineering velocity remains resilient at 94% sprint goal alignment.",
        "member": "Arjun Mehta",
        "role": "Frontend Architect",
        "ownership": 9.4,
        "velocity": 8.9,
        "quality": 9.6,
        "feedback": "Proactive communication and rapid turnaround on design token integrations.",
        "score": 9.3
    }
]

PM_WORKLOAD = [
    {"id": "WL-01", "member": "Vikram Singh", "role": "Senior Developer", "assigned_stories": 3, "story_points": 14, "capacity": 15, "utilization": 93, "status": "OPTIMAL"},
    {"id": "WL-02", "member": "Neha Sharma", "role": "Backend Developer", "assigned_stories": 4, "story_points": 18, "capacity": 15, "utilization": 120, "status": "OVERLOADED"},
    {"id": "WL-03", "member": "Arjun Mehta", "role": "Frontend Developer", "assigned_stories": 2, "story_points": 8, "capacity": 15, "utilization": 53, "status": "AVAILABLE"},
    {"id": "WL-04", "member": "Sneha Iyer", "role": "Full Stack Developer", "assigned_stories": 3, "story_points": 12, "capacity": 15, "utilization": 80, "status": "OPTIMAL"},
]

PM_HIGH_RISK_MEMBERS = [
    {"id": "HRM-01", "name": "Neha Sharma", "role": "Backend Developer", "risk_factors": ["Over capacity by 20%", "2 blocking stories"], "risk_level": "HIGH"},
    {"id": "HRM-02", "name": "Vikram Singh", "role": "Senior Developer", "risk_factors": ["Complex OAuth epic dependency"], "risk_level": "MEDIUM"},
]

PM_RETRO_SUMMARY = {
    "type": "pm_retro_summary",
    "sprint": "Sprint 23",
    "velocity": 48.5,
    "committed": 52,
    "completed": 49,
    "completion_rate": 94.2,
    "carryover_points": 3,
    "total_bugs": 2
}

PM_AI_SUGGESTIONS = [
    {"id": "SUG-01", "title": "Rebalance Backlog Story Distribution", "detail": "Reassign STY-112 to Arjun Mehta to reduce Neha's capacity pressure from 120% to 95%.", "impact": "High"},
    {"id": "SUG-02", "title": "Automate Release Smoke Tests", "detail": "Add smoke test pipeline gate on staging merge to prevent regression rollbacks.", "impact": "Medium"}
]

PM_DELAY_DISTRIBUTION = [
    {"range": "< 1 day", "count": 14},
    {"range": "1-2 days", "count": 22},
    {"range": "3-5 days", "count": 8},
    {"range": "> 5 days", "count": 3}
]

ORGANIZATION_RISKS = [
    {
        "id": "RISK-01",
        "category": "Delivery Schedule",
        "title": "Sprint 25 story points completion trailing behind planned burndown",
        "project": "Core Platform",
        "project_id": "PRJ-01",
        "status": "open",
        "risk_level": "HIGH",
        "impact": "Potential 4-day slippage in public release date if not remediated.",
        "mitigation": "Reassign 2 non-critical stories to Sprint 26; allocate senior lead review time.",
        "owner": "Marcus Vance",
        "created_at": datetime.now(timezone.utc).isoformat()
    },
    {
        "id": "RISK-02",
        "category": "Technical Architecture",
        "title": "Cyclomatic complexity in auth middleware exceeding safe thresholds",
        "project": "Security Engine",
        "project_id": "PRJ-02",
        "status": "open",
        "risk_level": "MEDIUM",
        "impact": "Elevated regression risk during token refresh and session invalidation.",
        "mitigation": "Refactor role-guard dispatch into segregated handler strategy.",
        "owner": "Vikram Singh",
        "created_at": datetime.now(timezone.utc).isoformat()
    },
    {
        "id": "RISK-03",
        "category": "Operational / CI/CD",
        "title": "Staging deployment failure rate increased over the last 48 hours",
        "project": "Infrastructure",
        "project_id": "PRJ-01",
        "status": "open",
        "risk_level": "HIGH",
        "impact": "DevOps team unblocking queue; slows QA validation turnarounds.",
        "mitigation": "Apply patch for npm packaging drift and pin transient rollup dependencies.",
        "owner": "Jordan Hayes",
        "created_at": datetime.now(timezone.utc).isoformat()
    },
    {
        "id": "RISK-04",
        "category": "Security Vulnerability",
        "title": "Outdated sub-dependency with known CVE in third-party parser",
        "project": "Code Quality Engine",
        "project_id": "PRJ-03",
        "status": "open",
        "risk_level": "LOW",
        "impact": "Contained to isolated sandbox analyzer run.",
        "mitigation": "Automated dependabot PR generated; pending Lead approval.",
        "owner": "Elena Rostova",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
]

QA_TEST_SUITES = [
    {"id": "ts-1", "name": "Unit Tests: Core Auth & RBAC", "type": "Unit", "run": 142, "passed": 142, "failed": 0, "duration": "4.2s", "status": "passed"},
    {"id": "ts-2", "name": "Integration: Tasks & Sprint APIs", "type": "Integration", "run": 68, "passed": 67, "failed": 1, "duration": "12.8s", "status": "failed"},
    {"id": "ts-3", "name": "E2E: Developer Workflow & PR Sync", "type": "E2E", "run": 35, "passed": 35, "failed": 0, "duration": "45.1s", "status": "passed"},
    {"id": "ts-4", "name": "Security: Token Expiry & Permission Escalation", "type": "Security", "run": 24, "passed": 24, "failed": 0, "duration": "6.4s", "status": "passed"},
    {"id": "ts-5", "name": "Performance: MongoDB Query Latency & Indexing", "type": "Performance", "run": 18, "passed": 18, "failed": 0, "duration": "18.9s", "status": "passed"},
]

QA_TEST_HEALTH = {
    "type": "qa_test_health",
    "summary": {
        "total_test_cases": 287,
        "passed_tests": 286,
        "failed_tests": 1,
        "pass_rate": 99.6,
        "avg_duration": "17.4s",
        "flaky_tests": 2
    },
    "suites": QA_TEST_SUITES,
    "chartData": [
        {"suite": "Core Auth", "passed": 142, "failed": 0},
        {"suite": "Tasks/Sprints", "passed": 67, "failed": 1},
        {"suite": "Workflow E2E", "passed": 35, "failed": 0},
        {"suite": "Security Checks", "passed": 24, "failed": 0},
        {"suite": "Performance", "passed": 18, "failed": 0},
    ]
}

QA_REGRESSION_METRICS = {
    "type": "qa_regression_metrics",
    "sprintRegression": [
        {"sprint": "S8", "passRate": 88},
        {"sprint": "S9", "passRate": 82},
        {"sprint": "S10", "passRate": 90},
        {"sprint": "S11", "passRate": 78},
        {"sprint": "S12", "passRate": 96},
    ],
    "aiInsights": [
        {"text": "Payment regression failing 3 sprints consecutively. Possible unstable backend logic in PaymentProcessor.", "type": "danger"},
        {"text": "Dashboard module has 2 flaky tests. Investigate CSS animation timing in chart re-renders.", "type": "warning"},
        {"text": "Authentication and User Management modules are stable with 94%+ pass rate.", "type": "success"},
    ]
}

PM_ANALYTICS = {
    "type": "pm_analytics",
    "velocityData": [
        {"sprint": "Sprint 21", "planned": 45, "completed": 42},
        {"sprint": "Sprint 22", "planned": 50, "completed": 48},
        {"sprint": "Sprint 23", "planned": 52, "completed": 51},
        {"sprint": "Sprint 24", "planned": 48, "completed": 46},
        {"sprint": "Sprint 25 (Active)", "planned": 55, "completed": 34},
    ],
    "burndownData": [
        {"day": "Day 1", "ideal": 55, "actual": 55},
        {"day": "Day 3", "ideal": 44, "actual": 48},
        {"day": "Day 5", "ideal": 33, "actual": 39},
        {"day": "Day 7", "ideal": 22, "actual": 28},
        {"day": "Day 9", "ideal": 11, "actual": 16},
        {"day": "Day 10", "ideal": 0, "actual": 12},
    ],
    "taskStatusData": [
        {"name": "Completed", "value": 34, "color": "var(--success)"},
        {"name": "In Progress", "value": 12, "color": "var(--info)"},
        {"name": "Review", "value": 5, "color": "var(--warning)"},
        {"name": "To Do", "value": 14, "color": "var(--text-muted)"},
    ]
}

HOMEPAGE_DATA = {
    "type": "homepage_data",
    "features": [
        {
            "num": "01",
            "title": "Custom Workspace",
            "desc": "Describe how you work, and shape the board, fields, and views around it. Built for any kind of work, not only what comes out of the box.",
            "imageUrl": "/features/01-workspace.jpg",
            "badge": "Workspace"
        },
        {
            "num": "02",
            "title": "Sprint Planning",
            "desc": "Turn sprint goals into a hybrid human-agent execution loop with real-time velocity tracking and automated story allocation.",
            "imageUrl": "/features/02-sprint-planning.jpg",
            "hasShare": True,
            "badge": "Agile Board"
        },
        {
            "num": "03",
            "title": "Product Roadmap",
            "desc": "Initiatives laid across quarters, grouped by team or theme with multi-team dependency tracking and critical path highlighting.",
            "imageUrl": "/features/03-roadmap.jpg",
            "badge": "Roadmap"
        },
        {
            "num": "04",
            "title": "Bug Tracker",
            "desc": "Severity, reproduction steps, error logs, and verification status in one clean, prioritized triage and resolution queue.",
            "imageUrl": "/features/04-bug-tracker.jpg",
            "badge": "Quality QA"
        },
        {
            "num": "05",
            "title": "Content & Release Calendar",
            "desc": "Every milestone, scheduled deploy, and release freeze date color-coded by channel, environment, and tier.",
            "imageUrl": "/features/05-release-calendar.jpg",
            "badge": "Releases"
        },
        {
            "num": "06",
            "title": "Sales & Delivery Pipeline",
            "desc": "Leads and feature branches staged as a funnel with value, cycle time, and throughput tracked at every milestone.",
            "imageUrl": "/features/06-pipeline-funnel.jpg",
            "badge": "Funnel"
        },
        {
            "num": "07",
            "title": "OKR Tracker",
            "desc": "One objective, a few key results, and delivery progress rolled up automatically from completed developer and sprint tasks.",
            "imageUrl": "/features/07-okr-tracker.jpg",
            "badge": "Objectives"
        },
        {
            "num": "08",
            "title": "Event & Milestone Planning",
            "desc": "Checklists, tech summits, demo days, and townhall details all in one shared organizational calendar before launch.",
            "imageUrl": "/features/08-event-planning.jpg",
            "badge": "Events"
        },
        {
            "num": "09",
            "title": "Hiring Pipeline",
            "desc": "Candidates moving through interview stages, technical evaluation, take-home reviews, ending in an executive offer.",
            "imageUrl": "/features/09-hiring-pipeline.jpg",
            "badge": "Talent HR"
        },
        {
            "num": "10",
            "title": "Client & Dev Onboarding",
            "desc": "A fixed sequence of setup steps, repo access tokens, and starter PRs so nothing gets skipped during team expansion.",
            "imageUrl": "/features/10-dev-onboarding.jpg",
            "badge": "Onboarding"
        }
    ],
    "events": [
        {"title": "Karnataka Cultural Festival & Folk Gala", "date": "Dec 20, 2025", "location": "Bengaluru HQ (Whitefield)", "color": "#2563eb"},
        {"title": "Annual Tech Summit 2026", "date": "Jan 15, 2026", "location": "Bengaluru HQ (Whitefield)", "color": "#7c3aed"},
        {"title": "Karnataka Innovation Sprint & Hackathon", "date": "Feb 01, 2026", "location": "Bengaluru Campus (Whitefield)", "color": "#10b981"},
        {"title": "Executive Leadership Workshop", "date": "Nov 10, 2025", "location": "Whitefield Campus", "color": "#f59e0b"}
    ],
    "branches": [
        {"city": "Bengaluru", "type": "Headquarters", "employees": 580, "address": "ITPB, Whitefield", "images": ["/branches/bengaluru-1.jpg", "/branches/bengaluru-2.jpg"]},
        {"city": "Hyderabad", "type": "Technology Center", "employees": 380, "address": "HITEC City, Madhapur", "images": ["/branches/hyderabad-1.jpg", "/branches/hyderabad-2.jpg"]},
        {"city": "Mumbai", "type": "Regional Office", "employees": 180, "address": "BKC, Bandra East", "images": ["/branches/mumbai-1.jpg", "/branches/mumbai-2.jpg"]},
        {"city": "Delhi NCR", "type": "Regional Office", "employees": 150, "address": "Cyber City, Gurgaon", "images": ["/branches/delhi-1.jpg", "/branches/delhi-2.jpg"]},
        {"city": "Pune", "type": "Development Center", "employees": 200, "address": "Hinjewadi IT Park", "images": ["/branches/pune-1.jpg", "/branches/pune-2.jpg"]},
        {"city": "Chennai", "type": "Support Center", "employees": 120, "address": "Tidel Park, Taramani", "images": ["/branches/chennai-1.jpg", "/branches/chennai-2.jpg"]}
    ],
    "workspaceCategories": [
        {"title": "Modern Workspaces", "subtitle": "Ergonomic Desks & Focus Pods", "badge": "Agile Office", "images": ["/workspaces/modern-1.jpg", "/workspaces/modern-2.jpg", "/workspaces/modern-3.jpg"]},
        {"title": "Collaboration Zones", "subtitle": "Breakout Lounges & Brainstorming", "badge": "Team Sync", "images": ["/workspaces/collab-1.jpg", "/workspaces/collab-2.jpg", "/workspaces/collab-3.jpg"]},
        {"title": "Innovation Labs", "subtitle": "High-Tech Multi-Screen R&D", "badge": "Engineering", "images": ["/workspaces/innov-1.jpg", "/workspaces/innov-2.jpg", "/workspaces/innov-3.jpg"]},
        {"title": "Training Centers", "subtitle": "Interactive Auditoriums & Workshops", "badge": "Learning Hub", "images": ["/workspaces/training-1.jpg", "/workspaces/training-2.jpg", "/workspaces/training-3.jpg"]}
    ],
    "companyEventsCategories": [
        {"title": "Annual Tech Summit 2026", "subtitle": "Keynotes, System Scale & Panels", "badge": "Engineering", "images": ["/events/tech-summit.jpg", "/events/tech-1.jpg", "/events/tech-2.jpg"]},
        {"title": "Innovation Hackathon", "subtitle": "48h Sprint & Prototype Finals", "badge": "Hackathon", "images": ["/events/hackathon.jpg", "/events/hackathon-1.jpg", "/events/hackathon-2.jpg"]},
        {"title": "Leadership Strategy Offsite", "subtitle": "Executive Roadmaps & Alignment", "badge": "Leadership", "images": ["/events/team-building.jpg", "/events/lead-1.jpg", "/events/lead-2.jpg"]},
        {"title": "Annual Excellence Awards", "subtitle": "Star Performers & Team Trophies", "badge": "Recognition", "images": ["/events/award-ceremony.jpg", "/events/awards-1.jpg", "/events/awards-2.jpg"]},
        {"title": "Sports & Fitness Carnival", "subtitle": "Cricket Cup, Relays & Games", "badge": "Wellness", "images": ["/events/sports-day.jpg", "/events/sports-1.jpg", "/events/sports-2.jpg"]},
        {"title": "Product Demo & Showcase", "subtitle": "Sprint Milestones & Live Demos", "badge": "Product Launch", "images": ["/events/demo-1.jpg", "/events/demo-2.jpg", "/events/cultural-night.jpg"]}
    ],
    "culturalCategories": [
        {"title": "Yakshagana Dance Fest", "subtitle": "Coastal Folk Theater & Lore", "badge": "Folk Theater", "images": ["/events/yakshagana.jpg", "/events/yakshagana-2.jpg", "/events/yakshagana-3.jpg"]},
        {"title": "Mysore Dasara Gala", "subtitle": "Illuminated Palace & Royal Utsav", "badge": "Royal Heritage", "images": ["/events/mysore-palace.jpg", "/events/mysore-1.jpg", "/events/mysore-2.jpg"]},
        {"title": "Dollu Kunitha Folk Art", "subtitle": "Traditional Drum Beats & Dance", "badge": "Folk Percussion", "images": ["/events/dollu-kunitha.jpg", "/events/dollu-1.jpg", "/events/dollu-3.jpg"]},
        {"title": "Hampi Heritage Summit", "subtitle": "UNESCO Stone Chariot & Ruins", "badge": "World Heritage", "images": ["/events/hampi.jpg", "/events/hampi-1.jpg", "/events/hampi-2.jpg"]},
        {"title": "Kambala Cultural Night", "subtitle": "Traditional Coastal Buffalo Race", "badge": "Folk Sport", "images": ["/events/kambala.jpg", "/events/kambala-1.jpg", "/events/kambala-3.jpg"]},
        {"title": "Karnataka Rajyotsava Gala", "subtitle": "State Celebration & Folk Music", "badge": "State Festival", "images": ["/events/rajyotsava-2.jpg", "/events/rajyotsava-3.jpg", "/events/cultural-night.jpg"]}
    ],
    "teamMembers": [
        {
            "name": "Mallikarjun",
            "role": "Full-Stack Lead & Platform Architect",
            "tag": "Core Platform",
            "bio": "Spearheading core architecture, scalable distributed microservices, and enterprise execution workflows.",
            "image": "/team/mallikarjun.png",
            "skills": ["React", "FastAPI", "System Architecture", "Agile Workflows"]
        },
        {
            "name": "Mounesh S.D",
            "role": "Backend & Data Infrastructure Lead",
            "tag": "Data & Cloud",
            "bio": "Leading high-throughput telemetry pipelines, database optimization, and secure role-based access.",
            "image": "/team/mounesh.png",
            "skills": ["Python", "PostgreSQL", "MongoDB", "Cloud Ops"]
        },
        {
            "name": "Shreyas K.T",
            "role": "Frontend Architect & UI/UX Specialist",
            "tag": "UI/UX Design",
            "bio": "Crafting responsive execution dashboards, micro-interactions, and visual interactive boards.",
            "image": "/team/shreyas.png",
            "skills": ["React", "CSS Architecture", "UI/UX Design", "Performance"]
        },
        {
            "name": "Sumitkumar Hosalli",
            "role": "AI/ML & Agentic Systems Engineer",
            "tag": "AIML & Decision AI",
            "bio": "Architecting LLM pipelines, autonomous reasoning agents, predictive overtime analytics, and smart telemetry.",
            "image": "/team/sumit.png",
            "skills": ["PyTorch", "Agentic AI", "LangChain", "FastAPI", "FARM Stack"],
            "links": {
                "github": "https://github.com/sumithosalli",
                "linkedin": "https://www.linkedin.com/in/sumitkumar-hosalli",
                "portfolio": "https://sumitkumar-portfolio-kohl.vercel.app"
            }
        }
    ]
}


async def seed():

    print("[*] Seeding Samanvaya Database from scratch...")
    password_hash = hash_password("password123")

    # 1. Companies (Multi-Tenant)
    companies_col = col("companies")
    for c in COMPANIES:
        await companies_col.update_one({"id": c["id"]}, {"$set": c}, upsert=True)
    print(f"  + Seeded {len(COMPANIES)} companies")

    # 2. Teams
    teams_col = col("teams")
    for t in TEAMS:
        await teams_col.update_one({"team_id": t["team_id"]}, {"$set": t}, upsert=True)
    print(f"  + Seeded {len(TEAMS)} teams")

    # 3. Users / Employees
    users_col = col("users")
    for u in ROLES_USERS:
        doc = {
            **u,
            "organisation_password": password_hash,
            "employee_password": password_hash,
            "organisation_password_hash": password_hash,
            "employee_password_hash": password_hash,
        }
        await users_col.update_one({"employee_id": u["employee_id"]}, {"$set": doc}, upsert=True)
    print(f"  + Seeded {len(ROLES_USERS)} users")

    # 4. Projects
    projects_col = col("projects")
    for p in PROJECTS:
        await projects_col.update_one({"id": p["id"]}, {"$set": p}, upsert=True)
    print(f"  + Seeded {len(PROJECTS)} projects")

    # 5. Sprints
    sprints_col = col("sprints")
    for s in SPRINTS:
        await sprints_col.update_one({"id": s["id"]}, {"$set": s}, upsert=True)
    print(f"  + Seeded {len(SPRINTS)} sprints")

    # 6. Stories
    stories_col = col("stories")
    for st in STORIES:
        await stories_col.update_one({"id": st["id"]}, {"$set": st}, upsert=True)
    print(f"  + Seeded {len(STORIES)} stories")

    # 7. Tasks
    tasks_col = col("tasks")
    for tk in TASKS:
        await tasks_col.update_one({"id": tk["id"]}, {"$set": tk}, upsert=True)
    print(f"  + Seeded {len(TASKS)} tasks")

    # 8. Audit Logs
    audit_col = col("audit_logs")
    for a in AUDIT_LOGS:
        await audit_col.update_one({"id": a["id"]}, {"$set": a}, upsert=True)
    print(f"  + Seeded {len(AUDIT_LOGS)} audit log records")

    # 9. Company Settings
    settings_col = col("company_settings")
    await settings_col.update_one({"company_id": COMPANY_SETTINGS["company_id"]}, {"$set": COMPANY_SETTINGS}, upsert=True)
    print("  + Seeded company settings")

    # 10. HR Reports & CEO Reports
    reports_col = col("hr_reports")
    for r in HR_REPORTS:
        await reports_col.update_one({"id": r["id"]}, {"$set": r}, upsert=True)
    print(f"  + Seeded {len(HR_REPORTS)} HR reports")

    ceo_reports_col = col("ceo_reports")
    for cr in CEO_REPORTS:
        await ceo_reports_col.update_one({"id": cr["id"]}, {"$set": cr}, upsert=True)
    print(f"  + Seeded {len(CEO_REPORTS)} CEO reports")

    gen_reports_col = col("reports")
    for gr in (HR_REPORTS + CEO_REPORTS):
        await gen_reports_col.update_one({"id": gr["id"]}, {"$set": gr}, upsert=True)
    print(f"  + Seeded {len(HR_REPORTS) + len(CEO_REPORTS)} general reports")


    # 11. HR Performance Metrics
    perf_col = col("hr_performance")
    await perf_col.update_one({"type": "metrics"}, {"$set": HR_PERFORMANCE_METRICS}, upsert=True)
    print("  + Seeded HR performance metrics")

    # 12. Candidates
    cand_col = col("candidates")
    for cd in CANDIDATES:
        await cand_col.update_one({"id": cd["id"]}, {"$set": cd}, upsert=True)
    print(f"  + Seeded {len(CANDIDATES)} candidates")

    # 13. Pull Requests (Multi-Agent Evidence)
    pr_col = col("pull_requests")
    for pr in PULL_REQUESTS:
        await pr_col.update_one({"pr_number": pr["pr_number"]}, {"$set": pr}, upsert=True)
    print(f"  + Seeded {len(PULL_REQUESTS)} pull requests")

    # 14. CI/CD Logs
    cicd_col = col("cicd_logs")
    for cl in CICD_LOGS:
        await cicd_col.update_one({"id": cl["id"]}, {"$set": cl}, upsert=True)
    print(f"  + Seeded {len(CICD_LOGS)} CI/CD logs")

    # 15. Active Developer Branches
    branches_col = col("branches")
    for b in BRANCHES:
        await branches_col.update_one({"id": b["id"]}, {"$set": b}, upsert=True)
    print(f"  + Seeded {len(BRANCHES)} active branches")

    # 16. Developer Pull Requests (Dashboard)
    for pr in DEV_PULL_REQUESTS:
        await pr_col.update_one({"id": pr["id"]}, {"$set": pr}, upsert=True)
    print(f"  + Seeded {len(DEV_PULL_REQUESTS)} developer pull requests")

    # 17. Code Submissions & Revisions
    sub_col = col("submissions")
    for s in DEV_SUBMISSIONS:
        await sub_col.update_one({"id": s["id"]}, {"$set": s}, upsert=True)
    print(f"  + Seeded {len(DEV_SUBMISSIONS)} code submissions")

    # 18. Sprint Blockers
    blockers_col = col("blockers")
    for blk in BLOCKERS:
        await blockers_col.update_one({"id": blk["id"]}, {"$set": blk}, upsert=True)
    print(f"  + Seeded {len(BLOCKERS)} sprint blockers")

    # 19. Sprint Retrospectives
    retro_col = col("retrospectives")
    for ret in RETROSPECTIVES:
        await retro_col.update_one({"id": ret["id"]}, {"$set": ret}, upsert=True)
    print(f"  + Seeded {len(RETROSPECTIVES)} retrospectives")

    # 20. Code Review Queue
    rev_col = col("review_queue")
    for rq in REVIEW_QUEUE:
        await rev_col.update_one({"id": rq["id"]}, {"$set": rq}, upsert=True)
    print(f"  + Seeded {len(REVIEW_QUEUE)} review queue items")

    # 21. Escalations
    esc_col = col("escalations")
    for esc in ESCALATIONS:
        await esc_col.update_one({"id": esc["id"]}, {"$set": esc}, upsert=True)
    print(f"  + Seeded {len(ESCALATIONS)} escalations")

    # 22. Developer Progress History
    await col("dev_progress").update_one({"type": "developer_progress"}, {"$set": DEV_PROGRESS}, upsert=True)
    print("  + Seeded developer progress history")

    # 23. AI Feedback & Insights
    await col("ai_feedback").update_one({"type": "ai_feedback"}, {"$set": DEV_AI_FEEDBACK}, upsert=True)
    print("  + Seeded AI feedback and suggestions")

    # 24. Team Workload & Suggestions
    workload_col = col("team_workload")
    for w in TEAM_WORKLOAD:
        await workload_col.update_one({"name": w["name"]}, {"$set": w}, upsert=True)
    sug_col = col("workload_suggestions")
    for sug in WORKLOAD_SUGGESTIONS:
        await sug_col.update_one({"id": sug["id"]}, {"$set": sug}, upsert=True)
    print(f"  + Seeded {len(TEAM_WORKLOAD)} team workload profiles & suggestions")

    # 25. Team Performance & Sprint Trends
    perf_mem_col = col("member_performance")
    for mp in TEAM_PERFORMANCE_MEMBERS:
        await perf_mem_col.update_one({"name": mp["name"]}, {"$set": mp}, upsert=True)
    trends_col = col("sprint_trends")
    for st in SPRINT_TRENDS:
        await trends_col.update_one({"sprint": st["sprint"]}, {"$set": st}, upsert=True)
    print(f"  + Seeded {len(TEAM_PERFORMANCE_MEMBERS)} member performance records & sprint trends")

    # 26. Alignment Insights
    align_col = col("alignment_breakdown")
    for ab in ALIGNMENT_BREAKDOWN:
        await align_col.update_one({"name": ab["name"]}, {"$set": ab}, upsert=True)
    low_col = col("low_alignment_stories")
    for las in LOW_ALIGNMENT_STORIES:
        await low_col.update_one({"id": las["id"]}, {"$set": las}, upsert=True)
    at_col = col("alignment_trend")
    for at in ALIGNMENT_TREND:
        await at_col.update_one({"sprint": at["sprint"]}, {"$set": at}, upsert=True)
    print("  + Seeded alignment breakdown, low stories, and trends")

    # 27. Behaviour History
    bh_col = col("behaviour_history")
    for bh in BEHAVIOUR_HISTORY:
        await bh_col.update_one({"month": bh["month"], "member": bh["member"]}, {"$set": bh}, upsert=True)
    print(f"  + Seeded {len(BEHAVIOUR_HISTORY)} behaviour history entries")

    # 28. CEO Metrics
    await col("ceo_metrics").update_one({"type": "ceo_dashboard"}, {"$set": CEO_METRICS}, upsert=True)
    print("  + Seeded CEO executive metrics")

    # 15. Employee Multi-Agent Evaluations (September 2026)
    print("  [*] Running specialist agent evaluation for seeded employees (Sep 2026)...")
    from agents.supervisor import evaluate_employee
    eval_employees = ["EMP-001", "EMP-002", "EMP-004", "EMP-005"]
    for eid in eval_employees:
        try:
            eval_res = await evaluate_employee(
                employee_id=eid,
                start_date="2026-09-01",
                end_date="2026-09-30",
                period_label="2026-09",
                company_id="ORG-001",
                skip_llm=True,
            )
            print(f"    -> Evaluated {eid}: Score {eval_res.get('overall_score')} (Grade: {eval_res.get('grade')})")
        except Exception as e:
            print(f"    -> Evaluation warning for {eid}: {e}")

    print("\n[OK] Seeding complete! All dynamic collections populated in MongoDB.")

    # 29. QA Collections
    tc_col = col("qa_test_cases")
    for tc in QA_TEST_CASES:
        await tc_col.update_one({"id": tc["id"]}, {"$set": tc}, upsert=True)
    print(f"  + Seeded {len(QA_TEST_CASES)} QA test cases")

    bugs_col = col("qa_bugs")
    for bug in QA_BUGS:
        await bugs_col.update_one({"id": bug["id"]}, {"$set": bug}, upsert=True)
    print(f"  + Seeded {len(QA_BUGS)} QA bugs")

    reg_col = col("qa_regression")
    for reg in QA_REGRESSION:
        await reg_col.update_one({"id": reg["id"]}, {"$set": reg}, upsert=True)
    print(f"  + Seeded {len(QA_REGRESSION)} QA regression suites")

    rc_col = col("qa_release_checks")
    await rc_col.delete_many({})
    for rc in QA_RELEASE_CHECKS:
        await rc_col.insert_one({**rc})
    print(f"  + Seeded {len(QA_RELEASE_CHECKS)} QA release checks")

    await col("qa_quality_metrics").update_one({"type": "qa_quality_metrics"}, {"$set": QA_QUALITY_METRICS}, upsert=True)
    print("  + Seeded QA quality metrics")

    tr_col = col("qa_test_runs")
    for tr in QA_TEST_RUNS:
        await tr_col.update_one({"id": tr["id"]}, {"$set": tr}, upsert=True)
    print(f"  + Seeded {len(QA_TEST_RUNS)} QA test runs")

    # 30. QA Assigned Stories & Metrics
    qas_col = col("qa_assigned_stories")
    for qas in QA_ASSIGNED_STORIES:
        await qas_col.update_one({"id": qas["id"]}, {"$set": qas}, upsert=True)
    print(f"  + Seeded {len(QA_ASSIGNED_STORIES)} QA assigned stories")

    await col("qa_reports_metrics").update_one({"type": "qa_reports_metrics"}, {"$set": QA_REPORTS_METRICS}, upsert=True)
    print("  + Seeded QA reports metrics")

    qr_col = col("qa_reports")
    for qr in QA_REPORTS:
        await qr_col.update_one({"id": qr["id"]}, {"$set": qr}, upsert=True)
    print(f"  + Seeded {len(QA_REPORTS)} QA reports")

    # 31. Shared Reports & Metrics
    sr_col = col("shared_reports")
    for sr in SHARED_REPORTS:
        await sr_col.update_one({"id": sr["id"]}, {"$set": sr}, upsert=True)
    await col("shared_reports_metrics").update_one({"type": "shared_reports_metrics"}, {"$set": SHARED_REPORTS_METRICS}, upsert=True)
    print(f"  + Seeded {len(SHARED_REPORTS)} shared reports and metrics")

    # 32. CI/CD Pipelines
    pipe_col = col("pipelines")
    for pl in PIPELINES:
        await pipe_col.update_one({"id": pl["id"]}, {"$set": pl}, upsert=True)
    await col("pipeline_metrics").update_one({"type": "pipeline_metrics"}, {"$set": PIPELINE_METRICS}, upsert=True)
    print(f"  + Seeded {len(PIPELINES)} CI/CD pipelines & metrics")

    # 33. Deployments
    dep_col = col("deployments")
    for dep in DEPLOYMENTS:
        await dep_col.update_one({"id": dep["id"]}, {"$set": dep}, upsert=True)
    await col("deploy_metrics").update_one({"type": "deploy_metrics"}, {"$set": DEPLOY_METRICS}, upsert=True)
    print(f"  + Seeded {len(DEPLOYMENTS)} deployments & metrics")

    # 34. DevOps System Health
    await col("devops_system_health").update_one({"type": "system_health"}, {"$set": DEVOPS_SYSTEM_HEALTH}, upsert=True)
    print("  + Seeded DevOps system health monitoring")

    # 35. DevOps Tasks
    devops_tasks_col = col("devops_tasks")
    for dt in DEVOPS_TASKS:
        await devops_tasks_col.update_one({"id": dt["id"]}, {"$set": dt}, upsert=True)
    print(f"  + Seeded {len(DEVOPS_TASKS)} DevOps tasks")

    # 36. DevOps Incidents
    inc_col = col("devops_incidents")
    for inc in DEVOPS_INCIDENTS:
        await inc_col.update_one({"id": inc["id"]}, {"$set": inc}, upsert=True)
    print(f"  + Seeded {len(DEVOPS_INCIDENTS)} DevOps incidents")

    # 37. DevOps Infrastructure Changes
    infra_col = col("devops_infra_changes")
    for chg in DEVOPS_INFRA_CHANGES:
        await infra_col.update_one({"id": chg["id"]}, {"$set": chg}, upsert=True)
    print(f"  + Seeded {len(DEVOPS_INFRA_CHANGES)} DevOps infrastructure changes")

    # 38. DevOps Logs & Analysis
    logs_col = col("devops_logs")
    for lg in DEVOPS_LOGS:
        await logs_col.update_one({"id": lg["id"]}, {"$set": lg}, upsert=True)
    await col("devops_logs_metrics").update_one({"type": "logs_metrics"}, {"$set": DEVOPS_LOGS_METRICS}, upsert=True)
    print(f"  + Seeded {len(DEVOPS_LOGS)} DevOps logs & analysis")

    # 39. DevOps Reports & Charts
    drep_col = col("devops_reports")
    for dr in DEVOPS_REPORTS:
        await drep_col.update_one({"id": dr["id"]}, {"$set": dr}, upsert=True)
    await col("devops_reports_charts").update_one({"type": "charts"}, {"$set": DEVOPS_REPORTS_CHARTS}, upsert=True)
    print(f"  + Seeded {len(DEVOPS_REPORTS)} DevOps reports & charts")

    # 40. General Platform Bugs & Alerts
    bugs_gen_col = col("bugs")
    for bg in BUGS:
        await bugs_gen_col.update_one({"id": bg["id"]}, {"$set": bg}, upsert=True)
    print(f"  + Seeded {len(BUGS)} platform bugs")

    alerts_col = col("alerts")
    for alt in ALERTS:
        await alerts_col.update_one({"id": alt["id"]}, {"$set": alt}, upsert=True)
    print(f"  + Seeded {len(ALERTS)} system alerts")

    # 41. Scope Drift & Offense Breakdown
    off_col = col("offense_breakdown")
    await off_col.delete_many({})
    for off in OFFENSE_BREAKDOWN:
        await off_col.insert_one({**off})

    sd_col = col("scope_drift")
    await sd_col.delete_many({})
    for sd in SCOPE_DRIFT:
        await sd_col.insert_one({**sd})
    print("  + Seeded offense breakdown and scope drift")

    # 42. CEO Risk Patterns
    crp_col = col("ceo_risk_patterns")
    for crp in CEO_RISK_PATTERNS:
        await crp_col.update_one({"id": crp["id"]}, {"$set": crp}, upsert=True)
    print(f"  + Seeded {len(CEO_RISK_PATTERNS)} CEO risk patterns")

    # 43. Retro Improvements
    imp_col = col("retro_improvements")
    for imp in RETRO_IMPROVEMENTS:
        await imp_col.update_one({"id": imp["id"]}, {"$set": imp}, upsert=True)
    print(f"  + Seeded {len(RETRO_IMPROVEMENTS)} retro improvement actions")

    # 44. CEO Behaviour Feedback
    cbf_col = col("ceo_behaviour_feedback")
    for cbf in CEO_BEHAVIOUR_FEEDBACK:
        await cbf_col.update_one({"id": cbf["id"]}, {"$set": cbf}, upsert=True)
    print(f"  + Seeded {len(CEO_BEHAVIOUR_FEEDBACK)} CEO behaviour feedback entries")

    # 45. PM Workload & High Risk Members
    wl_col = col("pm_workload")
    for wl in PM_WORKLOAD:
        await wl_col.update_one({"id": wl["id"]}, {"$set": wl}, upsert=True)
    hrm_col = col("pm_high_risk_members")
    for hrm in PM_HIGH_RISK_MEMBERS:
        await hrm_col.update_one({"id": hrm["id"]}, {"$set": hrm}, upsert=True)
    print(f"  + Seeded {len(PM_WORKLOAD)} PM workloads & {len(PM_HIGH_RISK_MEMBERS)} high-risk members")

    # 46. PM Retro Summary & AI Suggestions
    await col("pm_retro_summary").update_one({"type": "pm_retro_summary"}, {"$set": PM_RETRO_SUMMARY}, upsert=True)
    sug_col = col("pm_ai_suggestions")
    for sug in PM_AI_SUGGESTIONS:
        await sug_col.update_one({"id": sug["id"]}, {"$set": sug}, upsert=True)
    print("  + Seeded PM retro summary & AI suggestions")

    # 47. PM Delay Distribution
    delay_col = col("pm_delay_distribution")
    await delay_col.delete_many({})
    for dd in PM_DELAY_DISTRIBUTION:
        await delay_col.insert_one({**dd})
    print(f"  + Seeded {len(PM_DELAY_DISTRIBUTION)} PM delay distribution intervals")

    # 48. Organization Strategic Risks
    risks_col = col("risks")
    for rk in ORGANIZATION_RISKS:
        await risks_col.update_one({"id": rk["id"]}, {"$set": rk}, upsert=True)
    print(f"  + Seeded {len(ORGANIZATION_RISKS)} organization strategic risks")

    # 49. QA Test Suites & Test Health
    ts_col = col("qa_test_suites")
    for ts in QA_TEST_SUITES:
        await ts_col.update_one({"id": ts["id"]}, {"$set": ts}, upsert=True)
    await col("qa_test_health").update_one({"type": "qa_test_health"}, {"$set": QA_TEST_HEALTH}, upsert=True)
    print(f"  + Seeded {len(QA_TEST_SUITES)} QA test suites & health metrics")

    # 50. QA Regression Metrics
    await col("qa_regression_metrics").update_one({"type": "qa_regression_metrics"}, {"$set": QA_REGRESSION_METRICS}, upsert=True)
    print("  + Seeded QA regression suite metrics & AI insights")

    # 51. PM Delivery Analytics
    await col("pm_analytics").update_one({"type": "pm_analytics"}, {"$set": PM_ANALYTICS}, upsert=True)
    print("  + Seeded PM delivery analytics & burndown")

    # 52. Landing Homepage Data
    await col("homepage_data").update_one({"type": "homepage_data"}, {"$set": HOMEPAGE_DATA}, upsert=True)
    print("  + Seeded Homepage features, events, branches, workspaces, and team data")

    print("\n[OK] Full seeding complete! All dynamic collections populated in MongoDB.")


if __name__ == "__main__":
    asyncio.run(seed())
