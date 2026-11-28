"""DEF-CQ1-01: one unparsable Python file no longer fails complexity for the whole snapshot.

Found by running the Phase 1 analyzer fixtures through samanvaya-quality:3: radon
reports a file it cannot parse as {"error": ...}; the parser crashed, so every
Python file lost its complexity and the report showed JS-only numbers.
"""
import json

import pytest

from intelligence.analyzers.common import complexity


@pytest.mark.anyio
async def test_radon_measures_parseable_files_and_counts_the_unparsed(monkeypatch):
    output = {"fx/broken.py": {"error": "invalid syntax (<unknown>, line 1)"},
              "fx/branches.py": [{"type": "function", "name": "choose", "complexity": 3, "rank": "A"}]}

    async def fake_run(cmd):
        return json.dumps(output)

    monkeypatch.setattr(complexity, "_run", fake_run)
    result = await complexity._run_radon(["fx/broken.py", "fx/branches.py"])
    assert result["max_complexity"] == 3 and result["average_complexity"] == 3.0
    assert result["unparsed_files"] == 1
