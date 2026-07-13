"""AI Synapse terminal UI package."""
from ai_engine.tui.app import ChatTUI, run_tui
from ai_engine.tui.model_index import ModelEntry, ModelIndex

__all__ = ["ChatTUI", "ModelEntry", "ModelIndex", "run_tui"]
