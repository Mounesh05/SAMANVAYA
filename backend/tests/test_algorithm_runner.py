"""Controller tests never execute candidate source; trusted fixtures run only in Docker."""

import asyncio
import copy
import json
import os

from unittest.mock import patch

import pytest

from intelligence.algorithms.runner import (
    BenchmarkFailure,
    BenchmarkUnavailable,
    DockerBenchmarkRunner,
    IMAGES,
    MEMORY_METRICS,
)


def payload(language="python"):
    return {"language": language,
            "candidates": [{"name": "sort", "source": "def sort(a): return sorted(a)", "entrypoint": "sort"}],
            "sizes": [0, 12], "distributions": ["random", "sorted", "reversed", "duplicates"],
            "repetitions": 2, "seed": 42}


def report(request):
    return {"environment": {"runtime": "test"}, "tools": {"timing": "test"},
            "result": {"candidate": request["candidates"][0]["name"], "error": None,
                       "cases": [{"size": n, "distribution": d, "correct": True,
                                  "timings_seconds": [0.001] * request["repetitions"],
                                  "memory_bytes": 0, "memory_metric": MEMORY_METRICS[request["language"]],
                                  "error": None}
                                 for n in request["sizes"] for d in request["distributions"]]}}


class FakeStdin:
    def __init__(self):
        self.data = b""
        self.closed = False

    def write(self, data):
        self.data += data

    async def drain(self):
        pass

    def close(self):
        self.closed = True


class FakeProcess:
    def __init__(self, stdout=b"", stderr=b"", code=0, hang=False):
        self.stdin = FakeStdin()
        self.stdout = asyncio.StreamReader()
        self.stderr = asyncio.StreamReader()
        self.stdout.feed_data(stdout)
        self.stderr.feed_data(stderr)
        self.stdout.feed_eof()
        self.stderr.feed_eof()
        self.returncode = None
        self.code = code
        self.hang = hang
        self.killed = False
        self.done = asyncio.Event()

    async def wait(self):
        if self.hang and self.returncode is None:
            await self.done.wait()
        if self.returncode is None:
            self.returncode = self.code
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9
        self.done.set()


class DockerMock:
    def __init__(self, request=None, output=None, stderr=b"", run_code=0, hang=False):
        self.request = request or payload()
        self.output = output
        self.stderr = stderr
        self.run_code = run_code
        self.hang = hang
        self.calls = []
        self.runs = []
        self.missing = False
        self.daemon_down = False

    async def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        assert args[0] == "docker"
        assert set(kwargs) == {"stdin", "stdout", "stderr"}
        if args[1] == "version":
            return FakeProcess(b"27.0.0\n", code=1 if self.daemon_down else 0)
        if args[1:3] == ("image", "inspect"):
            return FakeProcess(b"sha256:test\n", code=1 if self.missing else 0)
        if args[1] == "rm":
            return FakeProcess()
        assert args[1] == "run"
        request = copy.deepcopy(self.request)
        request["candidates"] = [self.request["candidates"][len(self.runs)]]
        output = json.dumps(report(request)).encode() if self.output is None else self.output
        process = FakeProcess(output, self.stderr, self.run_code, self.hang)
        self.runs.append(process)
        return process


def run_mock(mock, runner=None, request=None):
    with patch("intelligence.algorithms.runner.asyncio.create_subprocess_exec", mock):
        return asyncio.run((runner or DockerBenchmarkRunner()).run(request or mock.request))


def test_security_flags_stdin_fixed_image_and_schema():
    mock = DockerMock()
    result = run_mock(mock)
    assert set(result) == {"environment", "results", "tools"}
    assert len(result["results"][0]["cases"]) == 8
    assert all(c["correct"] for c in result["results"][0]["cases"])
    args = next(args for args, _ in mock.calls if args[1] == "run")
    for flag in ("--rm", "--pull=never", "--network=none", "--cap-drop=ALL",
                 "--security-opt=no-new-privileges:true", "--user=65532:65532", "--read-only",
                 "--tmpfs=/tmp:rw,noexec,nosuid,nodev,size=64m,mode=1777", "--memory=512m",
                 "--memory-swap=512m", "--cpus=1", "--pids-limit=64", "--init", "--log-driver=none"):
        assert flag in args
    assert args[-1] == IMAGES["python"]
    assert not any(a in args for a in ("--volume", "-v", "--mount", "--privileged", "--publish"))
    assert mock.request == json.loads(mock.runs[0].stdin.data)
    assert mock.runs[0].stdin.closed
    name = args[args.index("--name") + 1]
    assert ("docker", "rm", "--force", name) in [a for a, _ in mock.calls]
    operations = [a[1] for a, _ in mock.calls]
    assert operations.index("image") < operations.index("run")


