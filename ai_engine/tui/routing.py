"""Provider/model routing helpers shared by TUI and media generation."""
from __future__ import annotations


def provider_priority(provider: str | None) -> int:
    try:
        from core.config import AI_CONFIGS

        return int(AI_CONFIGS.get(provider or "", {}).get("priority", 999))
    except Exception:
        return 999


def intent_provider_priority(provider: str | None) -> int:
    """Prefer direct providers over gateways when auto-routing by intent."""
    score = provider_priority(provider)
    if provider in {"openrouter", "vercel", "opencode_zen"}:
        score += 50
    return score


def model_name_matches(candidate: str, target: str) -> bool:
    c = candidate.lower().strip()
    t = target.lower().strip()
    if not c or not t:
        return False
    return (
        c == t
        or c.endswith(f"/{t}")
        or t.endswith(f"/{c}")
        or c.split("/")[-1] == t.split("/")[-1]
    )


def pick_route_by_priority(
    candidates: list[tuple[str, str | None]],
    *,
    for_intent: bool = False,
) -> tuple[str, str | None] | None:
    if not candidates:
        return None
    key_fn = intent_provider_priority if for_intent else provider_priority
    ranked = sorted(candidates, key=lambda item: key_fn(item[1]))
    return ranked[0]