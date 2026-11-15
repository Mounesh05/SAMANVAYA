"""Real local HTTP stalls/cancellation, no Ollama process or external traffic."""

import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import time

import httpx
import pytest

from agents import llm_provider


@pytest.fixture
def stalled_server():
    received, release = threading.Event(), threading.Event()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            received.set()
            # Two seconds is only a test fixture bound. A real provider timeout
            # must terminate first; this server does not generate model output.
            release.wait(2)
            self.close_connection = True

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", received
    finally:
        release.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)
        assert not thread.is_alive()


def test_sync_actual_transport_has_effective_stalled_inference_timeout(monkeypatch, stalled_server):
    url, received = stalled_server
    monkeypatch.setattr(llm_provider, "INFERENCE_TIMEOUT_SECONDS", 0.1)
    llm = llm_provider.get_ollama_llm(base_url=url)
    started = time.monotonic()
    try:
        with pytest.raises(httpx.ReadTimeout):
            llm.invoke("synthetic timeout probe")
        assert received.is_set() and time.monotonic() - started < 1.5
    finally:
        llm._client._client.close()


@pytest.mark.anyio
async def test_async_actual_transport_has_effective_stalled_inference_timeout(monkeypatch, stalled_server):
    url, received = stalled_server
    monkeypatch.setattr(llm_provider, "INFERENCE_TIMEOUT_SECONDS", 0.1)
    llm = llm_provider.get_ollama_llm(base_url=url)
    started = time.monotonic()
    try:
        with pytest.raises(httpx.ReadTimeout):
            await llm.ainvoke("synthetic timeout probe")
        assert received.is_set() and time.monotonic() - started < 1.5
    finally:
        await llm._async_client._client.aclose()
        llm._client._client.close()


@pytest.mark.anyio
async def test_async_cancellation_propagates_without_detached_inference(monkeypatch, stalled_server):
    url, received = stalled_server
    monkeypatch.setattr(llm_provider, "INFERENCE_TIMEOUT_SECONDS", 1)
    llm = llm_provider.get_ollama_llm(base_url=url)
    task = asyncio.create_task(llm.ainvoke("synthetic cancellation probe"))
    try:
        async with asyncio.timeout(1):
            while not received.is_set():
                await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 0.5)
        assert task.done()
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await llm._async_client._client.aclose()
        llm._client._client.close()