def test_candidates_are_separate_unique_containers():
    request = payload()
    request["candidates"].append({"name": "other", "source": "pass", "entrypoint": "other"})
    mock = DockerMock(request)
    result = run_mock(mock)
    assert [r["candidate"] for r in result["results"]] == ["sort", "other"]
    names = [a[a.index("--name") + 1] for a, _ in mock.calls if a[1] == "run"]
    assert len(set(names)) == 2
    assert all(len(json.loads(p.stdin.data)["candidates"]) == 1 for p in mock.runs)


@pytest.mark.parametrize("language", ["javascript", "typescript"])
def test_node_image_and_signed_heap_delta(language):
    request = payload(language)
    message = report(request)
    message["result"]["cases"][0]["memory_bytes"] = -100
    mock = DockerMock(request, json.dumps(message).encode())
    assert run_mock(mock)["results"][0]["cases"][0]["memory_bytes"] == -100
    assert next(a for a, _ in mock.calls if a[1] == "run")[-1] == IMAGES[language]


def test_docker_cli_unavailable():
    async def unavailable(*args, **kwargs):
        raise FileNotFoundError("docker")
    with patch("intelligence.algorithms.runner.asyncio.create_subprocess_exec", unavailable):
        with pytest.raises(BenchmarkUnavailable, match="install Docker"):
            asyncio.run(DockerBenchmarkRunner().run(payload()))
        assert not asyncio.run(DockerBenchmarkRunner().availability())["available"]


@pytest.mark.parametrize("failure", ["missing", "daemon_down"])
def test_unavailable_images_and_daemon(failure):
    mock = DockerMock()
    setattr(mock, failure, True)
    with pytest.raises(BenchmarkUnavailable, match="docker build" if failure == "missing" else "daemon"):
        run_mock(mock)
    assert not mock.runs
    with patch("intelligence.algorithms.runner.asyncio.create_subprocess_exec", mock):
        assert not asyncio.run(DockerBenchmarkRunner().availability())["available"]


def test_availability_inspects_both_fixed_images_without_running():
    mock = DockerMock()
    with patch("intelligence.algorithms.runner.asyncio.create_subprocess_exec", mock):
        result = asyncio.run(DockerBenchmarkRunner().availability())
    assert result["available"]
    assert set(result["environment"]["images"]) == set(IMAGES.values())
    assert not mock.runs


def test_timeout_kills_client_and_force_removes_container():
    mock = DockerMock(hang=True)
    with pytest.raises(BenchmarkFailure, match="total deadline"):
        run_mock(mock, DockerBenchmarkRunner(timeout_seconds=0.05))
    assert mock.runs[0].killed
    assert any(a[1:3] == ("rm", "--force") for a, _ in mock.calls)


def test_cancellation_force_removes_container_and_propagates():
    mock = DockerMock(hang=True)

    async def scenario():
        task = asyncio.create_task(DockerBenchmarkRunner().run(payload()))
        while not mock.runs:
            await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    with patch("intelligence.algorithms.runner.asyncio.create_subprocess_exec", mock):
        asyncio.run(scenario())
    assert mock.runs[0].killed
    assert any(a[1:3] == ("rm", "--force") for a, _ in mock.calls)


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_output_budget(stream):
    mock = DockerMock(output=b"x" * 1025 if stream == "stdout" else b"", stderr=b"x" * 1025 if stream == "stderr" else b"")
    with pytest.raises(BenchmarkFailure, match="output exceeded"):
        run_mock(mock, DockerBenchmarkRunner(max_output_bytes=1024))
    assert any(a[1] == "rm" for a, _ in mock.calls)


@pytest.mark.parametrize("output", [b"not JSON", b"{}", b"[]", b"null", b"{\"result\": NaN}", b"{}\nnoise"])
def test_invalid_worker_json(output):
    with pytest.raises(BenchmarkFailure, match="Malformed worker"):
        run_mock(DockerMock(output=output))


