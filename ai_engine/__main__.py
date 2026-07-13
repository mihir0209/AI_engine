"""AI Engine CLI — python -m ai_engine [command]

Commands:
    serve       Start the web server with dashboard and API
    status      Show engine status
    providers   List providers
    chat        Interactive chat (plain text, CLI)
    tui         Terminal UI chat (rich, visual)
    version     Show version
"""
import sys
import os
import argparse


def main():
    parser = argparse.ArgumentParser(
        prog="ai_engine",
        description="AI Synapse — Free Multi-Provider AI SDK"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # serve
    serve_parser = subparsers.add_parser("serve", help="Start the web server")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port number (default: 8000)")
    serve_parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")

    # status
    subparsers.add_parser("status", help="Show engine status")

    # providers
    subparsers.add_parser("providers", help="List all providers")

    # chat
    chat_parser = subparsers.add_parser("chat", help="Interactive chat (plain text, CLI)")
    chat_parser.add_argument("prompt", nargs="?", help="Single prompt (non-interactive mode)")
    chat_parser.add_argument("--model", "-m", default="default", help="Model name (default: auto)")
    chat_parser.add_argument("--provider", "-p", help="Provider name")
    chat_parser.add_argument("--image", "-i", help="Image path to attach to prompt")
    chat_parser.add_argument("--intent", action="store_true", help="Show intent classification")
    chat_parser.add_argument("--no-stream", action="store_true", help="Disable streaming")

    # tui
    tui_parser = subparsers.add_parser("tui", help="Terminal UI chat (rich, visual)")
    tui_parser.add_argument("--model", "-m", default="default", help="Model name (default: auto)")
    tui_parser.add_argument("--provider", "-p", help="Provider name")

    # version
    subparsers.add_parser("version", help="Show version")

    args = parser.parse_args()

    if args.command == "serve":
        _cmd_serve(args.host, args.port, args.reload)
    elif args.command == "status":
        _cmd_status()
    elif args.command == "providers":
        _cmd_providers()
    elif args.command == "chat":
        _cmd_chat(args)
    elif args.command == "tui":
        _cmd_tui(args)
    elif args.command == "version":
        _cmd_version()
    else:
        parser.print_help()


def _cmd_serve(host: str, port: int, reload: bool):
    from ai_engine import OpenAI

    client = OpenAI()
    client.serve(host=host, port=port, reload=reload)


def _cmd_status():
    pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if pkg_root not in sys.path:
        sys.path.insert(0, pkg_root)
    from config import AI_CONFIGS

    enabled = sum(1 for c in AI_CONFIGS.values() if c.get("enabled", True))
    print(f"Providers: {len(AI_CONFIGS)} configured, {enabled} enabled")


def _cmd_providers():
    pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if pkg_root not in sys.path:
        sys.path.insert(0, pkg_root)
    from config import AI_CONFIGS

    print(f"{'name':<20} {'enabled':<8} model")
    print("-" * 60)
    for name, cfg in sorted(AI_CONFIGS.items(), key=lambda x: x[1].get("priority", 99)):
        en = "yes" if cfg.get("enabled", True) else "no"
        print(f"{name:<20} {en:<8} {cfg.get('model', '')}")


def _cmd_version():
    from ai_engine import __version__
    print(f"ai-synapse {__version__}")


def _cmd_tui(args):
    """Launch the TUI chat application."""
    try:
        from textual.app import App  # noqa: F401
    except (ImportError, ModuleNotFoundError):
        print("Error: 'textual' is required for the TUI.")
        print("Install it with: pip install ai-synapse[tui]")
        print("Or: pip install textual")
        sys.exit(1)

    # Ensure core/ is importable
    pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if pkg_root not in sys.path:
        sys.path.insert(0, pkg_root)

    from core.env_bootstrap import bootstrap_user_environment

    bootstrap_user_environment()
    if not os.environ.get("CDN_CONFIG_URL"):
        os.environ["CDN_CONFIG_URL"] = "default"

    from ai_engine.tui import run_tui

    run_tui(model=args.model, provider=args.provider)


def _cmd_chat(args):
    """Interactive or single-prompt chat with intent routing."""
    # Ensure core/ is importable
    pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if pkg_root not in sys.path:
        sys.path.insert(0, pkg_root)

    if not os.environ.get("CDN_CONFIG_URL"):
        os.environ["CDN_CONFIG_URL"] = "default"

    from core.config_sync import config_fetcher
    config_fetcher.initialize()

    from ai_engine import OpenAI
    from core.intent_classifier import intent_classifier

    client = OpenAI()

    def run_prompt(prompt_text, image_path=None):
        messages = []

        # Attach image if provided
        content_parts = [{"type": "text", "text": prompt_text}]
        if image_path:
            import base64
            import mimetypes
            mime_type = mimetypes.guess_type(image_path)[0] or "image/png"
            with open(image_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{img_b64}"}
            })
            has_images = True
        else:
            has_images = False

        if len(content_parts) == 1:
            messages.append({"role": "user", "content": prompt_text})
        else:
            messages.append({"role": "user", "content": content_parts})

        # Intent classification
        intent_result = intent_classifier.classify(prompt_text, has_images=has_images)
        if args.intent:
            print(f"  Intent: {intent_result['intent']} (confidence={intent_result['confidence']})")
            print(f"  Input: {intent_result['input_modalities']} → Output: {intent_result['output_modalities']}")
            print()

        # Send via SDK
        try:
            response = client.chat.completions.create(
                model=args.model,
                messages=messages,
                provider=args.provider,
            )
            return response
        except Exception as e:
            print(f"Error: {e}")
            return None

    # Single prompt mode
    if args.prompt:
        response = run_prompt(args.prompt, args.image)
        if response and hasattr(response, 'choices') and response.choices:
            print(f"\n{response.choices[0].message.content}\n")
        return

    # Interactive mode
    print("AI Synapse Chat (Ctrl+C to exit)")
    print(f"Model: {args.model} | Provider: {args.provider or 'auto'}")
    print()

    history = []
    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                break

            history.append({"role": "user", "content": user_input})
            list(history)

            response = run_prompt(user_input, args.image)
            if response and hasattr(response, 'choices') and response.choices:
                assistant_content = response.choices[0].message.content
                print(f"\nAI: {assistant_content}\n")
                history.append({"role": "assistant", "content": assistant_content})

            # Reset image after first use
            args.image = None

        except KeyboardInterrupt:
            print("\nBye!")
            break
        except EOFError:
            break


if __name__ == "__main__":
    main()
