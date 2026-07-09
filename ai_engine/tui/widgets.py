"""Textual widget components for the AI Synapse TUI."""
from __future__ import annotations

import os

from markdown_it import MarkdownIt
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Button, Label, ListView, LoadingIndicator, Markdown, Static, TextArea,
)

from .common import (
    _chafa_fallback,
    _chat_markdown_parser,
    _image_size_key,
    _pixels_from_path,
)
from .personas import Persona

class ComposerInput(TextArea):
    """Chat input with shortcuts that work while the textarea is focused."""

    BINDINGS = [
        Binding("ctrl+j", "submit_message", "Send", priority=True, show=True),
        Binding("alt+enter", "submit_message", "Send", priority=True, show=True),
        Binding("ctrl+enter", "submit_message", "Send", priority=True, show=True),
        Binding("ctrl+n", "new_chat", "New Chat", priority=True),
        Binding("f2", "pick_model", "Model", priority=True, show=True),
        Binding("f3", "pick_provider", "Provider", priority=True, show=True),
        Binding("f4", "rename_chat", "Rename", priority=True),
        Binding("f5", "edit_system_prompt", "System", priority=True, show=True),
        Binding("f6", "toggle_intent", "Intent", priority=True, show=True),
        Binding("f8", "export_chat", "Export", priority=True, show=True),
        Binding("ctrl+f", "toggle_favorite", "Favorite", priority=True, show=True),
        Binding("ctrl+q", "quit_app", "Quit", priority=True),
        Binding("ctrl+c", "copy_selection", "Copy", priority=True),
    ]

    def action_copy_selection(self) -> None:
        selected = (self.selected_text or "").strip()
        if selected:
            self.app._copy_to_clipboard(selected)
            return
        self.app.action_copy_message()

    def action_submit_message(self) -> None:
        self.app.action_send_message()

    def action_new_chat(self) -> None:
        self.app.action_new_chat()

    def action_pick_model(self) -> None:
        self.app.action_pick_model()

    def action_pick_provider(self) -> None:
        self.app.action_pick_provider()

    def action_rename_chat(self) -> None:
        self.app.action_rename_chat()

    def action_edit_system_prompt(self) -> None:
        self.app.action_edit_system_prompt()

    def action_toggle_intent(self) -> None:
        self.app.action_toggle_intent_routing()

    def action_export_chat(self) -> None:
        self.app.action_export_chat()

    def action_toggle_favorite(self) -> None:
        self.app.action_toggle_favorite()

    def action_quit_app(self) -> None:
        self.app.exit()


class UserMessage(Static):
    """User message bubble."""

    def __init__(self, text: str, **kwargs):
        super().__init__(**kwargs)
        self._text = text

    def render(self):
        return self._text


