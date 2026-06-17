# API Documentation

## Base URL

```
http://localhost:8000
```

## Authentication

Management endpoints require API key via `X-API-Key` header:

```bash
curl -H "X-API-Key: your-admin-api-key" ...
```

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| `/v1/chat/completions` | 10 req/min |
| `/api/test-model` | 5 req/min |
| Other | No limit |

---

## Chat Completions

### POST `/v1/chat/completions`

OpenAI-compatible chat completions endpoint.

**Request Body:**

```json
{
  "model": "gpt-4",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"}
  ],
  "temperature": 0.7,
  "max_tokens": 1000
}
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| model | string | No | Model name (default: auto-select) |
| messages | array | Yes | Array of message objects |
| temperature | float | No | Sampling temperature (0-2) |
| max_tokens | int | No | Max tokens to generate |
| stream | bool | No | Enable streaming (use `/stream` endpoint) |

**Headers:**

| Header | Description |
|--------|-------------|
| X-Preferred-Provider | Force specific provider |

**Response:**

```json
{
  "id": "chatcmpl-123456",
  "object": "chat.completion",
  "created": 1700000000,
  "model": "openai/gpt-4",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Hello! How can I help you?"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 8,
    "total_tokens": 18
  }
}
```

---

### POST `/v1/chat/completions/stream`

Streaming chat completions (SSE).

**Response:**

```
data: {"id":"chatcmpl-123","object":"chat.completion.chunk","choices":[{"delta":{"content":"Hello"},"finish_reason":null}]}

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","choices":[{"delta":{"content":"!"},"finish_reason":null}]}

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","choices":[{}],"finish_reason":"stop"}

