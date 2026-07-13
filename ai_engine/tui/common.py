"""Shared TUI helpers — images, clipboard, model cache binding."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from markdown_it import MarkdownIt

try:
    from PIL import Image as PILImage
    from rich_pixels import HalfcellRenderer, Pixels as RichPixels
except ImportError:
    PILImage = None
    RichPixels = None
    HalfcellRenderer = None

_PIXELS_AVAILABLE = PILImage is not None and RichPixels is not None

pkg_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if pkg_root not in sys.path:
    sys.path.insert(0, pkg_root)

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".tif"}
MAX_IMAGE_BYTES = 20 * 1024 * 1024


def bind_model_cache_to_pkg_root() -> None:
    """Use a stable absolute cache path (no os.chdir in worker threads)."""
    from core.model_cache import shared_model_cache
    from core.user_paths import MODEL_CACHE_FILE, ensure_user_dirs

    ensure_user_dirs()
    shared_model_cache.cache_file = str(MODEL_CACHE_FILE)


def _chat_markdown_parser() -> MarkdownIt:
    """GFM-style parser tuned for chat rendering."""
    return MarkdownIt("gfm-like", {"breaks": True, "html": False, "linkify": True})


ATTACHMENTS_DIR = Path.home() / ".ai-engine" / "attachments"


def _format_image_ref(path: str) -> str:
    name = os.path.basename(path) or path
    return f"[dim]📎 {name}[/]\n[dim]{path}[/]"


def _user_message_display(text: str, image_path: str | None = None) -> str:
    body = (text or "").strip()
    if image_path:
        ref = _format_image_ref(image_path)
        return f"{body}\n\n{ref}" if body else ref
    return body


def _is_ephemeral_attachment(path: str) -> bool:
    abs_path = os.path.abspath(path)
    tmp = os.path.abspath(tempfile.gettempdir())
    return abs_path.startswith(tmp + os.sep) or "/tmp/" in abs_path


_IMAGE_SIZE_PRESETS = {
    # (max terminal columns, max image pixel height — half-cell ≈ height/2 rows)
    "preview": (68, 44),
    "chat": (80, 52),
    "large": (84, 60),
}


def _fit_image_dimensions(
    width: int, height: int, max_w: int, max_h: int
) -> tuple[int, int]:
    scale = min(max_w / max(width, 1), max_h / max(height, 1), 1.0)
    new_w = max(1, int(width * scale))
    new_h = max(1, int(height * scale))
    if new_h % 2:
        new_h += 1
    return new_w, new_h


def _image_size_key(*, compact: bool = False, size: str | None = None) -> str:
    if size in _IMAGE_SIZE_PRESETS:
        return size
    return "preview" if compact else "chat"


def _pixels_from_path(
    path: str, *, compact: bool = False, size: str | None = None
):
    """Render an image as rich-pixels (half-cell, LANCZOS). Returns None if unavailable."""
    if not _PIXELS_AVAILABLE or not os.path.exists(path):
        return None
    preset = _image_size_key(compact=compact, size=size)
    max_w, max_h = _IMAGE_SIZE_PRESETS[preset]
    try:
        with PILImage.open(path) as im:
            im = im.convert("RGBA")
            w, h = im.size
            new_w, new_h = _fit_image_dimensions(w, h, max_w, max_h)
            if (new_w, new_h) != (w, h):
                im = im.resize((new_w, new_h), PILImage.Resampling.LANCZOS)
            renderer = HalfcellRenderer() if HalfcellRenderer else None
            return RichPixels.from_image(im, resize=None, renderer=renderer)
    except Exception:
        return None


def _chafa_fallback(
    path: str, *, compact: bool = False, size: str | None = None
) -> str | None:
    """Optional chafa fallback when rich-pixels is not installed."""
    preset = _image_size_key(compact=compact, size=size)
    chafa_sizes = {
        "preview": "68x22",
        "chat": "80x26",
        "large": "84x30",
    }
    try:
        result = subprocess.run(
            [
                "chafa",
                "--size", chafa_sizes.get(preset, "80x26"),
                "--symbols",
                "--fill", "space",
                path,
            ],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    except Exception:
        pass
    return None



def is_image_path(path: str) -> bool:
    return Path(path).suffix.lower() in IMAGE_EXTENSIONS
