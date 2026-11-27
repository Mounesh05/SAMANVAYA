"""v4 live E2E (DEF-V4-028): JS PR comparisons were never available in the isolated worker.

The worker has no network, so `npm audit` always fails for a repository with a
package.json. It was recorded as a generic "npm-audit" skip, which the PR
comparability rule does not accept as an environment skip, so sindresorhus/p-limit
PR #93 got "partial_evidence" and no comparison. Python already records the same
situation as "dependency-advisories-offline" without attempting the lookup.
"""

from unittest.mock import AsyncMock

import pytest

from domain.services.pr_quality_comparison import comparable_sides
from intelligence.analyzers.javascript import analyzer as js

pytestmark = pytest.mark.anyio


async def test_isolated_worker_records_offline_advisories_without_running_npm(tmp_path, monkeypatch):
    (tmp_path / "package.json").write_text('{"name": "x", "version": "1.0.0"}')
    (tmp_path / "index.js").write_text("export const a = 1;\n")
    run = AsyncMock(return_value=None)
    monkeypatch.setattr(js, "_run", run)
    evidence = await js.JavaScriptAnalyzer().analyze(["index.js"], str(tmp_path), {"isolated_quality_worker": True})
    assert "dependency-advisories-offline" in evidence.tools_skipped
    assert "npm-audit" not in evidence.tools_skipped
    assert not any(call.args[0][:2] == ["npm", "audit"] for call in run.await_args_list)


def test_offline_advisories_keep_js_sides_comparable():
    side = {"quality_score": 95, "quality_analysis_status": "partial", "policy_digest": "p",
            "tools_executed": ["eslint", "lizard"],
            "tools_skipped": ["tsc:configuration-unavailable", "dependency-advisories-offline", "coverage"]}
    assert comparable_sides(dict(side), dict(side)) is None