class ChatMarkdown(Markdown):
    """Chat-optimized markdown with streaming and styled blocks."""

    DEFAULT_CSS = """
    ChatMarkdown {
        height: auto;
        padding: 0;
        margin: 0;
        background: transparent;
        border: none;
    }

    ChatMarkdown MarkdownH1 {
        text-style: bold;
        color: $text;
        margin: 1 0 0 0;
        padding: 0;
    }

    ChatMarkdown MarkdownH2, ChatMarkdown MarkdownH3 {
        text-style: bold;
        color: $text;
        margin: 1 0 0 0;
        padding: 0;
    }

    ChatMarkdown MarkdownH4, ChatMarkdown MarkdownH5, ChatMarkdown MarkdownH6 {
        text-style: bold;
        color: $text-muted;
        margin: 1 0 0 0;
        padding: 0;
    }

    ChatMarkdown MarkdownParagraph {
        margin: 0 0 1 0;
        padding: 0;
    }

    ChatMarkdown MarkdownFence {
        border: round $surface-lighten-1;
        background: $surface-darken-1;
        margin: 1 0;
        padding: 0;
    }

    ChatMarkdown MarkdownFence > Label {
        padding: 1;
    }

    ChatMarkdown MarkdownBlockQuote {
        border-left: thick $primary 60%;
        background: $surface-darken-1;
        padding: 0 1;
        margin: 1 0;
        color: $text-muted;
    }

    ChatMarkdown MarkdownBulletList, ChatMarkdown MarkdownOrderedList {
        margin: 0 0 1 0;
        padding: 0 0 0 1;
    }

    ChatMarkdown MarkdownTable {
        margin: 1 0;
        border: round $surface-lighten-1;
    }

    ChatMarkdown MarkdownHorizontalRule {
        color: $surface-lighten-1;
        margin: 1 0;
    }

    ChatMarkdown .code_inline {
        background: $surface;
        color: $accent;
        padding: 0 1;
    }
    """

    def __init__(self, content: str = "", **kwargs):
        super().__init__(
            content or "",
            parser_factory=_chat_markdown_parser,
            open_links=False,
            **kwargs,
        )
        self._buffer = content or ""
        self._markdown_stream = None
        self._stream_active = False

    def _ensure_stream(self) -> None:
        if self._markdown_stream is None:
            self._markdown_stream = Markdown.get_stream(self)
            self._markdown_stream.start()
            self._stream_active = True

    def append_chunk(self, piece: str) -> None:
        if not piece:
            return
        self._buffer += piece
        if not self._stream_active:
            self._ensure_stream()
        self.run_worker(self._write_piece(piece), exclusive=True, group="chat-md")

    async def _write_piece(self, piece: str) -> None:
        if self._markdown_stream is not None:
            await self._markdown_stream.write(piece)

    async def _stop_stream(self) -> None:
        if self._markdown_stream is not None:
            await self._markdown_stream.stop()
            self._markdown_stream = None
            self._stream_active = False

    def update_content(self, content: str) -> None:
        """Replace full content (replay / non-streaming fallback)."""
        self._buffer = content
        self.run_worker(self._apply_full_content(content), exclusive=True, group="chat-md")

    async def _apply_full_content(self, content: str) -> None:
        await self._stop_stream()
        self.update(content or "")


class TypingIndicator(Horizontal):
    """Thinking indicator."""

    DEFAULT_CSS = """
    TypingIndicator {
        height: auto;
        width: 100%;
        padding: 0 0 1 0;
    }
    TypingIndicator Static {
        width: auto;
        color: $text-muted;
        padding: 0 1 0 0;
    }
    TypingIndicator LoadingIndicator {
        width: auto;
        height: 1;
    }
    """

    def __init__(self, label: str = "Waiting for response…", **kwargs) -> None:
        super().__init__(**kwargs)
        self._label = label

    def compose(self) -> ComposeResult:
        yield Static(self._label, id="typing-label")
        yield LoadingIndicator()


class MessageBlock(Vertical):
    """Focusable chat message container for copy / edit actions."""

    can_focus = True

    DEFAULT_CSS = """
    MessageBlock {
        width: 100%;
        height: auto;
        margin-bottom: 1;
    }
    MessageBlock:focus {
        outline: solid $primary 50%;
    }
    """

    def __init__(self, *, role: str, plain_text: str, **kwargs):
        super().__init__(**kwargs)
        self.role = role
        self.plain_text = plain_text


class PersonaButton(Button):
    """Agent persona chip — sets system prompt for the chat."""

    def __init__(self, persona: Persona, **kwargs):
        super().__init__(f"{persona.emoji} {persona.label}", variant="default", **kwargs)
        self.persona_id = persona.id


class PersonaPanel(Vertical):
    """Empty-state greeting with selectable agent personas."""

    DEFAULT_CSS = """
    PersonaPanel {
        width: 88;
        max-width: 88;
        height: auto;
        align: center middle;
        text-align: center;
        padding: 0 2;
    }
    PersonaPanel .welcome-title {
        text-style: bold;
        padding-bottom: 1;
    }
    PersonaPanel .welcome-sub {
        color: $text-muted;
        padding-bottom: 1;
    }
    #persona-row {
        width: 100%;
        height: auto;
        align: center middle;
        content-align: center middle;
    }
    PersonaButton {
        margin: 0 1 1 0;
        background: $surface;
        border: round $surface-lighten-1;
    }
    PersonaButton:hover {
        border: round $primary 60%;
    }
    .persona-hint {
        color: $text-muted;
        padding-top: 1;
        height: auto;
    }
    """

    def __init__(self, personas: list[Persona], **kwargs):
        super().__init__(**kwargs)
        self._personas = personas

    def compose(self) -> ComposeResult:
        yield Static("[bold]Choose an agent[/]", classes="welcome-title")
        yield Static(
            "[dim]Sets a system prompt for this chat — then type your request[/]",
            classes="welcome-sub",
        )
        with Horizontal(id="persona-row"):
            for persona in self._personas[:6]:
                yield PersonaButton(persona)
        yield Static(
            "[dim]Add personas: ~/.ai-engine/personas/*.json · /persona clear[/]",
            classes="persona-hint",
        )


