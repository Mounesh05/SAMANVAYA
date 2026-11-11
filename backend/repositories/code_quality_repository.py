"""Function snapshots use the existing project-scoped code-quality run storage."""

import uuid
from datetime import datetime, timezone

from core.database import col


class CodeQualityRepository:
    async def save_discovery(self, project_id, report, pr_number=None, triggered_by="system"):
        run_id = "RUN-" + uuid.uuid4().hex[:12].upper()
        now = datetime.now(timezone.utc).isoformat()
        languages = sorted({f.language for f in report.functions})
        await col("code_quality_runs").insert_one({
            "run_id": run_id, "repository_id": project_id, "pr_number": pr_number,
            "commit_sha": report.source_revision, "analysis_level": "purpose_discovery",
            "status": "completed", "created_at": now, "completed_at": now,
            "triggered_by": triggered_by, "language": languages[0] if languages else "unknown",
            "detected_languages": languages, "function_discovery": report.model_dump(mode="json"),
            "quality_score": None, "risk_score": None,
        })
        return run_id
