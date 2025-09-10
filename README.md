# AI Engine v3.0 - Enterprise AI Provider Management

## Overview

AI Engine v3.0 is an enterprise-grade Python system for managing multiple AI providers with automatic failover, intelligent API key rotation, real-time error detection, and smart model-to-provider matching through the **autodecide** feature.

## Key Features

### Multi-Provider Support
- **23 AI Providers**: Comprehensive ecosystem including OpenAI, Google Gemini, Anthropic Claude, Meta Llama, and more
- **Universal Compatibility**: Support for OpenAI-compatible APIs, native formats, and specialized providers
- **No-Auth Options**: Providers that don't require API keys for testing and development

### Intelligent Model Discovery
- **Threaded Model Discovery**: Fast parallel discovery of 1300+ models from all providers
- **Automatic Model Caching**: 30-minute smart cache with background refresh
- **Provider-Specific Models**: Real-time model lists from each provider's API

### Verbose Mode Control
- **Production-Ready Startup**: Clean server startup with essential URLs only
- **Debug Mode**: Comprehensive logging with emoji indicators and threading progress
- **Configurable Logging**: Global verbose control via `config.py`

### Robust API Key Management
- **Multi-Key Support**: Up to 3 API keys per provider with automatic rotation
- **Error-Based Rotation**: Automatic key switching on rate limits, auth errors, quota exceeded
- **Real-Time Detection**: Live analysis of API responses triggers immediate rotation
- **Graceful Degradation**: Seamless fallback when keys are exhausted

### Advanced Error Handling
- **Intelligent Classification**: 8 distinct error types with specific handling strategies
- **Self-Healing System**: Automatic provider recovery and unflagging
- **Performance Monitoring**: Real-time success rates and response time tracking
- **Comprehensive Logging**: Detailed error analysis and debugging information

### FastAPI Web Server
- **RESTful API**: OpenAI-compatible endpoints for seamless integration
- **Interactive Web Dashboard**: Real-time monitoring with provider management interface
- **Model Discovery Interface**: Test model discovery and provider capabilities
- **Chat Interface**: Direct web-based chat with provider selection
- **Statistics Dashboard**: Performance analytics and provider health monitoring

### Security & Configuration
- **Environment Variables**: Secure API key storage using `.env` files
- **No Hardcoded Secrets**: All sensitive data externally managed
- **Configurable Limits**: Adjustable failure thresholds and timeout settings
- **Production Ready**: Enterprise-grade security and error handling

## Installation & Setup Options

AI Engine v3.0 offers flexible deployment options based on your needs. Choose the setup that matches your use case:

### 🎯 Setup Options Overview

| Use Case | Files Needed | Dependencies | Size | Best For |
|----------|-------------|--------------|------|----------|
| **Minimal API** | Core files only | 3 packages | ~20% | API integration, lightweight apps |
| **Full Server** | All files | 9 packages | 100% | Web dashboard, chat interface |
| **Production** | Core + server | 9 packages | ~80% | Clean deployment, no tests |
| **Development** | All files | 9 packages | 100% | Testing, examples, debugging |

---

### 🔥 Option 1: Minimal API Setup (Lightweight)

**Best for**: API integration, microservices, lightweight applications

```bash
# 1. Clone repository
git clone https://github.com/mihir0209/AI_engine.git
cd AI_engine

# 2. Install core dependencies only (3 packages)
pip install -r requirements.txt

# 3. Keep only essential files:
# ✅ ai_engine.py, config.py, statistics_manager.py, model_cache.py, .env
# 🗑️ Remove: server.py, chat_module/, templates/, static/, test_*.py
```

**Usage**:
```python
from ai_engine import AI_engine
engine = AI_engine()
result = engine.chat_completion([{"role": "user", "content": "Hello"}])
print(result.content)
```

**Size**: ~20% of full installation | **Dependencies**: requests, aiohttp, python-dotenv

---

### 🌐 Option 2: Full Server Setup (Complete Experience)

**Best for**: Web dashboard, chat interface, full feature access

```bash
# 1. Clone repository
git clone https://github.com/mihir0209/AI_engine.git
cd AI_engine

# 2. Install all dependencies
pip install -r requirements.txt
pip install -r requirements_server.txt

# 3. Keep all files for full functionality
```

**Features**: Web dashboard, chat interface, real-time monitoring, model discovery UI

**Size**: 100% of installation | **Dependencies**: 9 packages including FastAPI, Uvicorn

---

### 🚀 Option 3: Production Setup (Clean Deployment)

**Best for**: Production environments, clean deployments

```bash
# 1. Clone repository
git clone https://github.com/mihir0209/AI_engine.git
cd AI_engine

# 2. Install dependencies based on needs
pip install -r requirements.txt
pip install -r requirements_server.txt  # Only if web interface needed

# 3. Remove development files:
rm test_*.py PROVIDER_TESTING_REPORT.py
rm -rf __pycache__/ *.log
```