class SlashSuggest(Vertical):
    """Fuzzy slash-command hints shown while typing / in the composer."""

    DEFAULT_CSS = """
    SlashSuggest {
        display: none;
        width: 100%;
        height: auto;
        max-height: 12;
        margin-bottom: 1;
        border: round $surface-lighten-1;
        background: $surface-darken-1;
    }
    SlashSuggest.-visible {
        display: block;
    }
    #slash-list {
        height: auto;
        max-height: 12;
        border: none;
    }
    """

    def compose(self) -> ComposeResult:
        yield ListView(id="slash-list")


class FileSuggest(Vertical):
    """Fuzzy file hints for @attach and /read above the composer."""

    DEFAULT_CSS = """
    FileSuggest {
        display: none;
        width: 100%;
        height: auto;
        max-height: 12;
        margin-bottom: 1;
        border: round $surface-lighten-1;
        background: $surface-darken-1;
    }
    FileSuggest.-visible {
        display: block;
    }
    #file-suggest-title {
        padding: 0 1;
        color: $text-muted;
        height: auto;
    }
    #file-list {
        height: auto;
        max-height: 10;
        border: none;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("", id="file-suggest-title")
        yield ListView(id="file-list")


class TerminalImage(Static):
    """Terminal image preview via rich-pixels + Pillow."""

    def __init__(
        self,
        image_path: str,
        *,
        compact: bool = False,
        size: str | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.image_path = image_path
        self._image_preset = _image_size_key(compact=compact, size=size)

    def render(self):
        pixels = _pixels_from_path(self.image_path, size=self._image_preset)
        if pixels is not None:
            return pixels
        art = _chafa_fallback(self.image_path, size=self._image_preset)
        if art:
            return art
        return "[dim](image preview unavailable — pip install pillow rich-pixels)[/]"


class ImagePreview(Vertical):
    """Filename + terminal image preview."""

    DEFAULT_CSS = """
    ImagePreview {
        height: auto;
        width: 100%;
        padding: 0;
    }
    ImagePreview .attach-name {
        height: 1;
        color: $text-muted;
        padding: 0 0 0 0;
    }
    ImagePreview TerminalImage {
        height: auto;
        width: auto;
        max-width: 100%;
        padding: 0;
    }
    """

    def __init__(self, image_path: str, *, size: str = "preview", **kwargs):
        super().__init__(**kwargs)
        self.image_path = image_path
        self._image_preset = size

    def compose(self) -> ComposeResult:
        name = os.path.basename(self.image_path)
        file_size = os.path.getsize(self.image_path) if os.path.exists(self.image_path) else 0
        yield Static(f"📎 {name}  ({file_size:,} B)", classes="attach-name")
        yield TerminalImage(self.image_path, size=self._image_preset)


class PendingAttachment(Horizontal):
    """Compact attachment preview shown above the composer."""

    DEFAULT_CSS = """
    PendingAttachment {
        width: 100%;
        height: auto;
        padding: 0 0 1 0;
        align: left middle;
    }
    PendingAttachment ImagePreview {
        width: 1fr;
        height: auto;
        padding: 0;
    }
    PendingAttachment #clear-attach-btn {
        width: 5;
        min-width: 5;
        height: 3;
        margin-left: 1;
        background: transparent;
        border: none;
        color: $text-muted;
    }
    PendingAttachment #clear-attach-btn:hover {
        color: $error;
    }
    """

    def __init__(self, image_path: str, **kwargs):
        super().__init__(**kwargs)
        self.image_path = image_path

    def compose(self) -> ComposeResult:
        yield ImagePreview(self.image_path, size="preview")
        yield Button("✕", id="clear-attach-btn")


class PickerResult(dict):
    """Result from the file picker: optional path + last browsed directory."""

    def __init__(self, path: str | None = None, cwd: str | None = None) -> None:
        super().__init__(path=path, cwd=cwd)

    @property
    def path(self) -> str | None:
        return self.get("path")

    @property
    def cwd(self) -> str | None:
        return self.get("cwd")

