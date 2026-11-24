"""Discover release scope and verify build artifacts using immutable GitHub identities."""

import asyncio
import hashlib
import hmac
import re
from datetime import datetime
from types import SimpleNamespace

import httpx
from fastapi import HTTPException

from core.config import settings
from core.database import col
from domain.models.performance_evidence import canonical_digest
from domain.services.ai_evidence_service import _file, _repository
from domain.services.task_progress_service import TASK_ID_PATTERN
from integrations.github.client import GitHubClient
from integrations.github.test_artifacts import MAX_ARCHIVE_BYTES
from repositories.pr_repository import PRRepository


MAX_COMMITS = 150
COMPARE_PAGE_SIZE = 50
MAX_PULL_REQUESTS = 40
MAX_TASKS = 100
_SHA = re.compile(r"[a-f0-9]{40}")
_DIGEST = re.compile(r"[a-f0-9]{64}")
_WORKFLOW_PATH = re.compile(r"\.github/workflows/[A-Za-z0-9_-]+\.ya?ml")
_REVERT = re.compile(r"^This reverts commit ([a-f0-9]{40})\.?$", re.M)
_HUNK_OFFSET = re.compile(r"^@@ -\d+(,\d+)? \+\d+(,\d+)? @@", re.M)


def _sha(value):
    return isinstance(value, str) and _SHA.fullmatch(value) is not None


def _id(value):
    return type(value) is int and 0 < value < 2**63


def _repository_matches(value, repository_id, name):
    return (isinstance(value, dict) and _id(value.get("id")) and value["id"] == repository_id
            and isinstance(value.get("full_name"), str) and value["full_name"].casefold() == name.casefold())


def _time(value):
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError("GitHub event time is unavailable")
    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError("GitHub event time is unavailable") from None
    if timestamp.tzinfo is None:
        raise ValueError("GitHub event time must include a timezone")
    return timestamp


async def verify_trusted_run(client, owner, name, repository_id, target_sha, run_id, *, required_conclusion="success"):
    path = settings.RELEASE_TRUSTED_WORKFLOW_PATH
    expected_sha = settings.RELEASE_TRUSTED_WORKFLOW_SHA256
    branch = settings.RELEASE_TRUSTED_BUILD_REF
    if not _WORKFLOW_PATH.fullmatch(path) or not _DIGEST.fullmatch(expected_sha) or not branch:
        raise ValueError("Configure a trusted workflow path, digest and branch")
    if not _sha(target_sha) or not _id(run_id):
        raise ValueError("An exact commit and workflow run ID are required")

    repository = f"{owner}/{name}"
    run = await client.get_workflow_run(owner, name, run_id)
    allowed_results = {required_conclusion} if required_conclusion is not None else {"success", "failure"}
    if (not _id(run.get("id")) or run["id"] != run_id or not _id(run.get("run_attempt"))
            or not _id(run.get("workflow_id")) or run.get("head_sha") != target_sha
            or run.get("head_branch") != branch or run.get("path") != path
            or run.get("event") != "push" or run.get("status") != "completed"
            or run.get("conclusion") not in allowed_results
            or not _repository_matches(run.get("repository"), repository_id, repository)
            or not _repository_matches(run.get("head_repository"), repository_id, repository)):
        raise ValueError("GitHub run does not match the trusted completed workflow on the release revision")
    if _time(run.get("run_started_at")) > _time(run.get("updated_at")):
        raise ValueError("Workflow attempt times are inconsistent")

    source = SimpleNamespace(source_revision=target_sha, path=path, content_sha256=expected_sha)
    pinned = await _file(client, owner, name, source)
    return run, pinned["content_sha256"]


