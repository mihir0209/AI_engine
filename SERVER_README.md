# AI Engine FastAPI Server

A FastAPI-based REST API server for the AI Engine v3.0 with web dashboard.

## Features

### 🚀 API Endpoints
- **Chat Completions** (`/v1/chat/completions`) - OpenAI-compatible chat completions
- **Models List** (`/v1/models`) - List all available models by provider
- **Statistics** (`/api/statistics`) - Comprehensive key usage statistics
- **Status** (`/api/status`) - Engine status and health information
- **Providers** (`/api/providers`) - Provider configurations and status

### 🖥️ Web Dashboard
- **Dashboard** (`/`) - Real-time monitoring and charts
- **Providers** (`/providers`) - Provider management interface
- **Statistics** (`/statistics`) - Detailed analytics and reports
- **Models** (`/models`) - Model selection and testing interface

### 📚 Documentation
- **API Docs** (`/docs`) - Interactive Swagger UI documentation
- **ReDoc** (`/redoc`) - Alternative API documentation
- **OpenAPI JSON** (`/openapi.json`) - OpenAPI specification

## Installation

1. Install server dependencies:
```bash
pip install -r requirements_server.txt
```

2. Make sure you have the main AI Engine dependencies installed

## Usage

### Start the Server

```bash
# From the AI_engine directory
python server.py
```

Or from the main AI Engine:

```bash
python ai_engine.py server
```

### Access Points

- **Web Dashboard**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## API Examples

### Chat Completion
```bash
curl -X POST "http://localhost:8000/v1/chat/completions" \
     -H "Content-Type: application/json" \
     -d '{
       "model": "auto",
       "messages": [
         {"role": "user", "content": "Hello, how are you?"}
       ]
     }'
```

### List Models
```bash
curl -X GET "http://localhost:8000/v1/models"
```

### Get Statistics
```bash
curl -X GET "http://localhost:8000/api/statistics"
```

## Architecture

The server is designed as a separate module that imports the main AI Engine components:

- `server.py` - FastAPI application and routes
- `ai_engine.py` - Core AI Engine logic
- `statistics_manager.py` - Statistics tracking and persistence
- `config.py` - Provider configurations

This separation ensures the server is optional and doesn't clutter the main engine code.

## Configuration

The server automatically uses your existing AI Engine configuration. No additional configuration is required.

## Development

The server includes:
- Auto-reload during development
- Comprehensive error handling
- Background task processing for statistics
- Responsive web interface
- Real-time updates via JavaScript

## Production Deployment

For production use, consider:
- Using a production ASGI server (e.g., Gunicorn + Uvicorn)
- Setting up proper logging
- Adding authentication and rate limiting
- Using environment variables for configuration
- Setting up monitoring and health checks
