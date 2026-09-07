"""
Tests for the Quality Engine.
"""

import pytest
from intelligence.quality_engine import QualityEngine
from intelligence.evidence.models import (
    CodeQualityEvidence,
    Finding,
    SeverityEnum,
    ComplexityEvidence,
    DuplicationEvidence,
    TestingEvidence,
    SecurityEvidence,
    ArchitectureEvidence,
    ChangeContext,
    CICDEvidence,
    AnalysisQuality,
)


def _make_evidence(**overrides) -> CodeQualityEvidence:
    """Create a CodeQualityEvidence with sensible defaults for testing."""
    defaults = {
        "repository_id": "repo-1",
        "primary_language": "python",
        "detected_languages": ["python"],
        "files_analyzed": 10,
        "lines_added": 100,
        "lines_deleted": 50,
        "change_context": ChangeContext(),
        "static_findings": [],
        "complexity": ComplexityEvidence(),
        "duplication": DuplicationEvidence(),
        "testing": TestingEvidence(),
        "security": SecurityEvidence(),
        "architecture": ArchitectureEvidence(),
        "ci_cd": CICDEvidence(),
        "analysis_quality": AnalysisQuality(),
    }
    defaults.update(overrides)
    return CodeQualityEvidence(**defaults)


class TestQualityEngine:
    """Test quality score calculation."""

    @pytest.fixture
    def engine(self):
        return QualityEngine()

    @pytest.mark.asyncio
    async def test_perfect_evidence_scores_100(self, engine):
        # Explicitly set 100% coverage to avoid the None-coverage penalty
        testing = TestingEvidence(coverage_percentage=100.0)
        evidence = _make_evidence(testing=testing)
        result = await engine.calculate(evidence)
        assert result["quality_score"] == 100
        assert result["quality_grade"] == "A"

    @pytest.mark.asyncio
    async def test_critical_findings_reduce_score(self, engine):
        findings = [
            Finding(
                file_path="main.py",
                rule_id="SEC001",
                category="security",
                severity=SeverityEnum.CRITICAL,
                source_tool="bandit",
                message="Hardcoded password",
            )
        ]
        evidence = _make_evidence(static_findings=findings)
        result = await engine.calculate(evidence)
        assert result["quality_score"] < 100
        assert result["quality_score"] >= 80  # 1 critical = 10 penalty * 0.25 weight

    @pytest.mark.asyncio
    async def test_no_test_coverage_does_not_penalize(self, engine):
        testing = TestingEvidence(coverage_percentage=None)
        evidence = _make_evidence(testing=testing)

        result = await engine.calculate(evidence)

        assert result["quality_score"] == 100
        assert result["penalties"]["testing"] == 0.0

    @pytest.mark.asyncio
    async def test_low_coverage_penalized(self, engine):
        testing = TestingEvidence(coverage_percentage=50.0)
        evidence = _make_evidence(testing=testing)
        result = await engine.calculate(evidence)
        # 50% coverage: gap=30, penalty=(30/80)*100=37.5, weighted=37.5*0.25=9.375
        # Score = 100 - 9 = 91 (only testing penalty), so < 95 is a reliable check
        assert result["quality_score"] < 95

    @pytest.mark.asyncio
    async def test_high_complexity_penalized(self, engine):
        complexity = ComplexityEvidence(average_complexity=20.0)
        evidence = _make_evidence(complexity=complexity)
        result = await engine.calculate(evidence)
        assert result["quality_score"] < 95

    @pytest.mark.asyncio
    async def test_architecture_violations_penalized(self, engine):
        arch = ArchitectureEvidence(
            layer_violations=[{"from": "api", "to": "repo"}],
            circular_dependencies=["A -> B -> A"],
        )
        evidence = _make_evidence(architecture=arch)

        result = await engine.calculate(evidence)

        assert result["quality_score"] < 100
        assert result["penalties"]["architecture"] > 0

    @pytest.mark.asyncio
    async def test_duplication_penalized(self, engine):
        dup = DuplicationEvidence(duplication_percentage=25.0)
        evidence = _make_evidence(duplication=dup)
        result = await engine.calculate(evidence)
        assert result["quality_score"] < 95

    def test_grade_boundaries(self, engine):
        # Test grade mapping
        assert QualityEngine._grade(95) == "A"
        assert QualityEngine._grade(80) == "B"
        assert QualityEngine._grade(65) == "C"
        assert QualityEngine._grade(50) == "D"
        assert QualityEngine._grade(30) == "F"

    @pytest.mark.asyncio
    async def test_score_never_negative(self, engine):
        # Maximum penalty scenario
        findings = [
            Finding(
                file_path=f"file{i}.py",
                rule_id=f"RULE{i}",
                category="security",
                severity=SeverityEnum.CRITICAL,
                source_tool="bandit",
                message=f"Issue {i}",
            )
            for i in range(20)
        ]
        testing = TestingEvidence(coverage_percentage=0.0)
        complexity = ComplexityEvidence(average_complexity=50.0)
        arch = ArchitectureEvidence(
            layer_violations=[{"from": "a", "to": "b"}] * 10,
            circular_dependencies=["A -> B"] * 5,
        )
        dup = DuplicationEvidence(duplication_percentage=50.0)
        evidence = _make_evidence(
            static_findings=findings,
            testing=testing,
            complexity=complexity,
            architecture=arch,
            duplication=dup,
        )
        result = await engine.calculate(evidence)
        assert result["quality_score"] >= 0
