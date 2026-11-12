"""Bounded adapters over existing local collections, with no network or model calls."""

from datetime import datetime, timezone

from core.database import col
from intelligence.performance_evidence import source_identity

LIMIT = 200  # Resource bound, not an evidence sufficiency threshold.
_BASE = {"_id": 0, "id": 1, "project_id": 1, "org_id": 1, "updated_at": 1, "created_at": 1,
         "completed_at": 1, "status": 1, "deleted": 1, "disputed": 1}


def _timestamp(value):
    # BSON datetimes are UTC even when a Motor client decodes them without tzinfo.
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


async def collect_local_evidence(scope, subject):
    rows, connectors = [], []

    async def fetch(origin, extra, fields):
        query = {"$and": [
            {"$or": [{"project_id": scope.project_id}, {"repository_id": scope.project_id}]}
                if origin == "code_quality_runs" else {"project_id": scope.project_id},
            {"$or": [{"org_id": scope.organization_id}, {"org_id": {"$exists": False}}]}, extra,
        ]}
        try:
            documents = await col(origin).find(query, {**_BASE, **{key: 1 for key in fields}}).sort("_id", 1).limit(LIMIT + 1).to_list(LIMIT + 1)
            connectors.append({"origin": origin, "availability": "PARTIAL" if len(documents) > LIMIT else "AVAILABLE",
                "fetched_count": min(len(documents), LIMIT),
                "limitations": ("COLLECTION_TRUNCATED",) if len(documents) > LIMIT else ()})
            return documents[:LIMIT]
        except Exception:
            # Do not copy database errors/connection strings into evidence or user responses.
            connectors.append({"origin": origin, "availability": "UNAVAILABLE", "limitations": ("SOURCE_READ_FAILED",)})
            return []

    def row(document, origin, kind, **extra):
        return {"origin": origin, "kind": kind, "external_id": document.get("id"),
            "organization_id": document.get("org_id", scope.organization_id),
            "project_id": document.get("project_id", document.get("repository_id")),
            "scope_basis": "DIRECT_ORG" if document.get("org_id") else "AUTHORIZED_PARENT_PROJECT",
            "source_revision": _timestamp(document.get("updated_at")),
            "occurred_at": _timestamp(document.get("completed_at") or document.get("created_at")),
            "actor_id": scope.employee_id, "attribution_basis": "DIRECT_EMPLOYEE_ID",
            "shared": None, "facts": {"status": document.get("status") or "unknown"},
            "deleted": document.get("deleted") is True, "disputed": document.get("disputed") is True,
            **extra}

    for origin, kind in (("tasks", "task"), ("stories", "story"), ("qa_defects", "defect")):
        documents = await fetch(origin, {"assignee_id": scope.employee_id}, ("assignee_id", "resolved_at"))
        for doc in documents:
            item = row(doc, origin, kind)
            if origin == "qa_defects":
                item["occurred_at"] = _timestamp(doc.get("resolved_at") or doc.get("updated_at") or doc.get("created_at"))
                # QA's existing domain uses uppercase states; preserve the fact,
                # without interpreting FIXED as a validated regression repair.
                status = doc.get("status")
                item["facts"]["status"] = status.lower() if isinstance(status, str) else "unknown"
            rows.append(item)

    prs = []
    login = subject.get("github_username")
    if not scope.repository:
        connectors.append({"origin": "pull_requests", "availability": "UNAVAILABLE" if scope.repository_mapping_status == "UNAVAILABLE" else "NOT_CONFIGURED",
            "limitations": ("EXACT_REPOSITORY_MAPPING_" + scope.repository_mapping_status,)})
    elif not isinstance(login, str) or not login.strip():
        connectors.append({"origin": "pull_requests", "availability": "UNAVAILABLE", "limitations": ("EXACT_GITHUB_IDENTITY_MAPPING_MISSING",)})
    else:
        prs = await fetch("pull_requests", {"repo_id": scope.repository, "author_login": login},
            ("repo_id", "pr_number", "author_login", "head_sha", "merged_at"))
        for doc in prs:
            rows.append(row(doc, "pull_requests", "pr", external_id=doc.get("pr_number"), repository=doc.get("repo_id"),
                source_revision=doc.get("head_sha"), attribution_basis="EXACT_GITHUB_MAPPING",
                occurred_at=_timestamp(doc.get("merged_at") or doc.get("created_at")),
                facts={"status": doc.get("status") or "unknown", "head_sha": doc.get("head_sha")}))

    # Related executions are project/PR context, never personal credit inferred
    # from triggered_by. An exact PR revision link is mandatory for attribution.
    numbers = [doc["pr_number"] for doc in prs if type(doc.get("pr_number")) is int]
    heads = [doc["head_sha"] for doc in prs if isinstance(doc.get("head_sha"), str)]
    ids = [doc["id"] for doc in prs if isinstance(doc.get("id"), str)]
    for origin, kind in (("test_runs", "test_run"), ("code_quality_runs", "analysis"),
                         ("algorithm_benchmark_runs", "benchmark")):
        if not scope.repository or not prs:
            connectors.append({"origin": origin, "availability": "UNAVAILABLE",
                "limitations": ("ATTRIBUTABLE_PR_SNAPSHOT_UNAVAILABLE",)})
            continue
        if origin == "test_runs":
            try:
                config = await col("qa_ci_configs").find_one({"project_id": scope.project_id, "repository": scope.repository,
                    "$or": [{"org_id": scope.organization_id}, {"org_id": {"$exists": False}}]}, {"_id": 1})
            except Exception:
                connectors.append({"origin": origin, "availability": "UNAVAILABLE", "limitations": ("CI_CONFIGURATION_READ_FAILED",)})
                continue
            if not config:
                connectors.append({"origin": origin, "availability": "NOT_CONFIGURED", "limitations": ("CI_CONFIGURATION_UNAVAILABLE",)})
                continue
        extra = {"$or": [{"pr_number": {"$in": numbers}}, {"commit_sha": {"$in": heads}},
                         {"pr_automation.pr_id": {"$in": ids}}]}
        fields = ("run_id", "repository_id", "repository", "pr_number", "commit_sha", "head_sha", "baseline_sha",
                  "pr_automation.pr_id", "pr_automation.repository", "pr_automation.head_sha", "completed_at",
                  "tests_run", "tests_passed", "tests_failed", "tests_skipped", "workload_key")
        for doc in await fetch(origin, extra, fields):
            automation = doc.get("pr_automation") or {}
            matches = [pr for pr in prs if (automation.get("pr_id") == pr.get("id")
                if automation.get("pr_id") else doc.get("pr_number") == pr.get("pr_number")
                if doc.get("pr_number") is not None else doc.get("commit_sha") == pr.get("head_sha"))]
            if len(matches) != 1:
                continue  # Do not expose another employee's or ambiguous project runs.
            parent = matches[0]
            repository = doc.get("repository") or automation.get("repository")
            # Discovery stores repository_id=project ID, not a repository identity.
            # Only that documented adapter may inherit the validated parent mapping.
            if origin == "code_quality_runs" and repository is None:
                repository = parent.get("repo_id")
            facts = {"status": doc.get("status") or "unknown", "head_sha": doc.get("commit_sha") or automation.get("head_sha"),
                     "baseline_sha": doc.get("baseline_sha")}
            if kind == "test_run":
                facts.update({key: doc.get(key) for key in ("tests_run", "tests_passed", "tests_failed", "tests_skipped")})
            if kind == "benchmark":
                facts["workload_key"] = doc.get("workload_key")
            rows.append(row(doc, origin, kind, external_id=doc.get("run_id") or doc.get("id"), repository=repository,
                source_revision=doc.get("commit_sha") or automation.get("head_sha"),
                current_head_sha=parent.get("head_sha"), attribution_basis="PR_REVISION_LINK",
                parent_source_id=source_identity(scope, "pr", parent.get("pr_number"), parent.get("repo_id")), facts=facts))

    for origin in ("commits", "code_reviews", "incidents"):
        connectors.append({"origin": origin, "availability": "NOT_CONFIGURED",
            "limitations": ("NO_DURABLE_ATTRIBUTABLE_PERIOD_ADAPTER",)})
    return rows, connectors