@pytest.mark.parametrize("mutation", ["wrong_name", "missing_cases", "bad_timing", "wrong_metric", "missing_memory", "missing_samples", "bad_correct"])
def test_invalid_worker_schema(mutation):
    message = report(payload())
    case = message["result"]["cases"][0]
    if mutation == "wrong_name":
        message["result"]["candidate"] = "forged"
    elif mutation == "missing_cases":
        message["result"]["cases"].pop()
    elif mutation == "bad_timing":
        case["timings_seconds"][0] = -1
    elif mutation == "wrong_metric":
        case["memory_metric"] = "rss"
    elif mutation == "missing_memory":
        case["memory_bytes"] = None
    elif mutation == "missing_samples":
        case["timings_seconds"] = []
    else:
        case["correct"] = 1
    with pytest.raises(BenchmarkFailure, match="Malformed worker"):
        run_mock(DockerMock(output=json.dumps(message).encode()))


def test_worker_nonzero_exit():
    with pytest.raises(BenchmarkFailure, match="status 137"):
        run_mock(DockerMock(run_code=137, stderr=b"killed"))


def test_candidate_load_error_is_a_result_not_controller_failure():
    message = report(payload())
    message["result"].update(cases=[], error="SyntaxError: invalid source")
    assert run_mock(DockerMock(output=json.dumps(message).encode()))["results"][0]["error"]


@pytest.mark.parametrize("key,value", [("sizes", [10001]), ("sizes", [True]), ("sizes", []),
                                      ("candidates", []), ("repetitions", 11), ("repetitions", True),
                                      ("seed", -1), ("language", "shell"),
                                      ("distributions", ["unknown"]), ("distributions", ["random", "random"])])
def test_input_guards_before_subprocess(key, value):
    request = payload()
    request[key] = value
    mock = DockerMock(request)
    with pytest.raises(ValueError):
        run_mock(mock)
    assert not mock.calls


def test_too_many_candidates_and_entrypoint_injection():
    request = payload()
    request["candidates"] *= 6
    with pytest.raises(ValueError):
        DockerBenchmarkRunner._validate(request)
    request = payload()
    request["candidates"][0]["entrypoint"] = "sort();process.exit()"
    with pytest.raises(ValueError):
        DockerBenchmarkRunner._validate(request)


def test_input_generation_is_deterministic_and_distributions_preserve_multiset():
    # Importing this module doesn't import Memray/pyperf or execute candidate source.
    from benchmark_worker.python_worker import make_input
    random = make_input(100, "random", 42)
    assert random == make_input(100, "random", 42)
    assert random != make_input(100, "random", 43)
    assert sorted(random) == make_input(100, "sorted", 42)
    assert sorted(random, reverse=True) == make_input(100, "reversed", 42)
    assert set(make_input(100, "duplicates", 42)) == set(range(8))
    assert make_input(0, "random", 42) == []


@pytest.mark.skipif(os.environ.get("SAMANVAYA_DOCKER_BENCHMARK_TESTS") != "1",
                    reason="opt-in trusted fixtures: requires Docker and both prebuilt images")
@pytest.mark.parametrize("language", ["python", "javascript", "typescript"])
def test_trusted_sorting_fixtures_inside_docker_only(language):
    request = payload(language)
    request["sizes"] = [0, 1, 32]
    source = {
        "python": "def sort(a):\n print('noise that must not enter protocol')\n return sorted(a)",
        "javascript": "function sort(a) { console.log('noise'); return [...a].sort((a,b) => a-b); }",
        "typescript": "function sort(a: number[]): number[] { console.log('noise'); return [...a].sort((a,b) => a-b); }",
    }[language]
    inplace = {"python": "def sort(a): a.sort()",
               "javascript": "function sort(a) { a.sort((a,b) => a-b); }",
               "typescript": "function sort(a: number[]): void { a.sort((a,b) => a-b); }"}[language]
    wrong = {"python": "def sort(a): return [0] * len(a)",
             "javascript": "function sort(a) { return a.map(() => 0); }",
             "typescript": "function sort(a: number[]): number[] { return a.map(() => 0); }"}[language]
    request["candidates"] = [{"name": name, "source": code, "entrypoint": "sort"}
                             for name, code in [("returned", source), ("inplace", inplace), ("wrong", wrong)]]
    result = asyncio.run(DockerBenchmarkRunner().run(request))
    assert all(case["correct"] for entry in result["results"][:2] for case in entry["cases"])
    assert any(not case["correct"] for case in result["results"][2]["cases"])
    assert "noise" not in json.dumps(result)


@pytest.mark.skipif(os.environ.get("SAMANVAYA_DOCKER_BENCHMARK_TESTS") != "1",
                    reason="opt-in trusted syntax fixture requires Docker and Node image")
