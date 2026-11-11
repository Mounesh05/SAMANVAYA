"""Bounded parser adapters; developer functions are data, never executables."""

import asyncio
import json
import shutil
from pathlib import Path

from intelligence.algorithms.discovery.python_extractor import extract


async def python_source(source, path):
    return extract(source, path)


async def typescript_source(source, path):
    node = shutil.which("node")
    if not node:
        raise ValueError("Node parser runtime unavailable")
    script = Path(__file__).resolve().parents[3] / "benchmark_worker" / "function_discovery.cjs"
    proc = await asyncio.create_subprocess_exec(
        node, "--max-old-space-size=128", str(script),
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        output, _ = await asyncio.wait_for(proc.communicate(json.dumps({"source": source, "path": path}).encode()), 10)
        if proc.returncode or len(output) > 2_000_000:
            raise ValueError("TypeScript parser unavailable or output bound exceeded; install the pinned parser package")
        return json.loads(output)
    finally:
        if proc.returncode is None:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            await proc.wait()
