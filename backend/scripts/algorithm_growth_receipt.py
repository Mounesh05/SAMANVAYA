"""Independent verification fixture. Run from backend with python -m scripts.algorithm_growth_receipt."""

import asyncio
import json

from domain.schemas.algorithm_benchmark import BenchmarkRequest
from intelligence.algorithms.empirical import estimate_series
from intelligence.algorithms.runner import DockerBenchmarkRunner


async def measure():
    sizes = [16, 32, 64, 128, 256, 512, 1024]
    datasets = [{"id": str(n), "args": [list(range(n))], "expected": n*(n-1)//2,
                 "dimensions": {"length": n}} for n in sizes]
    series = {"dimension": "length", "argument_index": 0, "dataset_ids": [d["id"] for d in datasets],
              "distribution": "ascending integer prefixes starting at zero"}
    languages = {"python": "def total(xs):\n    acc = 0\n    for x in xs:\n        acc += x\n    return acc",
                 "javascript": "function total(xs){let acc=0;for(const x of xs){acc+=x;}return acc;}",
                 "typescript": "function total(xs:number[]):number{let acc=0;for(const x of xs){acc+=x;}return acc;}"}
    receipts = {}
    for language, source in languages.items():
        request = BenchmarkRequest.model_validate({
            "project_id": "local-growth-fixture", "language": language,
            "candidates": [{"name": "total", "entrypoint": "total", "source": source}],
            "contract": {"kind": "function", "name": "prefix-sum", "version": "1", "input_schema": {"type": "array"},
                         "output_schema": {"type": "integer"}, "correctness": "expected", "mutation": "forbidden"},
            "datasets": datasets, "repetitions": 7,
            "decision_policy": {"id": "fixture", "version": "1", "objective": "TRADEOFF_ONLY"},
        }).model_dump()
        evidence = await DockerBenchmarkRunner().run(request)
        assert all(case["correct"] is True for row in evidence["results"] for case in row["cases"])
        receipts[language] = {"raw": evidence, "estimate": estimate_series(series, datasets, evidence["results"])}
    print(json.dumps(receipts, indent=2))


if __name__ == "__main__":
    asyncio.run(measure())
