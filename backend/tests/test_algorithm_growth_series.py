import pytest

from intelligence.algorithms.empirical import estimate_series, prefix_workload


def workload():
    sizes = [4, 8, 16, 32, 64, 128, 256]
    datasets = [{"id": str(n), "args": [list(range(n))], "expected": n,
                 "dimensions": {"length": n}} for n in sizes]
    return {"dimension": "length", "argument_index": 0,
            "dataset_ids": [str(n) for n in sizes], "distribution": "ascending prefix"}, datasets


@pytest.mark.parametrize("exponent,model", [(1, "linear"), (2, "quadratic")])
def test_known_growth_held_out(exponent, model):
    series, datasets = workload()
    cases = [{"case_id": d["id"], "correct": True, "timing_status": "AVAILABLE",
              "timings_seconds": [0.00001 + 0.000001 * int(d["id"])**exponent] * 5} for d in datasets]
    def fit():
        return estimate_series(series, datasets, [{"candidate": "fixture", "cases": cases}])["candidates"][0]
    assert fit()["model"] == model
    assert fit()["held_out_sizes"] == [128, 256]
    cases[-1]["correct"] = False
    assert fit()["status"] == "insufficient_evidence"
    cases[-1]["correct"] = True
    cases[-1]["timings_seconds"] = [0.5] * 5
    assert fit()["status"] == "inconclusive"


def test_reviewer_cannot_group_different_distributions_or_wrong_dimension():
    series, datasets = workload()
    datasets[0]["args"][0].reverse()
    with pytest.raises(ValueError, match="prefix generator"):
        prefix_workload(series, datasets)
    datasets[0]["dimensions"]["length"] += 1
    with pytest.raises(ValueError, match="controlled array length"):
        prefix_workload(series, datasets)
