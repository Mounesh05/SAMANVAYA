"""AI-01: measure the configured Ollama model on this host and suggest limits.

    python -m scripts.ollama_latency_check            # 2 runs, evaluation-sized prompt
    python -m scripts.ollama_latency_check --runs 3

Sends a synthetic prompt of the size the developer evaluation uses (about
13 KB) and reports prompt-processing and generation time. No project data is
sent. Use the result to set OLLAMA_INFERENCE_TIMEOUT_SECONDS (and
VITE_AI_EVALUATION_TIMEOUT_MS on the frontend), or to decide that the host
needs a GPU or a faster model.
"""

import argparse
import json
import time
import urllib.request

from core.config import settings

SYNTHETIC_LINE = ("Commit a1b2c3: refactor the expenses model and add validation for amount and "
                  "category fields; file expenses.py +42 -10; README.md updated with setup notes.\n")


def measure_once(base_url, model, prompt_bytes, max_tokens):
    prompt = ("Evaluate this synthetic developer evidence and reply with JSON "
              '{"analysis": str, "strengths": [str], "recommendations": [str], "confidence": float}.\n')
    while len(prompt.encode()) < prompt_bytes:
        prompt += SYNTHETIC_LINE
    body = json.dumps({"model": model, "prompt": prompt, "stream": False, "format": "json",
                       "options": {"temperature": 0.3, "num_predict": max_tokens, "num_ctx": 16384}}).encode()
    url = base_url.rstrip("/") + "/api/generate"
    if not url.startswith(("http://", "https://")):
        raise SystemExit("OLLAMA_BASE_URL must be an http(s) URL")
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=1800) as response:  # nosec B310
        data = json.load(response)
    return {"wall_seconds": round(time.monotonic() - started, 1),
            "prompt_tokens": data.get("prompt_eval_count"),
            "prompt_seconds": round(data.get("prompt_eval_duration", 0) / 1e9, 1),
            "output_tokens": data.get("eval_count"),
            "generation_seconds": round(data.get("eval_duration", 0) / 1e9, 1)}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--prompt-bytes", type=int, default=13_500)
    parser.add_argument("--max-tokens", type=int, default=1024)
    args = parser.parse_args()
    print(f"Model {settings.OLLAMA_MODEL} at {settings.OLLAMA_BASE_URL}")
    results = []
    for number in range(1, max(args.runs, 1) + 1):
        result = measure_once(settings.OLLAMA_BASE_URL, settings.OLLAMA_MODEL, args.prompt_bytes, args.max_tokens)
        results.append(result)
        print(f"run {number}: {result}")
    slowest = max(r["wall_seconds"] for r in results)
    suggested = int(slowest * 1.5 + 30)
    print(f"\nSlowest run: {slowest}s. Current OLLAMA_INFERENCE_TIMEOUT_SECONDS: {settings.OLLAMA_INFERENCE_TIMEOUT_SECONDS}s.")
    print(f"Suggested OLLAMA_INFERENCE_TIMEOUT_SECONDS >= {suggested}; "
          f"VITE_AI_EVALUATION_TIMEOUT_MS >= {(suggested + 90) * 1000}.")
    if slowest > 120:
        print("This host is slow for interactive use. Prefer a GPU host or a faster model; "
              "a small model can also fail the evaluation's evidence checks.")


if __name__ == "__main__":
    main()
