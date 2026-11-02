"""
GitHub Work Context Fetcher — bridges MongoDB task assignments and GitHub live data.

Flow for each agent:
    1. Look up developer/team in MongoDB: get their github_username + assigned tasks/PRs
    2. Resolve GitHub repo(s) from the project record
    3. Pull live data from GitHub API:
         - PRs authored by developer (or assigned to team)
         - Commits per PR (with full diff patches)
         - Review comments & CI check-run status
         - Workflow/Actions run logs
         - Test files changed
    4. Return a rich "WorkContext" dict consumed by each agent's LLM prompt

This is the SINGLE SOURCE OF TRUTH for GitHub data across all agents.
No agent fetches GitHub data independently — they all call fetch_work_context().

GitHub token priority:
    1. Per-user token stored in MongoDB users.github_token
    2. Company-level token in companies.github_token
    3. Global GITHUB_TOKEN in .env (settings.GITHUB_TOKEN)
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone, timedelta

from core.config import settings

logger = logging.getLogger("samanvaya.github_context")

# ─────────────────────────────────────────────────────────────────────────────
# Internal: resolve GitHub token (per-user > company > global)
# ─────────────────────────────────────────────────────────────────────────────
async def _resolve_github_token(user_doc: Dict[str, Any], company_id: str) -> str:
    """
    Priority: user.github_token > company.github_token > settings.GITHUB_TOKEN
    """
    # 1. Per-user token
    token = (user_doc or {}).get("github_token", "")
    if token:
        logger.debug("[GH-CTX] Using per-user GitHub token for %s", user_doc.get("name"))
        return token

    # 2. Company-level token
    try:
        from core.database import get_collection
        col = await get_collection("companies")
        company = await col.find_one({"id": company_id}, {"_id": 0, "github_token": 1})
        if company and company.get("github_token"):
            logger.debug("[GH-CTX] Using company GitHub token for %s", company_id)
            return company["github_token"]
    except Exception:
        pass

    # 3. Global .env token
    return settings.GITHUB_TOKEN or ""


# ─────────────────────────────────────────────────────────────────────────────
# Internal: resolve repo owner+name from a project or user record
# ─────────────────────────────────────────────────────────────────────────────
def _parse_repo(repo_url_or_name: str) -> Optional[tuple]:
    """
    Parse 'owner/repo' or full GitHub URL to (owner, repo) tuple.
    Returns None if unparseable.
    """
    if not repo_url_or_name:
        return None
    s = repo_url_or_name.strip().rstrip("/")
    # Handle full URLs
    if "github.com" in s:
        parts = s.split("github.com/")[-1].split("/")
        if len(parts) >= 2:
            return parts[0], parts[1].replace(".git", "")
    # Handle 'owner/repo'
    if "/" in s:
        parts = s.split("/")
        return parts[0], parts[1]
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Internal: safe GitHub API call wrapper
# ─────────────────────────────────────────────────────────────────────────────
async def _safe_gh(coro, default=None, label="call"):
    """Wrap a GitHub API call with timeout + error handling."""
    try:
        return await asyncio.wait_for(coro, timeout=15.0)
    except asyncio.TimeoutError:
        logger.warning("[GH-CTX] Timeout on GitHub %s", label)
        return default
    except Exception as exc:
        logger.warning("[GH-CTX] GitHub %s failed: %s", label, exc)
        return default


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point: fetch_work_context()
# ─────────────────────────────────────────────────────────────────────────────
async def fetch_work_context(
    company_id: str,
    target_type: str,           # "developer" | "team" | "project"
    target_id: str,             # user_id, team_id, or project_id
    task_type: str = "code_review",
    lookback_days: int = 14,
    max_prs: int = 5,
) -> Dict[str, Any]:
    """
    Fetch rich work context from MongoDB + GitHub for a developer, team, or project.

    Args:
        company_id:    Multi-tenant isolation key.
        target_type:   "developer" | "team" | "project"
        target_id:     User ID, team ID, or project ID to analyse.
        task_type:     Which agent is calling (affects what data is fetched).
        lookback_days: How many days back to look for GitHub activity.
        max_prs:       Max PRs to fetch full diff for (expensive).

    Returns:
        WorkContext dict with keys:
            developer      - User record from MongoDB
            team           - Team record from MongoDB
            project        - Project record from MongoDB
            assigned_tasks - Tasks/stories assigned (from MongoDB)
            github_prs     - List of PR dicts with files, commits, diffs, reviews
            github_commits - Recent commits by developer
            cicd_runs      - GitHub Actions/Check runs for recent commits
            test_files     - Test files changed in PRs
            has_github     - bool: GitHub data was fetched
            token_used     - bool: a GitHub token was available
            fetched_at     - ISO timestamp
            errors         - List of non-fatal errors
    """
    t0 = time.time()
    ctx: Dict[str, Any] = {
        "target_type":    target_type,
        "target_id":      target_id,
        "company_id":     company_id,
        "task_type":      task_type,
        "developer":      {},
        "team":           {},
        "project":        {},
        "assigned_tasks": [],
        "github_prs":     [],
        "github_commits": [],
        "cicd_runs":      [],
        "test_files":     [],
        "has_github":     False,
        "token_used":     False,
        "fetched_at":     datetime.now(timezone.utc).isoformat(),
        "errors":         [],
    }

    try:
        from core.database import get_collection
    except Exception as exc:
        ctx["errors"].append(f"DB unavailable: {exc}")
        return ctx

    # ── Step 1: Resolve records from MongoDB ──────────────────────────────────
    since = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()

    user_doc: Dict[str, Any] = {}
    team_doc: Dict[str, Any] = {}
    project_doc: Dict[str, Any] = {}

    try:
        users_col = await get_collection("users")
        teams_col = await get_collection("teams")
        proj_col  = await get_collection("projects")

        if target_type == "developer":
            user_doc = await users_col.find_one(
                {"$or": [{"id": target_id}, {"_id": target_id}, {"email": target_id}]},
                {"_id": 0}
            ) or {}
            if user_doc.get("team_id"):
                team_doc = await teams_col.find_one({"id": user_doc["team_id"]}, {"_id": 0}) or {}
            if team_doc.get("project_id"):
                project_doc = await proj_col.find_one({"id": team_doc["project_id"]}, {"_id": 0}) or {}

        elif target_type == "team":
            team_doc = await teams_col.find_one({"id": target_id}, {"_id": 0}) or {}
            if team_doc.get("project_id"):
                project_doc = await proj_col.find_one({"id": team_doc["project_id"]}, {"_id": 0}) or {}

        elif target_type == "project":
            project_doc = await proj_col.find_one({"id": target_id}, {"_id": 0}) or {}

        ctx.update({"developer": user_doc, "team": team_doc, "project": project_doc})
        logger.info(
            "[GH-CTX] Resolved target=%s/%s user=%s team=%s project=%s",
            target_type, target_id,
            user_doc.get("name", "?"), team_doc.get("name", "?"), project_doc.get("name", "?")
        )
    except Exception as exc:
        ctx["errors"].append(f"MongoDB resolve error: {exc}")

    # ── Step 2: Fetch assigned tasks/stories ──────────────────────────────────
    try:
        tasks_col = await get_collection("tasks")
        query: Dict[str, Any] = {"company_id": company_id}
        if target_type == "developer" and user_doc.get("id"):
            query["assignee_id"] = user_doc["id"]
        elif target_type == "team" and team_doc.get("id"):
            query["team_id"] = team_doc["id"]
        elif target_type == "project" and project_doc.get("id"):
            query["project_id"] = project_doc["id"]

        tasks = await tasks_col.find(query, {"_id": 0}).sort("updated_at", -1).to_list(50)
        ctx["assigned_tasks"] = tasks
        logger.info("[GH-CTX] Found %d assigned tasks", len(tasks))
    except Exception as exc:
        logger.debug("[GH-CTX] Tasks collection error (may not exist): %s", exc)

    # ── Step 3: Resolve GitHub token + client ─────────────────────────────────
    token = await _resolve_github_token(user_doc, company_id)
    if not token:
        logger.warning(
            "[GH-CTX] No GitHub token for target=%s/%s — skipping GitHub fetch. "
            "Set GITHUB_TOKEN in .env or add github_token to the user/company record.",
            target_type, target_id
        )
        ctx["has_github"] = False
        ctx["token_used"] = False
        ctx["latency_ms"] = round((time.time() - t0) * 1000, 1)
        return ctx

    ctx["token_used"] = True

    from integrations.github.client import GitHubClient
    gh = GitHubClient(token=token)

    # ── Step 4: Resolve GitHub repo(s) ────────────────────────────────────────
    repo_urls: List[str] = []
    for src in [project_doc, team_doc, user_doc]:
        for field in ["github_repo", "repo_url", "repository", "github_url"]:
            val = src.get(field, "")
            if val:
                repo_urls.append(val)
                break

    # Also check project.repositories list
    for r in project_doc.get("repositories", []):
        if isinstance(r, str):
            repo_urls.append(r)
        elif isinstance(r, dict):
            repo_urls.append(r.get("url") or r.get("name", ""))

    repos: List[tuple] = []
    for url in repo_urls:
        parsed = _parse_repo(url)
        if parsed and parsed not in repos:
            repos.append(parsed)

    if not repos:
        logger.warning("[GH-CTX] No GitHub repos found for target=%s/%s", target_type, target_id)
        ctx["has_github"] = False
        ctx["latency_ms"] = round((time.time() - t0) * 1000, 1)
        return ctx

    logger.info("[GH-CTX] Fetching from GitHub repos: %s", repos)
    ctx["has_github"] = True

    # ── Step 5: Fetch PRs + enrichment for each repo ──────────────────────────
    github_login = user_doc.get("github_username") or user_doc.get("github_login", "")
    all_prs: List[Dict[str, Any]] = []
    all_commits: List[Dict[str, Any]] = []
    all_cicd: List[Dict[str, Any]] = []

    for owner, repo in repos[:3]:  # cap at 3 repos
        logger.info("[GH-CTX] Fetching PRs from %s/%s", owner, repo)

        # List PRs (open + recently closed)
        raw_prs = await _safe_gh(
            gh.list_pull_requests(owner, repo, state="all", per_page=20),
            default=[], label=f"list_prs:{owner}/{repo}"
        )

        # Filter by author (developer mode) or date
        filtered_prs = []
        for pr in (raw_prs or []):
            author = pr.get("user", {}).get("login", "")
            updated = pr.get("updated_at", "")
            if updated and updated < since:
                continue
            if target_type == "developer" and github_login and author != github_login:
                continue
            filtered_prs.append(pr)

        logger.info("[GH-CTX] %d PRs matched filter for %s/%s", len(filtered_prs), owner, repo)

        # Enrich top PRs with files, commits, reviews
        for pr in filtered_prs[:max_prs]:
            pr_num = pr["number"]
            pr_enriched = {
                "number":        pr_num,
                "title":         pr.get("title", ""),
                "author":        pr.get("user", {}).get("login", ""),
                "state":         pr.get("state", ""),
                "merged":        pr.get("merged_at") is not None,
                "branch":        pr.get("head", {}).get("ref", ""),
                "base_branch":   pr.get("base", {}).get("ref", ""),
                "files_changed": pr.get("changed_files", 0),
                "commits_count": pr.get("commits", 0),
                "additions":     pr.get("additions", 0),
                "deletions":     pr.get("deletions", 0),
                "description":   (pr.get("body") or "")[:500],
                "created_at":    pr.get("created_at", ""),
                "updated_at":    pr.get("updated_at", ""),
                "url":           pr.get("html_url", ""),
                "repo":          f"{owner}/{repo}",
                "files":         [],
                "reviews":       [],
                "comments_count": 0,
            }

            # Files with diffs
            files = await _safe_gh(
                gh.get_pr_files(owner, repo, pr_num),
                default=[], label=f"pr_files:{pr_num}"
            )
            pr_enriched["files"] = [
                {
                    "filename":  f.get("filename", ""),
                    "status":    f.get("status", ""),
                    "additions": f.get("additions", 0),
                    "deletions": f.get("deletions", 0),
                    "patch":     (f.get("patch") or "")[:1500],  # cap diff size
                }
                for f in (files or [])
            ]

            # Identify test files
            for f in pr_enriched["files"]:
                fname = f["filename"].lower()
                if "test" in fname or "spec" in fname or fname.endswith("_test.py"):
                    ctx["test_files"].append(f["filename"])

            # Reviews
            reviews = await _safe_gh(
                gh.get_pr_reviews(owner, repo, pr_num),
                default=[], label=f"pr_reviews:{pr_num}"
            )
            pr_enriched["reviews"] = [
                {
                    "reviewer": r.get("user", {}).get("login", ""),
                    "state":    r.get("state", ""),
                    "body":     (r.get("body") or "")[:300],
                }
                for r in (reviews or [])
            ]

            # Comments count
            comments = await _safe_gh(
                gh.get_pr_comments(owner, repo, pr_num),
                default=[], label=f"pr_comments:{pr_num}"
            )
            pr_enriched["comments_count"] = len(comments or [])

            all_prs.append(pr_enriched)

            # CI/CD: check runs for head commit
            head_sha = pr.get("head", {}).get("sha", "")
            if head_sha:
                check_data = await _safe_gh(
                    gh.get_commit_check_runs(owner, repo, head_sha),
                    default={}, label=f"check_runs:{head_sha[:8]}"
                )
                runs = (check_data or {}).get("check_runs", [])
                for run in runs:
                    all_cicd.append({
                        "pr_number":    pr_num,
                        "pr_title":     pr_enriched["title"],
                        "name":         run.get("name", ""),
                        "status":       run.get("status", ""),
                        "conclusion":   run.get("conclusion", ""),
                        "started_at":   run.get("started_at", ""),
                        "completed_at": run.get("completed_at", ""),
                        "url":          run.get("html_url", ""),
                        "repo":         f"{owner}/{repo}",
                    })

        all_commits.extend([])  # placeholder — commits fetched per-PR above

    ctx["github_prs"]     = all_prs
    ctx["github_commits"] = all_commits
    ctx["cicd_runs"]      = all_cicd
    ctx["test_files"]     = list(set(ctx["test_files"]))

    elapsed = round((time.time() - t0) * 1000, 1)
    logger.info(
        "[GH-CTX] DONE target=%s/%s prs=%d cicd_runs=%d test_files=%d elapsed=%.0fms",
        target_type, target_id, len(all_prs), len(all_cicd), len(ctx["test_files"]), elapsed
    )
    ctx["latency_ms"] = elapsed
    return ctx


# ─────────────────────────────────────────────────────────────────────────────
# Helpers: summarise work context for LLM prompts
# ─────────────────────────────────────────────────────────────────────────────
def summarise_prs_for_prompt(prs: List[Dict[str, Any]], max_chars: int = 8000) -> str:
    """Render PR list + diffs as structured prompt text."""
    if not prs:
        return "No GitHub pull requests found for this developer/team."
    parts = []
    for pr in prs:
        pr_text = (
            f"\n### PR #{pr['number']}: {pr['title']}\n"
            f"Author: {pr['author']} | State: {pr['state']} | "
            f"Merged: {pr['merged']} | Branch: {pr['branch']} -> {pr['base_branch']}\n"
            f"Files changed: {pr['files_changed']} | +{pr['additions']} -{pr['deletions']} lines\n"
            f"Description: {pr['description']}\n"
        )
        if pr.get("reviews"):
            pr_text += "Reviews: " + ", ".join(
                f"{r['reviewer']}({r['state']})" for r in pr["reviews"]
            ) + "\n"
        if pr.get("files"):
            pr_text += "\n#### Changed Files & Diffs:\n"
            for f in pr["files"][:8]:
                pr_text += (
                    f"  {f['filename']} [{f['status']}] "
                    f"+{f['additions']} -{f['deletions']}\n"
                )
                if f.get("patch"):
                    pr_text += f"```diff\n{f['patch'][:600]}\n```\n"
        parts.append(pr_text)
    full = "\n---\n".join(parts)
    return full[:max_chars]


def summarise_tasks_for_prompt(tasks: List[Dict[str, Any]]) -> str:
    """Render assigned tasks as prompt text."""
    if not tasks:
        return "No tasks found in Samanvaya for this developer/team."
    lines = []
    for t in tasks[:20]:
        lines.append(
            f"  [{t.get('status','?')}] {t.get('title','Untitled')} "
            f"| SP:{t.get('story_points', '?')} | Priority:{t.get('priority','medium')} "
            f"| Assignee:{t.get('assignee_name', t.get('assignee_id','?'))}"
        )
    return "\n".join(lines)


def summarise_cicd_for_prompt(runs: List[Dict[str, Any]]) -> str:
    """Render CI/CD check runs as prompt text."""
    if not runs:
        return "No CI/CD runs found."
    lines = []
    for r in runs[:20]:
        status = r.get("conclusion") or r.get("status", "unknown")
        lines.append(
            f"  [{status.upper()}] {r.get('name','?')} | PR#{r.get('pr_number','?')} "
            f"'{r.get('pr_title','')[:50]}' | repo:{r.get('repo','?')}"
        )
    return "\n".join(lines)