async def artifact_inventory(client, owner, name, repository_id, target_sha, run):
    """Normalize GitHub-reported artifacts scoped to the current attempt window."""
    run_id, attempt = run["id"], run["run_attempt"]
    started, updated = _time(run.get("run_started_at")), _time(run.get("updated_at"))
    listing = await client.get_workflow_artifacts(owner, name, run_id)
    artifacts = listing.get("artifacts")
    if (not isinstance(artifacts, list) or type(listing.get("total_count")) is not int
            or listing["total_count"] != len(artifacts) or len(artifacts) > 20):
        raise ValueError("The complete bounded workflow artifact list is required")
    output = []
    seen = set()
    for item in artifacts:
        item_name = item.get("name")
        if not isinstance(item_name, str) or not item_name.endswith(f"-{run_id}-{attempt}"):
            continue
        metadata = item.get("workflow_run") or {}
        digest = item.get("digest")
        size = item.get("size_in_bytes")
        if (not _id(item.get("id")) or item["id"] in seen or not 0 < len(item_name) <= 200
                or item.get("expired") is not False or type(size) is not int or not 0 < size <= MAX_ARCHIVE_BYTES
                or metadata.get("id") != run_id or metadata.get("head_sha") != target_sha
                or metadata.get("repository_id") != repository_id or metadata.get("head_repository_id") != repository_id
                or metadata.get("head_branch") != run["head_branch"]
                or not isinstance(digest, str) or not digest.startswith("sha256:") or not _DIGEST.fullmatch(digest[7:])
                or not started <= _time(item.get("created_at")) <= updated):
            raise ValueError("Workflow artifact identity, attempt or digest is invalid")
        seen.add(item["id"])
        output.append({"id": item["id"], "name": item_name, "digest": digest[7:], "algorithm": "sha256",
                       "size_bytes": size, "created_at": item["created_at"]})
    return output


async def verify_artifact(client, owner, name, repository_id, target_sha, run_id, artifact_id):
    if not _id(artifact_id):
        raise ValueError("GitHub artifact ID is required")
    run, workflow_digest = await verify_trusted_run(client, owner, name, repository_id, target_sha, run_id)
    artifacts = await artifact_inventory(client, owner, name, repository_id, target_sha, run)
    matches = [row for row in artifacts if row["id"] == artifact_id
               and row["name"] == f"samanvaya-candidate-{run_id}-{run['run_attempt']}"]
    if len(matches) != 1:
        raise ValueError("An immutable candidate artifact for the current build attempt is required")
    artifact = matches[0]
    raw = await client.download_workflow_artifact(owner, name, artifact_id)
    if len(raw) != artifact["size_bytes"] or not hmac.compare_digest(hashlib.sha256(raw).hexdigest(), artifact["digest"]):
        raise ValueError("Candidate artifact integrity verification failed")
    current = await client.get_workflow_run(owner, name, run_id)
    fields = ("run_attempt", "status", "conclusion", "head_sha", "workflow_id", "updated_at")
    if any(current.get(key) != run.get(key) for key in fields):
        raise ValueError("Workflow attempt changed during artifact verification")
    return {**artifact, "run_id": run_id, "run_attempt": run["run_attempt"], "workflow_id": run["workflow_id"],
            "workflow_path": run["path"], "workflow_sha256": workflow_digest,
            "source_reference": f"https://api.github.com/repos/{owner}/{name}/actions/artifacts/{artifact_id}"}


def _commit_view(item):
    sha = item["sha"]
    parents = [parent["sha"] for parent in item["parents"]]
    data = item["commit"]
    message, tree = data["message"], data["tree"]["sha"]
    if (not _sha(sha) or not all(_sha(p) for p in parents) or len(parents) > 2
            or sha in parents or len(set(parents)) != len(parents) or not isinstance(message, str) or not _sha(tree)):
        raise ValueError("GitHub commit graph is incomplete or unsupported")
    return {"sha": sha, "parents": parents, "tree": tree, "subject": message.split("\n", 1)[0][:300],
            "revert_refs": sorted(set(_REVERT.findall(message[:32_768])))}


def _reachable(commits, root):
    """Walk only the comparison's verified introduced commits."""
    seen = set()
    remaining = [root]
    while remaining:
        sha = remaining.pop()
        if sha in commits and sha not in seen:
            seen.add(sha)
            remaining.extend(commits[sha]["parents"])
    return seen


