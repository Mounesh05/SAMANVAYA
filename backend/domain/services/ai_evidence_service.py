"""Read-only evidence resolution for generic AI assistance, independent of scoring."""

import asyncio
import base64
import hashlib
import hmac
import json
import re
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException

from core.database import col
from core.permissions import Permission
from domain.models.performance_evidence import canonical_digest
from domain.services.ai_run_access import permissions
from integrations.github.client import GitHubClient

MAX_SOURCE_BYTES = 32768


async def _repository(project_id, organization_id):
    configs = await col("github_project_configs").find({"project_id": project_id}).limit(2).to_list(2)
    if len(configs) != 1:
        raise HTTPException(409, "One exact connected repository is required")
    config = configs[0]
    owner, name = config.get("repository_owner"), config.get("repository_name")
    if not all(isinstance(value, str) and value not in {".", ".."}
               and re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", value) for value in (owner, name)):
        raise HTTPException(409, "The repository mapping is invalid")
    for key in ("org_id", "organization_id"):
        if key in config and config[key] != organization_id:
            raise HTTPException(409, "The repository mapping has conflicting tenant provenance")
    # GitHub repository identity is case-insensitive.
    bindings = await col("github_project_configs").find({
        "repository_owner": {"$regex": "^" + re.escape(owner) + "$", "$options": "i"},
        "repository_name": {"$regex": "^" + re.escape(name) + "$", "$options": "i"},
    }).limit(2).to_list(2)
    if len(bindings) != 1 or bindings[0].get("project_id") != project_id:
        raise HTTPException(409, "Repository ownership is ambiguous")
    return owner, name


async def _file(client, owner, name, reference):
    revision, path = reference.source_revision, reference.path
    commit = await client.get_commit(owner, name, revision)
    if not isinstance(commit, dict) or commit.get("sha") != revision:
        raise HTTPException(409, "The exact source revision could not be verified")
    tree_sha = commit.get("commit", {}).get("tree", {}).get("sha")
    if not isinstance(tree_sha, str) or not re.fullmatch(r"[a-f0-9]{40}", tree_sha):
        raise HTTPException(409, "The source tree revision is unavailable")
    tree = await client.get_source_tree(owner, name, tree_sha)
    entries = [entry for entry in tree.get("tree", []) if entry.get("path") == path]
    if tree.get("truncated") or len(entries) != 1 or entries[0].get("type") != "blob" or entries[0].get("mode") not in {"100644", "100755"}:
        raise HTTPException(409, "A complete regular-file tree entry is required")
    data = await client.get_file(owner, name, path, ref=revision)
    if (not isinstance(data, dict) or data.get("type") != "file" or data.get("encoding") != "base64"
            or data.get("path") != path or type(data.get("size")) is not int
            or not 0 <= data["size"] <= MAX_SOURCE_BYTES or not isinstance(data.get("content"), str)
            or len(data["content"]) > MAX_SOURCE_BYTES * 2):
        raise HTTPException(409, "Unsupported or oversized source response")
    try:
        raw = base64.b64decode("".join(data["content"].split()), validate=True)
        content = raw.decode("utf-8")
    except (ValueError, UnicodeError):
        raise HTTPException(409, "Source encoding could not be verified") from None
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    digest = hashlib.sha256(raw).hexdigest()
    if (len(raw) != data["size"] or blob != data.get("sha") or blob != entries[0].get("sha")
            or not hmac.compare_digest(digest, reference.content_sha256)):
        raise HTTPException(409, "Source integrity or expected evidence hash mismatch")
    return {"kind": "github_file", "repository": owner + "/" + name, "path": path,
            "source_revision": revision, "content_sha256": digest, "blob_sha": blob,
            "status": "SERVER_VERIFIED", "verification_scope": "GITHUB_BLOB_AT_COMMIT",
            "content": content}


async def prepare_evidence(user, scope, task, evidence, context, references):
    sources = []
    if references:
        if user.get("role", "").upper() == "HR" or Permission.VIEW_AI_EVALUATION not in permissions(user):
            raise HTTPException(403, "Technical source evidence is not available to this account")
        if task != "code_review" or not scope["project_id"]:
            raise HTTPException(422, "File evidence v1 requires a scoped code_review request")
        owner, name = await _repository(scope["project_id"], scope["organization_id"])
        try:
            async with asyncio.timeout(30):
                client = GitHubClient()
                for reference in references:
                    source = await _file(client, owner, name, reference)
                    sources.append({**source, "project_id": scope["project_id"],
                                    "organization_id": scope["organization_id"]})
        except HTTPException:
            raise
        except (httpx.HTTPError, TimeoutError):
            raise HTTPException(503, "Source evidence is unavailable") from None
        except (KeyError, TypeError, AttributeError):
            raise HTTPException(409, "Source response could not be verified") from None
    caller = {"evidence": evidence, "context": context}
    try:
        digest = canonical_digest(caller)
    except (ValueError, TypeError):
        raise HTTPException(422, "Caller inputs must contain finite JSON values") from None
    provenance = {"schema_version": "ai-evidence-v1", "captured_at": datetime.now(timezone.utc).isoformat(),
                  "caller_evidence": {"status": "UNVERIFIED", "content_sha256": digest},
                  "server_sources": [{key: value for key, value in source.items() if key != "content"} for source in sources],
                  "model_interpretation": "ADVISORY"}
    prepared = dict(evidence)
    if task == "code_review":
        prepared["evidence_summary"] = (
            "Caller-supplied inputs are UNVERIFIED. Interpretations and numerical claims are ADVISORY.\n"
            + json.dumps(caller, allow_nan=False)
            + "\nServer-resolved file evidence (verification covers source identity and bytes only):\n"
            + json.dumps(sources, allow_nan=False)
        )
    stored = {"caller_supplied": caller, "server_sources": sources}
    return prepared, stored, provenance
