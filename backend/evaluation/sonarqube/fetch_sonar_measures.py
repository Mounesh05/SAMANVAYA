"""
Download SonarQube's results for one project into a JSON file that the
comparison scripts read (compare_duplication.py, compare_sonarqube.py).

Run it yourself after scanning (see evaluation/README.md). The token is read
from the SONAR_TOKEN environment variable; it is never written to the output.

    python evaluation/sonarqube/fetch_sonar_measures.py --project samanvaya-backend
           [--host http://localhost:9000] [--out evaluation/results/sonar_measures.json]

Fetches (SonarQube Web API):
    /api/measures/component        project measures
    /api/measures/component_tree   per-file measures
    /api/duplications/show         duplicated blocks of each file with duplicates
    /api/issues/search             open issues with their remediation effort
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

METRICS = [
    "ncloc", "functions", "complexity", "cognitive_complexity",
    "duplicated_lines", "duplicated_blocks", "duplicated_lines_density",
    "code_smells", "bugs", "vulnerabilities",
    "sqale_index", "sqale_debt_ratio", "sqale_rating",
]
FILE_METRICS = [m for m in METRICS if m not in ("sqale_debt_ratio", "sqale_rating")]
PAGE_SIZE = 500
MINUTES_PER_DAY = 8 * 60  # SonarQube's default working day

GetJson = Callable[[str, Dict[str, Any]], Dict[str, Any]]


def effort_minutes(effort: Optional[str]) -> int:
    """SonarQube effort strings ("2d 1h 5min", "45min") -> minutes (8-hour days)."""
    if not effort:
        return 0
    units = {"d": MINUTES_PER_DAY, "h": 60, "min": 1}
    return sum(int(n) * units[u] for n, u in re.findall(r"(\d+)\s*(min|d|h)", effort))


def rating_letter(value: Any) -> Optional[str]:
    """sqale_rating "1.0".."5.0" -> "A".."E"."""
    try:
        return "ABCDE"[int(float(value)) - 1]
    except (TypeError, ValueError, IndexError):
        return None


def http_getter(host: str, token: str) -> GetJson:
    auth = base64.b64encode(f"{token}:".encode()).decode()

    def get(path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{host.rstrip('/')}{path}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}"})
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))

    return get


def _measures(items: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    return {m["metric"]: m.get("value") for m in items}


def _strip_key(component_key: str, project: str) -> str:
    prefix = f"{project}:"
    return component_key[len(prefix):] if component_key.startswith(prefix) else component_key


def fetch(get: GetJson, project: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {"project_key": project, "fetched_at": datetime.now(timezone.utc).isoformat()}

    component = get("/api/measures/component", {"component": project, "metricKeys": ",".join(METRICS)})
    project_measures = _measures(component.get("component", {}).get("measures", []))
    project_measures["sqale_rating_letter"] = rating_letter(project_measures.get("sqale_rating"))
    result["project"] = {"measures": project_measures}

    files: Dict[str, Dict[str, Any]] = {}
    page = 1
    while True:
        tree = get("/api/measures/component_tree", {
            "component": project, "metricKeys": ",".join(FILE_METRICS),
            "qualifiers": "FIL", "ps": PAGE_SIZE, "p": page,
        })
        for comp in tree.get("components", []):
            path = comp.get("path") or _strip_key(comp["key"], project)
            files[path.replace("\\", "/")] = {"key": comp["key"], "measures": _measures(comp.get("measures", []))}
        paging = tree.get("paging", {})
        if page * PAGE_SIZE >= int(paging.get("total", 0)):
            break
        page += 1
    result["files"] = files

    groups: List[List[Dict[str, Any]]] = []
    seen = set()
    for path, info in files.items():
        if float(info["measures"].get("duplicated_lines", 0) or 0) <= 0:
            continue
        dup = get("/api/duplications/show", {"key": info["key"]})
        refs = {ref: _strip_key(f["key"], project) for ref, f in dup.get("files", {}).items()}
        for duplication in dup.get("duplications", []):
            blocks = [
                {"path": refs.get(b.get("_ref"), path), "start": int(b["from"]), "end": int(b["from"]) + int(b["size"]) - 1}
                for b in duplication.get("blocks", [])
            ]
            key = tuple(sorted((b["path"], b["start"], b["end"]) for b in blocks))
            if len(blocks) > 1 and key not in seen:  # each group is listed once per file it touches
                seen.add(key)
                groups.append(blocks)
    result["duplications"] = groups

    issues: List[Dict[str, Any]] = []
    page = 1
    while True:
        found = get("/api/issues/search", {"componentKeys": project, "resolved": "false", "ps": PAGE_SIZE, "p": page})
        for issue in found.get("issues", []):
            issues.append({
                "rule": issue.get("rule"),
                "type": issue.get("type"),
                "severity": issue.get("severity"),
                "path": _strip_key(issue.get("component", ""), project),
                "line": issue.get("line"),
                "effort_minutes": effort_minutes(issue.get("effort") or issue.get("debt")),
                "message": issue.get("message"),
            })
        total = int(found.get("paging", {}).get("total", found.get("total", 0)))
        if page * PAGE_SIZE >= total or page * PAGE_SIZE >= 10_000:  # API limit: 10,000 results
            break
        page += 1
    result["issues"] = issues
    return result


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", default="samanvaya-backend")
    parser.add_argument("--host", default=os.environ.get("SONAR_HOST_URL", "http://localhost:9000"))
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "results" / "sonar_measures.json")
    args = parser.parse_args(argv)
    token = os.environ.get("SONAR_TOKEN")
    if not token:
        sys.exit("Set the SONAR_TOKEN environment variable to a SonarQube user token first.")
    data = fetch(http_getter(args.host, token), args.project)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"Saved {len(data['files'])} files, {len(data['duplications'])} duplication groups, "
          f"{len(data['issues'])} issues -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
