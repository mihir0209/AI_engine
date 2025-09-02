# AI Engine v3.0 - Technical Documentation

## Architecture Overview

AI Engine v3.0 is a sophisticated multi-provider AI management system designed for enterprise applications requiring high availability, intelligent routing, and robust error handling. The system features an autodecide mechanism for automatic model-to-provider matching and comprehensive provider lifecycle management.

## Core Components

### 1. AI Engine Core (`ai_engine.py`)

The main engine class responsible for:
- **Provider Management**: Loading, configuring, and monitoring 24 AI providers
- **Request Routing**: Intelligent provider selection based on priorities and health status
- **Error Handling**: Comprehensive error classification and recovery mechanisms
- **Key Rotation**: Automatic API key rotation on authentication failures
- **Autodecide System**: Intelligent model discovery and provider matching

### 2. Configuration System (`config.py`)

Centralized configuration management with:
- **Provider Definitions**: Complete configuration for all 24 supported providers
- **Engine Settings**: Configurable timeouts, failure limits, and behavior options
- **Autodecide Configuration**: Caching and discovery settings
- **Environment Integration**: Secure API key loading from environment variables

### 3. FastAPI Server (`server.py`)

Production-ready web server providing:
- **OpenAI-Compatible APIs**: Standard chat completion endpoints
- **Provider Management**: REST APIs for provider configuration and testing
- **Web Dashboard**: Real-time monitoring and management interface
- **Autodecide Endpoints**: APIs for model discovery and intelligent routing

### 4. Statistics Manager (`statistics_manager.py`)

Performance monitoring system featuring:
- **Real-Time Metrics**: Success rates, response times, and error tracking
- **Provider Scoring**: Dynamic performance-based provider ranking
- **Persistent Storage**: Optional statistics persistence across sessions
- **Health Monitoring**: Automatic provider health assessment

## Supported Providers

### OpenAI-Compatible Providers (14)
- **OpenAI**: Official OpenAI API with GPT models
- **Groq**: High-performance inference with Llama and Mixtral models
- **Cerebras**: Ultra-fast inference with optimized hardware
- **Paxsenix**: Multi-model provider with competitive pricing
- **Chi**: Specialized provider with enhanced model variants
- **Samurai**: Community provider with diverse model selection
- **A4F**: Provider focused on latest model versions
- **Mango**: High-availability provider with redundancy
- **TypeGPT**: Specialized in text generation and completion
- **OpenRouter**: Meta-provider aggregating multiple AI services
- **NVIDIA**: Official NVIDIA AI services and models
- **Vercel**: Edge-optimized AI inference platform
- **GitHub**: GitHub Copilot and related AI services
- **Pawan**: Community provider with free tier options

### Native Format Providers (3)
- **Google Gemini**: Official Google AI with Gemini model family
- **Cohere**: Cohere's enterprise AI models and embeddings
- **Cloudflare Workers**: Cloudflare's edge AI infrastructure

### No-Authentication Providers (3)
- **A3Z**: Free access provider for testing and development
- **Omegatron**: Open access provider with rate limiting
- **Offline**: Local Ollama server integration for on-premise deployment

### Additional Providers (4)
- **Flowith**: Specialized workflow-optimized models
- **MiniMax**: Chinese AI provider with multilingual models
- **Anthropic**: Claude model family (via compatible providers)
- **Meta**: Llama model family (via multiple providers)

## Autodecide System

### Model Discovery Process

The autodecide system automatically discovers which providers support requested models through:

1. **Model Normalization**: Converts various model name formats to standardized form
2. **Provider Query**: Checks each provider's available models via API endpoints
3. **Compatibility Matching**: Uses fuzzy matching to find compatible models
4. **Priority Ranking**: Orders providers by configured priority and performance
5. **Caching**: Stores results for 60 minutes to improve performance

### Model Name Handling

The system intelligently handles various model naming conventions:

```python
# All these resolve to the same model family
"gpt-4" -> "gpt4"
"GPT-4" -> "gpt4" 
"gpt_4" -> "gpt4"
"gpt-4-turbo" -> "gpt4turbo"
"claude-3" -> "claude3"
"llama-3.1" -> "llama31"
```

### Provider Selection Algorithm