**Size**: ~80% of installation | **Features**: Core + server without tests

---

### 🛠️ Option 4: Development Setup (Full Features)

**Best for**: Development, testing, learning the system

```bash
# 1. Clone repository
git clone https://github.com/mihir0209/AI_engine.git
cd AI_engine

# 2. Install all dependencies
pip install -r requirements.txt
pip install -r requirements_server.txt

# 3. Keep all files including tests
```

**Features**: Examples, tests, full documentation

**Size**: 100% of installation | **Includes**: All test files, test scripts, examples

---

### 🔧 Configuration

3. Configure API keys in `.env` file:
```bash
# Core providers
OPENAI_API_KEY=your_openai_key
GEMINI_API_KEY=your_gemini_key
ANTHROPIC_API_KEY=your_anthropic_key

# Additional providers (see Configuration section for full list)
GROQ_API_KEY=your_groq_key
PAXSENIX_API_KEY=your_paxsenix_key
# ... add more as needed
```

### Basic Usage

```python
from ai_engine import AI_engine

# Initialize the engine
engine = AI_engine(verbose=True)

# Chat completion with automatic provider selection
messages = [{"role": "user", "content": "Explain quantum computing"}]
result = engine.chat_completion(messages)

if result.success:
    print(f"Response: {result.content}")
    print(f"Provider: {result.provider_used}")
    print(f"Model: {result.model_used}")
    print(f"Response time: {result.response_time:.2f}s")
else:
    print(f"Error: {result.error_message}")
```

### Autodecide Feature (Smart Model Matching)

```python
# Automatically find providers for any model
result = engine.chat_completion(
    messages=[{"role": "user", "content": "Hello!"}],
    model="gpt-4",  # Engine will find the best provider for gpt-4
    autodecide=True
)

# Works with various model name formats
models_to_try = ["gpt-4", "gpt4", "GPT-4", "claude", "llama", "gemini"]
for model in models_to_try:
    result = engine.chat_completion(messages, model=model, autodecide=True)
    if result.success:
        print(f"{model} -> {result.provider_used} with {result.model_used}")
```

### Web Server Usage

```bash
# Start the FastAPI server
python server.py

# Clean startup (verbose_mode: False)
🚀 Starting AI Engine FastAPI Server...
📊 Dashboard: http://localhost:8000
📚 API Docs: http://localhost:8000/docs
🔴 ReDoc: http://localhost:8000/redoc
📝 Server logs: ai_engine_server.log
```

### Verbose Mode Control

```python
# In config.py - Global setting
ENGINE_SETTINGS = {
    "verbose_mode": False,  # Clean production startup
    # "verbose_mode": True,  # Full debug output
}

# Or instance-level override
engine = AI_engine(verbose=True)  # Force verbose for this instance
```

## Architecture

### Core Components

```
AI_engine/
├── ai_engine.py          # Core engine with provider management
├── server.py             # FastAPI web server
├── config.py             # Provider configurations
├── statistics_manager.py # Performance tracking
├── templates/            # Web interface templates
└── static/              # Web assets (CSS, JS)
```

### Provider Configuration

The system supports 23 providers across different categories:

**OpenAI-Compatible Providers:**
- OpenAI, Groq, Cerebras, Paxsenix, Chi, Samurai, A4F, Mango, TypeGPT
- OpenRouter, NVIDIA, Vercel, GitHub, Pawan, CR (Close Router)

**Native Format Providers:**
- Google Gemini, Cohere, Cloudflare Workers, Flowith, MiniMax

**No-Auth Providers:**
- A3Z, Omegatron (no API keys required)

**Local/Offline:**
- Ollama integration for local models

### Model Discovery System

The engine automatically discovers 1300+ models using threaded discovery:

```python
# Threaded model discovery from all providers
🔍 Discovering models from 21 providers using threading...
✅ a4f: discovered 160 models
✅ groq: discovered 21 models  
✅ nvidia: discovered 159 models
✅ openrouter: discovered 326 models
✅ vercel: discovered 113 models
# ... continues for all providers
✅ Model discovery completed. Found 1310 models total.
💾 Saved 1310 models to cache
```

### Verbose Mode Behavior

