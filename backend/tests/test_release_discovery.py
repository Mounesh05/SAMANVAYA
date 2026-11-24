"""Release discovery must account for every commit and bind exact build evidence."""

import base64
import hashlib
from unittest.mock import AsyncMock

import pytest

from core import database
from core.config import settings
from domain.services import release_discovery as discovery


pytestmark = pytest.mark.anyio
BASE, A, B, TARGET, EXTRA, ORIGINAL, TREE = (char * 40 for char in "0123456")
REPO = {"id": 97, "full_name": "acme/tools"}
TASK = "TSK-1234ABCD"
OTHER_TASK = "TSK-0000ABCD"


def commit(sha, *parents, message="Change", tree=TREE):
    return {"sha": sha, "parents": [{"sha": parent} for parent in parents],
            "commit": {"tree": {"sha": tree}, "message": message}}


def comparison(baseline, commits, **changes):
    return {"status": "ahead", "behind_by": 0, "ahead_by": len(commits), "total_commits": len(commits),
            "base_commit": {"sha": baseline}, "merge_base_commit": {"sha": baseline}, "commits": commits, **changes}


def pr(number, merge, head=ORIGINAL, *, state="closed", body=TASK, commits=1):
    return {"number": number, "id": 100 + number, "merge_commit_sha": merge, "title": f"PR {number}",
            "base": {"repo": REPO}, "head": {"sha": head}, "state": state,
            "merged": state == "closed", "commits": commits, "body": body}


@pytest.fixture
async def setup(mock_db, monkeypatch):
    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    await mock_db.github_project_configs.insert_one({"project_id": "P", "org_id": "O", "repository_owner": "acme",
                                                      "repository_name": "tools"})
    await mock_db.tasks.insert_many([
        {"id": TASK, "project_id": "P", "title": "First task", "status": "done", "assignee_id": "E",
         "story_id": "S", "last_transition_id": "TR-current"},
        {"id": OTHER_TASK, "project_id": "P", "title": "Second task", "status": "done", "assignee_id": "E"},
    ])
    await mock_db.stories.insert_one({"id": "S", "project_id": "P", "title": "Acceptance story",
                                      "acceptance_criteria": ["CI passes on the merged target"]})
    client = AsyncMock()
    client.get_repository.return_value = REPO
    return mock_db, client


def configure(client, commits, mappings, prs):
    client.compare_revision_page.return_value = (comparison(BASE, commits), False)
    client.commit_pull_request_page.side_effect = lambda owner, name, sha, page, size: (
        [{"number": number} for number in mappings.get(sha, [])], False)
    client.get_pull_request.side_effect = lambda owner, name, number: prs[number]


async def test_discovers_normal_merge_squash_rebase_and_shared_task_links(setup):
    db, client = setup
    other, merge2, ref = "7" * 40, "8" * 40, "9" * 40
    configure(client, [
        commit(A, BASE), commit(B, BASE, A), commit(merge2, B), commit(other, merge2), commit(TARGET, other),
    ], {B: [1], merge2: [2], other: [3], TARGET: [3]},
        {1: pr(1, B, A), 2: pr(2, merge2, body=f"{TASK} {OTHER_TASK} {TASK}"), 3: pr(3, TARGET, ref, commits=2)})
    client.pull_request_commit_page.return_value = ([{"sha": ORIGINAL}, {"sha": ref}], False)
    patch_labels = {ORIGINAL: "a", other: "a", ref: "b", TARGET: "b"}
    def patch(owner, repo, sha):
        return {"sha": sha, "stats": {"additions": 1, "deletions": 1, "total": 2}, "files": [
            {"filename": "feature.py", "status": "modified", "additions": 1, "deletions": 1,
             "patch": f"@@ -1 +1 @@\n-old\n+{patch_labels[sha]}"}]}
    client.get_commit.side_effect = patch
    await db.pull_requests.insert_one({"id": "PR-local", "project_id": "P", "repo_id": "acme/tools", "pr_number": 1})
    await db.entity_relationships.insert_many([{"source_id": "PR-local", "source_type": "pull_request",
        "target_type": "task", "target_id": OTHER_TASK, "relationship_type": "implements"} for _ in range(2)])
    result = await discovery.discover("P", "O", BASE, TARGET, client=client)
    assert result["scope_complete"] and not result["complete"] and not result["unmapped_commits"]
    assert [row["integration"] for row in result["pull_requests"]] == ["merge", "single_commit", "rebase"]
    assert [row["commits"] for row in result["pull_requests"]] == [[A, B], [merge2], [other, TARGET]]
    assert [row["task_ids"] for row in result["pull_requests"]] == [[OTHER_TASK, TASK], [OTHER_TASK, TASK], [TASK]]
    tasks = {task["id"]: task for task in result["tasks"]}
    assert tasks[TASK]["story"]["acceptance_criteria"] == ["CI passes on the merged target"]
    assert tasks[TASK]["pr_numbers"] == [1, 2, 3]
    patch_labels[TARGET] = "changed since rebase"
    incomplete = await discovery.discover("P", "O", BASE, TARGET, client=client)
    assert not incomplete["scope_complete"] and "original patches" in incomplete["blockers"][0]


