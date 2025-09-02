# AI Engine v3.0 FastAPI Server

A production-ready FastAPI server providing OpenAI-compatible APIs and a comprehensive web dashboard for AI Engine v3.0 provider management.

## Overview

The AI Engine server transforms the core AI Engine into a web service with REST APIs, real-time monitoring, and an intuitive management interface. It provides OpenAI-compatible endpoints for seamless integration with existing applications while adding advanced features like autodecide model routing and comprehensive provider management.

## Features

### REST API Endpoints

#### OpenAI-Compatible APIs
- **`POST /v1/chat/completions`** - Standard chat completion endpoint with autodecide support
- **`GET /v1/models`** - List all available models across providers
- **`GET /health`** - Health check endpoint for load balancers

#### AI Engine Management APIs
- **`GET /api/status`** - Comprehensive engine status and provider health
- **`GET /api/providers`** - Provider configurations and real-time status
- **`POST /api/providers/{provider}/test`** - Test individual providers
- **`POST /api/providers/{provider}/toggle`** - Enable/disable providers
- **`POST /api/providers/{provider}/roll-key`** - Rotate provider API keys
- **`GET /api/statistics`** - Performance metrics and usage statistics

#### Autodecide APIs
- **`GET /api/autodecide/{model}`** - Discover providers for specific models
- **`POST /api/autodecide/test`** - Test autodecide functionality with custom requests

### Web Dashboard

#### Dashboard (`/`)
- Real-time engine status monitoring
- Provider health overview with success rates
- Performance metrics and response time charts
- System configuration display

#### Providers Page (`/providers`)
- Complete provider management interface
- Individual provider testing with live results
- API key rotation controls
- Provider enable/disable toggles
- Real-time status updates

#### Models Page (`/models`)
- Provider-specific model configuration
- Model discovery and testing interface
- Provider card layout with detailed information
- Model endpoint testing and validation

#### Statistics Page (`/statistics`)
- Comprehensive performance analytics
- Provider comparison charts
- Historical data visualization
- Export capabilities for reporting

### Interactive Documentation
- **`/docs`** - Swagger UI with interactive API testing
- **`/redoc`** - Alternative documentation interface
- **`/openapi.json`** - OpenAPI specification for integration

## Installation and Setup

### Prerequisites

```bash
# Core AI Engine dependencies
pip install -r requirements.txt

# Additional server dependencies
pip install -r requirements_server.txt
```

### Environment Configuration

Create a `.env` file with your API keys:

```bash
# Core providers
OPENAI_API_KEY=your_openai_key
GEMINI_API_KEY=your_gemini_key
GROQ_API_KEY=your_groq_key

# Additional providers (add as needed)
PAXSENIX_API_KEY=your_paxsenix_key
CHI_API_KEY=your_chi_key
ANTHROPIC_API_KEY=your_anthropic_key

# Optional: Multiple keys for rotation
OPENAI_API_KEY_2=backup_openai_key
GROQ_API_KEY_2=backup_groq_key
```

### Starting the Server

```bash
# Method 1: Direct server startup
python server.py

# Method 2: Through AI Engine CLI
python ai_engine.py server

# Method 3: With custom configuration
python server.py --host 0.0.0.0 --port 8080 --reload
```

### Access Points

Once started, the server provides:

- **Web Dashboard**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health
- **Provider Management**: http://localhost:8000/providers
- **Statistics**: http://localhost:8000/statistics

## API Usage Examples

### Chat Completion (OpenAI Compatible)

```bash
# Standard chat completion
curl -X POST "http://localhost:8000/v1/chat/completions" \
     -H "Content-Type: application/json" \
     -d '{
       "model": "gpt-4",
       "messages": [
         {"role": "user", "content": "Explain quantum computing"}
       ]
     }'

# With autodecide enabled
curl -X POST "http://localhost:8000/v1/chat/completions" \
     -H "Content-Type: application/json" \
     -d '{
       "model": "gpt-4",
       "messages": [
         {"role": "user", "content": "Hello world"}
       ],
       "autodecide": true
     }'
```

### Model Discovery

```bash
# List all available models
curl -X GET "http://localhost:8000/v1/models"

# Discover providers for specific model
curl -X GET "http://localhost:8000/api/autodecide/gpt-4"

# Test autodecide functionality
curl -X POST "http://localhost:8000/api/autodecide/test" \
     -H "Content-Type: application/json" \
     -d '{
       "model": "claude",
       "message": "Test message"
     }'
```

