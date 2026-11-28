"""Phase 1 CQ-16 (risk is not inverse quality) and CQ-20 (worker results are re-validated)."""
import asyncio
from unittest.mock import AsyncMock

import pytest

from intelligence.analyzers import isolated
from intelligence.evidence.models import ChangeContext, CodeQualityEvidence, Finding
from intelligence.quality_engine import QualityEngine
from intelligence.risk_engine import RiskEngine

SHA = "a" * 40
SOURCE = {"src/app.py": "import os\n"}


def _context():
    provenance = isolated.source_provenance("PRJ-1", "owner/repo", SHA, SOURCE, organization_id="ORG-1")
    return {"project_id": "PRJ-1", "commit_sha": SHA, "organization_id": "ORG-1",
            "source_files": SOURCE, "source_provenance": provenance}


def _evidence(**changes):
    base = {"repository_id": "PRJ-1", "commit_sha": SHA, "primary_language": "python", "files_analyzed": 1,
            "execution_provenance": {"method": isolated.PROTOCOL, "network": "none", "host_source_execution": False,
                                     "source_hashes": _context()["source_provenance"]["source_hashes"], "revision": SHA}}
    return CodeQualityEvidence(**{**base, **changes})


def _finding(path="src/app.py"):
    return Finding(file_path=path, line_number=1, rule_id="F401", category="maintainability",
                   severity="low", source_tool="ruff", message="`os` imported but unused")


def test_matching_worker_evidence_is_accepted():
    context = _context()
    payload = isolated.snapshot_payload(["src/app.py"], context)
    evidence = _evidence(static_findings=[_finding()])
    assert isolated.verify_brokered_evidence(evidence, payload, context) is evidence


@pytest.mark.parametrize("change", [
    {"commit_sha": "b" * 40},                      # stale / wrong revision
    {"repository_id": "PRJ-OTHER"},                # another project's measurements
    {"files_analyzed": 5},                         # more files than were sent
    {"static_findings": [_finding("etc/passwd")]},  # a finding outside the snapshot
])
def test_worker_evidence_for_another_source_is_rejected(change):
    context = _context()
    payload = isolated.snapshot_payload(["src/app.py"], context)
    with pytest.raises(ValueError, match="do not belong"):
        isolated.verify_evidence(_evidence(**change), payload, context)


@pytest.mark.parametrize("provenance", [
    {"network": "bridge"}, {"host_source_execution": True}, {"revision": "b" * 40},
    {"source_hashes": {"src/app.py": "0" * 64}}, {"method": "local-worktree"},
])
def test_broker_result_without_matching_isolation_provenance_is_rejected(provenance):
    context = _context()
    payload = isolated.snapshot_payload(["src/app.py"], context)
    evidence = _evidence()
    evidence.execution_provenance = {**evidence.execution_provenance, **provenance}
    with pytest.raises(ValueError, match="isolation provenance"):
        isolated.verify_brokered_evidence(evidence, payload, context)


def test_risk_is_not_the_inverse_of_quality(monkeypatch):
    from domain.models.risk_configuration import RiskConfiguration
    from domain.services.risk_config_service import get_risk_config_service

    monkeypatch.setattr(get_risk_config_service(), "get_configuration",
                        AsyncMock(return_value=RiskConfiguration(name="test", created_by="test")))
    files = [f"src/m{i}.py" for i in range(40)]
    measured = {"tools_executed": ["ruff", "bandit"], "detected_languages": ["python"]}
    messy_small = _evidence(files_analyzed=1, lines_added=12, change_context=ChangeContext(changed_files=["src/app.py"]),
                            static_findings=[_finding() for _ in range(12)], **measured)
    clean_large = _evidence(files_analyzed=40, lines_added=4000, lines_deleted=1500, **measured,
                            change_context=ChangeContext(changed_files=files, config_files_changed=True,
                                                         db_migrations_changed=True))

    async def measure(evidence):
        engine = QualityEngine()

        async def default_config(project_id=None):
            return engine._config_service._create_default_configuration(project_id)

        engine._config_service.get_configuration = default_config
        return await engine.calculate(evidence), await RiskEngine().analyze_evidence(evidence)

    (q_messy, r_messy), (q_clean, r_clean) = asyncio.run(measure(messy_small)), asyncio.run(measure(clean_large))
    assert q_clean["quality_score"] > q_messy["quality_score"]
    # Higher quality does not mean lower risk: the large, migration-touching change carries more risk.
    assert r_clean["risk_score"] > r_messy["risk_score"]
    assert r_clean["risk_factors"], "risk must be explained by its policy factors"