async def test_excludes_open_previously_deployed_and_later_prs_and_preserves_revert(setup):
    _, client = setup
    later = "7" * 40
    commits = [commit(A, BASE), commit(B, A), commit(TARGET, B, message=f"Revert feature\n\nThis reverts commit {B}.")]
    configure(client, commits, {A: [1, 9], B: [2, 8], TARGET: [3, 7]},
              {1: pr(1, A), 2: pr(2, B), 3: pr(3, TARGET), 9: pr(9, BASE), 8: pr(8, EXTRA, state="open"),
               7: pr(7, later)})
    def page(owner, repo, base, target, page, size):
        if (base, target) == (BASE, TARGET):
            return comparison(BASE, commits), False
        if (base, target) == (TARGET, later):
            return comparison(TARGET, [commit(later, TARGET)]), False
        return {**comparison(base, []), "status": "behind", "merge_base_commit": {"sha": BASE}}, False
    client.compare_revision_page.side_effect = page
    result = await discovery.discover("P", "O", BASE, TARGET, client=client)
    assert result["scope_complete"]
    assert [x["number"] for x in result["pull_requests"]] == [1, 2, 3]
    assert {x["number"]: x["reason"] for x in result["excluded_pull_requests"]} == {
        9: "already_in_baseline", 8: "unmerged", 7: "after_target"}
    assert result["reverts"] == [{"revision": TARGET, "referenced_revision": B, "status": "tree_restored",
                                  "original_in_candidate": True, "original_in_baseline": False, "ancestry_verified": True}]


async def test_hotfix_revert_preserves_prior_baseline_and_requires_review(setup):
    _, client = setup
    configure(client, [commit(TARGET, BASE, message=f"Revert part of deployed change\n\nThis reverts commit {BASE}.")],
              {TARGET: [1]}, {1: pr(1, TARGET)})
    result = await discovery.discover("P", "O", BASE, TARGET, client=client)
    assert result["scope_complete"]
    assert result["reverts"] == [{"revision": TARGET, "referenced_revision": BASE, "status": "review_required",
                                  "original_in_candidate": False, "original_in_baseline": True, "ancestry_verified": True}]


async def test_direct_commit_foreign_task_and_branch_only_link_block_scope(setup):
    db, client = setup
    await db.tasks.update_one({"id": TASK}, {"$set": {"organization_id": "FOREIGN"}})
    branch_only = pr(2, TARGET, body="")
    branch_only["head"]["ref"] = f"branch/{OTHER_TASK}"
    configure(client, [commit(A, BASE), commit(B, A), commit(TARGET, B)],
              {B: [1], TARGET: [2]}, {1: pr(1, B), 2: branch_only})
    result = await discovery.discover("P", "O", BASE, TARGET, client=client)
    assert not result["scope_complete"] and result["unmapped_commits"] == [A]
    assert any("outside its project" in reason for reason in result["blockers"])
    assert any("requires bounded, verified task links" in reason for reason in result["blockers"])
    assert not result["tasks"]


async def test_discovery_checks_all_pages_and_rejects_incomplete_responses(setup, monkeypatch):
    _, client = setup
    monkeypatch.setattr(discovery, "COMPARE_PAGE_SIZE", 1)
    configure(client, [], {A: [1], TARGET: [2]}, {1: pr(1, A), 2: pr(2, TARGET)})
    first, second = comparison(BASE, [commit(A, BASE)]), comparison(BASE, [commit(TARGET, A)])
    for page in (first, second):
        page.update(total_commits=2, ahead_by=2)
    client.compare_revision_page.side_effect = [(first, True), (second, False)]
    assert (await discovery.discover("P", "O", BASE, TARGET, client=client))["scope_complete"]
    client.compare_revision_page.side_effect = [(first, False)]
    incomplete = await discovery.discover("P", "O", BASE, TARGET, client=client)
    assert not incomplete["scope_complete"] and "pagination disagree" in incomplete["blockers"][0]


