"""
Integration of SAMANVAYA's own metrics with the evidence package,
the evidence merger and the QualityEngine.
"""

import textwrap
from types import SimpleNamespace

import pytest

from domain.models.risk_configuration import QualityDimensionWeights
from intelligence.analyzers.common.code_metrics import (
    apply_code_metrics,
    build_code_metrics,
    resolve_inside,
)
from intelligence.evidence.merger import EvidenceMerger
from intelligence.evidence.models import (
    CodeMetricsEvidence,
    CodeQualityEvidence,
    ComplexityEvidence,
    Finding,
    SeverityEnum,
    TestingEvidence as TestingEvidenceModel,
)
from intelligence.quality_engine import QualityEngine

# Long enough (> 100 tokens, > 10 lines) to count as a clone with SonarQube's defaults
DUPLICATED = textwrap.dedent('''
    def process_order(order, inventory):
        total = 0
        for item in order.items:
            if item.sku not in inventory:
                raise ValueError("missing sku")
            stock = inventory[item.sku]
            if stock.quantity < item.quantity:
                raise ValueError("insufficient stock")
            stock.quantity -= item.quantity
            line_total = item.price * item.quantity
            if item.discount:
                line_total -= line_total * item.discount / 100
            total += line_total
        order.total = round(total, 2)
        order.status = "processed"
        return order.total
''')


def deep_function(name: str, depth: int) -> str:
    body = "".join("    " * (i + 1) + f"if a > {i}:\n" for i in range(depth))
    return f"def {name}(a):\n{body}" + "    " * (depth + 1) + "return a\n"


def evidence(**overrides) -> CodeQualityEvidence:
    data = {"repository_id": "repo-1", "primary_language": "python"}
    data.update(overrides)
    return CodeQualityEvidence(**data)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    (root / "pkg").mkdir(parents=True)
    (root / "pkg" / "orders.py").write_text(DUPLICATED, encoding="utf-8")
    (root / "pkg" / "orders_copy.py").write_text(DUPLICATED.replace("process_order", "process_refund"), encoding="utf-8")
    (root / "pkg" / "deep.py").write_text(deep_function("deep", 7) + "\ndef ok(a):\n    return a\n", encoding="utf-8")
    (root / "pkg" / "style.css").write_text("body {}\n", encoding="utf-8")
    (tmp_path / "secret.py").write_text("PASSWORD = 'x'\n", encoding="utf-8")  # outside the repo
    return root


@pytest.fixture
def engine():
    eng = QualityEngine()

    async def defaults(project_id=None):
        return SimpleNamespace(quality_weights=QualityDimensionWeights())

    eng._config_service = SimpleNamespace(get_configuration=defaults)  # no database needed
    return eng


# ── path safety ───────────────────────────────────────────────────

def test_paths_outside_the_repository_are_rejected(repo, tmp_path):
    inside, rejected = resolve_inside(
        ["pkg/orders.py", "../secret.py", str(tmp_path / "secret.py"), "pkg/missing.py", "pkg"],
        str(repo),
    )
    assert [p.name for p in inside] == ["orders.py"]
    assert set(rejected) == {"../secret.py", str(tmp_path / "secret.py"), "pkg/missing.py", "pkg"}


def test_only_rejected_files_gives_empty_metrics_with_reasons(repo):
    metrics, summary = build_code_metrics(["../secret.py"], str(repo))
    assert summary is None
    assert metrics.files_rejected == ["../secret.py"] and metrics.files_measured == 0


def test_unsupported_languages_produce_no_metrics(repo):
    assert build_code_metrics(["pkg/style.css"], str(repo)) == (None, None)


# ── evidence population ───────────────────────────────────────────

