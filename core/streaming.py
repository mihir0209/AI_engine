"""Streaming chat completion mixin — extracted from AI_engine."""
from __future__ import annotations

from typing import Dict, List, Any, Optional, Iterator

try:
    from core.config import verbose_print
    from core.provider_reliability import get_fallback_chain, should_retry_provider
except ImportError:  # pragma: no cover
    from config import verbose_print  # type: ignore
    from core.provider_reliability import get_fallback_chain, should_retry_provider


class StreamingMixin:
    """Provides chat_completion_stream() to AI_engine."""

    def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        autodecide: bool = True,
        **kwargs: Any,
    ) -> Iterator[Dict[str, Any]]:
        """Stream chat completion chunks as they arrive.

        Yields:
            dict: {'content': str} or {'done': bool, ...} or {'error': str, 'done': True}
        """
        preferred_provider = kwargs.get("preferred_provider")

        if model and "/" in model:
            provider_part, model_part = model.split("/", 1)
            if provider_part in self.providers:
                preferred_provider = provider_part
                model = model_part

        available_providers = self._get_available_providers(preferred_provider)
        if not available_providers:
            yield {"error": "No available providers", "done": True}
            return

        available_set = {name for name, _ in available_providers}
        for provider_name, provider_config in available_providers:
            format_type = provider_config.get("format", "openai")

            if format_type not in ("openai", "ollama"):
                chain = get_fallback_chain(provider_name)
                fallback = chain.next(provider_name, available_set)
                if fallback and fallback in dict(available_providers):
                    if self.verbose:
                        verbose_print(
                            f"🔀 Fallback from {provider_name} (non-streaming) → {fallback}",
                            self.verbose,
                        )
                    provider_name = fallback
                    provider_config = dict(available_providers)[fallback]
                    format_type = provider_config.get("format", "openai")
                    if format_type not in ("openai", "ollama"):
                        continue
                else:
                    continue

            try:
                if self.verbose:
                    verbose_print(
                        f"🔄 Streaming from {provider_name} ({format_type})...",
                        self.verbose,
                    )

                if format_type == "ollama":
                    stream_gen = self._make_ollama_streaming_request(
                        provider_name, provider_config, messages, model
                    )
                else:
                    stream_gen = self._make_streaming_request(
                        provider_name, provider_config, messages, model
                    )

                stream_failed = False
                chunk: Dict[str, Any] = {}
                for chunk in stream_gen:
                    if chunk.get("error"):
                        stream_failed = True
                        if self.verbose:
                            verbose_print(
                                f"❌ Streaming error from {provider_name}: {chunk['error']}",
                                self.verbose,
                            )
                        break
                    if chunk.get("done"):
                        yield {
                            "done": True,
                            "provider": provider_name,
                            "model": model or provider_config.get("model"),
                        }
                        return
                    yield chunk

                if stream_failed:
                    error_message = chunk.get("error", "streaming failure")
                    error_type = self._classify_error(error_message, 0, None)
                    self._handle_provider_failure(provider_name, error_message, 0, None)
                    if should_retry_provider(error_type):
                        continue
                    yield {
                        "error": error_message,
                        "done": True,
                        "provider": provider_name,
                    }
                    return
                return
            except Exception as e:
                if self.verbose:
                    verbose_print(
                        f"❌ {provider_name} streaming exception: {e}",
                        self.verbose,
                    )
                continue

        yield {"error": "All providers failed for streaming", "done": True}