def test_typescript_transpilation_diagnostics_inside_docker():
    request = payload("typescript")
    request["candidates"][0]["source"] = "function sort(a: number[] { return a; }"
    result = asyncio.run(DockerBenchmarkRunner().run(request))
    assert "TypeScript transpilation failed" in result["results"][0]["error"]


@pytest.mark.skipif(os.environ.get("SAMANVAYA_DOCKER_BENCHMARK_TESTS") != "1",
                    reason="opt-in trusted unsupported-contract fixtures require Docker images")
@pytest.mark.parametrize("language", ["python", "javascript", "typescript"])
@pytest.mark.parametrize("contract", ["async", "generator", "nonnumeric", "wrong_return"])
def test_unsupported_sort_contracts_inside_docker(language, contract):
    request = payload(language)
    request.update(sizes=[3], distributions=["random"])
    sources = {
        "python": {
            "async": "async def sort(a): return sorted(a)",
            "generator": "def sort(a): yield from sorted(a)",
            "nonnumeric": "def sort(a): return [str(v) for v in sorted(a)]",
            "wrong_return": "def sort(a): return tuple(sorted(a))",
        },
        "javascript": {
            "async": "async function sort(a) { return a.sort((a,b) => a-b); }",
            "generator": "function* sort(a) { yield* a.sort((a,b) => a-b); }",
            "nonnumeric": "function sort(a) { return a.sort((a,b) => a-b).map(String); }",
            "wrong_return": "function sort(a) { a.sort((a,b) => a-b); return null; }",
        },
    }
    request["candidates"][0]["source"] = sources["javascript" if language == "typescript" else language][contract]
    result = asyncio.run(DockerBenchmarkRunner().run(request))["results"][0]
    if contract in ("async", "generator"):
        assert result["error"] and "synchronous function" in result["error"]
        assert result["cases"] == []
    else:
        assert result["error"] is None
        assert all(not case["correct"] and case["error"] for case in result["cases"])


def test_combined_stdout_stderr_budget():
    mock = DockerMock(output=b"x" * 600, stderr=b"y" * 600)
    with pytest.raises(BenchmarkFailure, match="output exceeded"):
        run_mock(mock, DockerBenchmarkRunner(max_output_bytes=1024))


def test_unknown_fields_cannot_select_image_or_reach_worker():
    request = payload()
    request["image"] = "untrusted:latest"
    request["candidates"][0]["extra"] = "not forwarded"
    mock = DockerMock(request)
    run_mock(mock)
    forwarded = json.loads(mock.runs[0].stdin.data)
    assert "image" not in forwarded
    assert "extra" not in forwarded["candidates"][0]
    assert next(a for a, _ in mock.calls if a[1] == "run")[-1] == IMAGES["python"]


@pytest.mark.parametrize("value", [0, -1, float("inf"), float("nan"), True])
def test_invalid_deadline(value):
    with pytest.raises(ValueError):
        DockerBenchmarkRunner(timeout_seconds=value)


def test_pure_python_correctness_rejects_non_numeric_and_changed_multiset():
    from benchmark_worker.python_worker import check_result
    check_result([1, 2], [2, 1], [1, 2])
    check_result(None, [1, 2], [1, 2])
    for output in ([True, 2], [1, 1], [2, 1], [1, 2, 3], ["1", "2"]):
        with pytest.raises(ValueError, match="incorrect numeric"):
            check_result(output, [], [1, 2])


@pytest.mark.skipif(os.environ.get("SAMANVAYA_DOCKER_BENCHMARK_TESTS") != "1",
                    reason="opt-in trusted stateful fixtures require Docker images")
@pytest.mark.parametrize("language", ["python", "javascript", "typescript"])
def test_every_sample_is_validated_inside_docker(language):
    request = payload(language)
    request.update(sizes=[16], distributions=["random"])
    source = {
        "python": "calls = 0\ndef sort(a):\n global calls\n calls += 1\n return sorted(a) if calls <= 2 else [0] * len(a)",
        "javascript": "let calls = 0; function sort(a) { return ++calls <= 2 ? [...a].sort((a,b)=>a-b) : a.map(()=>0); }",
        "typescript": "let calls = 0; function sort(a: number[]): number[] { return ++calls <= 2 ? [...a].sort((a,b)=>a-b) : a.map(()=>0); }",
    }[language]
    request["candidates"][0]["source"] = source
    case = asyncio.run(DockerBenchmarkRunner().run(request))["results"][0]["cases"][0]
    assert not case["correct"]
    assert case["timings_seconds"] == []
    assert "incorrect numeric" in case["error"]
