"""Image generation helpers — OpenAI-compatible response."""
from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional


def _parse_image_content(content: str, prompt: str) -> List[Dict[str, Any]]:
    data: List[Dict[str, Any]] = []
    if not content:
        return data
    img_match = re.search(r"!\[.*?\]\((https?://[^\)]+)\)", content)
    if img_match:
        data.append({"url": img_match.group(1), "revised_prompt": prompt})
        return data
    data_match = re.search(r"(data:image/[^;]+;base64,[A-Za-z0-9+/=]+)", content)
    if data_match:
        b64 = data_match.group(1).split(",", 1)[1]
        data.append({"b64_json": b64, "revised_prompt": prompt})
        return data
    # bare https URL
    url_match = re.search(r"(https?://\S+\.(?:png|jpg|jpeg|webp|gif)\S*)", content, re.I)
    if url_match:
        data.append({"url": url_match.group(1).rstrip(").,]"), "revised_prompt": prompt})
        return data
    return data


def generate_image(
    *,
    prompt: str,
    model: str = "auto",
    n: int = 1,
    size: str = "1024x1024",
    response_format: str = "url",
    engine=None,
    provider: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate image via engine chat path + capability routing.

    Returns OpenAI-style { created, data: [...] }.
    """
    if not prompt:
        return {"created": int(time.time()), "data": [], "error": "prompt is required"}

    if engine is None:
        from core.ai_engine import AI_engine
        engine = AI_engine(verbose=False)

    target_model = None
    preferred = provider or "openrouter"
    try:
        from core.capabilities import capability_manager
        capability_manager.fetch_openrouter_capabilities()
        image_gen_models = capability_manager.get_models_for_modality("image_gen")
        if model and model not in ("auto", "dall-e-3", "dall-e-2"):
            for m in image_gen_models:
                if model.lower() in m.lower():
                    target_model = m
                    break
            if not target_model and "/" in model:
                target_model = model
        if not target_model and image_gen_models:
            target_model = image_gen_models[0]
    except Exception:
        target_model = model if model not in ("auto",) else None

    if not target_model:
        return {
            "created": int(time.time()),
            "data": [],
            "error": "No image generation model available",
        }

    gen_messages = [{
        "role": "user",
        "content": f"Generate an image: {prompt}. Output ONLY the image URL or data URI. No text explanation.",
    }]
    result = engine.chat_completion(
        messages=gen_messages,
        model=target_model,
        preferred_provider=preferred,
        force_provider=bool(provider),
    )

    data: List[Dict[str, Any]] = []
    if getattr(result, "success", False) and getattr(result, "content", None):
        data = _parse_image_content(result.content, prompt)
        # If response_format prefers b64 and we only have url, leave as url
        if response_format == "b64_json" and data and "url" in data[0] and "b64_json" not in data[0]:
            pass  # keep url; remote fetch not always available offline
    elif not getattr(result, "success", False):
        return {
            "created": int(time.time()),
            "data": [],
            "error": getattr(result, "error_message", "image generation failed"),
        }

    return {"created": int(time.time()), "data": data[: max(1, n)], "model": target_model}
