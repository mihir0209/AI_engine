#!/usr/bin/env python3
"""Basic chat completion example using AI Engine SDK."""
from ai_engine import OpenAI

# Initialize client (uses config.json for provider priorities)
client = OpenAI()

# Non-streaming chat completion
print("=== Basic Chat ===")
response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "What is the capital of France?"}],
    max_tokens=50,
)
print(f"Response: {response.choices[0].message.content}")
print(f"Model: {response.model}")
print(f"Tokens: {response.usage.total_tokens}")