**Production Mode (`verbose_mode: False`)**:
```
🚀 Starting AI Engine FastAPI Server...
📊 Dashboard: http://localhost:8000
📚 API Docs: http://localhost:8000/docs
🔴 ReDoc: http://localhost:8000/redoc
📝 Server logs: ai_engine_server.log
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Debug Mode (`verbose_mode: True`)**:
```
🚀 Starting AI Engine FastAPI Server...
📊 Dashboard: http://localhost:8000
📚 API Docs: http://localhost:8000/docs
🔴 ReDoc: http://localhost:8000/redoc
📝 Server logs: ai_engine_server.log
Provider flowith disabled: No valid API keys found
Provider minimax disabled: No valid API keys found
Loaded 19 enabled providers out of 23 total
🚀 AI Engine v3.0 initialized with 19 providers
🔍 Discovering models from 21 providers using threading...
✅ a4f: discovered 160 models
# ... full discovery details
```

### Error Classification System

The engine classifies errors into 8 categories with specific handling:

| Error Type | Trigger | Action | Recovery Time |
|------------|---------|--------|---------------|
| `rate_limit` | Too many requests | Key rotation + flagging | 1 hour |
| `auth_error` | Invalid API key | Key rotation + flagging | 1 hour |
| `quota_exceeded` | Daily/monthly limit | Key rotation + flagging | 1 hour |
| `service_unavailable` | Provider down | Provider flagging | 10 minutes |
| `server_error` | 5xx HTTP errors | Provider flagging | 10 minutes |
| `network_error` | Connection issues | Provider flagging | 10 minutes |
| `bad_request` | Invalid request | Immediate switch | None |
| `unknown` | Unclassified errors | Provider flagging | 30 minutes |

## API Reference

### Core Methods

#### `chat_completion(messages, model=None, preferred_provider=None, autodecide=False)`

Main method for generating AI responses.

**Parameters:**
- `messages` (list): Chat messages in OpenAI format
- `model` (str, optional): Specific model to use
- `preferred_provider` (str, optional): Preferred provider name
- `autodecide` (bool): Enable automatic model-to-provider matching

**Returns:**
- `RequestResult` object with success status, content, provider info, and timing

#### `test_specific_provider(provider_name, message)`

Test a specific provider with a message.

**Parameters:**
- `provider_name` (str): Provider to test
- `message` (str): Test message

**Returns:**
- `RequestResult` object with test results

#### `stress_test_all_providers(iterations=3)`

Run comprehensive testing across all providers.

**Parameters:**
- `iterations` (int): Number of test iterations per provider

**Returns:**
- Dictionary with test results for each provider

### FastAPI Endpoints

#### `POST /v1/chat/completions`

OpenAI-compatible chat completions endpoint.

```json
{
  "model": "gpt-4",
  "messages": [
    {"role": "user", "content": "Hello!"}
  ],
  "autodecide": true
}
```

#### `GET /v1/models`

List all available models across providers (1300+ models total).

```bash
curl -X GET "http://localhost:8000/v1/models"
# Returns: {"object": "list", "data": [{"id": "gpt-4", "object": "model", "owned_by": "openai"}, ...]}
```

#### `GET /api/status`

Engine status and health information.

```bash
curl -X GET "http://localhost:8000/api/status"
# Returns: Provider counts, health status, flagged providers
```

#### `GET /api/providers`

Provider configurations and current status.

#### `GET /api/providers/{provider}/models`

Get models for a specific provider.

```bash
curl -X GET "http://localhost:8000/api/providers/groq/models" 
# Returns: {"discovery_available": true, "models": [...], "total_models": 21}
```

#### `GET /api/autodecide/{model}`

Discover providers for a specific model.

```bash
curl -X GET "http://localhost:8000/api/autodecide/gpt-4"
# Returns: {"model": "gpt-4", "providers": [...], "total_providers": 5}
```

#### `POST /api/autodecide/test`

Test autodecide functionality with a model and message.

```bash
curl -X POST "http://localhost:8000/api/autodecide/test" \
     -H "Content-Type: application/json" \
     -d '{"model": "claude", "message": "Hello!"}'
```

#### `GET /api/statistics`

Comprehensive performance statistics and provider analytics.

### Web Dashboard Pages

#### `/` - Main Dashboard
- Real-time engine status and provider health
- Performance metrics with success rates
- Quick provider testing interface

#### `/providers` - Provider Management
- Individual provider testing and configuration
- API key rotation controls
- Provider enable/disable toggles

#### `/models` - Model Discovery
- Provider-specific model browsing
- Model testing and validation
- Real-time model discovery status

#### `/statistics` - Analytics Dashboard
- Performance analytics and trends
- Provider comparison charts
- Historical data visualization

#### `/chat` - Interactive Chat Interface
- Direct chat with provider selection
- Model-specific conversations
- Real-time response testing

## Configuration

### Environment Variables

Create a `.env` file with your API keys:

```bash
# OpenAI ecosystem
OPENAI_API_KEY=your_key
OPENAI_API_KEY_2=backup_key  # Optional backup

# Google
GEMINI_API_KEY=your_key

# Anthropic
ANTHROPIC_API_KEY=your_key