@pytest.mark.parametrize("breakage", ["diverged", "missing_parent", "merge_base"])
async def test_invalid_baseline_or_unreachable_graph_blocks_discovery(setup, breakage):
    _, client = setup
    commits = [commit(A, BASE), commit(TARGET, EXTRA if breakage == "missing_parent" else A)]
    data = comparison(BASE, commits)
    if breakage == "diverged":
        data["status"] = "diverged"
    if breakage == "merge_base":
        data["merge_base_commit"] = {"sha": EXTRA}
    client.compare_revision_page.return_value = data, False
    result = await discovery.discover("P", "O", BASE, TARGET, client=client)
    assert not result["scope_complete"] and result["blockers"]
    client.commit_pull_request_page.assert_not_called()


@pytest.fixture
def build(monkeypatch):
    client = AsyncMock()
    workflow_path = ".github/workflows/samanvaya-release-build.yml"
    raw = b"name: Reviewed build\n"
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    workflow_hash = hashlib.sha256(raw).hexdigest()
    monkeypatch.setattr(settings, "RELEASE_TRUSTED_WORKFLOW_PATH", workflow_path)
    monkeypatch.setattr(settings, "RELEASE_TRUSTED_WORKFLOW_SHA256", workflow_hash)
    monkeypatch.setattr(settings, "RELEASE_TRUSTED_BUILD_REF", "main")
    client.get_commit.return_value = {"sha": TARGET, "commit": {"tree": {"sha": TREE}}}
    client.get_source_tree.return_value = {"tree": [{"path": workflow_path, "type": "blob", "mode": "100644", "sha": blob}]}
    client.get_file.return_value = {"type": "file", "path": workflow_path, "encoding": "base64",
                                    "size": len(raw), "sha": blob, "content": base64.b64encode(raw).decode()}
    run = {"id": 47, "path": workflow_path, "workflow_id": 11, "event": "push", "status": "completed",
           "conclusion": "success", "run_attempt": 2, "head_sha": TARGET, "head_branch": "main", "repository": REPO,
           "head_repository": REPO, "run_started_at": "2026-11-24T14:00:00Z", "updated_at": "2026-11-24T14:07:00Z"}
    archive = b"demonstration archive bytes"
    artifact = {"id": 116, "name": "samanvaya-candidate-47-2", "expired": False, "created_at": "2026-11-24T14:04:00Z",
                "digest": "sha256:" + hashlib.sha256(archive).hexdigest(), "size_in_bytes": len(archive),
                "workflow_run": {"id": 47, "head_sha": TARGET, "head_branch": "main",
                                 "repository_id": REPO["id"], "head_repository_id": REPO["id"]}}
    client.get_workflow_run.return_value = run
    client.get_workflow_artifacts.return_value = {"artifacts": [artifact], "total_count": 1}
    client.download_workflow_artifact.return_value = archive
    return client, run, artifact


async def test_artifact_is_pinned_to_verified_workflow_and_exact_github_archive(build):
    client, run, artifact = build
    result = await discovery.verify_artifact(client, "acme", "tools", REPO["id"], TARGET, run["id"], artifact["id"])
    assert result["digest"] == artifact["digest"][7:] and result["algorithm"] == "sha256"
    assert result["workflow_sha256"] == settings.RELEASE_TRUSTED_WORKFLOW_SHA256
    assert result["run_attempt"] == 2
    client.get_file.assert_awaited_once_with("acme", "tools", run["path"], ref=TARGET)


@pytest.mark.parametrize("reason", ["wrong_branch", "pull_request", "wrong_repo", "expired", "previous_attempt", "stale_time",
                                    "corrupt_bytes", "bad_workflow_pin", "rerun_race"])
async def test_artifact_rejects_invalid_provenance(build, monkeypatch, reason):
    client, run, artifact = build
    if reason == "wrong_branch":
        run["head_branch"] = "feature"
    elif reason == "pull_request":
        run["event"] = "pull_request"
    elif reason == "wrong_repo":
        artifact["workflow_run"]["repository_id"] = 96
    elif reason == "expired":
        artifact["expired"] = True
    elif reason == "previous_attempt":
        artifact["name"] = "samanvaya-candidate-47-1"
    elif reason == "stale_time":
        artifact["created_at"] = "2026-11-24T12:04:00Z"
    elif reason == "corrupt_bytes":
        client.download_workflow_artifact.return_value = b"corrupt"
    elif reason == "bad_workflow_pin":
        monkeypatch.setattr(settings, "RELEASE_TRUSTED_WORKFLOW_SHA256", "0" * 64)
    else:
        client.get_workflow_run.side_effect = [run, {**run, "run_attempt": 3}]
    with pytest.raises((ValueError, discovery.HTTPException)):
        await discovery.verify_artifact(client, "acme", "tools", REPO["id"], TARGET, run["id"], artifact["id"])
