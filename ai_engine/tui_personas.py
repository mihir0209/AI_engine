"""
Agent personas for the AI Synapse TUI.

Built-in personas ship with the package. Users can add custom personas as JSON
files under ~/.ai-engine/personas/ (same schema). User files override built-ins
with the same ``id``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PERSONAS_DIR = Path.home() / ".ai-engine" / "personas"

BUILTIN_PERSONAS: list[dict[str, str]] = [
    {
        "id": "coder",
        "label": "Coder",
        "emoji": "⌨",
        "description": "Write, refactor, and debug code",
        "system_prompt": (
            "You are a senior software engineer. Write clean, production-ready "
            "code with brief explanations. Prefer minimal diffs, name things clearly, "
            "and call out edge cases or tests when relevant."
        ),
    },
    {
        "id": "reviewer",
        "label": "Reviewer",
        "emoji": "🔍",
        "description": "Review code and suggest improvements",
        "system_prompt": (
            "You are a meticulous code reviewer. Focus on correctness, security, "
            "performance, and maintainability. Be direct and actionable; cite specific "
            "lines or patterns when possible."
        ),
    },
    {
        "id": "architect",
        "label": "Architect",
        "emoji": "🏗",
        "description": "Design systems and trade-offs",
        "system_prompt": (
            "You are a pragmatic software architect. Propose clear designs, compare "
            "trade-offs, and keep scope realistic. Use diagrams or bullet lists when "
            "they aid clarity."
        ),
    },
    {
        "id": "writer",
        "label": "Writer",
        "emoji": "✍",
        "description": "Docs, copy, and clear prose",
        "system_prompt": (
            "You are a technical writer. Produce clear, concise prose with strong "
            "structure. Match the audience's level and avoid filler."
        ),
    },
]


@dataclass(frozen=True, slots=True)
class Persona:
    id: str
    label: str
    system_prompt: str
    description: str = ""
    emoji: str = "🤖"


def _persona_from_dict(data: dict[str, Any]) -> Persona | None:
    persona_id = str(data.get("id", "")).strip()
    label = str(data.get("label", "")).strip()
    prompt = str(data.get("system_prompt", "")).strip()
    if not persona_id or not label or not prompt:
        return None
    return Persona(
        id=persona_id,
        label=label,
        system_prompt=prompt,
        description=str(data.get("description", "")).strip(),
        emoji=str(data.get("emoji", "🤖")).strip() or "🤖",
    )


def load_personas(*, personas_dir: Path | None = None) -> list[Persona]:
    """Load built-in personas plus optional user overrides from ~/.ai-engine/personas/."""
    by_id: dict[str, Persona] = {}
    for raw in BUILTIN_PERSONAS:
        persona = _persona_from_dict(raw)
        if persona:
            by_id[persona.id] = persona

    root = personas_dir or PERSONAS_DIR
    if root.is_dir():
        for path in sorted(root.glob("*.json")):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(data, dict):
                continue
            persona = _persona_from_dict(data)
            if persona:
                by_id[persona.id] = persona

    return list(by_id.values())


def find_persona(personas: list[Persona], query: str) -> Persona | None:
    """Find persona by id or label (case-insensitive)."""
    q = query.strip().lower()
    if not q:
        return None
    for persona in personas:
        if persona.id.lower() == q or persona.label.lower() == q:
            return persona
    return None