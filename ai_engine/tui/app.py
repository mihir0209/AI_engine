"""
AI Synapse TUI — ChatGPT-style terminal chat interface.

Usage:
    python -m ai_engine tui
    python -m ai_engine tui --model default
    python -m ai_engine tui --provider groq
"""
import os
import re
import sys
import time
import base64
import mimetypes
import threading
import subprocess
from pathlib import Path

try:
    from rapidfuzz import fuzz, process as rf_process
except ImportError:
    rf_process = None
    fuzz = None

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Footer, Static, Button, TextArea, Markdown, ListView, ListItem, Label,
    DirectoryTree, LoadingIndicator, Input,
)
from textual.binding import Binding
from textual.reactive import reactive
from textual.screen import ModalScreen, Screen
from textual import work, on, events
from textual.css.query import NoMatches
from textual.command import Provider, Hit, DiscoveryHit
from textual.system_commands import SystemCommandsProvider

pkg_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if pkg_root not in sys.path:
    sys.path.insert(0, pkg_root)

from .common import (
    ATTACHMENTS_DIR,
    IMAGE_EXTENSIONS,
    MAX_IMAGE_BYTES,
    bind_model_cache_to_pkg_root,
    is_image_path,
    _format_image_ref,
    _user_message_display,
    _is_ephemeral_attachment,
    pkg_root as _pkg_root,
)
from .files import FileHit, build_file_index, match_files
from .media import generate_image
from .model_index import (
    MODEL_PAGE_SIZE,
    ModelEntry,
    ModelIndex,
    favorite_key,
    parse_favorite_key,
    parse_model_entry,
)
from .personas import Persona, find_persona, load_personas
from .preferences import PreferencesStore
from .routing import (
    intent_provider_priority,
    model_name_matches,
    pick_route_by_priority,
    provider_priority,
)
from .slash import SlashHit, match_slash_commands
from .storage import (
    ChatStorage,
    _normalize_cwd,
    _sanitize_export_filename,
    write_chat_export,
)
from .widgets import (
    ChatMarkdown,
    ComposerInput,
    FileSuggest,
    ImagePreview,
    MessageBlock,
    PendingAttachment,
    PersonaButton,
    PersonaPanel,
    SlashSuggest,
    TerminalImage,
    TypingIndicator,
    UserMessage,
)
from .screens import (
    ChatCommandProvider,
    ConfirmDeleteScreen,
    ExportChatScreen,
    FilePickerScreen,
    ModelPickerScreen,
    PickerResult,
    ProviderPickerScreen,
    RenameChatScreen,
    SystemPromptScreen,
)

# Backward-compatible aliases for tests and internal callers
_MODEL_PAGE_SIZE = MODEL_PAGE_SIZE
_MAX_IMAGE_BYTES = MAX_IMAGE_BYTES
_bind_model_cache_to_pkg_root = bind_model_cache_to_pkg_root
_is_image_path = is_image_path
_parse_model_entry = parse_model_entry
_favorite_key = favorite_key
_parse_favorite_key = parse_favorite_key
_provider_priority = provider_priority
_intent_provider_priority = intent_provider_priority
_pick_route_by_priority = pick_route_by_priority
_model_name_matches = model_name_matches

def _load_providers() -> list[str]:
    try:
        from core.config import AI_CONFIGS
        return sorted(
            name for name, cfg in AI_CONFIGS.items()
            if cfg.get("enabled", True)
        )
    except Exception:
        return []


def _iter_cached_model_entries() -> list[tuple[str, str | None]]:
    """Yield (api_model, provider) pairs from the shared model cache."""
    try:
        from core.model_cache import shared_model_cache
        shared_model_cache.load_cache()
        raw_models = shared_model_cache.get_models()
    except Exception:
        raw_models = []
    entries: list[tuple[str, str | None]] = []
    for raw in raw_models:
        api_model, provider, _, _ = _parse_model_entry(raw)
        entries.append((api_model, provider))
    return entries


def _apply_intent_routing(
    intent_result: dict,
    *,
    has_images: bool,
    current_provider: str | None,
    current_model: str,
) -> tuple[str, str | None]:
    """Pick provider/model for non-text intents using capability + cache data."""
    from core.capabilities import capability_manager

    intent = intent_result.get("intent", "text_chat")
    requires_vision = intent_result.get("requires_vision", False)
    requires_image_gen = intent_result.get("requires_image_gen", False)
    requires_audio = intent_result.get("requires_audio", False)
    enabled = set(_load_providers())
    cached = _iter_cached_model_entries()

    if intent == "text_chat" or (
        not requires_vision and not requires_image_gen and not requires_audio
    ):
        return current_model, current_provider

    if requires_vision and has_images:
        candidates: list[tuple[str, str | None]] = []
        for vp in capability_manager.get_vision_providers():
            if vp not in enabled:
                continue
            vm = capability_manager.get_vision_model_for_provider(vp)
            if not vm:
                continue
            for api_model, provider in cached:
                if provider == vp and _model_name_matches(api_model, vm):
                    candidates.append((api_model, provider))
                    break
            else:
                candidates.append((vm, vp))
        picked = _pick_route_by_priority(candidates, for_intent=True)
        if picked:
            return picked
        return current_model, current_provider

    if requires_image_gen:
        capability_manager.fetch_openrouter_capabilities()
        image_gen_models = capability_manager.get_models_for_modality("image_gen")
        candidates = []
        for api_model, provider in cached:
            if provider not in enabled:
                continue
            if any(_model_name_matches(api_model, target) for target in image_gen_models):
                candidates.append((api_model, provider))
        picked = _pick_route_by_priority(candidates, for_intent=True)
        if picked:
            return picked
        for target in image_gen_models:
            if "openrouter" in enabled:
                return target, "openrouter"
        return current_model, current_provider

    if requires_audio:
        # TTS is handled locally via edge-tts; keep the user's model selection.
        return current_model, current_provider

    return current_model, current_provider


def _generated_media_dir() -> Path:
    path = Path.home() / ".ai-engine" / "generated"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _ensure_model_cache() -> list[str]:
    """Load model cache from disk; refresh via SDK if stale."""
    try:
        _bind_model_cache_to_pkg_root()
        from core.model_cache import shared_model_cache, sanitize_model_list
        from ai_engine import OpenAI

        if not shared_model_cache.load_cache() or not shared_model_cache.is_cache_valid():
            try:
                OpenAI().models.list()
            except Exception:
                pass
            shared_model_cache.load_cache()

        return sanitize_model_list(shared_model_cache.get_models(sanitize=False))
    except Exception:
        return []


def _start_model_cache_refresh() -> None:
    """Background TTL refresh using the shared model cache."""
    try:
        _bind_model_cache_to_pkg_root()
        from core.model_cache import shared_model_cache
        from ai_engine import OpenAI

        def refresh():
            try:
                _bind_model_cache_to_pkg_root()
                OpenAI().models.list()
            except Exception:
                pass

        if not shared_model_cache.is_cache_valid():
            threading.Thread(target=refresh, daemon=True).start()
        shared_model_cache.start_auto_refresh(refresh)
    except Exception:
        pass


def _copy_text_to_system_clipboard(text: str) -> bool:
    """Copy text to the OS clipboard (wl-copy, xclip, xsel, pbcopy)."""
    if not text:
        return False
    payload = text.encode("utf-8")
    commands = [
        ["wl-copy"],
        ["xclip", "-selection", "clipboard"],
        ["xsel", "--clipboard", "--input"],
        ["pbcopy"],
    ]
    for cmd in commands:
        try:
            subprocess.run(
                cmd,
                input=payload,
                check=True,
                capture_output=True,
                timeout=3,
            )
            return True
        except (OSError, subprocess.SubprocessError):
            continue
    return False


def _clipboard_image_path() -> str | None:
    """Try to read a PNG image from the system clipboard."""
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.close()
    commands = [
        ["wl-paste", "-t", "image/png"],
        ["xclip", "-selection", "clipboard", "-t", "image/png", "-o"],
        ["pngpaste", tmp.name],
    ]
    for cmd in commands:
        try:
            if cmd[0] == "pngpaste":
                result = subprocess.run(cmd, capture_output=True, timeout=3)
                if result.returncode == 0 and os.path.getsize(tmp.name) > 0:
                    return tmp.name
            else:
                result = subprocess.run(cmd, capture_output=True, timeout=3)
                if result.returncode == 0 and result.stdout:
                    with open(tmp.name, "wb") as f:
                        f.write(result.stdout)
                    return tmp.name
        except Exception:
            continue
    try:
        os.unlink(tmp.name)
    except OSError:
        pass
    return None


