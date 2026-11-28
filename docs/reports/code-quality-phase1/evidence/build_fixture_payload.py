"""Build one quality-snapshot payload holding every Phase 1 single-file analyzer fixture."""
import json
import sys

from intelligence.analyzers.isolated import snapshot_payload, source_provenance

import os
EXCLUDE = set(filter(None, os.environ.get("EXCLUDE", "").split(",")))
cases = [c for c in json.load(open("/fx/analyzer_cases.json"))["cases"] if c.get("path") and c["id"] not in EXCLUDE]
sources = {f"fx/{c['id']}/{c['path']}": c["source"] for c in cases}
revision = "f" * 40
context = {"project_id": "P", "organization_id": "ORG", "commit_sha": revision, "source_files": sources,
           "source_provenance": source_provenance("P", "owner/fixtures", revision, sources, "ORG")}
json.dump(snapshot_payload(list(sources), context), sys.stdout)