# Other providers
GROQ_API_KEY=your_key
etc etc
```

### Engine Settings

Modify `config.py` to customize behavior:

```python
ENGINE_SETTINGS = {
    "default_timeout": 60,           # Request timeout (seconds)
    "max_retries": 3,                # Maximum retry attempts
    "enable_auto_rotation": True,    # Enable automatic key rotation
    "consecutive_failure_limit": 5,  # Failures before flagging
    "key_rotation_enabled": True,    # Enable key rotation
    "provider_rotation_enabled": True, # Enable provider rotation on failure
    "verbose_mode": False,           # Global verbose mode for debugging/logging
    "stress_test_settings": {
        "min_pass_percentage": 75,   # Minimum pass rate for stress tests
        "test_iterations": 3,        # Number of test iterations per provider
        "test_timeout": 30,          # Timeout for individual tests
        "concurrent_tests": 2,       # Number of concurrent tests
    },
    "priority_settings": {
        "enable_dynamic_priority": True,    # Dynamic priority reranking
        "success_rate_weight": 0.4,         # Weight for success rate in scoring
        "response_time_weight": 0.3,        # Weight for response time in scoring
        "cost_weight": 0.2,                 # Weight for cost in scoring
        "reliability_weight": 0.1,          # Weight for reliability in scoring
        "rerank_interval_hours": 24         # How often to rerank providers
    }
}

AUTODECIDE_CONFIG = {
    "enabled": True,                 # Enable autodecide feature
    "cache_duration": 1800,          # Model discovery cache time (30 minutes)
    "model_cache": {}                # In-memory cache storage
}
```

## Command Line Interface

The engine provides a comprehensive CLI:

```bash
# Chat with automatic provider selection
python ai_engine.py auto "Explain machine learning"

# Test specific provider
python ai_engine.py groq "What is quantum computing?"

# Use autodecide with specific model
python ai_engine.py autodecide "gpt-4" "Hello world"

# System management
python ai_engine.py status          # Engine status
python ai_engine.py list            # List providers
python ai_engine.py stress          # Stress test all providers

# Start web server
python server.py                    # Start FastAPI server with clean startup
python server.py --verbose          # Start with full debug output
```

## Model Discovery & Caching

The system automatically discovers and caches models:

### Discovery Process
```bash
# Background threaded discovery on server startup
🔍 Discovering models from 21 providers using threading...
✅ a4f: discovered 160 models
✅ groq: discovered 21 models
✅ nvidia: discovered 159 models
✅ openrouter: discovered 326 models
# ... continues for all providers
✅ Model discovery completed. Found 1310 models total.
💾 Saved 1310 models to cache
```

### Cache Management
- **Duration**: 30 minutes automatic refresh
- **Storage**: JSON file (`model_cache.json`)
- **Background Refresh**: Fresh discovery on server startup
- **Fallback**: Default models if discovery fails

### Model Endpoints
- **`/v1/models`**: All 1300+ discovered models
- **`/api/providers/{provider}/models`**: Provider-specific models
- **Manual Discovery**: Background threading with 30s timeout

## Performance Benchmarks

Based on recent testing (results may vary):

| Provider | Success Rate | Avg Response Time | Performance Score |
|----------|-------------|------------------|-------------------|
| Cerebras | 100% | 1.08s | 91.3 |
| Groq | 100% | 1.23s | 90.2 |
| TypeGPT | 100% | 1.36s | 89.1 |
| Paxsenix | 100% | 1.38s | 89.0 |
| Gemini | 100% | 2.26s | 81.9 |
| NVIDIA | 100% | 2.46s | 80.3 |

*Performance Score = (Success Rate × 60%) + (Speed Score × 40%)*

## Development 

### Development Setup

1. Fork the repository
2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
```
3. Install development dependencies:
```bash
pip install -r requirements.txt
pip install -r requirements_server.txt
```
4. Set up your `.env` file with test API keys
5. Run tests to ensure everything works

## Production Deployment

### Docker Deployment

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY . .

RUN pip install -r requirements.txt
RUN pip install -r requirements_server.txt

EXPOSE 8000

CMD ["python", "server.py"]
```

### Environment Considerations

- Use environment variables for all API keys
- Set up proper logging and monitoring
- Configure rate limiting and authentication
- Use a production ASGI server (Gunicorn + Uvicorn)
- Set up health checks and auto-restart

## 📚 Documentation & Setup Guides

- **[SETUP_GUIDE.md](SETUP_GUIDE.md)** - Complete setup guide for all use cases
- **[SERVER_README.md](SERVER_README.md)** - Web server and API documentation  
- **[AI_ENGINE_DOCUMENTATION.md](AI_ENGINE_DOCUMENTATION.md)** - Technical documentation
- **[QUICKSTART.md](QUICKSTART.md)** - Quick start examples

## Support

- GitHub Issues: Report bugs and request features
- Documentation: Comprehensive guides and API reference

## Contribute
- If you want to contribute in this project, feel free to do it.
- If you know some more free tier providers then please contribute here in config file...