"""Local mock OpenAI-compatible provider for integration tests."""
from __future__ import annotations

import subprocess
import sys
import time

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

MOCK_PROVIDER_HOST = "127.0.0.1"
MOCK_PROVIDER_PORT = 18765
MOCK_PROVIDER_BASE = f"http://{MOCK_PROVIDER_HOST}:{MOCK_PROVIDER_PORT}"
DEMO_KEYS = {"alpha": "test-key-alpha", "beta": "test-key-beta", "gamma": "test-key-gamma"}

_KEY_BEHAVIOR = {
    DEMO_KEYS["alpha"]: (200, "alpha-ok"),
    DEMO_KEYS["beta"]: (429, "rate limit exceeded"),
    DEMO_KEYS["gamma"]: (401, "invalid api key"),
}


def create_app() -> FastAPI:
    app = FastAPI(title="AI Engine Mock Provider")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/v1/models")
    def list_models():
        return {"object": "list", "data": [{"id": "test-model", "object": "model"}]}

    @app.post("/v1/chat/completions")
    async def chat(request: Request):
        auth = request.headers.get("Authorization", "")
        key = auth.removeprefix("Bearer ").strip()
        status, msg = _KEY_BEHAVIOR.get(key, (401, "unknown key"))
        if status != 200:
            return JSONResponse(status_code=status, content={"error": {"message": msg}})
        body = await request.json()
        return {
            "id": "chatcmpl-mock",
            "object": "chat.completion",
            "model": body.get("model", "test-model"),
            "choices": [{"index": 0, "message": {"role": "assistant", "content": msg}, "finish_reason": "stop"}],
        }

    return app


def start(blocking: bool = False) -> subprocess.Popen | None:
    if blocking:
        import uvicorn

        uvicorn.run(create_app(), host=MOCK_PROVIDER_HOST, port=MOCK_PROVIDER_PORT, log_level="warning")
        return None
    return subprocess.Popen(
        [sys.executable, "-m", "tests.server", "--serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def stop(proc) -> None:
    if proc and proc.poll() is None:
        proc.terminate()
        proc.wait(timeout=5)


def wait_ready(timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if httpx.get(f"{MOCK_PROVIDER_BASE}/health", timeout=1).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    raise RuntimeError(f"Mock provider not ready at {MOCK_PROVIDER_BASE}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    args = parser.parse_args()
    if args.serve:
        start(blocking=True)