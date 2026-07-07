"""
AI Synapse TUI — Clean, generalized, professional terminal chat interface.

Inspired by modern chat TUIs (e.g. Elia, Textual examples).
Usage:
    python -m ai_engine tui
    python -m ai_engine tui --model default
    python -m ai_engine tui --provider groq
"""
import os
import sys
import asyncio
import base64
import mimetypes
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Header, Footer, Static, Button, TextArea, Markdown, ListView, ListItem, Label,
    DirectoryTree,
)
from textual.binding import Binding
from textual.reactive import reactive
from textual.screen import Screen
from textual import work, on, events
from textual.css.query import NoMatches
from textual.command import Provider, Hit
from collections.abc import AsyncIterator

pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if pkg_root not in sys.path:
    sys.path.insert(0, pkg_root)


# ============================================================
# WIDGETS
# ============================================================

class ChatMessage(Static):
    """User message bubble."""
    def __init__(self, text: str, **kwargs):
        super().__init__(**kwargs)
        self.text = text

    def render(self):
        return f"[bold #a5d8ff]You[/]\n{self.text}"


class AssistantMessage(Markdown):
    """AI response rendered with Markdown for rich content (code, lists, etc)."""
    BORDER_TITLE = "AI"

    def __init__(self, content: str, model: str = "", **kwargs):
        # Prepend model info as header-ish
        header = f"**{model}**  \n" if model else ""
        super().__init__(header + content, **kwargs)


