# User Guide

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone <repo-url>
cd AI_engine

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt -r requirements_server.txt

# Copy environment template
cp .env.example .env
# Edit .env with your API keys
```

### 2. Start Server

```bash
python server.py
```

Server starts at `http://localhost:8000`

### 3. Open Dashboard

Visit `http://localhost:8000` in your browser.

---

## Using the Chat Interface

### Create a Chat

1. Click "New Chat" in the sidebar
2. Enter a title
3. Select a model (or leave as "auto" for automatic selection)
4. Click "Create"

### Send Messages

1. Type your message in the input box
2. Press Enter or click Send
3. AI response appears automatically

### Chat Features

- **Edit Messages**: Click the edit icon on any message
- **Regenerate**: Click the regenerate icon to get a new AI response
- **Export**: Click export to download as Markdown or JSON
- **Branch**: Create alternative conversation paths from any message

---

## API Usage

### Chat Completions (OpenAI Compatible)

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [
      {"role": "user", "content": "Hello!"}
    ]
  }'
```

### Streaming

```bash
curl -X POST http://localhost:8000/v1/chat/completions/stream \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [
      {"role": "user", "content": "Tell me a story"}
    ]
  }'
```

### List Models

```bash
curl http://localhost:8000/v1/models
```

### Force Provider

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-Preferred-Provider: openai" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

---

## Provider Configuration

### Add API Keys

Edit `.env` file:

```bash
OPENAI_API_KEY=sk-your-key
GEMINI_API_KEY=your-gemini-key
GROQ_API_KEY=your-groq-key
```

### Enable/Disable Providers

Via API (requires admin key):

```bash
curl -X POST http://localhost:8000/api/providers/openai/toggle \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-admin-key" \
  -d '{"enabled": false}'
```

### Rotate API Keys

```bash
curl -X POST http://localhost:8000/api/providers/openai/roll-key \
  -H "X-API-Key: your-admin-key"
```

---

## File Upload

### Upload Text File

```bash
curl -X POST http://localhost:8000/api/chat/upload \
  -F "file=@document.txt"
```

### Upload to Chat

```bash
curl -X POST http://localhost:8000/api/chat/upload?chat_id=1 \
  -F "file=@code.py"
```

### Supported Formats

**Text files**: .txt, .md, .json, .csv, .py, .js, .ts, .html, .css, .yaml, .yml, .xml

**Images**: .png, .jpg, .jpeg, .gif, .webp

**Max size**: 10MB

---

## Conversation Branching

### Create Branch

```bash
curl -X POST http://localhost:8000/api/chat/chats/1/branch/5
```

### List Branches

```bash
curl http://localhost:8000/api/chat/chats/1/branches
```

### Switch Branch

```bash
curl -X POST http://localhost:8000/api/chat/chats/1/branches/1/switch
```

---

## Search

### Search Messages

```bash
curl -X POST http://localhost:8000/api/chat/search \
  -H "Content-Type: application/json" \
  -d '{"query": "python", "limit": 10}'
```

---

## Export

### Export as Markdown

```bash
curl http://localhost:8000/api/chat/chats/1/export?format=markdown
```

### Export as JSON

```bash
curl http://localhost:8000/api/chat/chats/1/export?format=json
```

---

## Monitoring

### Health Check

```bash
curl http://localhost:8000/health
```

### Provider Health

```bash
curl http://localhost:8000/api/providers/health
```

### Statistics

```bash
curl http://localhost:8000/api/statistics
```

### Prometheus Metrics

```bash
curl http://localhost:8000/metrics
```

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Enter | Send message |
| Shift+Enter | New line |
| Ctrl+L | Clear chat |
| Ctrl+E | Export chat |
| Ctrl+N | New chat |

---

## Troubleshooting

### Server won't start

1. Check if port 8000 is in use
2. Verify all dependencies are installed
3. Check `.env` file exists with API keys

### API returns 401/403

1. Verify `ADMIN_API_KEY` is set for management endpoints
2. Check API key in `X-API-Key` header

### Provider errors

1. Check API key is valid
2. Check rate limits
3. Use `/api/providers/health` to check status

### File upload fails

1. Check file size (max 10MB)
2. Verify file extension is allowed
3. Ensure `uploads/` directory exists

---

## Getting Help

- **API Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **GitHub Issues**: <repo-url>/issues