```python
def _select_best_provider(self, providers: List[Dict]) -> Dict:
    """
    Selection criteria (in order):
    1. Provider health (not flagged)
    2. Provider priority (lower number = higher priority)
    3. Performance score (success rate + speed)
    4. Available API keys
    """
```

## Error Classification and Handling

### Error Types and Responses

| Error Type | Triggers | Action | Recovery Time |
|------------|----------|--------|---------------|
| `rate_limit` | "rate limit", "too many requests" | Key rotation + provider flagging | 1 hour |
| `auth_error` | "unauthorized", "invalid api key" | Key rotation + provider flagging | 1 hour |
| `quota_exceeded` | "quota", "billing", "usage limit" | Key rotation + provider flagging | 1 hour |
| `service_unavailable` | HTTP 503, "unavailable", "maintenance" | Provider flagging only | 10 minutes |
| `server_error` | HTTP 5xx, "internal error" | Provider flagging only | 10 minutes |
| `network_error` | Connection timeout, DNS failures | Provider flagging only | 10 minutes |
| `bad_request` | HTTP 400, malformed request | Immediate provider switch | None |
| `unknown` | Unclassified errors | Provider flagging | 30 minutes |

### Error Recovery Mechanism

```python
def _handle_provider_success(self, provider_name: str, response_time: float):
    """
    Automatic recovery on successful response:
    1. Remove provider from flagged list
    2. Reset consecutive failure counter
    3. Update performance statistics
    4. Log recovery event
    """
```

## API Key Management

### Multi-Key Configuration

Each provider supports up to 3 API keys for redundancy:

```bash
# Primary key
OPENAI_API_KEY=primary_key_here

# Backup keys (optional)
OPENAI_API_KEY_2=backup_key_here
OPENAI_API_KEY_3=tertiary_key_here
```

### Rotation Logic

```python
def _rotate_api_key(self, provider_name: str) -> Optional[str]:
    """
    Key rotation algorithm:
    1. Identify current key index
    2. Move to next available key
    3. Skip None/empty keys
    4. Wrap around to first key if at end
    5. Return None if no valid keys available
    """
```

### Security Considerations

- **Environment Variables**: All keys stored in `.env` files
- **No Code Embedding**: Zero API keys in source code
- **Rotation Logging**: Key usage tracked without exposing keys
- **Error Sanitization**: Keys never appear in error messages or logs

## Performance Optimization

### Provider Priority System

Providers are ordered by priority (1 = highest priority):

```python
PROVIDER_PRIORITIES = {
    'paxsenix': 1,      # Primary choice
    'chi': 2,           # Secondary choice
    'gemini': 3,        # Third choice
    # ... etc
}
```

### Caching Strategy

- **Model Discovery Cache**: 60-minute TTL for provider discovery results
- **Performance Metrics**: Real-time success rate and response time tracking
- **Health Status Cache**: Flagged provider status with automatic expiry

### Performance Scoring

```python
def calculate_score(success_rate: float, avg_response_time: float) -> float:
    """
    Performance score calculation:
    - 60% weight on success rate
    - 40% weight on speed (inverse of response time)
    - Normalized to 0-100 scale
    """
    speed_score = max(0, 100 - (avg_response_time * 10))
    return (success_rate * 0.6) + (speed_score * 0.4)
```

## Production Deployment

### Environment Setup

```bash
# Required environment variables
OPENAI_API_KEY=your_openai_key
GEMINI_API_KEY=your_gemini_key
ANTHROPIC_API_KEY=your_anthropic_key
# ... additional keys as needed

# Optional configuration
AI_ENGINE_LOG_LEVEL=INFO
AI_ENGINE_TIMEOUT=30
AI_ENGINE_MAX_RETRIES=3
```

### Docker Configuration

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Environment variables from external source
ENV PYTHONPATH=/app

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "server.py"]
```

### Scaling Considerations

- **Stateless Design**: No persistent state between requests
- **Horizontal Scaling**: Multiple instances can run concurrently
- **Load Balancing**: Compatible with standard HTTP load balancers
- **Circuit Breaker**: Built-in provider failure detection and recovery

## Integration Examples

### Direct Integration

```python
from ai_engine import get_ai_engine

# Initialize once, reuse everywhere
engine = get_ai_engine(verbose=False)

