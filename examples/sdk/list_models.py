#!/usr/bin/env python3
"""List and retrieve models using AI Engine SDK."""
from ai_engine import OpenAI

client = OpenAI()

# List all available models
print("=== Available Models ===")
models = client.models.list()
print(f"Total: {len(models.data)} models\n")

# Show first 10
for m in models.data[:10]:
    print(f"  {m.id:60s} (owned by {m.owned_by})")

# Retrieve a specific model
print(f"\n=== Retrieve Model ===")
model = client.models.retrieve("gpt-4")
print(f"ID: {model.id}")
print(f"Object: {model.object}")
print(f"Owned by: {model.owned_by}")
