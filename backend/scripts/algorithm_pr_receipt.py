"""Read-only source and static-analysis receipt for a pinned GitHub pull request."""

import argparse
import asyncio
import json

from domain.services.github_api_service import GitHubAPIService
from domain.services.pr_algorithm_intelligence_service import changed_functions, static_findings
from intelligence.algorithms.discovery.service import discover_sources


async def inspect(repository, number):
    owner, repo = repository.split("/")
    api = GitHubAPIService()
    pr = await api.client.get_pull_request(owner, repo, number)
    files = await api.client.get_pr_files(owner, repo, number)
    if len(files) != pr["changed_files"]:
        raise ValueError("Changed file list incomplete")
    snapshots = {}
    receipt = {"repository": repository, "pull_request": number, "changed_files": len(files)}
    for side in ("base", "head"):
        revision = pr[side]["sha"]
        paths = files if side == "head" else [
            {"filename": f.get("previous_filename", f["filename"])} for f in files if f["status"] != "added"]
        sources, diagnostics = await api.fetch_analysis_sources(
            owner, repo, paths, revision, include_context=True, verified_snapshot=True, include_quality_context=False)
        report = await discover_sources(sources, repository, revision, diagnostics)
        snapshots[side] = (sources, report.model_dump())
        receipt[side] = {"sha": revision, "files_read": len(sources), "discovery_status": report.status,
                         "functions": len(report.functions), "diagnostics": [d.get("kind") for d in report.diagnostics]}
    before, base = snapshots["base"]
    after, head = snapshots["head"]
    receipt["changed_functions"] = []
    for row in changed_functions(base, head, files, before, after):
        fn = row["current"]
        cost = static_findings(fn, after[fn["path"]])["complexity"]
        receipt["changed_functions"].append({"function_id": fn["function_id"], "source_hash": fn["source_hash"],
                                            "mode": row["mode"], "language": fn["language"], "bound": cost["time_complexity"]})
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository")
    parser.add_argument("number", type=int)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(inspect(args.repository, args.number)), indent=2))
