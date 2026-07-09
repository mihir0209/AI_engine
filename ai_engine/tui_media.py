"""Media generation helpers for the TUI — routes via core engine + model cache."""
from __future__ import annotations

import base64
import os
import re
import time
from pathlib import Path
from typing import Any

import requests

GENERATED_DIR = Path.home() / ".ai-engine" / "generated"

IMAGE_API_MODELS = (
    "openai/gpt-5-image-mini",
    "openai/gpt-5-image",
    "google/gemini-2.5-flash-image",
    "google/gemini-3-pro-image",
    "bytedance-seed/seedream-4.5",
)


def _openrouter_key() -> str | None:
    from core.config import AI_CONFIGS

    keys = AI_CONFIGS.get("openrouter", {}).get("api_keys") or []
    for key in keys:
        if key:
            return key
    return os.getenv("OPENROUTER_API_KEY")


def _provider_priority(provider: str | None) -> int:
    try:
        from core.config import AI_CONFIGS
        score = int(AI_CONFIGS.get(provider or "", {}).get("priority", 999))
        if provider in {"openrouter", "vercel", "opencode_zen"}:
            score += 50
        return score
    except Exception:
        return 999


def _model_name_matches(candidate: str, target: str) -> bool:
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


def _image_route_candidates(
    preferred_model: str | None,
    preferred_provider: str | None,
) -> list[tuple[str, str]]:
    """Build ordered (model, provider) attempts using OpenRouter capabilities + model cache."""
    from core.capabilities import capability_manager
    from core.model_cache import shared_model_cache, sanitize_model_list

    capability_manager.fetch_openrouter_capabilities()
    capability_models = list(capability_manager.get_models_for_modality("image_gen"))

    models: list[str] = []
    if preferred_model and preferred_model not in ("default", "auto"):
        models.append(preferred_model)
    for target in capability_models:
        if target not in models:
            models.append(target)
    for target in IMAGE_API_MODELS:
        if target not in models:
            models.append(target)

    shared_model_cache.load_cache()
    cached = sanitize_model_list(shared_model_cache.get_models())
    routes: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str]] = set()

    if preferred_model and preferred_provider:
        key = (preferred_model, preferred_provider)
        if key not in seen:
            seen.add(key)
            routes.append((preferred_model, preferred_provider, _provider_priority(preferred_provider)))

    for target in models:
        for entry in cached:
            if "|" not in entry:
                continue
            provider, api_model = entry.split("|", 1)
            if not _model_name_matches(api_model, target) and not _model_name_matches(target, api_model):
                continue
            key = (api_model, provider)
            if key in seen:
                continue
            seen.add(key)
            routes.append((api_model, provider, _provider_priority(provider)))

        if not any(r[0] == target or _model_name_matches(r[0], target) for r in routes):
            key = (target, "openrouter")
            if key not in seen:
                seen.add(key)
                routes.append((target, "openrouter", _provider_priority("openrouter")))

    routes.sort(key=lambda item: item[2])
    return [(model, provider) for model, provider, _ in routes]


def _save_b64_image(b64_data: str, *, stem: str = "gen", ext: str = ".png") -> str:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    target = GENERATED_DIR / f"{stem}-{int(time.time())}{ext}"
    with open(target, "wb") as f:
        f.write(base64.b64decode(b64_data))
    return str(target)


def _extract_images_from_message(message: dict[str, Any]) -> tuple[str, list[str]]:
    content = message.get("content")
    texts: list[str] = []
    images: list[str] = []
    if isinstance(content, list):
        for part in content:
            if not isinstance(part, dict):
                continue
            ptype = part.get("type")
            if ptype == "text":
                texts.append(part.get("text", ""))
            elif ptype == "image_url":
                url = (part.get("image_url") or {}).get("url", "")
                if url:
                    images.append(url)
    elif isinstance(content, str):
        texts.append(content)
    for key in ("images", "image"):
        val = message.get(key)
        if isinstance(val, list):
            for item in val:
                if isinstance(item, dict):
                    url = item.get("url") or (item.get("image_url") or {}).get("url")
                    if url:
                        images.append(url)
                    b64 = item.get("b64_json")
                    if b64:
                        images.append(f"data:image/png;base64,{b64}")
    return "\n".join(texts).strip(), images


