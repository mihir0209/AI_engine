"""
Provider request methods — extracted from ai_engine.py monolith.
Mixin class that AI_engine inherits from to keep all methods accessible via self.
"""
import json
import logging
from typing import Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Circuit breaker thresholds per provider (configurable)
_PROVIDER_CIRCUIT_THRESHOLDS: Dict[str, Dict] = {
    "default": {"failure_threshold": 5, "recovery_timeout": 60, "half_open_max": 3},
    "groq": {"failure_threshold": 3, "recovery_timeout": 30, "half_open_max": 2},
    "gemini": {"failure_threshold": 3, "recovery_timeout": 45, "half_open_max": 2},
    "openrouter": {"failure_threshold": 4, "recovery_timeout": 60, "half_open_max": 3},
    "nvidia": {"failure_threshold": 4, "recovery_timeout": 60, "half_open_max": 3},
    "cerebras": {"failure_threshold": 4, "recovery_timeout": 60, "half_open_max": 3},
}


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

    def _get_circuit_breaker(self, provider_name: str):
        """Get or create a circuit breaker for a provider."""
        try:
            from core.infrastructure import get_circuit_breaker
        except ImportError:
            return None
        cb_name = f"provider:{provider_name}"
        thresholds = _PROVIDER_CIRCUIT_THRESHOLDS.get(
            provider_name, _PROVIDER_CIRCUIT_THRESHOLDS["default"]
        )
        cb = get_circuit_breaker(
            cb_name,
            failure_threshold=thresholds["failure_threshold"],
            recovery_timeout=thresholds["recovery_timeout"],
            half_open_max_calls=thresholds["half_open_max"],
        )
        return cb

    def _make_request(self, provider_name, config, messages, model=None, **kwargs):
        """Make a request to a specific provider, with circuit breaker protection."""
        cb = self._get_circuit_breaker(provider_name)
        if cb and not cb.can_execute():
            return RequestResult(
                success=False,
                error_message=f"Circuit breaker OPEN for {provider_name} — too many recent failures",
                error_type="circuit_open",
                provider_used=provider_name,
            )

        try:
            format_type = config.get('format', 'openai')

            if format_type == 'openai':
                result = self._make_openai_request(provider_name, config, messages, model, **kwargs)
            elif format_type == 'anthropic':
                result = self._make_anthropic_request(provider_name, config, messages, model, **kwargs)
            elif format_type == 'vertex_ai':
                result = self._make_vertex_ai_request(provider_name, config, messages, model, **kwargs)
            elif format_type == 'azure_openai':
                result = self._make_azure_openai_request(provider_name, config, messages, model, **kwargs)
            elif format_type == 'bedrock':
                result = self._make_bedrock_request(provider_name, config, messages, model, **kwargs)
            elif format_type == 'gemini':
                result = self._make_gemini_request(provider_name, config, messages, model, **kwargs)
            elif format_type == 'cohere':
                result = self._make_cohere_request(provider_name, config, messages, model, **kwargs)
            elif format_type == 'cloudflare':
                result = self._make_cloudflare_request(provider_name, config, messages, model, **kwargs)
            elif format_type == 'a3z_get':
                result = self._make_a3z_request(provider_name, config, messages, model, **kwargs)
            else:
                result = self._make_openai_request(provider_name, config, messages, model, **kwargs)

            if cb:
                if result.success:
                    cb.record_success()
                else:
                    cb.record_failure()
            return result
        except Exception as e:
            if cb:
                cb.record_failure()
            return RequestResult(
                success=False,
                error_message=f"Provider request failed: {str(e)}",
                error_type="provider_exception"
            )

    def _make_azure_openai_request(self, provider_name, config, messages, model=None, **kwargs):
        """Make request to Azure OpenAI provider"""

        import requests as _requests

        endpoint = config.get("endpoint", "")
        config.get("api_keys", [])
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
        """Make request to AWS Bedrock provider using the Converse API."""
        import requests as _requests
        import json
        import hashlib
        import hmac
        import datetime

        endpoint = config.get("endpoint", "")
        current_key = self._get_current_api_key(provider_name)
        region = config.get("region", "us-east-1")

        if not current_key:
            return RequestResult(success=False, error_message="No API key available", error_type="auth_error")

        # Extract model from endpoint or use config model
        model_id = model or config.get("model", "anthropic.claude-3-sonnet-20240229-v1:0")

        # Build the Converse API request
        api_url = f"{endpoint}/model/{model_id}/converse"

        # Convert messages to Bedrock Converse format
        bedrock_messages = []
        system_prompt = None

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                system_prompt = content
                continue

            bedrock_content = [{"text": content}]
            bedrock_messages.append({
                "role": role,
                "content": bedrock_content,
            })

        payload = {
            "messages": bedrock_messages,
            "inferenceConfig": {
                "maxTokens": config.get("max_tokens", 4096),
                "temperature": config.get("temperature", 0.7),
            },
        }

        if system_prompt:
            payload["system"] = [{"text": system_prompt}]

        # AWS Signature V4 signing
        now = datetime.datetime.now(datetime.timezone.utc)
        date_stamp = now.strftime("%Y%m%d")
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")

        # Parse access key and secret from the API key (format: access_key:secret_key)
        key_parts = current_key.split(":", 1) if ":" in current_key else [current_key, ""]
        access_key = key_parts[0]
        secret_key = key_parts[1] if len(key_parts) > 1 else ""

        # Create canonical request
        payload_bytes = json.dumps(payload).encode("utf-8")
        payload_hash = hashlib.sha256(payload_bytes).hexdigest()

        headers_to_sign = {
            "content-type": "application/json",
            "host": endpoint.replace("https://", "").replace("http://", ""),
            "x-amz-date": amz_date,
            "x-amz-content-sha256": payload_hash,
        }

        signed_headers = ";".join(sorted(headers_to_sign.keys()))
        canonical_headers = "".join(f"{k}:{v}\n" for k, v in sorted(headers_to_sign.items()))

        canonical_request = "\n".join([
            "POST",
            f"/model/{model_id}/converse",
            "",
            canonical_headers,
            signed_headers,
            payload_hash,
        ])

        # Create string to sign
        credential_scope = f"{date_stamp}/{region}/aws4_request"
        string_to_sign = "\n".join([
            "AWS4-HMAC-SHA256",
            amz_date,
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ])

        # Calculate signature
        def _sign(key, msg):
            return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

        k_date = _sign(("AWS4" + secret_key).encode("utf-8"), date_stamp)
        k_region = _sign(k_date, region)
        k_service = _sign(k_region, "bedrock")
        k_signing = _sign(k_service, "aws4_request")
        signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

        # Build authorization header
        auth_header = (
            f"AWS4-HMAC-SHA256 Credential={access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )

        request_headers = {
            "Content-Type": "application/json",
            "Host": headers_to_sign["host"],
            "X-Amz-Date": amz_date,
            "X-Amz-Content-Sha256": payload_hash,
            "Authorization": auth_header,
        }

        timeout = config.get("timeout", 60)
        try:
            resp = _requests.post(api_url, headers=request_headers, data=payload_bytes, timeout=timeout)

            if resp.status_code == 200:
                data = resp.json()
                # Extract text from Converse response
                output = data.get("output", {})
                message = output.get("message", {})
                content_blocks = message.get("content", [])
                content = " ".join(block.get("text", "") for block in content_blocks if "text" in block)

                return RequestResult(
                    success=True,
                    content=content,
                    provider_used=provider_name,
                    model_used=model_id,
                    status_code=200,
                    raw_response=data,
                )
            else:
                return RequestResult(
                    success=False,
                    error_message=f"Bedrock {resp.status_code}: {resp.text[:200]}",
                    error_type="provider_error",
                    status_code=resp.status_code,
                )
        except Exception as e:
            return RequestResult(success=False, error_message=str(e), error_type="request_exception")

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
            try:
                from core.http_client import stream_sse
                for data_str in stream_sse(endpoint, headers=headers, json_body=payload, timeout=timeout):
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
                return
            except Exception:
                # Fall back to direct requests streaming
                pass

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
        """Make request to Vertex AI provider using the Gemini API format."""
        import requests as _requests

        current_key = self._get_current_api_key(provider_name)
        project_id = config.get("project_id", "")
        location = config.get("region", "us-central1")

        if not current_key:
            return RequestResult(success=False, error_message="No API key available", error_type="auth_error")

        model_id = model or config.get("model", "gemini-1.5-pro")

        # Build Vertex AI endpoint
        api_url = (
            f"https://{location}-aiplatform.googleapis.com/v1/"
            f"projects/{project_id}/locations/{location}"
            f"/publishers/google/models/{model_id}:generateContent"
        )

        # Convert messages to Vertex AI format
        contents = []
        system_instruction = None

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                system_instruction = content
                continue

            # Vertex AI uses "user" and "model" roles
            vertex_role = "user" if role == "user" else "model"
            contents.append({
                "role": vertex_role,
                "parts": [{"text": content}],
            })

        payload = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": config.get("max_tokens", 4096),
                "temperature": config.get("temperature", 0.7),
            },
        }

        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {current_key}",
        }

        timeout = config.get("timeout", 60)
        try:
            resp = _requests.post(api_url, headers=headers, json=payload, timeout=timeout)

            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                content = ""
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    content = " ".join(part.get("text", "") for part in parts)

                return RequestResult(
                    success=True,
                    content=content,
                    provider_used=provider_name,
                    model_used=model_id,
                    status_code=200,
                    raw_response=data,
                )
            else:
                return RequestResult(
                    success=False,
                    error_message=f"Vertex AI {resp.status_code}: {resp.text[:200]}",
                    error_type="provider_error",
                    status_code=resp.status_code,
                )
        except Exception as e:
            return RequestResult(success=False, error_message=str(e), error_type="request_exception")

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
