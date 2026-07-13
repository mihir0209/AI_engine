"""Modal screens for the AI Synapse TUI."""
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path

from textual import events, on
from textual.command import DiscoveryHit, Hit, Provider
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Button, DirectoryTree, Input, Label, ListItem, ListView, Static, TextArea

from .model_index import (
    MODEL_PAGE_SIZE,
    ModelEntry,
    ModelIndex,
    favorite_key,
    parse_favorite_key,
)
from .storage import _normalize_cwd
from .widgets import PickerResult

class FilePickerScreen(ModalScreen[PickerResult | None]):
    """File picker starting at pwd; navigate anywhere via tree or path bar."""

    DEFAULT_CSS = """
    FilePickerScreen {
        align: center middle;
    }
    #picker-panel {
        width: 92%;
        height: 82%;
        max-width: 110;
        min-width: 70;
        background: $surface;
        border: round $surface-lighten-1;
        padding: 1 2;
    }
    #picker-title {
        text-style: bold;
        padding-bottom: 1;
    }
    #path-input {
        margin-bottom: 1;
    }
    #dir-tree {
        height: 1fr;
        border: round $surface-lighten-1;
    }
    #picker-actions {
        height: 3;
        margin-top: 1;
    }
    .picker-help {
        color: $text-muted;
        padding-top: 1;
        text-align: center;
    }
    """

    def __init__(self, start_path: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.start_path = os.path.abspath(start_path or os.getcwd())

    def compose(self) -> ComposeResult:
        with Vertical(id="picker-panel"):
            yield Static("Pick a file to attach", id="picker-title")
            yield Input(self.start_path, id="path-input", placeholder="Type a path and press Enter")
            yield DirectoryTree(self.start_path, id="dir-tree")
            with Horizontal(id="picker-actions"):
                yield Button("Home", id="btn-home", variant="default")
                yield Button("Root /", id="btn-root", variant="default")
                yield Button("Here", id="btn-here", variant="default")
            yield Static(
                "[dim]↑↓ navigate · Enter select file · Esc cancel · Paste path in bar[/]",
                classes="picker-help",
            )

    def on_mount(self) -> None:
        self.query_one("#dir-tree", DirectoryTree).focus()

    def _finish(self, path: str | None = None) -> None:
        raw = (self.query_one("#path-input", Input).value or "").strip()
        cwd = _normalize_cwd(raw or self.start_path)
        self.dismiss(PickerResult(path=path, cwd=cwd))

    def _reload_tree(self, path: str) -> None:
        path = os.path.abspath(os.path.expanduser(path))
        if not os.path.isdir(path):
            return
        tree = self.query_one("#dir-tree", DirectoryTree)
        tree.path = path
        tree.reload()
        self.query_one("#path-input", Input).value = path

    @on(Input.Submitted, "#path-input")
    def on_path_submitted(self, event: Input.Submitted) -> None:
        self._reload_tree(event.value)

    @on(Button.Pressed, "#btn-home")
    def go_home(self) -> None:
        self._reload_tree(str(Path.home()))

    @on(Button.Pressed, "#btn-root")
    def go_root(self) -> None:
        self._reload_tree("/")

    @on(Button.Pressed, "#btn-here")
    def go_pwd(self) -> None:
        self._reload_tree(os.getcwd())

    @on(DirectoryTree.DirectorySelected)
    def on_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        self.query_one("#path-input", Input).value = str(event.path)

    @on(DirectoryTree.FileSelected)
    def select_file(self, event: DirectoryTree.FileSelected) -> None:
        self._finish(str(event.path))

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self._finish(None)


class RenameChatScreen(ModalScreen[str | None]):
    """Rename the active chat."""

    DEFAULT_CSS = """
    RenameChatScreen {
        align: center middle;
    }
    #rename-panel {
        width: 70%;
        max-width: 70;
        min-width: 40;
        background: $surface;
        border: round $surface-lighten-1;
        padding: 1 2;
    }
    #rename-title {
        text-style: bold;
        padding-bottom: 1;
    }
    #rename-input {
        margin-bottom: 1;
    }
    #rename-actions {
        height: 3;
        align: right middle;
    }
    .picker-help {
        color: $text-muted;
        padding-top: 1;
        text-align: center;
    }
    """

    def __init__(self, title: str = "", **kwargs):
        super().__init__(**kwargs)
        self._title = title

    def compose(self) -> ComposeResult:
        with Vertical(id="rename-panel"):
            yield Static("Rename chat", id="rename-title")
            yield Input(value=self._title, placeholder="Chat title…", id="rename-input")
            with Horizontal(id="rename-actions"):
                yield Button("Cancel", id="rename-cancel")
                yield Button("Save", id="rename-save", variant="primary")
            yield Static("[dim]Enter save · Esc cancel[/]", classes="picker-help")

    def on_mount(self) -> None:
        inp = self.query_one("#rename-input", Input)
        inp.focus()
        inp.cursor_position = len(inp.value or "")

    @on(Input.Submitted, "#rename-input")
    def on_rename_submitted(self, event: Input.Submitted) -> None:
        title = (event.value or "").strip()
        self.dismiss(title or None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "rename-save":
            title = (self.query_one("#rename-input", Input).value or "").strip()
            self.dismiss(title or None)
        elif event.button.id == "rename-cancel":
            self.dismiss(None)

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.dismiss(None)


class SystemPromptScreen(ModalScreen[str | None]):
    """Edit the per-chat system prompt."""

    DEFAULT_CSS = """
    SystemPromptScreen {
        align: center middle;
    }
    #system-panel {
        width: 92%;
        height: 80%;
        max-width: 110;
        min-width: 70;
        background: $surface;
        border: round $surface-lighten-1;
        padding: 1 2;
    }
    #system-title {
        text-style: bold;
        padding-bottom: 1;
    }
    #system-prompt-input {
        height: 1fr;
        min-height: 10;
        border: round $surface-lighten-1;
        margin-bottom: 1;
    }
    #system-actions {
        height: 3;
        align: right middle;
    }
    .picker-help {
        color: $text-muted;
        padding-top: 1;
        text-align: center;
    }
    """

    def __init__(self, prompt: str = "", **kwargs):
        super().__init__(**kwargs)
        self._prompt = prompt

    def compose(self) -> ComposeResult:
        with Vertical(id="system-panel"):
            yield Static("System prompt", id="system-title")
            yield TextArea(
                self._prompt,
                id="system-prompt-input",
                show_line_numbers=False,
                soft_wrap=True,
            )
            with Horizontal(id="system-actions"):
                yield Button("Clear", id="system-clear", variant="warning")
                yield Button("Cancel", id="system-cancel")
                yield Button("Save", id="system-save", variant="primary")
            yield Static(
                "[dim]Applies to this chat only · Esc cancel[/]",
                classes="picker-help",
            )

    def on_mount(self) -> None:
        self.query_one("#system-prompt-input", TextArea).focus()

    def _current_text(self) -> str:
        return (self.query_one("#system-prompt-input", TextArea).text or "").strip()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "system-save":
            self.dismiss(self._current_text())
        elif event.button.id == "system-clear":
            self.dismiss("")
        elif event.button.id == "system-cancel":
            self.dismiss(None)

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.dismiss(None)


class ExportChatScreen(ModalScreen[str | None]):
    """Choose export format for the active chat."""

    DEFAULT_CSS = """
    ExportChatScreen {
        align: center middle;
    }
    #export-panel {
        width: 60%;
        max-width: 60;
        min-width: 40;
        background: $surface;
        border: round $surface-lighten-1;
        padding: 1 2;
    }
    #export-title {
        text-style: bold;
        padding-bottom: 1;
    }
    #export-actions {
        height: 3;
        align: center middle;
    }
    .picker-help {
        color: $text-muted;
        padding-top: 1;
        text-align: center;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="export-panel"):
            yield Static("Export chat", id="export-title")
            with Horizontal(id="export-actions"):
                yield Button("Markdown", id="export-md", variant="primary")
                yield Button("JSON", id="export-json", variant="default")
                yield Button("Cancel", id="export-cancel")
            yield Static("[dim]Saved to last browsed folder · Esc cancel[/]", classes="picker-help")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "export-md":
            self.dismiss("markdown")
        elif event.button.id == "export-json":
            self.dismiss("json")
        elif event.button.id == "export-cancel":
            self.dismiss(None)

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.dismiss(None)


class ConfirmDeleteScreen(ModalScreen[bool]):
    """Confirm chat deletion."""

    DEFAULT_CSS = """
    ConfirmDeleteScreen {
        align: center middle;
    }
    #confirm-panel {
        width: 70%;
        max-width: 70;
        min-width: 40;
        background: $surface;
        border: round $error 40%;
        padding: 1 2;
    }
    #confirm-title {
        text-style: bold;
        color: $error;
        padding-bottom: 1;
    }
    #confirm-message {
        padding-bottom: 1;
    }
    #confirm-actions {
        height: 3;
        align: right middle;
    }
    """

    def __init__(self, title: str, **kwargs):
        super().__init__(**kwargs)
        self._title = title

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-panel"):
            yield Static("Delete chat?", id="confirm-title")
            yield Static(f'Delete "{self._title}"? This cannot be undone.', id="confirm-message")
            with Horizontal(id="confirm-actions"):
                yield Button("Cancel", id="confirm-cancel")
                yield Button("Delete", id="confirm-delete", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-delete":
            self.dismiss(True)
        elif event.button.id == "confirm-cancel":
            self.dismiss(False)

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.dismiss(False)


class ModelPickerRow(ListItem):
    """One model row with a clickable star on the right."""

    DEFAULT_CSS = """
    ModelPickerRow {
        height: 3;
        padding: 0 1;
    }
    ModelPickerRow .model-row-label {
        width: 1fr;
        height: 100%;
        content-align: left middle;
    }
    ModelPickerRow .model-star-btn {
        width: 4;
        min-width: 4;
        height: 100%;
        background: transparent;
        border: none;
        color: $text-muted;
        content-align: center middle;
    }
    ModelPickerRow .model-star-btn.-favorite {
        color: #D4AF37;
        text-style: bold;
    }
    ModelPickerRow .model-star-btn:hover {
        background: $surface-lighten-1;
    }
    """

    def __init__(
        self,
        *,
        api_model: str,
        provider: str | None,
        label: str,
        is_favorite: bool,
        is_current: bool,
        on_toggle_favorite,
    ) -> None:
        super().__init__()
        self.api_model = api_model
        self.provider = provider
        self._display_label = label
        self._is_favorite = is_favorite
        self._is_current = is_current
        self._on_toggle_favorite = on_toggle_favorite

    def _marker_label(self) -> str:
        marker = "★ " if self._is_favorite else ("● " if self._is_current else "  ")
        return f"{marker}{self._display_label}"

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Label(self._marker_label(), classes="model-row-label")
            yield Button(
                "★" if self._is_favorite else "☆",
                id="model-star-btn",
                classes="model-star-btn -favorite" if self._is_favorite else "model-star-btn",
            )

    def set_favorite(self, is_favorite: bool) -> None:
        self._is_favorite = is_favorite
        try:
            self.query_one(".model-row-label", Label).update(self._marker_label())
            btn = self.query_one("#model-star-btn", Button)
            btn.label = "★" if is_favorite else "☆"
            btn.set_class(is_favorite, "-favorite")
        except NoMatches:
            pass

    @on(Button.Pressed, "#model-star-btn")
    def on_star_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if self._on_toggle_favorite:
            self._on_toggle_favorite(self.api_model, self.provider)


class ModelPickerScreen(ModalScreen[tuple[str, str | None] | None]):
    """Searchable model picker backed by model_cache.json."""

    DEFAULT_CSS = """
    ModelPickerScreen {
        align: center middle;
    }
    #model-panel {
        width: 92%;
        height: 85%;
        max-width: 120;
        min-width: 80;
        background: $surface;
        border: round $surface-lighten-1;
        padding: 1 2;
    }
    #model-search {
        margin-bottom: 1;
    }
    #model-list {
        height: 1fr;
        border: round $surface-lighten-1;
    }
    .picker-help {
        color: $text-muted;
        padding-top: 1;
        text-align: center;
    }
    """

    def __init__(
        self,
        index: ModelIndex,
        current: str = "",
        favorites: list[str] | None = None,
        on_toggle_favorite=None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._index = index
        self._current = current
        self._favorites = set(favorites or [])
        self._on_toggle_favorite = on_toggle_favorite
        self._pending_query = ""
        self._all_matches: list[ModelEntry] = []
        self._loaded_count = 0
        self._loading_more = False
        self._active_query: str | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="model-panel"):
            yield Static("Select model", id="picker-title")
            yield Input(placeholder="Search models…", id="model-search")
            yield ListView(id="model-list")
            yield Static("", id="picker-help", classes="picker-help")

    def on_mount(self) -> None:
        self._refresh_list(reset=True)
        self._update_picker_help()
        self.query_one("#model-search", Input).focus()

    def _entries_for_query(self, query: str) -> list[ModelEntry]:
        q = query.strip()
        if not q and self._favorites:
            fav_entries: list[ModelEntry] = []
            seen: set[str] = set()
            for key in self._favorites:
                model, provider = parse_favorite_key(key)
                for entry in self._index.entries:
                    entry_key = favorite_key(entry.api_model, entry.provider)
                    if entry.api_model == model and entry.provider == provider:
                        fav_entries.append(entry)
                        seen.add(entry_key)
                        break
            rest = [
                entry for entry in self._index.entries
                if favorite_key(entry.api_model, entry.provider) not in seen
            ]
            return fav_entries + rest
        return self._index.search(query, limit=None)

    def _update_picker_help(self) -> None:
        total = len(self._all_matches)
        shown = self._loaded_count
        cache_total = len(self._index.entries)
        parts = [f"{shown}/{total} shown"]
        if shown < total:
            parts.append("↓ in list or scroll for more")
        parts.append(f"{cache_total} cached")
        parts.append("☆/★ saves to preferences")
        parts.append("Esc cancel")
        try:
            self.query_one("#picker-help", Static).update(
                "[dim]" + " · ".join(parts) + "[/]"
            )
        except NoMatches:
            pass

    def _append_page(self) -> None:
        if self._loading_more or self._loaded_count >= len(self._all_matches):
            return
        self._loading_more = True
        try:
            lst = self.query_one("#model-list", ListView)
            start = self._loaded_count
            end = min(start + MODEL_PAGE_SIZE, len(self._all_matches))
            for entry in self._all_matches[start:end]:
                entry_key = favorite_key(entry.api_model, entry.provider)
                lst.append(
                    ModelPickerRow(
                        api_model=entry.api_model,
                        provider=entry.provider,
                        label=entry.label,
                        is_favorite=entry_key in self._favorites,
                        is_current=entry.api_model == self._current,
                        on_toggle_favorite=self._toggle_row_favorite,
                    )
                )
            self._loaded_count = end
            self._update_picker_help()
            self.call_after_refresh(self._fill_viewport)
        finally:
            self._loading_more = False

    def _fill_viewport(self) -> None:
        """Keep loading pages until the list scrolls or all matches are shown."""
        if self._loaded_count >= len(self._all_matches):
            return
        try:
            lst = self.query_one("#model-list", ListView)
        except NoMatches:
            return
        if lst.max_scroll_y <= 0:
            self._append_page()

    def _maybe_load_more(self, index: int | None) -> None:
        if index is None or self._loaded_count >= len(self._all_matches):
            return
        if index >= max(0, self._loaded_count - 8):
            self._append_page()

    def _refresh_list(self, *, reset: bool) -> None:
        query = self._pending_query
        if reset or query != self._active_query:
            self._active_query = query
            self._all_matches = self._entries_for_query(query)
            self._loaded_count = 0
            self.query_one("#model-list", ListView).clear()
        self._append_page()

    def _toggle_row_favorite(self, model: str, provider: str | None) -> None:
        if self._on_toggle_favorite:
            self._on_toggle_favorite(model, provider)
        key = favorite_key(model, provider)
        if key in self._favorites:
            self._favorites.discard(key)
        else:
            self._favorites.add(key)
        try:
            lst = self.query_one("#model-list", ListView)
            for child in lst.children:
                if (
                    isinstance(child, ModelPickerRow)
                    and child.api_model == model
                    and child.provider == provider
                ):
                    child.set_favorite(key in self._favorites)
                    break
        except NoMatches:
            pass

    def _run_search(self) -> None:
        self._refresh_list(reset=True)

    @on(Input.Changed, "#model-search")
    def on_search_changed(self, event: Input.Changed) -> None:
        self._pending_query = event.value
        self.set_timer(0.05, self._run_search, name="model-search-debounce")

    @on(ListView.Highlighted, "#model-list")
    def on_model_highlighted(self, event: ListView.Highlighted) -> None:
        self._maybe_load_more(event.list_view.index)

    @on(events.MouseScrollDown, "#model-list")
    def on_model_list_scroll_down(self, event: events.MouseScrollDown) -> None:
        lst = self.query_one("#model-list", ListView)
        if lst.max_scroll_y <= 0 or lst.scroll_offset.y >= max(0, lst.max_scroll_y - 24):
            self._append_page()

    @on(ListView.Selected, "#model-list")
    def on_model_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if hasattr(item, "api_model"):
            self.dismiss((item.api_model, item.provider))

    async def on_event(self, event: events.Event) -> None:
        try:
            await super().on_event(event)
        except AttributeError as exc:
            if "region" in str(exc) and isinstance(
                event, (events.MouseDown, events.MouseUp, events.Click)
            ):
                return
            raise

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.dismiss(None)
            return
        if event.key not in {"down", "j"}:
            return
        inp = self.query_one("#model-search", Input)
        lst = self.query_one("#model-list", ListView)
        if inp.has_focus:
            lst.focus()
            if lst.index is None and lst.children:
                lst.index = 0
            event.stop()
            return
        if not lst.has_focus or lst.index is None:
            return
        at_end = lst.index >= len(lst.children) - 1
        if at_end and self._loaded_count < len(self._all_matches):
            prev_len = len(lst.children)
            self._append_page()

            def advance() -> None:
                if len(lst.children) > prev_len:
                    lst.index = prev_len

            self.call_after_refresh(advance)
            event.stop()


class ProviderPickerScreen(ModalScreen[str | None]):
    """Provider picker from enabled AI_CONFIGS providers."""

    DEFAULT_CSS = """
    ProviderPickerScreen {
        align: center middle;
    }
    #provider-panel {
        width: 70%;
        height: 75%;
        max-width: 80;
        min-width: 50;
        background: $surface;
        border: round $surface-lighten-1;
        padding: 1 2;
    }
    #provider-list {
        height: 1fr;
        border: round $surface-lighten-1;
    }
    .picker-help {
        color: $text-muted;
        padding-top: 1;
        text-align: center;
    }
    """

    def __init__(self, providers: list[str], current: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self._providers = ["auto", *providers]
        self._current = current or "auto"

    def compose(self) -> ComposeResult:
        with Vertical(id="provider-panel"):
            yield Static("Select provider", id="picker-title")
            yield ListView(id="provider-list")
            yield Static("[dim]Esc cancel[/]", classes="picker-help")

    def on_mount(self) -> None:
        lst = self.query_one("#provider-list", ListView)
        for prov in self._providers:
            marker = "● " if prov == self._current else "  "
            item = ListItem(Label(f"{marker}{prov}"))
            item.provider_name = prov
            lst.append(item)

    @on(ListView.Selected, "#provider-list")
    def on_provider_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if hasattr(item, "provider_name"):
            prov = item.provider_name
            self.dismiss(None if prov == "auto" else prov)

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.dismiss(None)


class ChatCommandProvider(Provider):
    """Command palette entries."""

    _COMMANDS = (
        ("New Chat", "Start a fresh conversation", "new_chat"),
        ("Rename Chat", "Rename the active conversation", "rename_chat"),
        ("Delete Chat", "Delete the active conversation", "delete_chat"),
        ("Search Chats", "Focus sidebar chat search", "focus_chat_search"),
        ("Pick Model", "Choose from cached models", "pick_model"),
        ("Favorite Chat", "Star/unstar the active chat", "toggle_favorite"),
        ("Pick Provider", "Choose inference provider", "pick_provider"),
        ("Toggle Intent Routing", "Auto-route by prompt intent", "toggle_intent_routing"),
        ("List Personas", "Show available agent personas", "list_personas"),
        ("System Prompt", "Edit per-chat system instructions", "edit_system_prompt"),
        ("Export Chat", "Save chat as Markdown or JSON", "export_chat"),
        ("Send Message", "Send the current prompt", "send_message"),
        ("Stop Generation", "Cancel the current reply", "stop_generation"),
        ("Regenerate", "Redo the last assistant reply", "regenerate"),
        ("Copy Message", "Copy focused or last message", "copy_message"),
        ("Edit & Resend", "Edit last user message", "edit_resend"),
        ("Attach File", "Attach an image above the composer", "attach_file"),
        ("Set Defaults", "Save current model & provider as defaults", "set_defaults"),
        ("Reset to Defaults", "Restore model & provider from preferences", "apply_defaults"),
        ("Toggle Sidebar", "Collapse or expand the chat sidebar", "toggle_sidebar"),
        ("Quit", "Exit AI Synapse", "quit"),
    )

    def _make_runner(self, action: str):
        if action == "attach_file":
            return lambda: self.app._open_file_picker()
        return lambda: getattr(self.app, f"action_{action}")()

    async def discover(self) -> AsyncIterator[DiscoveryHit]:
        for title, help_text, action in self._COMMANDS:
            yield DiscoveryHit(title, self._make_runner(action), help=help_text, text=title)

    async def search(self, query: str) -> AsyncIterator[Hit]:
        q = query.lower().strip()
        for title, help_text, action in self._COMMANDS:
            hay = f"{title} {help_text}".lower()
            if not q or q in hay:
                score = 1.0 if q and q in title.lower() else 0.8
                yield Hit(score, title, self._make_runner(action), help=help_text, text=title)

