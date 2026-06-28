"""AI Engine CLI — python -m ai_engine [command]

Commands:
    serve       Start the web server with dashboard and API
    status      Show engine status
    providers   List providers
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

    # version
    subparsers.add_parser("version", help="Show version")

    args = parser.parse_args()

    if args.command == "serve":
        _cmd_serve(args.host, args.port, args.reload)
    elif args.command == "status":
        _cmd_status()
    elif args.command == "providers":
        _cmd_providers()
    elif args.command == "version":
        from ai_engine import __version__
        print(f"ai-synapse {__version__}")
    else:
        parser.print_help()


def _cmd_serve(host, port, reload):
    """Start the web server."""
    # Ensure core/ and config.py are importable
    pkg_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if pkg_root not in sys.path:
        sys.path.insert(0, pkg_root)

    # Initialize CDN config
    from core.config_sync import config_fetcher
    config_fetcher.initialize()

    # Import and run the server
    from ai_engine.server.app import app
    import uvicorn
    print(f"Starting AI Synapse server on {host}:{port}")
    print(f"Dashboard:  http://{host}:{port}/")
    print(f"Chat UI:    http://{host}:{port}/chat")
    print(f"API Docs:   http://{host}:{port}/docs")
    uvicorn.run(app, host=host, port=port, reload=reload)


def _cmd_status():
    """Show engine status."""
    from ai_engine import OpenAI
    client = OpenAI()
    enabled = {n for n, c in client._engine.providers.items() if c.get("enabled")}
    print(f"AI Synapse v{__import__('ai_engine').__version__}")
    print(f"Providers: {len(enabled)} enabled / {len(client._engine.providers)} total")


def _cmd_providers():
    """List all providers."""
    from ai_engine import OpenAI
    client = OpenAI()
    for name, config in sorted(client._engine.providers.items(), key=lambda x: x[1].get("priority", 999)):
        enabled = "✅" if config.get("enabled") else "⬜"
        has_key = "🔑" if any(k for k in config.get("api_keys", []) if k) else "  "
        print(f"  {enabled} {has_key} P{config.get('priority', 99):2d} {name}")


if __name__ == "__main__":
    main()
