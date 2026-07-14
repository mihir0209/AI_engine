#!/usr/bin/env python3
"""Start AI Synapse server and test with OpenAI SDK."""
import subprocess
import sys
import time

# Start server in background
print("Starting AI Synapse server...")
server = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", "8766"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL
)

try:
    time.sleep(3)

    from openai import OpenAI
    client = OpenAI(base_url="http://127.0.0.1:8766/v1", api_key="dummy")

    print("=== Server + OpenAI SDK Test ===")

    # List models
    models = client.models.list()
    print(f"Models: {len(models.data)}")

    # Chat completion
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello from AI Engine server!"}],
        max_tokens=20,
    )
    print(f"Response: {response.choices[0].message.content}")

    # Streaming
    print("Streaming: ", end="")
    for chunk in client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Say hi"}],
        stream=True,
        max_tokens=10,
    ):
        if chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="")
    print()

    print("\nALL SERVER TESTS PASSED")

finally:
    server.terminate()
    server.wait(timeout=5)