async def _compare(client, owner, name, baseline, target):
    if not _sha(baseline) or not _sha(target) or baseline == target:
        raise ValueError("A distinct, exact baseline and target commit are required")
    commits = {}
    total = None
    for page in range(1, MAX_COMMITS // COMPARE_PAGE_SIZE + 1):
        data, more = await client.compare_revision_page(owner, name, baseline, target, page, COMPARE_PAGE_SIZE)
        count = data.get("total_commits")
        if (data.get("status") != "ahead" or type(data.get("behind_by")) is not int or data["behind_by"] != 0
                or data.get("base_commit", {}).get("sha") != baseline or data.get("merge_base_commit", {}).get("sha") != baseline
                or type(count) is not int or not 1 <= count <= MAX_COMMITS or count != data.get("ahead_by")
                or (total is not None and count != total)):
            raise ValueError("Baseline must be an ancestor and comparison must fit the discovery limit")
        total = count
        batch = data["commits"]
        if not isinstance(batch, list) or not batch or len(batch) > COMPARE_PAGE_SIZE:
            raise ValueError("Commit comparison page is incomplete")
        for raw in batch:
            item = _commit_view(raw)
            sha = item["sha"]
            if sha == baseline or sha in commits:
                raise ValueError("Commit comparison contains inconsistent revisions")
            commits[sha] = item
        if len(commits) > total or more != (len(commits) < total):
            raise ValueError("Commit comparison count and pagination disagree")
        if not more:
            break
    if (len(commits) != total or _reachable(commits, target) != set(commits)
            or not any(baseline in row["parents"] for row in commits.values())):
        raise ValueError("GitHub comparison has missing or unrelated commits")
    return commits


async def _associations(client, owner, name, revision, semaphore):
    numbers = set()
    async with semaphore:
        for page in range(1, 4):
            batch, more = await client.commit_pull_request_page(owner, name, revision, page, 30)
            if not isinstance(batch, list) or len(batch) > 30 or (more and not batch):
                raise ValueError("Commit-to-PR pagination is incomplete")
            for row in batch:
                number = row.get("number")
                if not _id(number) or number in numbers:
                    raise ValueError("Commit-to-PR associations are ambiguous")
                numbers.add(number)
            if not more:
                return numbers
    raise ValueError("Commit-to-PR association limit exceeded")


async def _pr_detail(client, owner, name, number, semaphore):
    async with semaphore:
        return await client.get_pull_request(owner, name, number)


async def _batch(coroutines):
    rows = await asyncio.gather(*coroutines, return_exceptions=True)
    for row in rows:
        if isinstance(row, BaseException):
            raise row
    return rows


async def _pull_requests(client, owner, name, repository_id, commits):
    semaphore = asyncio.Semaphore(8)
    revisions = list(commits)
    rows = await _batch(_associations(client, owner, name, sha, semaphore) for sha in revisions)
    associations = dict(zip(revisions, rows))
    numbers = sorted(set().union(*rows))
    if len(numbers) > MAX_PULL_REQUESTS:
        raise ValueError("Release pull request association limit exceeded")
    relevant = {}
    excluded = []
    repository = f"{owner}/{name}"
    details = await _batch(_pr_detail(client, owner, name, n, semaphore) for n in numbers)
    for number, pr in zip(numbers, details):
        if (pr.get("number") != number or not _id(pr.get("id"))
                or not _repository_matches((pr.get("base") or {}).get("repo"), repository_id, repository)):
            raise ValueError("GitHub pull request identity is inconsistent")
        merge_sha = pr.get("merge_commit_sha")
        if pr.get("state") != "closed" or pr.get("merged") is not True:
            excluded.append({"number": number, "reason": "unmerged"})
        elif not _sha(merge_sha):
            raise ValueError("Merged pull request revision is unavailable")
        elif merge_sha not in commits:
            excluded.append({"number": number, "reason": "outside_comparison", "merge_commit_sha": merge_sha})
        else:
            relevant[number] = pr
    return associations, relevant, excluded


async def _ancestor(client, owner, name, ancestor, descendant):
    if ancestor == descendant:
        return True
    data, _ = await client.compare_revision_page(owner, name, ancestor, descendant, 1, 1)
    if data.get("base_commit", {}).get("sha") != ancestor or not _sha(data.get("merge_base_commit", {}).get("sha")):
        raise ValueError("Could not verify commit ancestry")
    return (data.get("status") == "ahead" and data.get("behind_by") == 0
            and data["merge_base_commit"]["sha"] == ancestor)


async def _classify_exclusion(client, owner, name, baseline, target, row, semaphore):
    if row["reason"] != "outside_comparison":
        return row
    revision = row["merge_commit_sha"]
    async with semaphore:
        if await _ancestor(client, owner, name, revision, baseline):
            return {**row, "reason": "already_in_baseline"}
        if await _ancestor(client, owner, name, target, revision):
            return {**row, "reason": "after_target"}
    return row


async def _exclusions(client, owner, name, baseline, target, rows):
    semaphore = asyncio.Semaphore(8)
    return await _batch(_classify_exclusion(client, owner, name, baseline, target, row, semaphore) for row in rows)


def _attribute(commits, associations, prs):
    assigned = {sha: set() for sha in commits}
    modes = {}
    for number, pr in prs.items():
        merge_sha = pr["merge_commit_sha"]
        parents = commits[merge_sha]["parents"]
        head = (pr.get("head") or {}).get("sha")
        if not _sha(head) or not parents:
            raise ValueError(f"PR #{number} has incomplete Git ancestry")
        unique = {merge_sha}
        if len(parents) == 2:
            if parents[1] != head:
                raise ValueError(f"The second parent of PR #{number} does not match the recorded PR head")
            unique |= _reachable(commits, parents[1]) - _reachable(commits, parents[0])
            modes[number] = "merge"
        else:
            # GitHub rebases rewrite commit identities. Require unique provider
            # attribution on a contiguous parent chain ending at the PR merge SHA.
            previous = parents[0]
            while (previous in commits and associations[previous] & prs.keys() == {number}
                   and len(commits[previous]["parents"]) == 1):
                if previous in unique:
                    raise ValueError("Commit ancestry contains a cycle")
                unique.add(previous)
                previous = commits[previous]["parents"][0]
            if len(unique) > 1:
                if pr.get("commits") != len(unique):
                    raise ValueError(f"Rebased PR #{number} has incomplete commit attribution")
                modes[number] = "rebase"
            else:
                modes[number] = "single_commit"
        for sha in unique:
            assigned[sha].add(number)
    return assigned, modes


async def _original_pr_commits(client, owner, name, number, length):
    shas = []
    for page in range(1, (length + 49) // 50 + 1):
        rows, more = await client.pull_request_commit_page(owner, name, number, page, 50)
        if not isinstance(rows, list) or not rows or len(rows) > 50:
            raise ValueError(f"Original commit history for rebased PR #{number} is incomplete")
        shas.extend(row.get("sha") for row in rows)
        if len(shas) > length or more != (len(shas) < length):
            raise ValueError(f"Original commit history for rebased PR #{number} is incomplete")
        if not more:
            break
    if len(shas) != length or not all(_sha(sha) for sha in shas) or len(set(shas)) != length:
        raise ValueError(f"Original commit history for rebased PR #{number} is incomplete")
    return shas


async def _patch_identity(client, owner, name, sha, semaphore):
    async with semaphore:
        item = await client.get_commit(owner, name, sha)
    files = item.get("files")
    if item.get("sha") != sha or not isinstance(files, list) or not 0 < len(files) < 300:
        raise ValueError("A complete text patch is required to verify rebased commits")
    identity = []
    added = deleted = patch_size = 0
    for row in files:
        patch = row.get("patch")
        if (not isinstance(row.get("filename"), str) or not isinstance(patch, str) or not patch
                or len(patch) > 180_000 or "\n...\n" in patch or not _HUNK_OFFSET.search(patch)):
            raise ValueError("A complete text patch is required to verify rebased commits")
        patch_size += len(patch)
        if patch_size > 512_000:
            raise ValueError("Rebase patch verification exceeds the discovery limit")
        additions = sum(line.startswith("+") for line in patch.splitlines())
        deletions = sum(line.startswith("-") for line in patch.splitlines())
        if additions != row.get("additions") or deletions != row.get("deletions"):
            raise ValueError("A rebased commit patch was truncated or inconsistent")
        # Rebasing can shift the line numbers while retaining exactly the same hunks.
        normalized = _HUNK_OFFSET.sub(lambda match: "@@ -" + (match[1] or "") + " +" + (match[2] or "") + " @@", patch)
        identity.append((row["filename"], row.get("previous_filename") or "", row.get("status") or "", normalized))
        added += additions
        deleted += deletions
    if any(item.get("stats", {}).get(key) != value for key, value in
           (("additions", added), ("deletions", deleted), ("total", added + deleted))):
        raise ValueError("GitHub commit statistics disagree with the rebased patch")
    return canonical_digest(sorted(identity))


async def _verify_rebases(client, owner, name, commits, assigned, prs, modes):
    semaphore = asyncio.Semaphore(8)
    for number, mode in modes.items():
        if mode != "rebase":
            continue
        rebased = [prs[number]["merge_commit_sha"]]
        while assigned.get(commits[rebased[-1]]["parents"][0]) == {number}:
            rebased.append(commits[rebased[-1]]["parents"][0])
        originals = await _original_pr_commits(client, owner, name, number, len(rebased))
        if originals[-1] != prs[number]["head"]["sha"]:
            raise ValueError(f"Original commit list does not match the head of rebased PR #{number}")
        shas = originals + list(reversed(rebased))
        patches = await _batch(_patch_identity(client, owner, name, sha, semaphore) for sha in shas)
        if patches[:len(originals)] != patches[len(originals):]:
            raise ValueError(f"Rebased PR #{number} could not be reconciled with its original patches")


def _text_in_limit(value, limit):
    return value is None or isinstance(value, str) and len(value) <= limit


def _requirements_in_limit(value):
    return (_text_in_limit(value, 8000) or isinstance(value, list) and len(value) <= 40
            and all(isinstance(line, str) and len(line) <= 600 for line in value))


async def _read_tasks(scope, repository, prs):
    pr_output, tasks, blockers = [], {}, []
    for number, provider in prs.items():
        pr = {"number": number, "github_id": provider["id"], "head_sha": provider["head"]["sha"],
              "merge_commit_sha": provider["merge_commit_sha"], "title": str(provider.get("title") or "")[:300],
              "task_ids": []}
        pr_output.append(pr)
        local = await col("pull_requests").find({**scope, "repo_id": {
            "$regex": "^" + re.escape(repository) + "$", "$options": "i", "$not": {"$type": "array"}},
            "pr_number": {"$eq": number, "$not": {"$type": "array"}}}, {"id": 1, "head_sha": 1}).limit(2).to_list(2)
        if len(local) > 1:
            blockers.append(f"PR #{number} has ambiguous local records")
            continue
        links = []
        if len(local) == 1 and isinstance(local[0].get("id"), str):
            if local[0].get("head_sha") == pr["head_sha"]:
                pr["local_pr_id"] = local[0]["id"]
            links = await col("entity_relationships").find({
                "source_type": "pull_request", "source_id": local[0]["id"], "target_type": "task",
                "relationship_type": "implements",
            }, {"target_id": 1}).limit(MAX_TASKS + 1).to_list(MAX_TASKS + 1)
        refs = {row["target_id"] for row in links if isinstance(row.get("target_id"), str)}
        body = provider.get("body") or ""
        if (len(links) > MAX_TASKS or any(not isinstance(row.get("target_id"), str) for row in links)
                or not isinstance(body, str) or len(body) > 70_000):
            blockers.append(f"PR #{number} has malformed or excessive task links")
            continue
        refs.update(match.upper() for match in TASK_ID_PATTERN.findall(body))
        if not refs or len(refs | tasks.keys()) > MAX_TASKS:
            blockers.append(f"PR #{number} requires bounded, verified task links")
            continue
        for task_id in sorted(refs):
            if task_id not in tasks:
                rows = await col("tasks").find({**scope, "id": task_id}, {
                    "id": 1, "title": 1, "status": 1, "assignee_id": 1, "story_id": 1,
                    "last_transition_id": 1, "acceptance_criteria": 1,
                }).limit(2).to_list(2)
                if len(rows) != 1 or rows[0].get("id") != task_id:
                    blockers.append(f"PR #{number} references a task outside its project or with an ambiguous identity")
                    continue
                task = {key: value for key, value in rows[0].items() if key != "_id"}
                if (not all(_text_in_limit(task.get(key), limit) for key, limit in
                            (("title", 300), ("status", 50), ("assignee_id", 128),
                             ("story_id", 128), ("last_transition_id", 128)))
                        or not _requirements_in_limit(task.get("acceptance_criteria"))):
                    blockers.append(f"Task {task_id} has unsupported requirement or workflow fields")
                    continue
                task["story"] = None
                task["pr_numbers"] = []
                if isinstance(task.get("story_id"), str):
                    stories = await col("stories").find({**scope, "id": task["story_id"]}, {
                        "_id": 0, "id": 1, "title": 1, "description": 1, "acceptance_criteria": 1,
                    }).limit(2).to_list(2)
                    if len(stories) != 1 or stories[0].get("id") != task["story_id"]:
                        blockers.append(f"Task {task_id} has an unavailable or ambiguous story")
                    elif (not _text_in_limit(stories[0].get("title"), 300)
                          or not _text_in_limit(stories[0].get("description"), 8000)
                          or not _requirements_in_limit(stories[0].get("acceptance_criteria"))):
                        blockers.append(f"Task {task_id} has unsupported story requirements")
                    else:
                        task["story"] = stories[0]
                tasks[task_id] = task
            tasks[task_id]["pr_numbers"].append(number)
            pr["task_ids"].append(task_id)
    return pr_output, [tasks[key] for key in sorted(tasks)], blockers


async def _reverts(client, owner, name, baseline, commits):
    result = []
    for item in commits.values():
        for original in item["revert_refs"] or ([None] if item["subject"].lower().startswith("revert") else []):
            if len(result) >= MAX_PULL_REQUESTS:
                raise ValueError("Revert ancestry exceeds the discovery limit")
            previous = commits.get(original)
            prior_tree = (commits.get(previous["parents"][0], {}).get("tree") if previous and previous["parents"] else None)
            exact_tree = bool(prior_tree and prior_tree == item["tree"] and item["parents"] == [original])
            in_baseline = False
            if original and not previous:
                try:
                    in_baseline = await _ancestor(client, owner, name, original, baseline)
                except httpx.HTTPStatusError as error:
                    if error.response.status_code not in {404, 422}:
                        raise
            result.append({"revision": item["sha"], "referenced_revision": original,
                           "status": "tree_restored" if exact_tree else "review_required",
                           "original_in_candidate": previous is not None, "original_in_baseline": in_baseline,
                           "ancestry_verified": bool(original != item["sha"] and (
                               in_baseline or original in _reachable(commits, item["sha"])))})
    return result


async def discover(project_id, organization_id, baseline_sha, target_sha, run_id=None, artifact_id=None, *, client=None):
    """Build a deterministic manifest, retaining missing scope as blockers."""
    result = {"repository": None, "repository_id": None, "complete": False, "scope_complete": False,
              "blockers": [], "commits": [], "pull_requests": [], "excluded_pull_requests": [], "tasks": [],
              "unmapped_commits": [], "reverts": [], "artifact": None}
    client = client or GitHubClient()
    blockers = result["blockers"]
    try:
        async with asyncio.timeout(45):
            owner, name = await _repository(project_id, organization_id)
            repository = f"{owner}/{name}"
            info = await client.get_repository(owner, name)
            repository_id = info.get("id")
            if not _repository_matches(info, repository_id, repository):
                raise ValueError("GitHub repository identity could not be verified")
            result.update(repository=repository, repository_id=repository_id)
            commits = await _compare(client, owner, name, baseline_sha, target_sha)
            result["commits"] = list(commits.values())
            result["reverts"] = await _reverts(client, owner, name, baseline_sha, commits)
            associations, prs, excluded = await _pull_requests(client, owner, name, repository_id, commits)
            result["excluded_pull_requests"] = await _exclusions(client, owner, name, baseline_sha, target_sha, excluded)
            assigned, modes = _attribute(commits, associations, prs)
            await _verify_rebases(client, owner, name, commits, assigned, prs, modes)
            direct = [sha for sha, pr_numbers in assigned.items() if len(pr_numbers) != 1]
            result["unmapped_commits"] = direct
            if direct:
                blockers.append("Some commits have no verified pull request or have overlapping attribution")
            scope = PRRepository._project_scope([project_id], organization_id)
            pr_rows, tasks, missing = await _read_tasks(scope, repository, prs)
            for pr in pr_rows:
                pr["integration"] = modes[pr["number"]]
                pr["commits"] = [sha for sha, numbers in assigned.items() if pr["number"] in numbers]
            result.update(pull_requests=pr_rows, tasks=tasks)
            blockers.extend(missing)
    except HTTPException as error:
        blockers.append(str(error.detail))
    except (httpx.HTTPError, TimeoutError):
        blockers.append("GitHub release scope is temporarily unavailable")
    except ValueError as error:
        blockers.append(str(error))
    except (AttributeError, KeyError, TypeError):
        blockers.append("GitHub returned incomplete release-scope evidence")
    result["scope_complete"] = bool(result["pull_requests"]) and not blockers
    if result["repository_id"] and (run_id is not None or artifact_id is not None):
        try:
            async with asyncio.timeout(45):
                result["artifact"] = await verify_artifact(client, owner, name, result["repository_id"],
                                                           target_sha, run_id, artifact_id)
        except HTTPException as error:
            blockers.append(str(error.detail))
        except (httpx.HTTPError, TimeoutError):
            blockers.append("GitHub build provenance is temporarily unavailable")
        except (AttributeError, KeyError, TypeError):
            blockers.append("GitHub returned incomplete build provenance")
        except ValueError as error:
            blockers.append(str(error))
    result["complete"] = result["scope_complete"] and result["artifact"] is not None
    return result
