"""Model picker index — pre-indexed cache entries for fuzzy search."""
from __future__ import annotations

from dataclasses import dataclass

try:
    from rapidfuzz import fuzz, process as rf_process
except ImportError:
    rf_process = None
    fuzz = None


def parse_model_entry(entry: str) -> tuple[str, str | None, str, str]:
    """Return (api_model, provider, display_label, plain_display) from a cache entry."""
    if "|" in entry:
        provider, model = entry.split("|", 1)
        display = model.split("/")[-1] if "/" in model else model
        return model, provider, f"{display}  [dim]({provider})[/]", display
    if "/" in entry:
        provider, model = entry.split("/", 1)
        return model, provider, f"{model}  [dim]({provider})[/]", model
    return entry, None, entry, entry


def favorite_key(model: str, provider: str | None) -> str:
    return f"{model}|{provider or ''}"


def parse_favorite_key(key: str) -> tuple[str, str | None]:
    if "|" in key:
        model, provider = key.split("|", 1)
        return model, provider or None
    return key, None


MODEL_PAGE_SIZE = 100


@dataclass(frozen=True, slots=True)
class ModelEntry:
    api_model: str
    provider: str | None
    label: str
    plain: str
    search_key: str


class ModelIndex:
    """Pre-indexed model list for instant picker search."""

    __slots__ = ("entries", "_choices")

    def __init__(self, raw_models: list[str]):
        from core.model_cache import sanitize_model_cache_entry

        entries: list[ModelEntry] = []
        for raw in raw_models:
            cleaned = sanitize_model_cache_entry(raw) or raw
            api_model, provider, label, plain = parse_model_entry(cleaned)
            search_key = f"{plain} {api_model} {provider or ''}".lower()
            entries.append(ModelEntry(api_model, provider, label, plain, search_key))
        entries.sort(key=lambda e: e.plain.lower())
        self.entries = entries
        self._choices = [e.search_key for e in entries]

    @classmethod
    def build(cls, raw_models: list[str]) -> "ModelIndex":
        return cls(raw_models)

    def search(self, query: str, *, limit: int | None = 200) -> list[ModelEntry]:
        q = query.strip().lower()
        max_hits = len(self.entries) if limit is None else limit
        if not q:
            return list(self.entries) if limit is None else self.entries[:limit]

        if rf_process is not None and fuzz is not None:
            hits = rf_process.extract(
                q,
                self._choices,
                scorer=fuzz.WRatio,
                limit=max_hits,
                score_cutoff=35,
            )
            if hits:
                return [self.entries[idx] for _, _, idx in hits]

        tokens = q.split()
        results: list[ModelEntry] = []
        for entry in self.entries:
            if all(tok in entry.search_key for tok in tokens):
                results.append(entry)
                if limit is not None and len(results) >= limit:
                    break
        return results

