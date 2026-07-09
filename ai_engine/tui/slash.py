"""Slash command registry and fuzzy matching for the TUI composer."""
from __future__ import annotations

from dataclasses import dataclass

try:
    from rapidfuzz import fuzz, process as rf_process
except ImportError:
    rf_process = None
    fuzz = None

# Coding-agent style commands — curated for terminal chat
SLASH_COMMANDS: list[tuple[str, str]] = [
    ("help", "Commands and keyboard shortcuts"),
    ("read", "<path>  Load a file into the composer"),
    ("clear", "Start a new chat"),
    ("persona", "<id>  Apply an agent persona"),
    ("persona clear", "Remove active persona / system prompt"),
    ("persona list", "List available personas"),
    ("export", "[md|json] [path]  Export this chat"),
    ("intent", "[on|off]  Toggle intent routing"),
    ("system", "[text|clear]  Per-chat system prompt"),
    ("model", "<name>  Set model"),
    ("models", "Open model picker"),
    ("provider", "<name>  Set provider"),
    ("favorite", "<model>  Toggle model favorite"),
    ("image", "<path>  Attach an image"),
    ("rename", "Rename current chat"),
    ("delete", "Delete current chat"),
    ("defaults", "Save current model & provider as defaults"),
    ("defaults clear", "Reset model & provider to saved defaults"),
    ("quit", "Exit AI Synapse"),
]


@dataclass(frozen=True, slots=True)
class SlashHit:
    command: str
    description: str
    score: float


def match_slash_commands(query: str, *, limit: int = 8) -> list[SlashHit]:
    """Fuzzy-match slash commands. *query* is text after the leading ``/``."""
    q = query.strip().lower()
    if not q:
        return [
            SlashHit(cmd, desc, 1.0) for cmd, desc in SLASH_COMMANDS[:limit]
        ]

    if rf_process is not None and fuzz is not None:
        choices = [f"{cmd} {desc}" for cmd, desc in SLASH_COMMANDS]
        hits = rf_process.extract(
            q,
            choices,
            scorer=fuzz.WRatio,
            limit=limit,
            score_cutoff=35,
        )
        results: list[SlashHit] = []
        for _, score, idx in hits:
            cmd, desc = SLASH_COMMANDS[idx]
            results.append(SlashHit(cmd, desc, score / 100.0))
        if results:
            return results

    tokens = q.split()
    results = []
    for cmd, desc in SLASH_COMMANDS:
        hay = f"{cmd} {desc}".lower()
        if all(tok in hay for tok in tokens):
            results.append(SlashHit(cmd, desc, 0.7))
        if len(results) >= limit:
            break
    return results