#!/usr/bin/env python3
"""Streaming chat completion example using AI Engine SDK."""
from ai_engine import OpenAI

client = OpenAI()

print("=== Streaming Chat ===")
print("User: Tell me a joke about programming\nAI: ", end="")

stream = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "Tell me a joke about programming"}],
    stream=True,
    max_tokens=100,
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")

print("\n")
