"""
Provider request methods — extracted from ai_engine.py monolith.
Mixin class that AI_engine inherits from to keep all methods accessible via self.
"""
import re
import json
import time
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RequestResult:
    """Result of an AI request"""
    success: bool
    content: str = ""
    status_code: int = 0
    response_time: float = 0.0
    error_message: str = ""
    error_type: str = "unknown"
    provider_used: str = ""
    model_used: str = ""
    raw_response: Optional[Dict] = None


class ProviderRequestMixin:
    """All HTTP request methods for communicating with AI providers."""

    def _make_request(self, provider_name, config, messages, model=None, **kwargs):
        """Make a request to a specific provider"""
        try:
            format_type = config.get('format', 'openai')

            if format_type == 'openai':
                return self._make_openai_request(provider_name, config, messages, model, **kwargs)
            elif format_type == 'anthropic':
                return self._make_anthropic_request(provider_name, config, messages, model, **kwargs)
            elif format_type == 'vertex_ai':
                return self._make_vertex_ai_request(provider_name, config, messages, model, **kwargs)
            elif format_type == 'azure_openai':
                return self._make_azure_openai_request(provider_name, config, messages, model, **kwargs)
            elif format_type == 'bedrock':
                return self._make_bedrock_request(provider_name, config, messages, model, **kwargs)
            elif format_type == 'gemini':
                return self._make_gemini_request(provider_name, config, messages, model, **kwargs)
            elif format_type == 'cohere':
                return self._make_cohere_request(provider_name, config, messages, model, **kwargs)
            elif format_type == 'cloudflare':
                return self._make_cloudflare_request(provider_name, config, messages, model, **kwargs)
            elif format_type == 'a3z_get':
                return self._make_a3z_request(provider_name, config, messages, model, **kwargs)
            else:
                return self._make_openai_request(provider_name, config, messages, model, **kwargs)
        except Exception as e:
            return RequestResult(
                success=False,
                error_message=f"Provider request failed: {str(e)}",
                error_type="provider_exception"
            )

    def _make_azure_openai_request(self, provider_name, config, messages, model=None, **kwargs):
        """Make request to Azure OpenAI provider"""

        import requests as _requests

        endpoint = config.get("endpoint", "")
        api_keys = config.get("api_keys", [])
        current_key = self._get_current_api_key(provider_name)
        if not current_key:
            return RequestResult(success=False, error_message="No API key available", error_type="auth_error")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {current_key}"
        }

        payload = {
            "messages": messages,
            "max_tokens": config.get("max_tokens", 4096),
            "temperature": config.get("temperature", 0.7),
            "stream": False
        }

        if model:
            payload["model"] = model

        timeout = config.get("timeout", 60)
        try:
            resp = _requests.post(endpoint, json=payload, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return RequestResult(
                    success=True,
                    content=content,
                    provider_used=provider_name,
                    model_used=data.get("model", model),
                    status_code=200
                )
            else:
                return RequestResult(
                    success=False,
                    error_message=f"Azure error {resp.status_code}: {resp.text[:200]}",
                    error_type="provider_error",
                    status_code=resp.status_code
                )
        except Exception as e:
            return RequestResult(success=False, error_message=str(e), error_type="request_exception")

    def _make_bedrock_request(self, provider_name, config, messages, model=None, **kwargs):
        """Make request to AWS Bedrock provider"""

        return RequestResult(
            success=False,
            error_message="Bedrock provider not yet implemented",
            error_type="not_implemented"
        )

    def _make_streaming_request(self, provider_name, config, messages, model=None, **kwargs):
        """Make streaming request to a provider (yields chunks)"""
        import requests as _requests

        endpoint = config.get("endpoint", "")
        current_key = self._get_current_api_key(provider_name)
        headers = {"Content-Type": "application/json"}

        auth_type = config.get("auth_type")
        if auth_type in ("bearer", "bearer_lowercase") and current_key:
            headers["Authorization"] = f"Bearer {current_key}"

        payload = {
            "messages": messages,
            "model": model or config.get("model", "gpt-4"),
            "max_tokens": config.get("max_tokens", 4096),
            "temperature": config.get("temperature", 0.7),
            "stream": True
        }

        timeout = config.get("timeout", 60)

        try:
            resp = _requests.post(endpoint, json=payload, headers=headers, timeout=timeout, stream=True)

            if resp.status_code != 200:
                yield {'error': f'HTTP {resp.status_code}: {resp.text[:200]}', 'done': True}
                return

            for line in resp.iter_lines():
                if not line:
                    continue
                line = line.decode('utf-8', errors='replace')
                if line.startswith('data: '):
                    data_str = line[6:]
                    if data_str.strip() == '[DONE]':
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data.get('choices', [{}])[0].get('delta', {})
                        content = delta.get('content')
                        if content:
                            yield {'content': content}
                    except json.JSONDecodeError:
                        continue

            yield {'done': True}

        except Exception as e:
            yield {'error': str(e), 'done': True}

    def _make_ollama_streaming_request(self, provider_name, config, messages, model=None, **kwargs):
        """Make streaming request to Ollama-compatible provider"""
        import requests as _requests

        endpoint = config.get("endpoint", "")
        model_name = model or config.get("model", "llama3.1")

        payload = {
            "model": model_name,
            "prompt": "\n".join(m["content"] for m in messages if m["role"] == "user"),
            "stream": True
        }

        timeout = config.get("timeout", 120)

        try:
            resp = _requests.post(endpoint, json=payload, timeout=timeout, stream=True)

            if resp.status_code != 200:
                yield {'error': f'HTTP {resp.status_code}', 'done': True}
                return

            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line.decode('utf-8'))
                    if data.get('done'):
                        break
                    content = data.get('response', '')
                    if content:
                        yield {'content': content}
                except json.JSONDecodeError:
                    continue

            yield {'done': True}

        except Exception as e:
            yield {'error': str(e), 'done': True}

    def _make_anthropic_request(self, provider_name, config, messages, model=None, **kwargs):
        """Make request to Anthropic provider"""

        import requests as _requests

        endpoint = config.get("endpoint", "https://api.anthropic.com/v1/messages")
        current_key = self._get_current_api_key(provider_name)

        headers = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        if current_key:
            headers["x-api-key"] = current_key

        system_msg = ""
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                user_messages.append({"role": msg["role"], "content": msg["content"]})

        payload = {
            "model": model or config.get("model", "claude-3-haiku-20240307"),
            "max_tokens": config.get("max_tokens", 4096),
            "messages": user_messages
        }
        if system_msg:
            payload["system"] = system_msg

        timeout = config.get("timeout", 60)
        try:
            resp = _requests.post(endpoint, json=payload, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("content", [{}])[0].get("text", "")
                return RequestResult(
                    success=True, content=content, provider_used=provider_name,
                    model_used=data.get("model", model), status_code=200
                )
            else:
                return RequestResult(
                    success=False, error_message=f"Anthropic {resp.status_code}: {resp.text[:200]}",
                    error_type="provider_error", status_code=resp.status_code
                )
        except Exception as e:
            return RequestResult(success=False, error_message=str(e), error_type="request_exception")

    def _make_vertex_ai_request(self, provider_name, config, messages, model=None, **kwargs):
        """Make request to Vertex AI provider"""

        return RequestResult(success=False, error_message="Vertex AI not yet implemented", error_type="not_implemented")

    def _make_openai_request(self, provider_name, config, messages, model=None, **kwargs):
        """Make request to OpenAI-compatible provider"""

        import requests as _requests

        endpoint = config.get("endpoint", "")
        current_key = self._get_current_api_key(provider_name)
        headers = {"Content-Type": "application/json"}

        auth_type = config.get("auth_type")
        if auth_type in ("bearer", "bearer_lowercase") and current_key:
            headers["Authorization"] = f"Bearer {current_key}"

        payload = {
            "messages": messages,
            "model": model or config.get("model", "gpt-4"),
            "max_tokens": config.get("max_tokens", 4096),
            "temperature": config.get("temperature", 0.7),
            "stream": False
        }

        timeout = config.get("timeout", 60)
        try:
            resp = _requests.post(endpoint, json=payload, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                return RequestResult(
                    success=True, content=content, provider_used=provider_name,
                    model_used=data.get("model", model), status_code=200
                )
            else:
                return RequestResult(
                    success=False, error_message=f"HTTP {resp.status_code}: {resp.text[:200]}",
                    error_type="provider_error", status_code=resp.status_code
                )
        except Exception as e:
            return RequestResult(success=False, error_message=str(e), error_type="request_exception")

    def _make_gemini_request(self, provider_name, config, messages, model=None, **kwargs):
        """Make request to Google Gemini provider"""

        import requests as _requests

        endpoint = config.get("endpoint", "")
        current_key = self._get_current_api_key(provider_name)

        gemini_messages = []
        system_instruction = None
        for msg in messages:
            if msg["role"] == "system":
                system_instruction = {"parts": [{"text": msg["content"]}]}
            else:
                role = "user" if msg["role"] == "user" else "model"
                gemini_messages.append({"role": role, "parts": [{"text": msg["content"]}]})

        payload = {"contents": gemini_messages}
        if system_instruction:
            payload["systemInstruction"] = system_instruction
        payload["generationConfig"] = {
            "maxOutputTokens": config.get("max_tokens", 4096),
            "temperature": config.get("temperature", 0.7)
        }

        sep = "&" if "?" in endpoint else "?"
        url = f"{endpoint}{sep}key={current_key}"

        timeout = config.get("timeout", 60)
        try:
            resp = _requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                return RequestResult(
                    success=True, content=content, provider_used=provider_name,
                    model_used=model, status_code=200
                )
            else:
                return RequestResult(
                    success=False, error_message=f"Gemini {resp.status_code}: {resp.text[:200]}",
                    error_type="provider_error", status_code=resp.status_code
                )
        except Exception as e:
            return RequestResult(success=False, error_message=str(e), error_type="request_exception")

    def _make_cohere_request(self, provider_name, config, messages, model=None, **kwargs):
        """Make request to Cohere provider"""

        import requests as _requests

        endpoint = config.get("endpoint", "https://api.cohere.com/v2/chat")
        current_key = self._get_current_api_key(provider_name)

        headers = {"Content-Type": "application/json"}
        if current_key:
            headers["Authorization"] = f"Bearer {current_key}"

        chat_history = []
        preamble = ""
        for msg in messages:
            if msg["role"] == "system":
                preamble = msg["content"]
            else:
                chat_history.append({"role": msg["role"], "message": msg["content"]})

        payload = {
            "model": model or config.get("model", "command"),
            "messages": chat_history
        }
        if preamble:
            payload["preamble"] = preamble

        timeout = config.get("timeout", 60)
        try:
            resp = _requests.post(endpoint, json=payload, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("message", {}).get("content", [{}])[0].get("text", "")
                return RequestResult(
                    success=True, content=content, provider_used=provider_name,
                    model_used=model, status_code=200
                )
            else:
                return RequestResult(
                    success=False, error_message=f"Cohere {resp.status_code}: {resp.text[:200]}",
                    error_type="provider_error", status_code=resp.status_code
                )
        except Exception as e:
            return RequestResult(success=False, error_message=str(e), error_type="request_exception")

    def _make_a3z_request(self, provider_name, config, messages, model=None, **kwargs):
        """Make request to A3Z-style provider (GET-based)"""

        import requests as _requests

        endpoint = config.get("endpoint", "")
        user_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        url = f"{endpoint}?message={_requests.utils.quote(user_msg)}"

        timeout = config.get("timeout", 30)
        try:
            resp = _requests.get(url, timeout=timeout)
            if resp.status_code == 200:
                return RequestResult(
                    success=True, content=resp.text, provider_used=provider_name,
                    model_used=model, status_code=200
                )
            else:
                return RequestResult(
                    success=False, error_message=f"A3Z {resp.status_code}",
                    error_type="provider_error", status_code=resp.status_code
                )
        except Exception as e:
            return RequestResult(success=False, error_message=str(e), error_type="request_exception")

    def _make_cloudflare_request(self, provider_name, config, messages, model=None, **kwargs):
        """Make request to Cloudflare Workers AI"""

        import requests as _requests

        endpoint = config.get("endpoint", "")
        current_key = self._get_current_api_key(provider_name)

        headers = {"Content-Type": "application/json"}
        if current_key:
            headers["Authorization"] = f"Bearer {current_key}"

        user_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        payload = {"messages": [{"role": "user", "content": user_msg}], "stream": False}

        timeout = config.get("timeout", 60)
        try:
            resp = _requests.post(endpoint, json=payload, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                result = data.get("result", data)
                content = result.get("response", "") or result.get("result", "")
                return RequestResult(
                    success=True, content=content, provider_used=provider_name,
                    model_used=model, status_code=200
                )
            else:
                return RequestResult(
                    success=False, error_message=f"Cloudflare {resp.status_code}: {resp.text[:200]}",
                    error_type="provider_error", status_code=resp.status_code
                )
        except Exception as e:
            return RequestResult(success=False, error_message=str(e), error_type="request_exception")