def _persist_image_ref(ref: str, *, stem: str = "gen") -> str | None:
    if ref.startswith("data:image"):
        match = re.search(r"base64,([A-Za-z0-9+/=]+)", ref)
        if match:
            return _save_b64_image(match.group(1), stem=stem)
        return None
    if ref.startswith("http"):
        ext = ".png"
        target = GENERATED_DIR / f"{stem}-{int(time.time())}{ext}"
        try:
            GENERATED_DIR.mkdir(parents=True, exist_ok=True)
            urllib_mod = __import__("urllib.request")
            urllib_mod.urlretrieve(ref, target)
            return str(target)
        except Exception:
            return None
    if os.path.isfile(ref):
        return ref
    return None


def _extract_image_from_text(content: str) -> str | None:
    url_match = re.search(r"!\[.*?\]\((https?://[^\)]+)\)", content)
    if url_match:
        return _persist_image_ref(url_match.group(1), stem="gen")
    data_match = re.search(r"(data:image/[^;]+;base64,([A-Za-z0-9+/=]+))", content)
    if data_match:
        return _save_b64_image(data_match.group(2), stem="gen")
    return None


def _try_openrouter_images_api(prompt: str, model: str, key: str) -> tuple[str | None, str]:
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/mihir0209/AI_engine",
        "X-Title": "AI Synapse TUI",
    }
    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/images",
            headers=headers,
            json={"model": model, "prompt": prompt, "n": 1},
            timeout=180,
        )
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get("data", []):
                b64 = item.get("b64_json")
                if b64:
                    path = _save_b64_image(b64, stem="gen")
                    return path, f"Generated with {model} via openrouter"
            return None, f"{model}: empty image data"
        err = resp.json().get("error", {}).get("message", resp.text[:120])
        return None, f"{model}: {err}"
    except Exception as exc:
        return None, f"{model}: {exc}"


def _try_engine_chat_completion(
    prompt: str, model: str, provider: str
) -> tuple[str | None, str, str, str]:
    """Use the shared AI_engine chat path (same as server image generation)."""
    from core.ai_engine import AI_engine

    engine = AI_engine()
    gen_messages = [
        {
            "role": "user",
            "content": f"Generate an image: {prompt}. Output ONLY the image. No text explanation.",
        }
    ]
    force = provider not in (None, "", "auto")
    result = engine.chat_completion(
        messages=gen_messages,
        model=model,
        preferred_provider=provider if force else None,
        force_provider=force,
    )
    if not result.success or not result.content:
        err = result.error_message or "no image returned"
        return None, f"{provider}/{model}: {err}", model, provider

    path = _extract_image_from_text(result.content)
    if path:
        used = result.model_used or model
        prov = result.provider_used or provider
        return path, f"Generated with {used} ({prov})", used, prov
    return None, f"{provider}/{model}: response had no image data", model, provider


def generate_image(
    prompt: str,
    *,
    preferred_model: str | None = None,
    preferred_provider: str | None = None,
) -> tuple[str | None, str, str, str]:
    """
    Generate an image for a prompt.

    Returns (local_image_path, status_message, model_used, provider_used).
    Tries providers from the shared model cache before falling back to OpenRouter.
    """
    routes = _image_route_candidates(preferred_model, preferred_provider)
    if not routes:
        return None, "No image-capable models found in cache", "", ""

    errors: list[str] = []
    or_key = _openrouter_key()

    for model, provider in routes:
        if provider == "openrouter" and or_key:
            path, status = _try_openrouter_images_api(prompt, model, or_key)
            if path:
                return path, status, model, "openrouter"
            errors.append(status)

        path, status, used, prov = _try_engine_chat_completion(prompt, model, provider)
        if path:
            return path, status, used, prov
        errors.append(status)

    detail = errors[-1] if errors else "no models tried"
    if "credit" in detail.lower():
        return (
            None,
            "Image generation needs OpenRouter credits for image models. "
            f"({detail})",
            "",
            "",
        )
    return None, f"Could not generate image. {detail}", "", ""