# ============================================================
# WIDGETS
# ============================================================
class ChatTUI(App):
    """ChatGPT-inspired terminal chat."""

    CSS = """
    Screen {
        layout: horizontal;
        background: $background;
    }

    #sidebar {
        width: 28;
        height: 1fr;
        background: $surface-darken-1;
        border-right: solid $surface-darken-2;
        layout: vertical;
    }

    #sidebar.-collapsed {
        width: 3;
    }

    #sidebar.-collapsed #sidebar-brand,
    #sidebar.-collapsed #sidebar-body,
    #sidebar.-collapsed #sidebar-footer {
        display: none;
    }

    #sidebar.-collapsed #sidebar-top {
        width: 100%;
        align: center middle;
        padding: 0;
    }

    #sidebar-top {
        height: 3;
        width: 100%;
        align: left middle;
        padding: 0 1;
    }

    #sidebar-brand {
        width: 1fr;
        height: 3;
        padding: 1 1;
        text-style: bold;
        content-align: left middle;
    }

    #sidebar-toggle-btn {
        width: 3;
        min-width: 3;
        height: 3;
        padding: 0;
        border: none;
        background: transparent;
        color: $text-muted;
        content-align: center middle;
    }

    #sidebar-toggle-btn:hover {
        color: $text;
        background: $surface;
    }

    #sidebar-body {
        height: 1fr;
        layout: vertical;
    }

    #new-chat-btn {
        width: 1fr;
        margin: 0 2 1 2;
        background: transparent;
        border: round $surface-lighten-1;
    }

    #chat-search {
        margin: 0 2 1 2;
        height: 3;
        border: round $surface-lighten-1;
        background: $surface;
    }

    .chat-favorite {
        color: #D4AF37;
        text-style: bold;
    }

    #chat-list {
        height: 1fr;
        border: none;
        padding: 0 1;
        background: transparent;
        scrollbar-visibility: hidden;
    }

    #model-list {
        scrollbar-size-vertical: 1;
        scrollbar-background: $surface-darken-1;
        scrollbar-color: $surface-lighten-1;
        scrollbar-color-hover: $primary 40%;
        scrollbar-color-active: $primary 60%;
    }

    #chat-view {
        scrollbar-size-vertical: 1;
        scrollbar-background: transparent;
        scrollbar-color: $surface-lighten-1;
        scrollbar-color-hover: $primary 40%;
        scrollbar-color-active: $primary 60%;
    }

    ListItem {
        padding: 0 1;
        height: 2;
    }

    ListItem:hover {
        background: $surface;
    }

    ListItem.-selected {
        background: $surface;
        text-style: bold;
    }

    #sidebar-footer {
        height: auto;
        padding: 1 2;
        color: $text-muted;
        border-top: solid $surface-darken-2;
    }

    #main-panel {
        width: 1fr;
        height: 1fr;
        layout: vertical;
    }

    #chat-header {
        height: 3;
        content-align: center middle;
        border-bottom: solid $surface-darken-1;
        color: $text-muted;
    }

    #chat-view {
        height: 1fr;
        min-height: 8;
        scrollbar-gutter: stable;
    }

    #messages-outer {
        width: 100%;
        height: auto;
        align: center top;
    }

    #messages-wrap {
        width: 88;
        max-width: 88;
        height: auto;
        padding: 2 0;
    }

    #empty-state {
        height: 1fr;
        min-height: 14;
        align: center middle;
        text-align: center;
        width: 100%;
    }

    .welcome-msg {
        width: 88;
        max-width: 88;
        text-align: center;
        padding: 0 2;
    }

    .message-block {
        width: 100%;
        height: auto;
        margin-bottom: 1;
    }

    .user-block {
        width: 100%;
        height: auto;
        align-horizontal: right;
        padding: 0 0 1 0;
    }

    .user-bubble {
        width: auto;
        max-width: 70;
        padding: 1 2;
        background: $surface;
        border: round $surface-lighten-1;
        text-align: right;
    }

    .assistant-image {
        width: auto;
        max-width: 100%;
        height: auto;
        padding: 0 0 1 0;
    }

    .assistant-block {
        width: 100%;
        padding: 0 0 1 0;
    }

    .assistant-label {
        color: $text-muted;
        text-style: bold;
        height: 1;
        padding-bottom: 0;
    }

    .assistant-bubble {
        width: 100%;
        background: transparent;
        border: none;
        padding: 0;
    }

    .system-msg {
        color: $text-muted;
        text-align: center;
        padding: 0 0 1 0;
    }

    .error-msg {
        color: $error;
        padding: 1 2;
        border: round $error 40%;
        background: $error 10%;
    }

    #composer {
        height: auto;
        padding: 1 0 2 0;
        align-horizontal: center;
        border-top: solid $surface-darken-1;
    }

    #composer-inner {
        width: 88;
        max-width: 88;
        height: auto;
    }

    #attachment-strip {
        width: 100%;
        height: auto;
        display: none;
        padding: 0 0 1 0;
    }

    #attachment-strip.-visible {
        display: block;
    }

    #composer-box {
        width: 100%;
        height: auto;
        border: round $surface-lighten-1;
        background: $surface;
        padding: 0 1;
    }

    #composer-box:focus-within {
        border: round $primary 60%;
    }

    ComposerInput {
        width: 1fr;
        height: auto;
        min-height: 3;
        max-height: 10;
        padding: 1;
        border: none;
        background: transparent;
    }

    #input-controls {
        height: 3;
        align: right middle;
        content-align: center middle;
    }

    #attach-btn {
        width: auto;
        min-width: 10;
        height: 3;
        min-height: 3;
        max-height: 3;
        padding: 0 2;
        background: transparent;
        border: none;
        color: $text-muted;
        content-align: center middle;
    }

    #attach-btn:hover {
        color: $text;
    }

    #send-btn {
        width: auto;
        min-width: 6;
        height: 3;
        min-height: 3;
        max-height: 3;
        margin-left: 1;
        padding: 0 2;
        content-align: center middle;
        text-style: bold;
    }

    Footer {
        background: $background;
    }
    """

    BINDINGS = [
        Binding("ctrl+j", "send_message", "Send", priority=True, show=True),
        Binding("alt+enter", "send_message", "Send", priority=True, show=True),
        Binding("ctrl+enter", "send_message", "Send", priority=True, show=True),
        Binding("ctrl+n", "new_chat", "New Chat"),
        Binding("f2", "pick_model", "Model"),
        Binding("f3", "pick_provider", "Provider"),
        Binding("f4", "rename_chat", "Rename"),
        Binding("ctrl+d", "delete_chat", "Delete"),
        Binding("ctrl+f", "toggle_favorite", "Favorite"),
        Binding("ctrl+shift+f", "focus_chat_search", "Search"),
        Binding("f6", "toggle_intent_routing", "Intent", show=True),
        Binding("f5", "edit_system_prompt", "System", show=True),
        Binding("f8", "export_chat", "Export", show=True),
        Binding("y", "copy_message", "Copy"),
        Binding("ctrl+c", "copy_message", "Copy", priority=True),
        Binding("ctrl+shift+c", "copy_message", "Copy", priority=True),
        Binding("r", "regenerate", "Regenerate"),
        Binding("e", "edit_resend", "Edit"),
        Binding("escape", "stop_generation", "Stop", show=False),
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("ctrl+b", "toggle_sidebar", "Sidebar", show=True),
    ]

    TITLE = "AI Synapse"
    COMMAND_PALETTE_BINDING = "ctrl+p"
    COMMANDS = {SystemCommandsProvider, ChatCommandProvider}
    AUTO_FOCUS = "ComposerInput"

    current_model = reactive("default")
    current_provider = reactive(None)
    is_processing = reactive(False)
    current_chat_id = reactive(0)
    chat_counter = reactive(0)
    sidebar_collapsed = reactive(False)

    def __init__(
        self,
        model="default",
        provider=None,
        *,
        storage: ChatStorage | None = None,
        preferences: PreferencesStore | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._storage = storage or ChatStorage()
        self._preferences = preferences or PreferencesStore()
        self._chat_order: list[int] = []
        self._persona_banner = None
        self._last_cwd = os.getcwd()
        self._pending_image = None
        self._typing_widget = None
        self._active_response = None
        self._active_block: MessageBlock | None = None
        self._cancel_event = threading.Event()
        self._generation_chat_id: int | None = None
        self._stick_to_bottom = True
        self._cached_models: list[str] = []
        self._model_index: ModelIndex | None = None
        self._favorite_models: list[str] = []
        self._intent_routing_enabled = True
        self._sidebar_filter = ""
        self._personas = load_personas()
        self._file_index: list[str] = []
        self._file_index_root = ""
        self._file_suggest_mode = ""
        self._prefs = self._preferences.load()

        loaded = self._storage.load()
        if loaded and loaded.get("chats"):
            self.chats = loaded["chats"]
            self.chat_counter = loaded["chat_counter"]
            self.current_chat_id = loaded["current_chat_id"]
            self._chat_order = loaded.get("chat_order") or list(self.chats.keys())
            self._last_cwd = loaded.get("last_cwd") or os.getcwd()
            if loaded.get("current_model"):
                self.current_model = loaded["current_model"]
            elif model not in (None, "", "default"):
                self.current_model = model
            else:
                self.current_model = self._prefs.get("default_model", "default")
            saved_provider = loaded.get("current_provider", provider)
            if saved_provider is not None:
                self.current_provider = saved_provider
            elif provider not in (None, "", "auto"):
                self.current_provider = provider
            else:
                self.current_provider = self._prefs.get("default_provider")
            legacy = list(loaded.get("_legacy_favorite_models", []))
            self._favorite_models = self._preferences.migrate_favorite_models_from_meta(
                legacy
            )
            self._intent_routing_enabled = bool(
                loaded.get("intent_routing_enabled", True)
            )
        else:
            self._favorite_models = self._prefs.get("favorite_models", [])
            if model not in (None, "", "default"):
                self.current_model = model
            else:
                self.current_model = self._prefs.get("default_model", "default")
            if provider not in (None, "", "auto"):
                self.current_provider = provider
            else:
                self.current_provider = self._prefs.get("default_provider")
            self.chats = {}
            self.chat_counter = 0
            self.current_chat_id = 0
            self._new_chat()

    def _new_chat(self):
        self.chat_counter += 1
        self.current_chat_id = self.chat_counter
        now = time.time()
        self.chats[self.current_chat_id] = {
            "title": "New chat",
            "messages": [],
            "system_prompt": "",
            "persona_id": "",
            "favorite": False,
            "created_at": now,
            "updated_at": now,
        }
        self._touch_chat(self.current_chat_id)

    def _touch_chat(self, chat_id: int) -> None:
        if chat_id in self._chat_order:
            self._chat_order.remove(chat_id)
        self._chat_order.insert(0, chat_id)

    def _set_last_cwd(self, path: str) -> None:
        self._last_cwd = _normalize_cwd(path)
        self._refresh_file_index()
        try:
            self._storage.save_last_cwd(self._last_cwd)
        except Exception:
            pass

    def _persist_session(self) -> None:
        try:
            self._storage.save_session(
                chats=self.chats,
                chat_counter=self.chat_counter,
                current_chat_id=self.current_chat_id,
                chat_order=self._chat_order,
                last_cwd=self._last_cwd,
                current_model=self.current_model,
                current_provider=self.current_provider,
                intent_routing_enabled=self._intent_routing_enabled,
            )
        except Exception as exc:
            self.notify(
                f"Failed to save session: {exc}",
                severity="error",
                timeout=5,
            )

    def _bound_chat_id(self) -> int:
        """Chat that owns an in-flight generation (falls back to current)."""
        if self._generation_chat_id is not None:
            return self._generation_chat_id
        return self.current_chat_id

    def on_unmount(self) -> None:
        self._persist_session()

    def compose(self) -> ComposeResult:
        with Vertical(id="sidebar"):
            with Horizontal(id="sidebar-top"):
                yield Static("AI Synapse", id="sidebar-brand")
                yield Button("«", id="sidebar-toggle-btn", variant="default")
            with Vertical(id="sidebar-body"):
                yield Button("+  New chat", id="new-chat-btn", variant="default")
                yield Input(placeholder="Search chats…", id="chat-search")
                yield ListView(id="chat-list")
                yield Static("", id="sidebar-footer")

        with Vertical(id="main-panel"):
            yield Static("", id="chat-header")
            with VerticalScroll(id="chat-view", can_focus=False):
                with Container(id="empty-state"):
                    yield PersonaPanel(self._personas, classes="welcome-msg")
                with Horizontal(id="messages-outer"):
                    with Container(id="messages-wrap"):
                        pass
            with Container(id="composer"):
                with Container(id="composer-inner"):
                    with Container(id="attachment-strip"):
                        pass
                    with Container(id="composer-box"):
                        yield FileSuggest(id="file-suggest")
                        yield SlashSuggest(id="slash-suggest")
                        yield ComposerInput(
                            id="user-input",
                            placeholder="Ask anything · @ attach file · / commands",
                            show_line_numbers=False,
                            soft_wrap=True,
                        )
                        with Horizontal(id="input-controls"):
                            yield Button("Attach", id="attach-btn")
                            yield Button("⏎", id="send-btn", variant="primary")

        yield Footer()

    async def on_event(self, event: events.Event) -> None:
        """Guard Textual selection crash on double-clicking Toast/status overlays."""
        try:
            await super().on_event(event)
        except AttributeError as exc:
            if "region" in str(exc) and isinstance(
                event, (events.MouseDown, events.MouseUp, events.Click)
            ):
                return
            raise

    def on_mount(self) -> None:
        self.query_one(ComposerInput).focus()
        self._refresh_sidebar()
        self._update_header()
        _start_model_cache_refresh()
        self._preload_model_index()
        self._refresh_file_index()
        current = self.chats.get(self.current_chat_id, {})
        if current.get("messages"):
            self._load_current_chat_messages()
        else:
            self._show_empty_state(True)

    @on(events.Paste)
    def on_paste(self, event: events.Paste) -> None:
        """Attach pasted image paths or clipboard image data."""
        text = (event.text or "").strip().strip("'\"")
        if text and os.path.isfile(text) and _is_image_path(text):
            path = os.path.abspath(text)
            self._set_last_cwd(os.path.dirname(path))
            self._attach_image(path)
            event.stop()
            return
        clip_path = _clipboard_image_path()
        if clip_path:
            self._attach_image(clip_path)
            event.stop()

    @work(thread=True)
    def _preload_model_index(self) -> None:
        models = _ensure_model_cache()
        index = ModelIndex.build(models)

        def apply():
            self._cached_models = models
            self._model_index = index

        self.call_from_thread(apply)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "send-btn":
            self.action_send_message()
        elif bid == "attach-btn":
            self._open_file_picker()
        elif bid == "new-chat-btn":
            self.action_new_chat()
        elif bid == "sidebar-toggle-btn":
            self.action_toggle_sidebar()
        elif bid == "clear-attach-btn":
            self._clear_attachment_preview()
        elif hasattr(event.button, "persona_id"):
            if self.is_processing:
                return
            self._apply_persona(event.button.persona_id)

    @on(ListView.Selected, "#chat-list")
    def on_chat_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if hasattr(item, "chat_id"):
            self._switch_to_chat(item.chat_id)

    @on(Input.Changed, "#chat-search")
    def on_chat_search_changed(self, event: Input.Changed) -> None:
        self._sidebar_filter = event.value or ""
        self.set_timer(0.05, self._refresh_sidebar, name="chat-search-debounce")

    @on(TextArea.Changed, "#user-input")
    def on_composer_changed(self, event: TextArea.Changed) -> None:
        text = event.text_area.text or ""

        at_match = re.search(r"@([^\s]*)$", text)
        if at_match:
            self._hide_slash_suggest()
            self._show_file_suggest(at_match.group(1), mode="attach")
            return

        read_match = re.match(r"^/read(?:\s+(.*))?$", text, re.DOTALL)
        if read_match is not None:
            query = (read_match.group(1) or "").strip()
            if not query or not os.path.isfile(query):
                self._hide_slash_suggest()
                self._show_file_suggest(query, mode="read")
                return

        if not text.startswith("/"):
            self._hide_slash_suggest()
            self._hide_file_suggest()
            return
        self._hide_file_suggest()
        tail = text[1:]
        if " " in tail:
            first = tail.split(maxsplit=1)[0].lower()
            if first not in {
                "persona", "read", "export", "system", "model", "intent", "defaults",
            }:
                self._hide_slash_suggest()
                return
        hits = match_slash_commands(tail)
        if hits:
            self._show_slash_suggest(hits)
        else:
            self._hide_slash_suggest()

    @on(ListView.Selected, "#file-list")
    def on_file_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if hasattr(item, "file_path"):
            self._apply_file_pick(item.file_path, self._file_suggest_mode)

    @on(ListView.Selected, "#slash-list")
    def on_slash_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if hasattr(item, "slash_command"):
            self.query_one(ComposerInput).text = f"/{item.slash_command} "
            self.query_one(ComposerInput).focus()
            self._hide_slash_suggest()

    def _show_slash_suggest(self, hits: list[SlashHit]) -> None:
        try:
            strip = self.query_one("#slash-suggest", SlashSuggest)
            lst = self.query_one("#slash-list", ListView)
            lst.clear()
            for hit in hits:
                item = ListItem(Label(f"/{hit.command}  [dim]{hit.description}[/]"))
                item.slash_command = hit.command
                lst.append(item)
            strip.add_class("-visible")
        except NoMatches:
            pass

    def _hide_slash_suggest(self) -> None:
        try:
            strip = self.query_one("#slash-suggest", SlashSuggest)
            strip.remove_class("-visible")
            self.query_one("#slash-list", ListView).clear()
        except NoMatches:
            pass

    def _refresh_file_index(self) -> None:
        root = self._last_cwd if os.path.isdir(self._last_cwd) else os.getcwd()
        self._file_index_root = root
        self._file_index = build_file_index(root)

    def _show_file_suggest(self, query: str, *, mode: str) -> None:
        self._file_suggest_mode = mode
        hits = match_files(query, self._file_index, root=self._file_index_root, limit=8)
        if not hits and query:
            self._refresh_file_index()
            hits = match_files(query, self._file_index, root=self._file_index_root, limit=8)
        try:
            strip = self.query_one("#file-suggest", FileSuggest)
            lst = self.query_one("#file-list", ListView)
            lst.clear()
            title = "Attach file" if mode == "attach" else "Read file"
            self.query_one("#file-suggest-title", Static).update(
                f"[dim]{title} · ↑↓ select · Enter pick · Esc dismiss[/]"
            )
            for hit in hits:
                item = ListItem(Label(f"📄 {hit.label}"))
                item.file_path = hit.path
                lst.append(item)
            if hits:
                strip.add_class("-visible")
            else:
                strip.remove_class("-visible")
        except NoMatches:
            pass

    def _hide_file_suggest(self) -> None:
        self._file_suggest_mode = ""
        try:
            strip = self.query_one("#file-suggest", FileSuggest)
            strip.remove_class("-visible")
            self.query_one("#file-list", ListView).clear()
        except NoMatches:
            pass

    def _read_file_content(self, path: str, *, max_chars: int = 12000) -> str | None:
        if not os.path.isfile(path):
            return None
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError:
            return None
        if len(content) > max_chars:
            content = content[:max_chars] + "\n\n[file truncated]"
        return content

    def _inject_file_content(self, path: str, composer: ComposerInput) -> None:
        content = self._read_file_content(path)
        if content is None:
            self.notify(f"Cannot read file: {path}", severity="error", timeout=3)
            return
        block = f"File: {path}\n```\n{content}\n```"
        existing = (composer.text or "").strip()
        composer.text = f"{existing}\n\n{block}".strip() if existing else block
        self._set_last_cwd(os.path.dirname(os.path.abspath(path)))
        self.notify(f"Loaded {os.path.basename(path)}", timeout=2)

    def _apply_file_pick(self, path: str, mode: str) -> None:
        composer = self.query_one(ComposerInput)
        text = composer.text or ""
        if mode == "attach":
            composer.text = re.sub(r"@[^\s]*$", "", text).rstrip()
            self._set_last_cwd(os.path.dirname(os.path.abspath(path)))
            if _is_image_path(path):
                self._attach_image(path)
            else:
                self._inject_file_content(path, composer)
        elif mode == "read":
            composer.text = ""
            self._inject_file_content(path, composer)
        self._hide_file_suggest()
        composer.focus()

    def _messages_container(self) -> Container:
        return self.query_one("#messages-wrap", Container)

    def _scroll_to_end(self, *, force: bool = False) -> None:
        if force or self._stick_to_bottom:
            self.query_one("#chat-view", VerticalScroll).scroll_end(animate=False)

    @on(events.MouseScrollUp, "#chat-view")
    def on_chat_scroll_up(self, event: events.MouseScrollUp) -> None:
        self._stick_to_bottom = False

    @on(events.MouseScrollDown, "#chat-view")
    def on_chat_scroll_down(self, event: events.MouseScrollDown) -> None:
        scroll = self.query_one("#chat-view", VerticalScroll)
        if scroll.is_vertical_scroll_end:
            self._stick_to_bottom = True

    def _show_empty_state(self, show: bool) -> None:
        try:
            self.query_one("#empty-state", Container).display = "block" if show else "none"
        except NoMatches:
            pass

    def _attachment_strip(self) -> Container:
        return self.query_one("#attachment-strip", Container)

    def _clear_attachment_preview(self) -> None:
        strip = self._attachment_strip()
        for child in list(strip.children):
            child.remove()
        strip.remove_class("-visible")
        self._pending_image = None

    def _persist_attachment_path(self, path: str) -> str:
        """Keep a stable path ref; copy clipboard/temp images into ~/.ai-engine/attachments."""
        abs_path = os.path.abspath(path)
        if not os.path.isfile(abs_path):
            return abs_path
        attachments_root = ATTACHMENTS_DIR.resolve()
        attachments_root.mkdir(parents=True, exist_ok=True)
        try:
            if Path(abs_path).resolve().is_relative_to(attachments_root):
                return abs_path
        except (ValueError, AttributeError):
            if abs_path.startswith(str(attachments_root)):
                return abs_path
        if _is_ephemeral_attachment(abs_path):
            stem = Path(abs_path).stem or "paste"
            suffix = Path(abs_path).suffix or ".png"
            dest = attachments_root / f"{self.current_chat_id}_{int(time.time())}_{stem}{suffix}"
            shutil.copy2(abs_path, dest)
            return str(dest)
        return abs_path

    def _attach_image(self, path: str) -> None:
        if not os.path.exists(path):
            return
        self._set_last_cwd(os.path.dirname(os.path.abspath(path)))
        self._pending_image = path
        strip = self._attachment_strip()
        for child in list(strip.children):
            child.remove()
        strip.mount(PendingAttachment(path))
        strip.add_class("-visible")
        self.notify(f"Attached {os.path.basename(path)}", timeout=2)

    def _mount_user_message(
        self,
        text: str,
        *,
        plain_text: str | None = None,
    ) -> MessageBlock:
        wrap = self._messages_container()
        display = (text or "").strip()
        block = MessageBlock(
            role="user",
            plain_text=plain_text or display,
            classes="message-block user-block",
        )
        wrap.mount(block)
        if display:
            block.mount(UserMessage(display, classes="user-bubble"))
        return block

    def _format_response_label(self, model: str, provider: str | None) -> str:
        short = model.split("/")[-1] if "/" in model else model
        if len(short) > 36:
            short = "…" + short[-33:]
        prov = provider or "auto"
        return f"{short} · {prov}"

    def _set_assistant_label(self, model: str, provider: str | None) -> None:
        if self._active_block is None:
            return
        try:
            self._active_block.query_one(".assistant-label", Static).update(
                self._format_response_label(model, provider)
            )
        except NoMatches:
            pass

    def _mount_assistant_message(
        self,
        content: str = "",
        *,
        plain_text: str | None = None,
        image_path: str | None = None,
        model: str | None = None,
        provider: str | None = None,
    ) -> ChatMarkdown:
        wrap = self._messages_container()
        block = MessageBlock(
            role="assistant",
            plain_text=plain_text or content,
            classes="message-block assistant-block",
        )
        wrap.mount(block)
        label = self._format_response_label(
            model or self.current_model,
            provider if provider is not None else self.current_provider,
        )
        block.mount(Static(label, classes="assistant-label"))
        msg = ChatMarkdown(content, classes="assistant-bubble")
        block.mount(msg)
        if image_path and os.path.exists(image_path):
            block.mount(TerminalImage(image_path, size="chat", classes="assistant-image"))
        self._active_block = block
        return msg

    def _show_typing(self, *, model: str | None = None, provider: str | None = None) -> None:
        self._hide_typing()
        label = (
            f"{self._format_response_label(model, provider)} is thinking"
            if model
            else "Waiting for response…"
        )
        self._messages_container().mount(TypingIndicator(label))
        self._typing_widget = self.query(TypingIndicator).last()
        self._scroll_to_end()

    def _update_typing_label(self, model: str, provider: str | None) -> None:
        if self._typing_widget is None:
            return
        try:
            self._typing_widget.query_one("#typing-label", Static).update(
                f"{self._format_response_label(model, provider)} is thinking"
            )
        except NoMatches:
            pass

    def _hide_typing(self) -> None:
        if self._typing_widget is not None:
            try:
                self._typing_widget.remove()
            except Exception:
                pass
            self._typing_widget = None

    def action_send_message(self) -> None:
        if self.is_processing:
            self._stop_generation()
            return
        try:
            strip = self.query_one("#file-suggest", FileSuggest)
            if strip.has_class("-visible"):
                lst = self.query_one("#file-list", ListView)
                item = lst.highlighted_child
                if item is not None and hasattr(item, "file_path"):
                    self._apply_file_pick(item.file_path, self._file_suggest_mode)
                    return
                if lst.children:
                    first = lst.children[0]
                    if hasattr(first, "file_path"):
                        self._apply_file_pick(first.file_path, self._file_suggest_mode)
                        return
        except NoMatches:
            pass
        input_widget = self.query_one(ComposerInput)
        text = (input_widget.text or "").strip()
        if not text:
            return
        input_widget.text = ""
        input_widget.focus()
        self._hide_file_suggest()
        if text.startswith("/"):
            self._handle_command(text)
            return
        self._send_message(text)

    def action_stop_generation(self) -> None:
        try:
            if self.query_one("#file-suggest", FileSuggest).has_class("-visible"):
                self._hide_file_suggest()
                return
            if self.query_one("#slash-suggest", SlashSuggest).has_class("-visible"):
                self._hide_slash_suggest()
                return
        except NoMatches:
            pass
        if self.is_processing:
            self._stop_generation()

    def _copy_to_clipboard(self, text: str) -> None:
        if not (text or "").strip():
            self.notify("Nothing to copy", severity="warning", timeout=2)
            return
        super().copy_to_clipboard(text)
        if _copy_text_to_system_clipboard(text):
            self.notify("Copied to clipboard", timeout=2)
        else:
            self.notify("Copied (use Ctrl+Shift+V if paste fails)", timeout=3)

    def _get_screen_selection(self) -> str:
        try:
            selected = self.screen.get_selected_text()
        except Exception:
            return ""
        return (selected or "").strip()

    def action_copy_message(self) -> None:
        selected = self._get_screen_selection()
        if selected:
            self._copy_to_clipboard(selected)
            return

        focused = self.focused
        if isinstance(focused, ComposerInput):
            composer_sel = (focused.selected_text or "").strip()
            if composer_sel:
                self._copy_to_clipboard(composer_sel)
                return

        if isinstance(focused, MessageBlock) and focused.plain_text:
            self._copy_to_clipboard(focused.plain_text)
            return

        chat = self.chats.get(self.current_chat_id, {})
        for msg in reversed(chat.get("messages", [])):
            if msg["role"] == "assistant" and msg.get("content"):
                self._copy_to_clipboard(str(msg["content"]))
                return
        self.notify("No message to copy", severity="warning", timeout=2)

    def action_regenerate(self) -> None:
        if self.is_processing:
            return
        chat = self.chats.get(self.current_chat_id)
        if not chat:
            return
        messages = chat["messages"]
        if not messages or messages[-1]["role"] != "assistant":
            self.notify("No assistant reply to regenerate", severity="warning", timeout=2)
            return
        messages.pop()
        wrap = self._messages_container()
        assistant_blocks = [
            child for child in wrap.children
            if isinstance(child, MessageBlock) and child.role == "assistant"
        ]
        if assistant_blocks:
            assistant_blocks[-1].remove()
        self._persist_session()
        self._start_ai_generation()

    def action_edit_resend(self) -> None:
        if self.is_processing:
            return
        chat = self.chats.get(self.current_chat_id)
        if not chat:
            return
        messages = chat["messages"]
        last_user_idx = None
        for idx in range(len(messages) - 1, -1, -1):
            if messages[idx]["role"] == "user":
                last_user_idx = idx
                break
        if last_user_idx is None:
            self.notify("No user message to edit", severity="warning", timeout=2)
            return
        user_text = messages[last_user_idx]["content"]
        image_path = messages[last_user_idx].get("_image_path")
        del messages[last_user_idx:]
        self._persist_session()
        wrap = self._messages_container()
        self._clear_messages()
        if messages:
            self._show_empty_state(False)
            self._replay_messages(wrap, chat)
        else:
            self._show_empty_state(True)
        composer = self.query_one(ComposerInput)
        composer.text = user_text
        if image_path and os.path.exists(image_path):
            self._attach_image(image_path)
        else:
            self._clear_attachment_preview()
        composer.focus()

    def _save_model_favorites(self) -> None:
        prefs = self._preferences.load()
        prefs["favorite_models"] = self._favorite_models
        self._preferences.save(prefs)

    def _toggle_model_favorite(self, model: str, provider: str | None) -> None:
        key = _favorite_key(model, provider)
        if key in self._favorite_models:
            self._favorite_models.remove(key)
            self.notify("Model removed from preferences", timeout=2)
        else:
            self._favorite_models.insert(0, key)
            self.notify("Model saved to preferences", timeout=2)
        self._save_model_favorites()

    def action_toggle_favorite(self) -> None:
        chat = self.chats.get(self.current_chat_id)
        if not chat:
            return
        chat["favorite"] = not bool(chat.get("favorite"))
        self._persist_session()
        self._refresh_sidebar()
        self._update_header()
        state = "favorited" if chat["favorite"] else "unfavorited"
        self.notify(f"Chat {state}", timeout=2)

    def _is_persona_banner(self, widget) -> bool:
        if widget is self._persona_banner:
            return True
        has_class = getattr(widget, "has_class", None)
        if callable(has_class) and has_class("persona-banner"):
            return True
        classes = getattr(widget, "classes", None)
        return bool(classes and "persona-banner" in classes)

    def _remove_persona_banner(self) -> None:
        if self._persona_banner is not None:
            try:
                self._persona_banner.remove()
            except Exception:
                pass
            self._persona_banner = None
        try:
            wrap = self._messages_container()
            for child in list(wrap.children):
                if self._is_persona_banner(child):
                    child.remove()
        except NoMatches:
            pass

    def _mount_persona_banner(self, persona) -> None:
        self._remove_persona_banner()
        banner = Static(
            f"{persona.emoji} [bold]{persona.label}[/] persona active — "
            f"[dim]{persona.description or 'type your request below'}[/]",
            classes="system-msg persona-banner",
        )
        self._messages_container().mount(banner)
        self._persona_banner = banner

    def _show_persona_banner_for_chat(self, chat: dict) -> None:
        persona_id = (chat.get("persona_id") or "").strip()
        if not persona_id:
            return
        persona = find_persona(self._personas, persona_id)
        if persona:
            self._mount_persona_banner(persona)

    def action_toggle_intent_routing(self) -> None:
        self._intent_routing_enabled = not self._intent_routing_enabled
        state = "on" if self._intent_routing_enabled else "off"
        self._persist_session()
        self._update_header()
        self.notify(f"Intent routing {state}", timeout=2)

    def _clear_persona(self) -> None:
        chat = self.chats.get(self.current_chat_id)
        if not chat:
            return
        chat["system_prompt"] = ""
        chat["persona_id"] = ""
        self._remove_persona_banner()
        self._persist_session()
        self._update_header()
        self._refresh_sidebar()
        self.notify("Persona cleared", timeout=2)
        self.query_one(ComposerInput).focus()

    def _apply_persona(self, persona_id: str) -> None:
        if persona_id.lower() in {"clear", "off", "none"}:
            self._clear_persona()
            return
        persona = find_persona(self._personas, persona_id)
        if not persona:
            self.notify(f"Unknown persona: {persona_id}", severity="warning", timeout=2)
            return
        chat = self.chats[self.current_chat_id]
        if chat.get("persona_id") == persona.id:
            self._clear_persona()
            return
        chat["system_prompt"] = persona.system_prompt
        chat["persona_id"] = persona.id
        if not chat.get("messages"):
            chat["title"] = persona.label
        self._persist_session()
        self._update_header()
        self._refresh_sidebar()
        self._show_empty_state(False)
        self._mount_persona_banner(persona)
        self._scroll_to_end()
        self.notify(f"{persona.emoji} {persona.label} persona active", timeout=2)
        self.query_one(ComposerInput).focus()

    def action_list_personas(self) -> None:
        lines = [f"{p.emoji} [bold]{p.id}[/] — {p.label}" for p in self._personas]
        text = "Agent personas:\n" + "\n".join(lines)
        text += "\n\n[dim]Add: ~/.ai-engine/personas/<id>.json[/]"
        self._show_empty_state(False)
        self._messages_container().mount(Static(text, classes="system-msg"))
        self._scroll_to_end()

    def action_edit_system_prompt(self) -> None:
        if self.is_processing:
            return
        chat = self.chats.get(self.current_chat_id)
        if not chat:
            return
        current = chat.get("system_prompt", "")

        def on_done(prompt: str | None) -> None:
            if prompt is None:
                return
            chat["system_prompt"] = prompt
            chat["persona_id"] = ""
            self._persist_session()
            self._update_header()
            if prompt:
                self.notify("System prompt saved", timeout=2)
            else:
                self.notify("System prompt cleared", timeout=2)

        self.push_screen(SystemPromptScreen(prompt=current), callback=on_done)

    def _export_chat(self, fmt: str = "markdown", path: str | None = None) -> str | None:
        chat = self.chats.get(self.current_chat_id)
        if not chat:
            return None
        if not chat.get("messages") and not (chat.get("system_prompt") or "").strip():
            self.notify("Nothing to export", severity="warning", timeout=2)
            return None
        base_dir = self._last_cwd if os.path.isdir(self._last_cwd) else os.getcwd()
        if path:
            target = os.path.expanduser(path)
        else:
            stem = _sanitize_export_filename(chat.get("title", f"chat-{self.current_chat_id}"))
            ext = "json" if fmt == "json" else "md"
            target = os.path.join(base_dir, f"{stem}-{self.current_chat_id}.{ext}")
        try:
            written = write_chat_export(
                chat,
                chat_id=self.current_chat_id,
                path=target,
                fmt=fmt,
                model=self.current_model,
                provider=self.current_provider,
            )
            return written
        except OSError as exc:
            self.notify(f"Export failed: {exc}"[:120], severity="error", timeout=4)
            return None

    def action_export_chat(self) -> None:
        if self.is_processing:
            return

        def on_format(fmt: str | None) -> None:
            if not fmt:
                return
            written = self._export_chat(fmt)
            if written:
                self.notify(f"Exported to {written}", timeout=4)

        self.push_screen(ExportChatScreen(), callback=on_format)

    def action_focus_chat_search(self) -> None:
        try:
            self.query_one("#chat-search", Input).focus()
        except NoMatches:
            pass

    def action_rename_chat(self) -> None:
        if self.is_processing:
            return
        chat = self.chats.get(self.current_chat_id)
        if not chat:
            return
        current_title = chat.get("title", f"Chat {self.current_chat_id}")

        def on_done(title: str | None) -> None:
            if not title:
                return
            chat["title"] = title[:64]
            self._refresh_sidebar()
            self._persist_session()
            self.notify("Chat renamed", timeout=2)

        self.push_screen(RenameChatScreen(title=current_title), callback=on_done)

    def action_delete_chat(self) -> None:
        if self.is_processing:
            return
        chat_id = self.current_chat_id
        chat = self.chats.get(chat_id)
        if not chat:
            return
        title = chat.get("title", f"Chat {chat_id}")[:32]

        def on_confirm(confirmed: bool | None) -> None:
            if confirmed:
                self._delete_chat(chat_id)

        self.push_screen(ConfirmDeleteScreen(title=title), callback=on_confirm)

    def _delete_chat(self, chat_id: int) -> None:
        if chat_id not in self.chats:
            return
        del self.chats[chat_id]
        if chat_id in self._chat_order:
            self._chat_order.remove(chat_id)
        if self.current_chat_id == chat_id:
            self._clear_attachment_preview()
            if self._chat_order:
                self._switch_to_chat(self._chat_order[0])
            else:
                self._new_chat()
                self._clear_messages()
                self._show_empty_state(True)
                self._refresh_sidebar()
                self._persist_session()
                self.query_one(ComposerInput).focus()
        else:
            self._refresh_sidebar()
            self._persist_session()
        self.notify("Chat deleted", timeout=2)

    def _chat_search_blob(self, chat: dict) -> str:
        parts = [chat.get("title", "")]
        for msg in chat.get("messages", []):
            parts.append(msg.get("content", ""))
        return " ".join(parts).lower()

    def _chat_matches_filter(self, chat: dict) -> bool:
        query = self._sidebar_filter.strip().lower()
        if not query:
            return True
        blob = self._chat_search_blob(chat)
        if query in blob:
            return True
        if rf_process is not None and fuzz is not None:
            score = fuzz.partial_ratio(query, blob)
            return score >= 60
        tokens = query.split()
        return all(tok in blob for tok in tokens)

    def _last_user_context(self) -> tuple[str, bool]:
        messages = self.chats.get(self._bound_chat_id(), {}).get("messages", [])
        for msg in reversed(messages):
            if msg.get("role") == "user":
                text = msg.get("content", "")
                has_images = bool(
                    msg.get("_image_path") and os.path.exists(msg["_image_path"])
                )
                return text, has_images
        return "", False

    def _resolve_routing_for_request(
        self, user_text: str, *, has_images: bool
    ) -> tuple[str, str | None, dict | None]:
        if not self._intent_routing_enabled or not user_text.strip():
            return self.current_model, self.current_provider, None
        try:
            from core.intent_classifier import intent_classifier
            intent_result = intent_classifier.classify(user_text, has_images=has_images)
        except Exception:
            return self.current_model, self.current_provider, None
        if intent_result.get("intent") == "text_chat":
            return self.current_model, self.current_provider, intent_result
        model, provider = _apply_intent_routing(
            intent_result,
            has_images=has_images,
            current_provider=self.current_provider,
            current_model=self.current_model,
        )
        return model, provider, intent_result

    def _notify_intent_routing(
        self,
        intent_result: dict,
        model: str,
        provider: str | None,
    ) -> None:
        intent = intent_result.get("intent", "text_chat")
        prov = provider or "auto"
        self.notify(
            f"Intent: {intent} → {model} ({prov})",
            timeout=3,
        )

    def action_pick_model(self) -> None:
        index = self._model_index
        if index is None:
            models = self._cached_models or _ensure_model_cache()
            if not models:
                self.notify("No models in cache yet — discovery running…", severity="warning", timeout=4)
                return
            index = ModelIndex.build(models)
            self._model_index = index

        def on_picked(result: tuple[str, str | None] | None) -> None:
            if not result:
                return
            api_model, provider = result
            self.current_model = api_model
            if provider:
                self.current_provider = provider
            self._update_header()
            self._persist_session()
            self.notify(f"Model: {api_model}", timeout=2)

        def on_toggle_favorite(model: str, provider: str | None) -> None:
            self._toggle_model_favorite(model, provider)

        self.push_screen(
            ModelPickerScreen(
                index,
                current=self.current_model,
                favorites=self._favorite_models,
                on_toggle_favorite=on_toggle_favorite,
            ),
            callback=on_picked,
        )

    def action_pick_provider(self) -> None:
        providers = _load_providers()
        current = self.current_provider or "auto"

        def on_picked(result: str | None) -> None:
            self.current_provider = result
            self._update_header()
            self._persist_session()
            label = result or "auto"
            self.notify(f"Provider: {label}", timeout=2)

        self.push_screen(ProviderPickerScreen(providers, current=current), callback=on_picked)

    def _apply_preference_defaults(self, *, notify: bool = False) -> None:
        """Restore model/provider from ~/.ai-engine/preferences.json."""
        prefs = self._preferences.load()
        self._prefs = prefs
        self.current_model = prefs.get("default_model", "default")
        self.current_provider = prefs.get("default_provider")
        self._update_header()
        self._persist_session()
        if notify:
            prov = self.current_provider or "auto"
            self.notify(f"Reset to defaults: {self.current_model} · {prov}", timeout=3)

    def action_apply_defaults(self) -> None:
        self._apply_preference_defaults(notify=True)

    def action_set_defaults(self) -> None:
        """Save current model/provider as session defaults."""
        self._preferences.save_defaults(
            model=self.current_model,
            provider=self.current_provider,
        )
        self._prefs = self._preferences.load()
        prov = self.current_provider or "auto"
        self._update_header()
        self.notify(f"Defaults set: {self.current_model} · {prov}", timeout=3)

    def action_toggle_sidebar(self) -> None:
        self.sidebar_collapsed = not self.sidebar_collapsed

    def watch_sidebar_collapsed(self, collapsed: bool) -> None:
        try:
            sidebar = self.query_one("#sidebar")
            btn = self.query_one("#sidebar-toggle-btn", Button)
            if collapsed:
                sidebar.add_class("-collapsed")
                btn.label = "»"
            else:
                sidebar.remove_class("-collapsed")
                btn.label = "«"
        except NoMatches:
            pass

    def _handle_defaults_command(self, text: str) -> None:
        wrap = self._messages_container()
        parts = text.strip().split()
        if len(parts) >= 2 and parts[1].lower() == "clear":
            self._apply_preference_defaults(notify=True)
            prov = self.current_provider or "auto"
            wrap.mount(
                Static(
                    f"Reset to defaults: [bold]{self.current_model}[/] · [bold]{prov}[/]",
                    classes="system-msg",
                )
            )
            self._scroll_to_end()
            return
        if text.strip().lower() != "/defaults":
            wrap.mount(
                Static(
                    "Use /defaults to save · /defaults clear to restore saved defaults",
                    classes="system-msg",
                )
            )
            self._scroll_to_end()
            return
        self.action_set_defaults()
        prov = self.current_provider or "auto"
        wrap.mount(
            Static(
                f"Defaults saved: [bold]{self.current_model}[/] · [bold]{prov}[/]\n"
                "[dim]/defaults clear restores these · shown in sidebar footer[/]",
                classes="system-msg",
            )
        )
        self._scroll_to_end()

    def _open_file_picker(self) -> None:
        start = self._last_cwd if os.path.isdir(self._last_cwd) else os.getcwd()

        def on_picker_done(result: PickerResult | None) -> None:
            if result and result.cwd:
                self._set_last_cwd(result.cwd)
            path = result.path if result else None
            if not path:
                return
            if os.path.exists(path):
                composer = self.query_one(ComposerInput)
                if _is_image_path(path):
                    self._attach_image(path)
                else:
                    self._inject_file_content(path, composer)
            else:
                self._messages_container().mount(
                    Static(f"File not found: {path}", classes="error-msg")
                )
                self._scroll_to_end()

        self.push_screen(FilePickerScreen(start_path=start), callback=on_picker_done)

    def _handle_command(self, text: str) -> None:
        cmd = text.strip().lower()
        wrap = self._messages_container()

        if cmd == "/clear":
            self.action_new_chat()
        elif cmd == "/help":
            help_text = (
                "[bold]Chat[/]\n"
                "/persona [id|list] · /system [text|clear] · /read [file] · /export [md|json]\n"
                "/rename · /delete · /clear · /quit\n"
                "@filename attach · type /read for file picker\n\n"
                "[bold]Model & defaults[/]\n"
                "/model · /provider · /models · /favorite · /intent [on|off]\n"
                "/defaults — save current model & provider\n"
                "/defaults clear — restore saved defaults (also on /clear new chat)\n"
                "/image <path> [prompt]\n\n"
                "[bold]Shortcuts[/]\n"
                "F2 model · F3 provider · F5 system · F6 intent · F8 export\n"
                "Ctrl+D delete · Ctrl+F favorite chat (★ in sidebar) · Ctrl+Shift+F search\n"
                "Model picker (F2): click ☆ on the right to save model to preferences\n"
                "/help /read /persona clear — type / for suggestions\n"
                "y / Ctrl+C copy (selection first) · r regenerate · e edit · Esc stop"
            )
            self._show_empty_state(False)
            wrap.mount(Static(help_text, classes="system-msg"))
            self._scroll_to_end()
        elif cmd.startswith("/image "):
            parts = text.split(" ", 2)
            path = parts[1].strip().strip("'\"") if len(parts) > 1 else ""
            prompt = parts[2].strip() if len(parts) > 2 else ""
            if path and os.path.exists(path):
                self._attach_image(path)
                if prompt:
                    self._send_message(prompt)
            else:
                wrap.mount(Static(f"Image not found: {path}", classes="error-msg"))
                self._scroll_to_end()
        elif cmd.startswith("/model "):
            self.current_model = text.split(" ", 1)[1].strip()
            self._update_header()
            wrap.mount(Static(f"Model set to {self.current_model}", classes="system-msg"))
            self._scroll_to_end()
        elif cmd.startswith("/provider "):
            new_prov = text.split(" ", 1)[1].strip()
            self.current_provider = new_prov if new_prov.lower() != "auto" else None
            self._update_header()
            wrap.mount(Static(f"Provider set to {new_prov}", classes="system-msg"))
            self._scroll_to_end()
        elif cmd == "/models":
            self.action_pick_model()
        elif cmd.startswith("/rename "):
            new_title = text.split(" ", 1)[1].strip()
            if new_title:
                self.chats[self.current_chat_id]["title"] = new_title[:64]
                self._refresh_sidebar()
                self._persist_session()
                wrap.mount(Static(f"Renamed to {new_title}", classes="system-msg"))
                self._scroll_to_end()
        elif cmd == "/delete":
            self.action_delete_chat()
        elif cmd.startswith("/intent"):
            parts = text.split()
            if len(parts) > 1:
                self._intent_routing_enabled = parts[1].lower() in {"on", "1", "true", "yes"}
            else:
                self._intent_routing_enabled = not self._intent_routing_enabled
            self._persist_session()
            self._update_header()
            state = "on" if self._intent_routing_enabled else "off"
            wrap.mount(Static(f"Intent routing {state}", classes="system-msg"))
            self._scroll_to_end()
        elif cmd == "/favorite":
            self.action_toggle_favorite()
        elif cmd.startswith("/system"):
            parts = text.split(" ", 1)
            if len(parts) == 1:
                self.action_edit_system_prompt()
            else:
                arg = parts[1].strip()
                if arg.lower() == "clear":
                    self.chats[self.current_chat_id]["system_prompt"] = ""
                    self.chats[self.current_chat_id]["persona_id"] = ""
                    self._remove_persona_banner()
                    self._persist_session()
                    self._update_header()
                    self._refresh_sidebar()
                    wrap.mount(Static("System prompt cleared", classes="system-msg"))
                else:
                    self.chats[self.current_chat_id]["system_prompt"] = arg
                    self._persist_session()
                    self._update_header()
                    wrap.mount(Static("System prompt saved", classes="system-msg"))
                self._scroll_to_end()
        elif cmd.startswith("/persona") or cmd == "/personas":
            parts = text.split()
            if len(parts) == 1 or (len(parts) > 1 and parts[1].lower() in {"list", "ls"}):
                self.action_list_personas()
            elif len(parts) > 1 and parts[1].lower() in {"clear", "off", "none"}:
                self._clear_persona()
            elif len(parts) > 1:
                self._apply_persona(parts[1])
        elif cmd == "/read" or cmd.startswith("/read "):
            if cmd == "/read":
                self._show_file_suggest("", mode="read")
                self.query_one(ComposerInput).focus()
                return
            path = text.split(" ", 1)[1].strip().strip("'\"")
            if os.path.isfile(path):
                composer = self.query_one(ComposerInput)
                composer.text = ""
                self._inject_file_content(path, composer)
                wrap.mount(Static(f"Loaded {path} into composer", classes="system-msg"))
                composer.focus()
            else:
                self._show_file_suggest(path, mode="read")
                self.query_one(ComposerInput).focus()
            self._scroll_to_end()
        elif cmd == "/defaults" or cmd.startswith("/defaults "):
            self._handle_defaults_command(text)
        elif cmd.startswith("/export"):
            parts = text.split()
            fmt = "markdown"
            path = None
            if len(parts) > 1:
                if parts[1].lower() in {"json", "md", "markdown"}:
                    fmt = "json" if parts[1].lower() == "json" else "markdown"
                    if len(parts) > 2:
                        path = " ".join(parts[2:])
                else:
                    path = " ".join(parts[1:])
            written = self._export_chat(fmt, path=path)
            if written:
                wrap.mount(Static(f"Exported to {written}", classes="system-msg"))
                self._scroll_to_end()
        elif cmd == "/quit":
            self.exit()
        else:
            wrap.mount(Static(f"Unknown command: {cmd}. Try /help", classes="system-msg"))
            self._scroll_to_end()

    def _send_message(self, text: str) -> None:
        image_path = self._pending_image
        self._clear_attachment_preview()

        chat = self.chats[self.current_chat_id]
        stored_path = None
        if image_path:
            stored_path = self._persist_attachment_path(image_path)
        user_msg = {"role": "user", "content": text}
        if stored_path:
            user_msg["_image_path"] = stored_path
        chat["messages"].append(user_msg)

        if len(chat["messages"]) == 1:
            chat["title"] = text[:32] + ("…" if len(text) > 32 else "")
            self._refresh_sidebar()

        self._touch_chat(self.current_chat_id)
        self._persist_session()

        self._show_empty_state(False)
        display = _user_message_display(text, stored_path)
        plain = text
        if stored_path:
            plain = f"{text}\n\n📎 {stored_path}" if text.strip() else f"📎 {stored_path}"
        self._mount_user_message(display, plain_text=plain)
        self._start_ai_generation()

    def _start_ai_generation(self) -> None:
        self.is_processing = True
        self._generation_chat_id = self.current_chat_id
        self._cancel_event.clear()
        self._stick_to_bottom = True
        self._show_typing(
            model=self.current_model if self.current_model not in ("default", "auto") else None,
            provider=self.current_provider,
        )
        self._scroll_to_end(force=True)
        self._perform_ai_call()

    def _stop_generation(self) -> None:
        if not self.is_processing:
            return
        self._cancel_event.set()

    def _build_api_messages(self) -> list[dict]:
        messages = []
        chat = self.chats[self._bound_chat_id()]
        system_prompt = (chat.get("system_prompt") or "").strip()
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        for m in chat["messages"]:
            if "_image_path" in m and os.path.exists(m["_image_path"]):
                path = m["_image_path"]
                size = os.path.getsize(path)
                if size > _MAX_IMAGE_BYTES:
                    raise ValueError(
                        f"Image too large ({size // (1024 * 1024)} MB). "
                        f"Max {_MAX_IMAGE_BYTES // (1024 * 1024)} MB."
                    )
                mime = mimetypes.guess_type(path)[0] or "image/png"
                with open(path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                content = [
                    {"type": "text", "text": m["content"]},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ]
                messages.append({"role": m["role"], "content": content})
            else:
                messages.append({"role": m["role"], "content": m["content"]})
        return messages

    def _prepare_response_widget(self) -> None:
        self._hide_typing()
        self._active_response = self._mount_assistant_message("")
        self._scroll_to_end()

    def _on_generation_stopped(self, partial_content: str = "") -> None:
        self._hide_typing()
        partial = (partial_content or "").strip()
        if not partial and self._active_response is not None:
            partial = (getattr(self._active_response, "_buffer", "") or "").strip()
        chat_id = self._bound_chat_id()
        if partial and chat_id in self.chats:
            self.chats[chat_id]["messages"].append({
                "role": "assistant",
                "content": f"{partial}\n\n*[stopped]*",
            })
            self._persist_session()
        if self._active_block is not None:
            try:
                self._active_block.remove()
            except Exception:
                pass
        self._active_block = None
        self._active_response = None
        self._generation_chat_id = None
        self._finish_processing()
        self.notify("Generation stopped", timeout=2)

    def _run_image_generation(
        self, prompt: str, model: str, provider: str | None
    ) -> None:
        try:
            ready = threading.Event()

            def _begin():
                if not self._cancel_event.is_set():
                    self._prepare_response_widget()
                    self._set_assistant_label(model, provider)
                ready.set()

            self.call_from_thread(_begin)
            ready.wait(timeout=2.0)
            if self._cancel_event.is_set():
                self.call_from_thread(self._on_generation_stopped)
                return

            _bind_model_cache_to_pkg_root()
            image_path, status, model_used, provider_used = generate_image(
                prompt,
                preferred_model=model,
                preferred_provider=provider,
            )
            if self._cancel_event.is_set():
                self.call_from_thread(self._on_generation_stopped)
                return

            provider_used = provider_used or provider or "openrouter"
            if not image_path:
                err = status or "Image generation failed."
                self.call_from_thread(self._display_generation_error, err)
                return

            content = f"{status}\nSaved to `{image_path}`"
            assistant_msg = {
                "role": "assistant",
                "content": content,
                "_image_path": image_path,
                "_model": model_used or model,
                "_provider": provider_used,
            }
            self.chats[self._bound_chat_id()]["messages"].append(assistant_msg)

            def _finish():
                if self._active_response is not None:
                    self._active_response.update_content(content)
                if self._active_block is not None:
                    self._active_block.mount(
                        TerminalImage(image_path, size="chat", classes="assistant-image")
                    )
                self._set_assistant_label(model_used or model, provider_used)
                self._on_response_done(model_used or model, provider_used)

            self.call_from_thread(_finish)
        except Exception as e:
            if self._cancel_event.is_set():
                self.call_from_thread(self._on_generation_stopped)
            else:
                self.call_from_thread(self._display_error, str(e)[:300])

    def _run_audio_generation(self, text: str) -> None:
        try:
            ready = threading.Event()

            def _begin():
                if not self._cancel_event.is_set():
                    self._prepare_response_widget()
                    self._set_assistant_label("tts-1", "edge-tts")
                ready.set()

            self.call_from_thread(_begin)
            ready.wait(timeout=2.0)
            if self._cancel_event.is_set():
                self.call_from_thread(self._on_generation_stopped)
                return

            try:
                import asyncio
                import edge_tts
            except ImportError:
                self.call_from_thread(
                    self._display_error,
                    "Audio generation requires: pip install edge-tts",
                )
                return

            out_path = str(_generated_media_dir() / f"speech-{int(time.time())}.mp3")

            async def _speak() -> None:
                communicate = edge_tts.Communicate(text, "en-US-AriaNeural")
                await communicate.save(out_path)

            asyncio.run(_speak())
            if self._cancel_event.is_set():
                self.call_from_thread(self._on_generation_stopped)
                return

            content = f"Speech audio saved to `{out_path}`"
            self.chats[self._bound_chat_id()]["messages"].append({
                "role": "assistant",
                "content": content,
                "_model": "tts-1",
                "_provider": "edge-tts",
            })

            def _finish():
                if self._active_response is not None:
                    self._active_response.update_content(content)
                self._set_assistant_label("tts-1", "edge-tts")
                self._on_response_done("tts-1", "edge-tts")

            self.call_from_thread(_finish)
        except Exception as e:
            if self._cancel_event.is_set():
                self.call_from_thread(self._on_generation_stopped)
            else:
                self.call_from_thread(self._display_error, str(e)[:300])

    @work(exclusive=True, thread=True)
    def _perform_ai_call(self) -> None:
        try:
            if self._cancel_event.is_set():
                self.call_from_thread(self._on_generation_stopped)
                return

            user_text, has_images = self._last_user_context()
            effective_model, effective_provider, intent_info = self._resolve_routing_for_request(
                user_text, has_images=has_images
            )
            intent = (intent_info or {}).get("intent", "text_chat")
            if intent_info and intent != "text_chat":
                self.call_from_thread(
                    self._notify_intent_routing,
                    intent_info,
                    effective_model,
                    effective_provider,
                )

            def _show_route_label():
                self._update_typing_label(effective_model, effective_provider)
                self._set_assistant_label(effective_model, effective_provider)

            if intent == "image_generation":
                self._run_image_generation(
                    user_text, effective_model, effective_provider
                )
                return
            if intent == "audio_generation":
                self._run_audio_generation(user_text)
                return

            messages = self._build_api_messages()
            ready = threading.Event()

            def _begin_response():
                if self._cancel_event.is_set():
                    ready.set()
                    return
                self._prepare_response_widget()
                ready.set()

            self.call_from_thread(_begin_response)
            ready.wait(timeout=2.0)
            self.call_from_thread(_show_route_label)

            if self._cancel_event.is_set():
                self.call_from_thread(self._on_generation_stopped)
                return

            from ai_engine import OpenAI
            client = OpenAI()

            stream = client.chat.completions.create(
                model=effective_model,
                messages=messages,
                provider=effective_provider,
                stream=True,
            )

            content = ""
            model_used = effective_model
            provider_used = effective_provider or "auto"
            response_msg = self._active_response

            for chunk in stream:
                if self._cancel_event.is_set():
                    break
                if not getattr(chunk, "choices", None):
                    continue
                delta = chunk.choices[0].delta
                piece = getattr(delta, "content", None) or ""
                if piece:
                    content += piece
                    if response_msg is not None:
                        self.call_from_thread(response_msg.append_chunk, piece)
                        self.call_from_thread(self._scroll_to_end)
                if hasattr(chunk, "model") and chunk.model:
                    model_used = chunk.model

            if self._cancel_event.is_set():
                self.call_from_thread(self._on_generation_stopped, content)
                return

            if not content:
                self.call_from_thread(
                    self._display_generation_error,
                    "Model returned an empty response.",
                )
                return

            self.chats[self._bound_chat_id()]["messages"].append({
                "role": "assistant",
                "content": content,
                "_model": model_used,
                "_provider": provider_used,
            })
            self.call_from_thread(self._set_assistant_label, model_used, provider_used)
            self.call_from_thread(self._on_response_done, model_used, provider_used)

        except Exception as e:
            if self._cancel_event.is_set():
                self.call_from_thread(self._on_generation_stopped)
            else:
                self.call_from_thread(self._display_error, str(e)[:300])

    def _on_response_done(self, model_used: str, provider_used: str) -> None:
        self._hide_typing()
        if self._active_block is not None and self._active_response is not None:
            self._active_block.plain_text = getattr(self._active_response, "_buffer", "") or ""
        self._set_assistant_label(model_used, provider_used)
        chat = self.chats.get(self._bound_chat_id(), {})
        messages = chat.get("messages", [])
        if messages and messages[-1].get("role") == "assistant":
            messages[-1]["_model"] = model_used
            messages[-1]["_provider"] = provider_used
        self._active_block = None
        self._active_response = None
        self._generation_chat_id = None
        self._update_header()
        self._persist_session()
        self._finish_processing()

    def _cleanup_active_response(self) -> None:
        if self._active_block is not None:
            try:
                self._active_block.remove()
            except Exception:
                pass
        self._active_block = None
        self._active_response = None

    def _display_generation_error(self, error_msg: str) -> None:
        self._hide_typing()
        self._cleanup_active_response()
        self._generation_chat_id = None
        self._show_empty_state(False)
        self._messages_container().mount(
            Static(f"[bold]Generation failed[/]\n{error_msg}", classes="error-msg")
        )
        self._scroll_to_end()
        self._finish_processing()

    def _display_error(self, error_msg: str) -> None:
        self._hide_typing()
        self._cleanup_active_response()
        self._generation_chat_id = None
        self._show_empty_state(False)
        self._messages_container().mount(Static(f"Error: {error_msg}", classes="error-msg"))
        self._scroll_to_end()
        self._persist_session()
        self._finish_processing()

    def _finish_processing(self) -> None:
        self.is_processing = False
        try:
            self.query_one(ComposerInput).focus()
        except NoMatches:
            pass

    def _clear_messages(self) -> None:
        wrap = self._messages_container()
        for child in list(wrap.children):
            child.remove()
        self._persona_banner = None

    def action_new_chat(self) -> None:
        self._clear_attachment_preview()
        self._new_chat()
        self._clear_messages()
        self._apply_preference_defaults(notify=False)
        self._show_empty_state(True)
        self._refresh_sidebar()
        self._persist_session()
        self.query_one(ComposerInput).focus()

    def _switch_to_chat(self, chat_id: int) -> None:
        if chat_id not in self.chats:
            return
        if self.is_processing:
            self.notify(
                "Stop generation first (■ or Esc)",
                severity="warning",
                timeout=3,
            )
            return
        self.current_chat_id = chat_id
        self._load_current_chat_messages()
        self._refresh_sidebar()
        self._persist_session()
        self.query_one(ComposerInput).focus()

    def _replay_messages(self, wrap: Container, chat: dict) -> None:
        for m in chat["messages"]:
            if m["role"] == "user":
                img = m.get("_image_path")
                content = _user_message_display(m.get("content") or "", img)
                plain = m.get("content") or ""
                if img:
                    plain = (
                        f"{plain}\n\n📎 {img}" if plain.strip() else f"📎 {img}"
                    )
                block = MessageBlock(
                    role="user",
                    plain_text=plain,
                    classes="message-block user-block",
                )
                wrap.mount(block)
                if content.strip():
                    block.mount(UserMessage(content, classes="user-bubble"))
            else:
                plain = m.get("content", "")
                block = MessageBlock(
                    role="assistant",
                    plain_text=plain,
                    classes="message-block assistant-block",
                )
                wrap.mount(block)
                if m.get("_model"):
                    label = self._format_response_label(
                        m["_model"],
                        m.get("_provider"),
                    )
                else:
                    label = "[dim]assistant · unknown[/]"
                block.mount(Static(label, classes="assistant-label"))
                block.mount(ChatMarkdown(plain, classes="assistant-bubble"))
                img = m.get("_image_path")
                if img and os.path.exists(img):
                    block.mount(TerminalImage(img, size="chat", classes="assistant-image"))
        self._scroll_to_end()

    def _load_current_chat_messages(self) -> None:
        wrap = self._messages_container()
        self._clear_messages()
        chat = self.chats.get(self.current_chat_id, {})
        if chat.get("messages"):
            self._show_empty_state(False)
            self._replay_messages(wrap, chat)
        else:
            self._show_empty_state(True)
        self._show_persona_banner_for_chat(chat)

    def _sidebar_chat_ids(self) -> list[int]:
        order = self._chat_order or list(self.chats.keys())
        visible = [
            cid
            for cid in order
            if cid in self.chats and self._chat_matches_filter(self.chats[cid])
        ]
        favorites = [cid for cid in visible if self.chats[cid].get("favorite")]
        rest = [cid for cid in visible if not self.chats[cid].get("favorite")]
        return favorites + rest

    def _default_labels(self) -> tuple[str, str]:
        prefs = self._prefs or self._preferences.load()
        def_model = str(prefs.get("default_model", "default") or "default")
        def_prov = prefs.get("default_provider") or "auto"
        if len(def_model) > 36:
            def_model = "…" + def_model[-33:]
        return def_model, str(def_prov)

    def _update_header(self) -> None:
        prov = self.current_provider or "auto"
        model_label = self.current_model
        if len(model_label) > 48:
            model_label = "…" + model_label[-45:]
        def_model, def_prov = self._default_labels()
        chat = self.chats.get(self.current_chat_id, {})
        chat_fav = "★ " if chat.get("favorite") else ""
        intent = " · intent" if self._intent_routing_enabled else ""
        system = " · sys" if (chat.get("system_prompt") or "").strip() else ""
        persona = ""
        if chat.get("persona_id"):
            p = find_persona(self._personas, chat["persona_id"])
            if p:
                persona = f" · {p.emoji}{p.label}"
        active_is_default = (
            self.current_model == (self._prefs or {}).get("default_model", "default")
            and (self.current_provider or None)
            == (self._prefs or {}).get("default_provider")
        )
        default_marker = " ★" if active_is_default else ""
        try:
            self.query_one("#chat-header", Static).update(
                f"{chat_fav}{model_label}  ·  {prov}{default_marker}{intent}{system}{persona}"
            )
            self.query_one("#sidebar-footer", Static).update(
                f"[dim]now {model_label} · {prov}[/]\n"
                f"[dim]defaults {def_model} · {def_prov}[/]"
            )
        except NoMatches:
            pass

    def _refresh_sidebar(self) -> None:
        try:
            chat_list = self.query_one("#chat-list", ListView)
            chat_list.clear()
            shown = 0
            for cid in self._sidebar_chat_ids():
                chat = self.chats[cid]
                title = chat.get("title", f"Chat {cid}")[:22]
                if (chat.get("system_prompt") or "").strip():
                    title = f"⚙ {title}"
                star = "★ " if chat.get("favorite") else ""
                marker = "● " if cid == self.current_chat_id else "  "
                label = Label(
                    f"{marker}{star}{title}",
                    classes="chat-favorite" if chat.get("favorite") else "",
                )
                item = ListItem(label)
                item.chat_id = cid
                chat_list.append(item)
                shown += 1
            if self._sidebar_filter.strip() and shown == 0:
                item = ListItem(Label("[dim]No matching chats[/]"))
                chat_list.append(item)
        except NoMatches:
            pass

    def watch_is_processing(self, processing: bool) -> None:
        try:
            btn = self.query_one("#send-btn", Button)
            btn.label = "■" if processing else "⏎"
        except Exception:
            pass


def run_tui(model="default", provider=None):
    """Entry point."""
    try:
        from core.env_bootstrap import bootstrap_user_environment

        bootstrap_user_environment()
        _bind_model_cache_to_pkg_root()
        if pkg_root not in sys.path:
            sys.path.insert(0, pkg_root)
        if not os.environ.get("CDN_CONFIG_URL"):
            os.environ["CDN_CONFIG_URL"] = "default"
        from core.config_sync import config_fetcher
        config_fetcher.initialize()
    except Exception:
        pass

    app = ChatTUI(model=model, provider=provider)
    app.run()


if __name__ == "__main__":
    run_tui()