### Provider Management

```bash
# Get provider status
curl -X GET "http://localhost:8000/api/providers"

# Test specific provider
curl -X POST "http://localhost:8000/api/providers/groq/test" \
     -H "Content-Type: application/json" \
     -d '{"message": "Test message"}'

# Toggle provider status
curl -X POST "http://localhost:8000/api/providers/openai/toggle"

# Rotate API keys
curl -X POST "http://localhost:8000/api/providers/openai/roll-key"
```

### Statistics and Monitoring

```bash
# Get engine status
curl -X GET "http://localhost:8000/api/status"

# Get detailed statistics
curl -X GET "http://localhost:8000/api/statistics"
```

## Architecture

### Server Structure

```
server.py                 # Main FastAPI application
├── AI Engine Integration # Core engine functionality
├── Route Handlers        # API endpoint implementations
├── Web Interface         # Dashboard and management pages
├── Static Assets         # CSS, JavaScript, images
└── Templates            # HTML templates for web pages
```

### Key Components

#### FastAPI Application
- **CORS Support**: Cross-origin request handling for web dashboard
- **Error Handling**: Comprehensive error catching and response formatting
- **Request Validation**: Pydantic models for API request/response validation
- **Background Tasks**: Asynchronous processing for statistics and monitoring

#### Template System
- **Jinja2 Templates**: Dynamic HTML generation with real-time data
- **Bootstrap 5**: Modern, responsive UI framework
- **JavaScript Integration**: Real-time updates and interactive functionality
- **Modal Interfaces**: Provider testing and configuration modals

#### Static Assets
- **CSS Styling**: Custom dashboard styling with dark/light theme support
- **JavaScript Logic**: Real-time API calls and UI updates
- **Image Assets**: Provider logos and system icons

### Security Features

- **Input Validation**: All API inputs validated with Pydantic models
- **Error Sanitization**: API keys and sensitive data removed from error responses
- **CORS Configuration**: Controlled cross-origin access
- **Rate Limiting**: Built-in request throttling (configurable)

## Web Dashboard Features

### Real-Time Monitoring

The dashboard provides live updates of:
- Provider health status
- Success rates and response times
- Active/flagged provider counts
- Recent request statistics

### Provider Management

Each provider can be managed through the web interface:
- **Test Provider**: Send test messages and view responses
- **Toggle Status**: Enable or disable providers
- **Rotate Keys**: Trigger API key rotation
- **View Configuration**: See provider settings and priorities

### Interactive Testing

- **Model Discovery**: Test autodecide functionality with any model name
- **Provider Testing**: Send custom messages to specific providers
- **Performance Monitoring**: View real-time response times and success rates
- **Error Analysis**: Detailed error reporting and classification

## Production Deployment

### Docker Deployment

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt requirements_server.txt ./
RUN pip install -r requirements.txt && \
    pip install -r requirements_server.txt

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Start server
CMD ["python", "server.py"]
```

### Environment Variables

```bash
# Required for production
AI_ENGINE_HOST=0.0.0.0
AI_ENGINE_PORT=8000
AI_ENGINE_WORKERS=4

# Optional configuration
AI_ENGINE_LOG_LEVEL=INFO
AI_ENGINE_ACCESS_LOG=true
AI_ENGINE_RELOAD=false

# Security settings
AI_ENGINE_CORS_ORIGINS=["https://yourdomain.com"]
AI_ENGINE_MAX_REQUEST_SIZE=10485760  # 10MB
```

### Nginx Configuration

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket support for real-time updates
    location /ws {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ai-engine-server
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ai-engine-server
  template:
    metadata:
      labels:
        app: ai-engine-server
    spec:
      containers:
      - name: ai-engine-server
        image: ai-engine:latest
        ports:
        - containerPort: 8000
        env:
        - name: AI_ENGINE_HOST
          value: "0.0.0.0"
        - name: AI_ENGINE_PORT
          value: "8000"
        envFrom:
        - secretRef:
            name: ai-engine-secrets
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: ai-engine-service
spec:
  selector:
    app: ai-engine-server
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8000
  type: LoadBalancer
```

## Development

### Running in Development Mode

```bash
# Start with auto-reload and debug logging
python server.py --reload --debug

# Or with environment variables
export AI_ENGINE_RELOAD=true
export AI_ENGINE_LOG_LEVEL=DEBUG
python server.py
```