# Standard chat completion
def get_ai_response(user_message: str) -> str:
    messages = [{"role": "user", "content": user_message}]
    result = engine.chat_completion(messages)
    
    if result.success:
        return result.content
    else:
        raise Exception(f"AI request failed: {result.error_message}")

# Smart model selection
def get_model_response(user_message: str, preferred_model: str) -> str:
    messages = [{"role": "user", "content": user_message}]
    result = engine.chat_completion(
        messages, 
        model=preferred_model, 
        autodecide=True
    )
    
    return result.content if result.success else None
```

### FastAPI Integration

```python
from fastapi import FastAPI, HTTPException
from ai_engine import get_ai_engine

app = FastAPI()
engine = get_ai_engine()

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    result = engine.chat_completion(request.messages)
    
    if result.success:
        return {
            "content": result.content,
            "provider": result.provider_used,
            "model": result.model_used,
            "response_time": result.response_time
        }
    else:
        raise HTTPException(
            status_code=500, 
            detail=f"AI request failed: {result.error_message}"
        )
```

## Monitoring and Debugging

### Logging Configuration

```python
import logging

# Enable detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Engine with verbose output
engine = get_ai_engine(verbose=True)
```

### Health Monitoring

```python
# Check engine health
def check_engine_health(engine):
    """
    Returns comprehensive health status
    """
    return {
        'total_providers': len(engine.providers),
        'enabled_providers': engine.enabled_providers_count,
        'flagged_providers': len(engine.flagged_keys),
        'key_rotation_enabled': engine.key_rotation_enabled,
        'consecutive_failure_limit': engine.consecutive_failure_limit
    }
```

### Performance Metrics

```python
# Get detailed statistics
stats = engine.statistics_manager.get_statistics()

# Key metrics to monitor
metrics = {
    'total_requests': stats.get('total_requests', 0),
    'success_rate': stats.get('overall_success_rate', 0),
    'average_response_time': stats.get('average_response_time', 0),
    'provider_health': {
        name: data.get('success_rate', 0) 
        for name, data in stats.get('provider_stats', {}).items()
    }
}
```

## Troubleshooting

### Common Issues

1. **No Valid API Keys**
   - Check `.env` file exists and contains valid keys
   - Verify environment variable names match config
   - Test individual keys with provider APIs

2. **All Providers Flagged**
   - Check network connectivity
   - Verify API key validity and quotas
   - Review error logs for specific failure reasons

3. **Slow Response Times**
   - Enable autodecide to use fastest providers
   - Check provider status and health
   - Consider timeout adjustments

4. **High Error Rates**
   - Monitor provider-specific error rates
   - Check for quota limitations
   - Verify request format compatibility

### Debug Commands

```bash
# Check engine status
python ai_engine.py status

# Test specific provider
python ai_engine.py test groq "test message"

# Run comprehensive tests
python ai_engine.py stress

# View provider list
python ai_engine.py list

# Start debug server
python server.py --debug
```

## Future Enhancements

### Planned Features

1. **Advanced Caching**: Redis/Memcached integration for distributed caching
2. **Provider Analytics**: Detailed cost and usage analytics per provider
3. **Custom Models**: Support for fine-tuned and custom model endpoints
4. **Load Balancing**: Intelligent request distribution across healthy providers
5. **Async Support**: Full asyncio support for concurrent request handling
6. **Provider Marketplace**: Dynamic provider discovery and registration

### API Evolution

The system is designed for extensibility with:
- **Plugin Architecture**: Easy addition of new providers
- **Configuration Templates**: Standardized provider configuration
- **Middleware Support**: Request/response modification hooks
- **Event System**: Comprehensive event hooks for monitoring and customization

## Security Best Practices

### API Key Security
- Store keys in environment variables only
- Use separate keys for development/staging/production
- Rotate keys regularly and update configuration
- Monitor key usage for unusual patterns

### Network Security
- Use HTTPS for all API communications
- Implement request/response logging for audit trails
- Consider VPN or private networks for sensitive deployments
- Apply rate limiting and DDoS protection

### Data Privacy
- Review each provider's data handling policies
- Implement request sanitization for sensitive data
- Consider on-premise deployment for highly sensitive use cases
- Enable logging controls to prevent data leakage

This documentation covers the complete technical architecture and implementation details of AI Engine v3.0. For additional support, refer to the GitHub repository issues and discussions.
