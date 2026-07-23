"""Embeddings generation — local deterministic + optional remote provider.

OpenAI-compatible response shape:
  { object, data: [{ object, embedding, index }], model, usage }
"""
from __future__ import annotations

import hashlib
import math
import os
import re
import struct
from typing import Any, Dict, List, Optional, Sequence, Union

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore


DEFAULT_DIMS = 1536
TextInput = Union[str, Sequence[str]]


def _as_list(text: TextInput) -> List[str]:
    if isinstance(text, str):
        return [text]
    return [str(t) for t in text]


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower()) or [" "]


def local_embedding(text: str, dimensions: int = DEFAULT_DIMS) -> List[float]:
    """Deterministic bag-of-tokens embedding (no external deps).

    Suitable for cache keys, similarity demos, and offline OpenAI-compat clients.
    Not a substitute for a trained embedding model.
    """
    dims = max(8, int(dimensions))
    vec = [0.0] * dims
    tokens = _tokenize(text)
    for tok in tokens:
        h = hashlib.sha256(tok.encode("utf-8")).digest()
        # Map token into several dimensions with signed contribution
        for i in range(0, min(len(h) - 4, 28), 4):
            idx = struct.unpack_from(">I", h, i)[0] % dims
            sign = 1.0 if (h[i] & 1) == 0 else -1.0
            vec[idx] += sign
    # L2 normalize
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def local_embeddings(texts: TextInput, dimensions: int = DEFAULT_DIMS) -> List[List[float]]:
    return [local_embedding(t, dimensions=dimensions) for t in _as_list(texts)]


def remote_embeddings(
    texts: TextInput,
    *,
    model: str = "text-embedding-3-small",
    endpoint: Optional[str] = None,
    api_key: Optional[str] = None,
    dimensions: Optional[int] = None,
    timeout: float = 60,
) -> Optional[Dict[str, Any]]:
    """Call an OpenAI-compatible embeddings API if endpoint + key available.

    Returns full OpenAI-style response dict, or None on failure / unavailable.
    """
    if requests is None:
        return None
    endpoint = endpoint or os.getenv("EMBEDDINGS_ENDPOINT") or os.getenv("OPENAI_BASE_URL")
    api_key = api_key or os.getenv("EMBEDDINGS_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not endpoint or not api_key:
        return None
    if endpoint.rstrip("/").endswith("/embeddings"):
        url = endpoint
    elif endpoint.rstrip("/").endswith("/v1"):
        url = endpoint.rstrip("/") + "/embeddings"
    else:
        url = endpoint.rstrip("/") + "/v1/embeddings"

    payload: Dict[str, Any] = {
        "model": model,
        "input": _as_list(texts),
    }
    if dimensions:
        payload["dimensions"] = dimensions
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if not isinstance(data, dict) or "data" not in data:
            return None
        return data
    except Exception:
        return None


def create_embeddings(
    input_text: TextInput,
    *,
    model: str = "text-embedding-3-small",
    dimensions: Optional[int] = None,
    encoding_format: str = "float",
    prefer_remote: bool = True,
    endpoint: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Create embeddings — remote if configured, else local deterministic.

    Always returns an OpenAI-compatible embeddings response.
    """
    texts = _as_list(input_text)
    dims = dimensions or DEFAULT_DIMS

    if prefer_remote:
        remote = remote_embeddings(
            texts, model=model, endpoint=endpoint, api_key=api_key, dimensions=dimensions
        )
        if remote is not None:
            # Ensure required keys
            remote.setdefault("object", "list")
            remote.setdefault("model", model)
            return remote

    vectors = local_embeddings(texts, dimensions=dims)
    if encoding_format == "base64":
        import base64
        import struct as st

        encoded = []
        for i, vec in enumerate(vectors):
            raw = b"".join(st.pack("<f", float(v)) for v in vec)
            encoded.append({
                "object": "embedding",
                "embedding": base64.b64encode(raw).decode("ascii"),
                "index": i,
            })
        data = encoded
    else:
        data = [
            {"object": "embedding", "embedding": vec, "index": i}
            for i, vec in enumerate(vectors)
        ]

    prompt_tokens = sum(max(1, len(_tokenize(t))) for t in texts)
    return {
        "object": "list",
        "data": data,
        "model": model if model != "auto" else f"local-hash-{dims}",
        "usage": {"prompt_tokens": prompt_tokens, "total_tokens": prompt_tokens},
        "backend": "local",
    }