### Adding New Endpoints

```python
# Example: Adding a new provider endpoint
@app.post("/api/providers/{provider_name}/custom-action")
async def custom_provider_action(provider_name: str, request: CustomRequest):
    try:
        # Validate provider exists
        if provider_name not in ai_engine.providers:
            raise HTTPException(status_code=404, detail="Provider not found")
        
        # Perform custom action
        result = ai_engine.custom_action(provider_name, request.data)
        
        return {"success": True, "result": result}
    
    except Exception as e:
        logger.error(f"Custom action failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### Frontend Development

The web interface uses:
- **Bootstrap 5**: For responsive layouts and components
- **Vanilla JavaScript**: For API interactions and real-time updates
- **Chart.js**: For performance visualization (optional)
- **WebSocket**: For real-time dashboard updates (planned feature)

### Testing

```bash
# Run API tests
python -m pytest tests/test_server.py

# Test specific endpoints
curl -X GET "http://localhost:8000/health"
curl -X GET "http://localhost:8000/api/status"

# Load testing
ab -n 100 -c 10 http://localhost:8000/api/status
```

## Monitoring and Logging

### Application Logs

The server provides comprehensive logging:

```python
# Access logs (requests/responses)
127.0.0.1 - "GET /api/status HTTP/1.1" 200

# Application logs (business logic)
2025-09-03 10:30:15 - ai_engine - INFO - Provider groq successful (1.23s)
2025-09-03 10:30:16 - server - INFO - Chat completion successful: groq

# Error logs (failures and exceptions)
2025-09-03 10:30:17 - ai_engine - ERROR - Provider openai failed: rate limit exceeded
```

### Metrics Collection

The server exposes metrics for monitoring:

```bash
# Provider health metrics
curl -X GET "http://localhost:8000/api/statistics" | jq '.provider_stats'

# System performance metrics
curl -X GET "http://localhost:8000/api/status" | jq '.performance'
```

### Health Checks

Multiple health check levels:

```bash
# Basic health (server running)
curl -X GET "http://localhost:8000/health"

# Detailed health (engine status)
curl -X GET "http://localhost:8000/api/status"

# Provider health (individual providers)
curl -X GET "http://localhost:8000/api/providers"
```

## Troubleshooting

### Common Issues

1. **Server Won't Start**
   - Check port availability: `netstat -an | grep 8000`
   - Verify dependencies: `pip list | grep fastapi`
   - Check environment variables: `env | grep AI_ENGINE`

2. **API Keys Not Working**
   - Verify `.env` file location and format
   - Check environment variable names match config
   - Test individual provider APIs directly

3. **Web Dashboard Not Loading**
   - Check static file serving: `curl http://localhost:8000/static/css/dashboard.css`
   - Verify template rendering: Check server logs for template errors
   - Clear browser cache and cookies

4. **Slow API Responses**
   - Enable autodecide for faster provider selection
   - Check provider health: `curl http://localhost:8000/api/providers`
   - Monitor response times: `curl http://localhost:8000/api/statistics`

### Debug Commands

```bash
# Start server with maximum logging
python server.py --log-level DEBUG --reload

# Test all providers
curl -X GET "http://localhost:8000/api/providers" | jq '.[] | select(.enabled == true)'

# Check autodecide functionality
curl -X GET "http://localhost:8000/api/autodecide/gpt-4"

# Monitor real-time logs
tail -f ai_engine_server.log
```

## Security Considerations

### API Security
- Input validation on all endpoints
- Rate limiting to prevent abuse
- Error message sanitization
- CORS policy enforcement

### Data Protection
- API keys stored in environment variables only
- No sensitive data in logs or responses
- Secure session handling for web interface
- HTTPS enforcement in production

### Access Control
- Consider implementing authentication for production
- Role-based access for different API endpoints
- IP whitelisting for admin functions
- Audit logging for sensitive operations

## Contributing

To contribute to the server component:

1. Fork the repository
2. Create a feature branch
3. Add tests for new endpoints
4. Update documentation
5. Submit a pull request

### Code Standards

- Follow FastAPI best practices
- Use Pydantic models for request/response validation
- Include comprehensive error handling
- Add logging for all major operations
- Write unit tests for new endpoints

The AI Engine v3.0 server provides a production-ready interface for the core AI Engine functionality, making it easy to integrate with existing applications while providing powerful management and monitoring capabilities.