def test_apply_code_metrics_fills_evidence(repo):
    ev = evidence(
        complexity=ComplexityEvidence(average_complexity=99, max_complexity=99, lines_of_code=1, avg_nesting_depth=2.5),
        static_findings=[Finding(file_path="pkg/orders.py", line_number=2, rule_id="F401", category="maintainability",
                                 severity=SeverityEnum.LOW, source_tool="ruff", message="unused import")],
    )
    files = ["pkg/orders.py", "pkg/orders_copy.py", "pkg/deep.py", "pkg/style.css", "../secret.py"]
    apply_code_metrics(ev, files, str(repo))

    m = ev.metrics
    assert m is not None and m.files_measured == 3
    assert m.files_rejected == ["../secret.py"]
    assert m.cognitive_max == 28                      # 1 + 2 + ... + 7
    assert [f["function"] for f in m.high_cognitive_functions] == ["deep"]
    assert m.high_cognitive_functions[0]["file"] == "pkg/deep.py"
    assert 0 < m.hard_to_read_code_share < 100
    assert m.duplicate_blocks == 1 and m.duplication_density > 0
    assert m.issue_count == 3                         # deep complexity + duplicated block + ruff finding
    assert m.maintainability_rating in {"A", "B", "C", "D", "E"}

    # older detectors' numbers are replaced, untouched fields are kept
    assert ev.complexity.max_complexity == 8          # deep(): 1 + 7 ifs
    assert ev.complexity.average_complexity == m.cyclomatic_average
    assert ev.complexity.lines_of_code == m.code_lines
    assert ev.complexity.avg_nesting_depth == 2.5
    assert ev.duplication.duplicate_blocks_count == 1
    assert ev.duplication.duplication_percentage == m.duplication_density
    assert {d["file"] for d in ev.duplication.duplicated_files} == {"pkg/orders.py", "pkg/orders_copy.py"}
    assert "samanvaya-metrics" in ev.tools_executed


def test_apply_code_metrics_is_a_no_op_for_other_languages(repo):
    ev = evidence(complexity=ComplexityEvidence(average_complexity=7))
    apply_code_metrics(ev, ["pkg/style.css"], str(repo))
    assert ev.metrics is None and ev.complexity.average_complexity == 7


def test_merger_keeps_metrics_from_the_python_analyzer():
    metrics = CodeMetricsEvidence(files_measured=2, maintainability_rating="B")
    merged = EvidenceMerger.merge([
        evidence(primary_language="javascript"),
        evidence(metrics=metrics),
    ])
    assert merged.metrics == metrics


# ── QualityEngine ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_engine_output_unchanged_without_metrics(engine):
    result = await engine.calculate(evidence(testing=TestingEvidenceModel(coverage_percentage=100.0)))
    assert result["quality_score"] == 100
    assert "maintainability" not in result


@pytest.mark.asyncio
async def test_hard_to_read_code_raises_complexity_penalty(engine):
    low_avg = ComplexityEvidence(average_complexity=3.0)        # cyclomatic penalty would be 0
    plain = await engine.calculate(evidence(complexity=low_avg))
    with_metrics = await engine.calculate(evidence(
        complexity=low_avg,
        metrics=CodeMetricsEvidence(function_count=10, hard_to_read_code_share=25.0),
    ))
    assert plain["penalties"]["complexity"] == 0
    assert with_metrics["penalties"]["complexity"] == 50.0      # 25% of a 50% max
    assert with_metrics["quality_score"] < plain["quality_score"]


@pytest.mark.asyncio
async def test_cyclomatic_penalty_still_wins_when_larger(engine):
    result = await engine.calculate(evidence(
        complexity=ComplexityEvidence(average_complexity=50.0),
        metrics=CodeMetricsEvidence(function_count=10, hard_to_read_code_share=5.0),
    ))
    assert result["penalties"]["complexity"] == 100.0


@pytest.mark.asyncio
async def test_engine_reports_maintainability_section(engine, repo):
    ev = evidence()
    apply_code_metrics(ev, ["pkg/orders.py", "pkg/orders_copy.py", "pkg/deep.py"], str(repo))
    result = await engine.calculate(ev)
    section = result["maintainability"]
    assert section["rating"] == ev.metrics.maintainability_rating
    assert section["technical_debt_minutes"] == ev.metrics.technical_debt_minutes > 0
    assert section["cognitive_max"] == 28
    assert section["source"] == "samanvaya-metrics"
    assert result["penalties"]["duplication"] > 0              # our duplication feeds the old dimension