class ImagePreview(Static):
    """Simple image attachment preview (filename + size, optional ascii via chafa if present)."""
    def __init__(self, image_path: str, **kwargs):
        super().__init__(**kwargs)
        self.image_path = image_path

    def render(self):
        name = os.path.basename(self.image_path)
        size = os.path.getsize(self.image_path) if os.path.exists(self.image_path) else 0
        try:
            import subprocess
            result = subprocess.run(
                ["chafa", "--size", "40x12", "--fill", "block", self.image_path],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0 and result.stdout.strip():
                return f"[dim]📎 {name} ({size} bytes)[/]\n{result.stdout}"
        except Exception:
            pass
        return f"[dim]📎 Attached image: {name} ({size} bytes)[/]\n[dim](preview requires chafa)[/]"


class WelcomeMessage(Static):
    """Big centered welcome like ChatGPT empty state."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def render(self):
        return """[bold #e0e0e0]Where should we begin?[/]

[dim]AI Synapse — free multi-provider chat[/]"""


class FilePickerScreen(Screen[str | None]):
    """Cross-platform file picker using Textual's DirectoryTree (no OS dialogs needed)."""
    def compose(self) -> ComposeResult:
        yield Header("Select file to attach (click or Enter on file)")
        yield DirectoryTree(".", id="dir-tree")
        yield Static("[dim]Esc to cancel[/]", classes="help")
        yield Footer()

    @on(DirectoryTree.FileSelected)
    def select_file(self, event: DirectoryTree.FileSelected) -> None:
        self.dismiss(str(event.path))

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            self.dismiss(None)


class ChatCommandProvider(Provider):
    """Register our TUI actions in the Command Palette (Ctrl+P)."""
    async def search(self, query: str) -> AsyncIterator[Hit]:
        q = query.lower().strip()
        items = [
            ("New Chat", "Start a new conversation", "new_chat"),
            ("Change Model", "Cycle the current model", "change_model"),
            ("Change Provider", "Cycle the current provider", "change_provider"),
            ("Clear / New Chat", "Clear the current view and start fresh", "new_chat"),
        ]
        for title, help_text, action in items:
            if not q or q in title.lower():
                def _runner(act=action):
                    return lambda: getattr(self.app, f"action_{act}")()
                yield Hit(title, help_text, _runner())


class StatusBar(Static):
    """Reactive status bar."""
    model = reactive("default")
    provider = reactive("auto")
    status = reactive("Ready")

    def render(self):
        prov = self.provider or "auto"
        return f"Model: [bold]{self.model}[/]  •  Provider: [bold]{prov}[/]  •  {self.status}"


# ============================================================
# MAIN APP
# ============================================================

class ChatTUI(App):
    """Generalized professional chat TUI (ChatGPT-like in terminal)."""

    CSS = """
    Screen {
        layout: horizontal;
    }

    /* Sidebar */
    #sidebar {
        width: 28;
        background: $surface;
        border-right: thick $surface-darken-2;
    }

    #sidebar-header {
        height: 3;
        padding: 1 1;
        background: $surface-darken-1;
        text-style: bold;
    }

    #new-chat-btn {
        width: 100%;
        margin: 1 1;
    }

    #chat-list {
        height: 1fr;
        border: none;
        padding: 0 1;
    }

    ListItem {
        padding: 0 1;
    }

    ListItem:hover {
        background: $surface-darken-1;
    }

    ListItem.-selected {
        background: $primary 20%;
        text-style: bold;
    }

    /* Main chat area - vertical flow with scroll taking most space */
    #main-area {
        width: 1fr;
        height: 1fr;
        layout: vertical;
    }

    #chat-scroll {
        height: 1fr;
        padding: 1 2;
        overflow-y: auto;
    }

    #chat-body {
        height: 1fr;
    }

    .chat-msg {
        margin: 0 0 1 0;
        padding: 1 2;
    }

    .user-msg {
        background: $primary 10%;
        border-left: thick $primary;
    }

    .ai-msg {
        background: $surface-darken-1;
        border-left: thick $success;
    }

    .image-preview {
        margin: 0 0 1 0;
        padding: 0 1;
        color: $text-muted;
    }

    .welcome-msg {
        width: 100%;
        height: 100%;
        content-align: center middle;
        text-align: center;
        padding: 4 6;
    }

    /* Input bar at the bottom of the chat area */
    #input-area {
        dock: bottom;
        height: auto;
        padding: 0 2 1 2;
        background: $surface;
    }

    #input-box {
        background: $surface-darken-1;
        border: round $surface-darken-2;
        padding: 0 1;
    }

    #user-input {
        width: 1fr;
        height: auto;
        min-height: 3;
        max-height: 8;
        padding: 1;
        border: none;
        background: transparent;
    }

    #input-controls {
        height: 3;
        padding: 0 1;
    }

    #send-btn {
        min-width: 10;
        margin-left: 1;
    }

    #attach-btn {
        min-width: 12;
    }

    /* Status */
    #status-bar {
        height: 1;
        dock: bottom;
        background: $surface-darken-1;
        padding: 0 1;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("ctrl+enter", "send_message", "Send", priority=True, show=True),
        Binding("ctrl+n", "new_chat", "New Chat"),
        Binding("ctrl+m", "change_model", "Model"),
        # ctrl+p is now for the built-in Command Palette (see ChatCommandProvider)
        # Use ctrl+shift+p for direct provider cycle if needed
        Binding("ctrl+shift+p", "change_provider", "Provider"),
        Binding("ctrl+q", "quit", "Quit", priority=True),
        Binding("ctrl+c", "quit", "Quit"),
    ]

    TITLE = "AI Synapse"
    SUB_TITLE = "Free multi-provider chat"

    # Enable Command Palette on Ctrl+P and register our custom commands
    COMMAND_PALETTE_BINDING = "ctrl+p"
    COMMANDS = {ChatCommandProvider}

    current_model = reactive("default")
    current_provider = reactive(None)
    is_processing = reactive(False)
    current_chat_id = reactive(0)
    chat_counter = reactive(0)

    def __init__(self, model="default", provider=None, **kwargs):
        super().__init__(**kwargs)
        self.current_model = model
        self.current_provider = provider
        self.chats = {}  # id -> {"title": , "messages": [{"role", "content", "_image_path"?}] }
        self._pending_image = None
        self._new_chat()

    def _new_chat(self):
        self.chat_counter += 1
        self.current_chat_id = self.chat_counter
        self.chats[self.current_chat_id] = {
            "title": f"Chat {self.chat_counter}",
            "messages": [],
        }

    def compose(self) -> ComposeResult:
        # Sidebar
        with Vertical(id="sidebar"):
            yield Static("  AI Synapse", id="sidebar-header")
            yield Button("+ New Chat", id="new-chat-btn", variant="primary")
            yield ListView(id="chat-list")

        # Main
        with Vertical(id="main-area"):
            with Container(id="chat-body"):
                with VerticalScroll(id="chat-scroll"):
                    yield WelcomeMessage(classes="welcome-msg")

            with Container(id="input-area"):
                with Container(id="input-box"):
                    yield TextArea(
                        id="user-input",
                        placeholder="Message AI Synapse... (Ctrl+Enter to send)",
                        show_line_numbers=False,
                        soft_wrap=True,
                    )
                    with Horizontal(id="input-controls"):
                        yield Button("📎 Attach", id="attach-btn")
                        yield Button("Send", id="send-btn", variant="primary")

        yield StatusBar(id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#user-input", TextArea).focus()
        self._refresh_sidebar()
        self._update_status()
        # If the current chat already has messages (e.g. switched or restored), show them
        current = self.chats.get(self.current_chat_id, {})
        if current.get("messages"):
            self._load_current_chat_messages()
        else:
            # ensure welcome is there for empty
            try:
                scroll = self.query_one("#chat-scroll", VerticalScroll)
                if not list(scroll.children):
                    scroll.mount(WelcomeMessage(classes="welcome-msg"))
            except Exception:
                pass

    # ===== Key handling for reliable Ctrl+Enter (TextArea consumes many keys) =====
    def on_key(self, event: events.Key) -> None:
        key = event.key
        if key in ("ctrl+enter", "control+enter"):
            self.action_send_message()
            event.prevent_default()
            event.stop()

    def key_ctrl_enter(self) -> None:
        """Fallback for some terminal emulators."""
        self.action_send_message()

    # ===== Events =====
    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id
        if bid == "send-btn":
            self.action_send_message()
        elif bid == "attach-btn":
            self._open_file_picker()
        elif bid == "new-chat-btn":
            self.action_new_chat()

    @on(ListView.Selected, "#chat-list")
    def on_chat_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if hasattr(item, "chat_id"):
            self._switch_to_chat(item.chat_id)

    # ===== Core actions =====
    def action_send_message(self) -> None:
        if self.is_processing:
            return
        input_widget = self.query_one("#user-input", TextArea)
        text = (input_widget.text or "").strip()
        if not text:
            return
        input_widget.text = ""
        input_widget.focus()

        # Commands
        if text.startswith("/"):
            self._handle_command(text)
            return

        self._send_message(text)

    def _open_file_picker(self) -> None:
        """Open cross-platform Textual file picker (using DirectoryTree in modal)."""
        def on_file_chosen(path: str | None) -> None:
            if not path:
                return
            if os.path.exists(path):
                self._pending_image = path
                try:
                    container = self.query_one("#chat-scroll", VerticalScroll)
                    container.mount(ImagePreview(path, classes="image-preview"))
                    container.scroll_end(animate=False)
                except Exception:
                    pass
            else:
                try:
                    container = self.query_one("#chat-scroll", VerticalScroll)
                    container.mount(Static(f"[red]File not found: {path}[/]", classes="chat-msg"))
                    container.scroll_end(animate=False)
                except Exception:
                    pass

        self.push_screen(FilePickerScreen(), callback=on_file_chosen)

    def _handle_command(self, text: str) -> None:
        cmd = text.strip().lower()
        container = self.query_one("#chat-scroll", VerticalScroll)

        if cmd == "/clear":
            self.action_new_chat()
        elif cmd == "/help":
            container.mount(WelcomeMessage(classes="welcome-msg"))
            container.scroll_end(animate=False)
        elif cmd.startswith("/image "):
            parts = text.split(" ", 2)
            path = parts[1].strip() if len(parts) > 1 else ""
            prompt = parts[2].strip() if len(parts) > 2 else ""
            if path and os.path.exists(path):
                self._pending_image = path
                container.mount(ImagePreview(path, classes="image-preview"))
                container.scroll_end(animate=False)
                if prompt:
                    # immediately send the remaining prompt with image
                    self._send_message(prompt)
            else:
                container.mount(Static(f"[red]Image not found: {path}[/]", classes="chat-msg"))
                container.scroll_end(animate=False)
        elif cmd.startswith("/model "):
            new_model = text.split(" ", 1)[1].strip()
            self.current_model = new_model
            self._update_status()
            container.mount(Static(f"[dim]Model set to {new_model}[/]", classes="chat-msg"))
            container.scroll_end(animate=False)
        elif cmd.startswith("/provider "):
            new_prov = text.split(" ", 1)[1].strip()
            self.current_provider = new_prov if new_prov.lower() != "auto" else None
            self._update_status()
            container.mount(Static(f"[dim]Provider set to {new_prov}[/]", classes="chat-msg"))
            container.scroll_end(animate=False)
        elif cmd == "/quit":
            self.exit()
        else:
            container.mount(Static(f"[dim]Unknown command: {cmd}. Try /help[/]", classes="chat-msg"))
            container.scroll_end(animate=False)

    def _send_message(self, text: str) -> None:
        self.is_processing = True
        try:
            self.query_one("#send-btn", Button).disabled = True
        except NoMatches:
            pass
        self.query_one(StatusBar).status = "Thinking..."

        image_path = self._pending_image
        self._pending_image = None

        chat = self.chats[self.current_chat_id]
        user_msg = {"role": "user", "content": text}
        if image_path:
            user_msg["_image_path"] = image_path
        chat["messages"].append(user_msg)

        if len(chat["messages"]) == 1:
            chat["title"] = text[:30]
            self._refresh_sidebar()

        # Render immediately
        container = self.query_one("#chat-scroll", VerticalScroll)
        # Remove welcome on first real message
        try:
            w = container.query_one(WelcomeMessage)
            w.remove()
        except Exception:
            pass
        container.mount(ChatMessage(text, classes="chat-msg user-msg"))
        if image_path and os.path.exists(image_path):
            container.mount(ImagePreview(image_path, classes="image-preview"))
        container.scroll_end(animate=False)

        # Kick off AI (thread worker)
        self._perform_ai_call(text, image_path)

    @work(exclusive=True, thread=True)
    def _perform_ai_call(self, text: str, image_path: str = None) -> None:
        """Thread worker: blocking call + call_from_thread for UI."""
        try:
            messages = []
            for m in self.chats[self.current_chat_id]["messages"]:
                if "_image_path" in m and os.path.exists(m["_image_path"]):
                    path = m["_image_path"]
                    mime = mimetypes.guess_type(path)[0] or "image/png"
                    with open(path, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode()
                    content = [
                        {"type": "text", "text": m["content"]},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
                    ]
                    messages.append({"role": m["role"], "content": content})
                else:
                    messages.append({"role": m["role"], "content": m["content"]})

            from ai_engine import OpenAI
            client = OpenAI()

            response = client.chat.completions.create(
                model=self.current_model,
                messages=messages,
                provider=self.current_provider,
            )

            content = ""
            model_used = self.current_model
            provider_used = self.current_provider or "auto"

            if response and getattr(response, "choices", None):
                content = response.choices[0].message.content or ""
                if hasattr(response, "model") and response.model:
                    model_used = response.model
                if hasattr(response, "provider") and response.provider:
                    provider_used = response.provider

            self.chats[self.current_chat_id]["messages"].append({
                "role": "assistant",
                "content": content
            })

            self.call_from_thread(self._display_response, content, model_used, provider_used)

        except Exception as e:
            err = str(e)[:300]
            self.call_from_thread(self._display_error, err)

    def _display_response(self, content: str, model_used: str, provider_used: str) -> None:
        container = self.query_one("#chat-scroll", VerticalScroll)
        # Ensure welcome is gone when response arrives
        try:
            w = container.query_one(WelcomeMessage)
            w.remove()
        except Exception:
            pass
        container.mount(AssistantMessage(content, model=model_used, classes="chat-msg ai-msg"))
        container.scroll_end(animate=False)

        status = self.query_one(StatusBar)
        status.status = f"Done • {model_used}"
        status.provider = provider_used or status.provider

        self._finish_processing()

    def _display_error(self, error_msg: str) -> None:
        container = self.query_one("#chat-scroll", VerticalScroll)
        try:
            w = container.query_one(WelcomeMessage)
            w.remove()
        except Exception:
            pass
        container.mount(Static(f"[bold red]Error:[/] {error_msg}", classes="chat-msg"))
        container.scroll_end(animate=False)

        status = self.query_one(StatusBar)
        status.status = "Error"

        self._finish_processing()

    def _finish_processing(self) -> None:
        self.is_processing = False
        try:
            self.query_one("#send-btn", Button).disabled = False
        except NoMatches:
            pass
        try:
            self.query_one("#user-input", TextArea).focus()
        except NoMatches:
            pass

    # ===== Chat management =====
    def action_new_chat(self) -> None:
        self._new_chat()
        container = self.query_one("#chat-scroll", VerticalScroll)
        try:
            for child in list(container.children):
                child.remove()
        except Exception:
            pass
        container.mount(WelcomeMessage(classes="welcome-msg"))
        self.query_one(StatusBar).status = "New chat"
        self._refresh_sidebar()
        self.query_one("#user-input", TextArea).focus()

    def _switch_to_chat(self, chat_id: int) -> None:
        if chat_id not in self.chats:
            return
        self.current_chat_id = chat_id
        self._load_current_chat_messages()
        self._refresh_sidebar()
        try:
            self.query_one("#user-input", TextArea).focus()
            self.query_one(StatusBar).status = "Switched chat"
        except Exception:
            pass

    def _replay_messages(self, container: VerticalScroll, chat: dict) -> None:
        for m in chat["messages"]:
            if m["role"] == "user":
                container.mount(ChatMessage(m["content"], classes="chat-msg user-msg"))
                if "_image_path" in m and os.path.exists(m["_image_path"]):
                    container.mount(ImagePreview(m["_image_path"], classes="image-preview"))
            else:
                container.mount(AssistantMessage(m.get("content", ""), model="", classes="chat-msg ai-msg"))
        container.scroll_end(animate=False)

    def _load_current_chat_messages(self) -> None:
        """Clear scroll and replay messages for current chat (used on mount/switch)."""
        try:
            container = self.query_one("#chat-scroll", VerticalScroll)
            for child in list(container.children):
                child.remove()
            chat = self.chats.get(self.current_chat_id, {})
            if chat.get("messages"):
                self._replay_messages(container, chat)
            else:
                container.mount(WelcomeMessage(classes="welcome-msg"))
        except Exception:
            pass

    def action_change_model(self) -> None:
        models = ["default", "gemini-2.5-flash", "gpt-4o", "claude-3.5-sonnet",
                  "llama-3.3-70b-versatile", "mistral-large-latest", "codestral-latest"]
        try:
            idx = models.index(self.current_model)
        except ValueError:
            idx = 0
        self.current_model = models[(idx + 1) % len(models)]
        self._update_status()

    def action_change_provider(self) -> None:
        providers = [None, "groq", "gemini", "openrouter", "mistral", "g4f_gemini", "pollinations"]
        try:
            idx = providers.index(self.current_provider)
        except ValueError:
            idx = 0
        self.current_provider = providers[(idx + 1) % len(providers)]
        self._update_status()

    def _update_status(self) -> None:
        try:
            bar = self.query_one(StatusBar)
            bar.model = self.current_model
            bar.provider = self.current_provider or "auto"
        except NoMatches:
            pass

    def _refresh_sidebar(self) -> None:
        try:
            chat_list = self.query_one("#chat-list", ListView)
            chat_list.clear()
            for cid in reversed(list(self.chats.keys())):
                chat = self.chats[cid]
                title = chat.get("title", f"Chat {cid}")[:26]
                is_active = (cid == self.current_chat_id)
                item = ListItem(Label(f"{'● ' if is_active else '  '}{title}"))
                item.chat_id = cid  # attach for handler
                chat_list.append(item)
        except NoMatches:
            pass

    def watch_is_processing(self, processing: bool) -> None:
        try:
            bar = self.query_one(StatusBar)
            if processing:
                bar.status = "Thinking..."
            elif bar.status == "Thinking...":
                bar.status = "Ready"
        except (NoMatches, Exception):
            pass


def run_tui(model="default", provider=None):
    """Entry point."""
    # Ensure config sync for providers (same as CLI)
    try:
        pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