data: [DONE]
```

---

## Models

### GET `/v1/models`

List all available models across providers.

**Response:**

```json
{
  "object": "list",
  "data": [
    {"id": "openai|gpt-4", "object": "model", "created": 1700000000, "owned_by": "openai"},
    {"id": "anthropic|claude-3", "object": "model", "created": 1700000000, "owned_by": "anthropic"}
  ]
}
```

---

## Providers

### GET `/api/providers`

List all provider configurations (sanitized - no API keys).

**Response:**

```json
{
  "openai": {
    "id": 10,
    "priority": 11,
    "endpoint": "https://api.openai.com/v1/chat/completions",
    "model": "gpt-4-turbo-preview",
    "enabled": true,
    "keys_count": 3,
    "has_keys": true
  }
}
```

---

### POST `/api/providers/{name}/toggle`

Enable or disable a provider. **Requires API key.**

**Request Body:**

```json
{"enabled": false}
```

**Headers:**

| Header | Required |
|--------|----------|
| X-API-Key | Yes |

---

### POST `/api/providers/{name}/roll-key`

Rotate to next API key. **Requires API key.**

---

### POST `/api/providers/{name}/change-model`

Change provider model. **Requires API key.**

**Request Body:**

```json
{"model": "gpt-4-turbo"}
```

---

### GET `/api/providers/{name}/models`

Discover available models for a provider.

**Response:**

```json
{
  "provider": "openai",
  "models": [
    {"id": "gpt-4", "name": "gpt-4", "owned_by": "openai"}
  ],
  "total_models": 50,
  "discovery_available": true
}
```

---

## Status & Statistics

### GET `/api/status`

Get engine status.

**Response:**

```json
{
  "total_providers": 22,
  "enabled_providers": 20,
  "disabled_providers": 2,
  "available_providers": 18,
  "flagged_providers": 2,
  "current_provider": "openai",
  "flagged_details": [...]
}
```

---

### GET `/api/statistics`

Get usage statistics.

**Response:**

```json
{
  "summary": {
    "total_providers": 22,
    "total_keys": 66,
    "total_requests": 1500,
    "overall_success_rate": "94.5%"
  },
  "providers": {
    "openai": {
      "Key #1": {"requests": 500, "successes": 480, "failures": 20}
    }
  },
  "timestamp": "2024-01-15T10:30:00"
}
```

---

### POST `/api/test-model`

Test a specific model with a provider. **Rate limited: 5/min.**

**Request Body:**

```json
{
  "provider": "openai",
  "model": "gpt-4",
  "message": "Hello! Please respond with a test message."
}
```

**Response:**

```json
{
  "success": true,
  "provider": "openai",
  "model": "gpt-4",
  "response": "Hello! I'm working correctly.",
  "response_time": 1.23,
  "timestamp": "2024-01-15T10:30:00"
}
```

---

## Autodecide

### GET `/api/autodecide/{model}`

Discover which providers have a specific model.

**Response:**

```json
{
  "model": "gpt-4",
  "autodecide_enabled": true,
  "providers": [
    {"provider": "openai", "model": "gpt-4", "priority": 1, "enabled": true},
    {"provider": "a4f", "model": "gpt-4", "priority": 5, "enabled": true}
  ],
  "total_providers": 2
}
```

---

### POST `/api/autodecide/test`

Test autodecide functionality.

**Request Body:**

```json
{
  "model": "gpt-4",
  "message": "Hello! This is a test of the autodecide feature."
}
```

---

## Chat Module

### GET `/api/chat/chats`

List all chats.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| include_temporary | bool | false | Include temporary chats |
| limit | int | 50 | Max chats to return |

---

### POST `/api/chat/chats`

Create a new chat.

**Request Body:**

```json
{
  "title": "My Chat",
  "model": "gpt-4",
  "provider": "openai",
  "system_prompt": "You are a helpful assistant.",
  "is_temporary": false,
  "force_provider": false
}
```

---

### GET `/api/chat/chats/{id}`

Get chat with messages.

---

### PUT `/api/chat/chats/{id}`

Update chat properties.

---

### DELETE `/api/chat/chats/{id}`

Delete a chat.

---

### POST `/api/chat/chats/{id}/messages`

Send a message to a chat.

**Request Body:**

```json
{
  "role": "user",
  "content": "Hello!"
}
```

---

### GET `/api/chat/chats/{id}/messages`

Get messages for a chat.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| limit | int | 100 | Max messages |
| after_id | int | - | Get messages after this ID |

---

### GET `/api/chat/chats/{id}/export`

Export chat conversation.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| format | string | markdown | Export format: `markdown` or `json` |

**Response (Markdown):**

```json
{
  "export": "# My Chat\n\n**User:**\nHello!\n\n**Assistant:**\nHi there!",
  "format": "markdown"
}
```

**Response (JSON):**

```json
{
  "chat": {"id": 1, "title": "My Chat", ...},
  "messages": [{"role": "user", "content": "Hello!"}, ...]
}
```

---

### WebSocket `/api/chat/chats/{id}/stream`

Real-time chat streaming via WebSocket.

**Client Messages:**

```json
{"type": "user_message", "content": "Hello!", "model": "gpt-4"}
```

**Server Messages:**

```json
{"type": "ai_thinking", "provider": "openai", "model": "gpt-4"}
{"type": "ai_typing_keepalive"}
{"type": "ai_chunk", "content": "Hello", "is_final": false}
{"type": "ai_complete", "message_id": 1, "provider": "openai", "model": "gpt-4"}
```

---

## Health Check

### GET `/health`

**Response:**

```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00"
}
```

---

## Metrics

### GET `/metrics`

Prometheus-compatible metrics endpoint.

**Response:** Plain text metrics format

**Available Metrics:**

| Metric | Type | Description |
|--------|------|-------------|
| `ai_engine_requests_total` | Counter | Total requests by endpoint/method/status |
| `ai_engine_request_latency_seconds` | Histogram | Request latency by endpoint |
| `ai_engine_chat_completions_total` | Counter | Chat completions by provider/success |
| `ai_engine_active_providers` | Gauge | Number of active providers |

---

## Web Dashboard

| Route | Description |
|-------|-------------|
| `/` | Main dashboard |
| `/providers` | Provider management |
| `/statistics` | Usage statistics |
| `/models` | Model browser |
| `/chat` | Chat interface |

---

## Interactive API Docs

- **Swagger UI**: `/docs`
- **ReDoc**: `/redoc`
- **OpenAPI JSON**: `/openapi.json`
