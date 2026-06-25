import os
import json
import time
import uuid
import asyncio
import aiohttp
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks, Header
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import uvicorn
import logging

# Structured logging setup
logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","module":"%(module)s","message":"%(message)s"}'
)
logger = logging.getLogger(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter('ai_engine_requests_total', 'Total requests', ['endpoint', 'method', 'status'])
REQUEST_LATENCY = Histogram('ai_engine_request_latency_seconds', 'Request latency', ['endpoint'])
CHAT_COMPLETIONS = Counter('ai_engine_chat_completions_total', 'Total chat completions', ['provider', 'success'])
ACTIVE_PROVIDERS = Gauge('ai_engine_active_providers', 'Number of active providers')

# Import AI Engine components
try:
    from core.ai_engine import AI_engine
    from core.statistics_manager import get_stats_manager
    from config import verbose_print, ENGINE_SETTINGS, AI_CONFIGS
    from core.model_cache import shared_model_cache
    # Import chat module
    from chat_module.router import router as chat_router
    # Import new modules
    from core.caching import lru_cache, request_deduplicator
    from core.middleware import metrics_collector, RequestTracker
    from core.capabilities import capability_manager, error_message_manager
    from core.infrastructure import health_checker
    from core.logging_sla import sla_monitor
    from core.health_monitor import health_monitor
    from core.latency_tracker import latency_tracker
    from core.rate_limit_manager import rate_limit_manager
    from core.usage_tracker import usage_tracker
except ImportError as e:
    print(f"Failed to import AI Engine components: {e}")
    print("Make sure you're running from the AI_engine directory")
    exit(1)

# Initialize AI Engine with global verbose setting
engine = AI_engine(verbose=ENGINE_SETTINGS.get("verbose_mode", False))
stats_manager = get_stats_manager()

# API Key Authentication for management endpoints
# Set ADMIN_API_KEY environment variable to enable (leave empty to disable)
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")

def verify_admin_api_key(api_key: str = Header(None, alias="X-API-Key")) -> bool:
    """Verify admin API key for management endpoints"""
    if not ADMIN_API_KEY:
        # In development mode (no key set), allow access with warning
        verbose_print("Warning: ADMIN_API_KEY not set - management endpoints unprotected", True)
        return True
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")
    if api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return True

# Set the global engine in chat module to prevent duplicate initialization
try:
    from chat_module.router import set_global_engine
    set_global_engine(engine)
except ImportError:
    verbose_print("⚠️ Could not set global engine in chat module")

# Initialize shared model cache
shared_model_cache.load_cache()

# Lifespan event handler for FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events"""
    # Startup
    import threading

    def initialize_cache():
        """Initialize cache in background thread - ALWAYS refresh on startup"""
        try:
            verbose_print("🚀 Initializing fresh model cache on server startup...")
            verbose_print("🔄 Skipping old cache - refreshing models from providers...")

            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                result = loop.run_until_complete(discover_and_cache_models())
                verbose_print(f"✅ Fresh model cache initialized with {len(result['data'])} models")
            except Exception as e:
                verbose_print(f"❌ Error during cache initialization: {e}")
            finally:
                loop.close()

        except Exception as e:
            verbose_print(f"❌ Critical error in cache initialization: {e}")

    def refresh_cache():
        """Refresh cache function for auto-refresh"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(discover_and_cache_models())
                verbose_print(f"🔄 Auto-refresh completed: {len(result['data'])} models")
            finally:
                loop.close()
        except Exception as e:
            verbose_print(f"❌ Auto-refresh failed: {e}")

    # Start fresh cache initialization in background thread
    cache_thread = threading.Thread(target=initialize_cache, daemon=True)
    cache_thread.start()
    verbose_print("🎯 Fresh model cache initialization started in background thread")

    # Start auto-refresh background task
    shared_model_cache.start_auto_refresh(refresh_cache)

    # Start temporary chat cleanup task
    try:
        from chat_module.router import start_cleanup_task
        start_cleanup_task()
        verbose_print("🧹 Temporary chat cleanup task started")
    except ImportError:
        verbose_print("⚠️ Could not start temporary chat cleanup task")

    yield  # Server is running

    # Shutdown (cleanup if needed)
    shared_model_cache.stop_auto_refresh()
    try:
        from chat_module.router import stop_cleanup_task
        stop_cleanup_task()
    except Exception:
        pass
    verbose_print("🛑 Server shutting down...")

# FastAPI app with lifespan handler
app = FastAPI(
    title="AI Engine v3.0",
    description="Advanced AI Engine with Multi-Provider Support",
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# Rate limiting configuration
# Default: 60 requests per minute for API, 10 per minute for chat completions
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add CORS middleware
# In production, set CORS_ORIGINS environment variable (comma-separated)
cors_origins_str = os.getenv("CORS_ORIGINS", "*")
cors_origins = [origin.strip() for origin in cors_origins_str.split(",")] if cors_origins_str != "*" else ["*"]

# Security: warn if using wildcard CORS with credentials
if cors_origins_str == "*":
    verbose_print("Warning: CORS_ORIGINS is set to '*' - restrict in production", True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=cors_origins_str != "*",  # Don't allow credentials with wildcard
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
templates = Jinja2Templates(directory="templates")

# Include chat router
app.include_router(chat_router)

# Request size limiting middleware
MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10MB

@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    """Limit request body size"""
    if request.method in ("POST", "PUT", "PATCH"):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_REQUEST_SIZE:
            return JSONResponse(
                status_code=413,
                content={"error": "Request too large", "max_size_mb": MAX_REQUEST_SIZE // (1024 * 1024)}
            )
    return await call_next(request)

# Rate limit headers middleware
@app.middleware("http")
async def add_rate_limit_headers(request: Request, call_next):
    """Add X-RateLimit-* headers to API responses"""
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/v1/") or path.startswith("/api/"):
        client_ip = request.client.host if request.client else "unknown"
        key = f"{client_ip}:{path}"
        if "/chat/completions" in path:
            limit = 10
        elif "/test-model" in path:
            limit = 5
        else:
            limit = 60
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - 1))
        response.headers["X-RateLimit-Policy"] = f"{limit}-per-minute"
    return response

# Request/response logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all API requests with timing"""
    import uuid
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    
    # Log request
    verbose_print(f"📥 [{request_id}] {request.method} {request.url.path}")
    
    response = await call_next(request)
    
    # Log response
    duration = time.time() - start_time
    verbose_print(f"📤 [{request_id}] {response.status_code} ({duration:.3f}s)")
    
    return response

# Request validation and sanitization

def sanitize_input(text: str) -> str:
    """Sanitize user input to prevent injection attacks"""
    if not text:
        return text
    # Remove null bytes
    text = text.replace('\x00', '')
    # Limit length to prevent DoS
    max_length = 100000  # 100KB
    if len(text) > max_length:
        text = text[:max_length]
    return text

# Pydantic models for API
class ChatMessage(BaseModel):
    role: str  # "system", "user", "assistant", "tool", "developer"
    content: Optional[str] = None  # Can be null for tool calls
    name: Optional[str] = None
    tool_calls: Optional[List[Any]] = None
    tool_call_id: Optional[str] = None

    @field_validator('role')
    @classmethod
    def validate_role(cls, v):
        if v not in ('system', 'user', 'assistant', 'tool', 'developer'):
            raise ValueError(f'role must be one of: system, user, assistant, tool, developer')
        return v

    @field_validator('content')
    @classmethod
    def validate_content(cls, v):
        if v is None:
            return None
        return sanitize_input(v)

class ChatCompletionRequest(BaseModel):
    model: str = "auto"
    messages: List[ChatMessage]
    max_tokens: Optional[int] = None
    max_completion_tokens: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    n: Optional[int] = 1
    stream: bool = False
    stream_options: Optional[Dict[str, Any]] = None
    stop: Optional[List[str]] = None
    presence_penalty: Optional[float] = None
    frequency_penalty: Optional[float] = None
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None
    tools: Optional[List[Any]] = None
    tool_choice: Optional[Any] = None
    response_format: Optional[Dict[str, Any]] = None
    seed: Optional[int] = None

class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: Optional[str] = None  # "stop", "length", "tool_calls", null
    logprobs: Optional[Any] = None

class ChatCompletionUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: Optional[ChatCompletionUsage] = None
    system_fingerprint: Optional[str] = None

class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    created: int
    owned_by: str

class ModelsResponse(BaseModel):
    object: str = "list"
    data: List[ModelInfo]

# Helper function to format OpenAI-compatible response
def format_openai_response(result, messages, request, start_time) -> ChatCompletionResponse:
    """Transform AI Engine response to OpenAI-compatible format"""

    prompt_text = " ".join([msg.get("content", "") or "" for msg in messages])
    prompt_tokens = max(1, len(prompt_text.split()) + len(prompt_text) // 4)
    completion_tokens = max(1, len(result.content.split()) + len(result.content) // 4)

    finish_reason = "stop"
    if hasattr(request, 'max_tokens') and request.max_tokens and len(result.content.split()) >= request.max_tokens:
        finish_reason = "length"

    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"

    # Use the model from the request, falling back to what the provider returned
    requested_model = getattr(request, 'model', None) or "auto"
    model_name = result.model_used or requested_model

    return ChatCompletionResponse(
        id=completion_id,
        object="chat.completion",
        created=int(start_time),
        model=model_name,
        choices=[ChatCompletionChoice(
            index=0,
            message=ChatMessage(
                role="assistant",
                content=result.content
            ),
            finish_reason=finish_reason,
            logprobs=None
        )],
        usage=ChatCompletionUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens
        ),
        system_fingerprint=None
    )

# API Routes
@app.post("/v1/chat/completions")
@limiter.limit("10/minute")
async def chat_completions(request: Request, background_tasks: BackgroundTasks, x_preferred_provider: str = Header(None, alias="X-Preferred-Provider")):
    """OpenAI-compatible chat completions endpoint - handles both streaming and non-streaming"""
    from fastapi.responses import StreamingResponse
    
    try:
        body = await request.json()
        messages = body.get("messages", [])
        model = body.get("model", "auto")
        stream = body.get("stream", False)
        tools = body.get("tools")
        tool_choice = body.get("tool_choice")
        response_format = body.get("response_format")
        temperature = body.get("temperature")
        max_tokens = body.get("max_tokens")
        
        # Validate messages
        if not messages:
            return JSONResponse(
                status_code=400,
                content={"error": {"message": "messages is required", "type": "invalid_request_error", "param": "messages", "code": "missing_messages"}}
            )
        
        # Handle streaming
        if stream:
            return await handle_streaming_response(messages, model, x_preferred_provider, background_tasks)
        
        # Non-streaming request
        start_time = asyncio.get_event_loop().time()
        result = await asyncio.to_thread(
            engine.chat_completion,
            messages=messages,
            model=model if model != "auto" else None,
            preferred_provider=x_preferred_provider
        )
        end_time = asyncio.get_event_loop().time()
        
        background_tasks.add_task(save_statistics_async)
        
        if not result.success:
            error_code = "server_error"
            status_code = 500
            if "rate_limit" in (result.error_type or "").lower():
                error_code = "rate_limit_error"
                status_code = 429
            elif "auth" in (result.error_type or "").lower():
                error_code = "authentication_error"
                status_code = 401
            elif "not_found" in (result.error_type or "").lower():
                error_code = "model_not_found"
                status_code = 404
            
            request_id = f"req-{uuid.uuid4().hex[:12]}"
            return JSONResponse(
                status_code=status_code,
                headers={"x-request-id": request_id},
                content={"error": {"message": result.error_message, "type": error_code, "param": None, "code": error_code}}
            )
        
        response = format_openai_response(result, messages, body, start_time)
        request_id = f"req-{uuid.uuid4().hex[:12]}"
        return JSONResponse(
            content=response.model_dump(),
            headers={"x-request-id": request_id}
        )
        
    except Exception as e:
        request_id = f"req-{uuid.uuid4().hex[:12]}"
        return JSONResponse(
            status_code=500,
            headers={"x-request-id": request_id},
            content={"error": {"message": str(e), "type": "server_error", "param": None, "code": "internal_error"}}
        )


async def handle_streaming_response(messages, model, preferred_provider, background_tasks):
    """Handle streaming chat completion — fully OpenAI-compatible SSE"""
    from fastapi.responses import StreamingResponse

    async def generate_stream():
        completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
        created = int(time.time())
        model_name = model if model and model != "auto" else "auto"

        def stream_from_engine():
            for chunk in engine.chat_completion_stream(
                messages=messages,
                model=model if model != "auto" else None,
                preferred_provider=preferred_provider
            ):
                yield chunk

        loop = asyncio.get_event_loop()
        stream_iter = stream_from_engine()

        # First chunk must include role
        first_chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model_name,
            "choices": [{
                "index": 0,
                "delta": {"role": "assistant", "content": ""},
                "finish_reason": None
            }]
        }
        yield f"data: {json.dumps(first_chunk)}\n\n"

        total_content = ""

        try:
            while True:
                chunk = await loop.run_in_executor(None, lambda: next(stream_iter, None))
                if chunk is None:
                    break

                if chunk.get('error'):
                    error_data = {"error": {"message": chunk['error'], "type": "server_error", "param": None, "code": None}}
                    yield f"data: {json.dumps(error_data)}\n\n"
                    break

                if chunk.get('done'):
                    break

                if chunk.get('content'):
                    total_content += chunk['content']
                    chunk_data = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model_name,
                        "choices": [{
                            "index": 0,
                            "delta": {"content": chunk['content']},
                            "finish_reason": None
                        }]
                    }
                    yield f"data: {json.dumps(chunk_data)}\n\n"
        except Exception as e:
            error_data = {"error": {"message": str(e), "type": "server_error", "param": None, "code": None}}
            yield f"data: {json.dumps(error_data)}\n\n"

        # Final chunk with finish_reason: stop
        final_chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model_name,
            "choices": [{
                "index": 0,
                "delta": {},
                "finish_reason": "stop"
            }]
        }
        yield f"data: {json.dumps(final_chunk)}\n\n"
        yield "data: [DONE]\n\n"

        background_tasks.add_task(save_statistics_async)

    request_id = f"req-{uuid.uuid4().hex[:12]}"
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "x-request-id": request_id
        }
    )


@app.post("/v1/chat/completions/stream")
@limiter.limit("10/minute")
async def chat_completions_stream_legacy(request: Request, background_tasks: BackgroundTasks, x_preferred_provider: str = Header(None, alias="X-Preferred-Provider")):
    """Legacy streaming endpoint - redirects to main endpoint with stream=true"""
    body = await request.json()
    body["stream"] = True
    return await handle_streaming_response(
        body.get("messages", []),
        body.get("model", "auto"),
        x_preferred_provider,
        background_tasks
    )

@app.get("/v1/models")
@app.post("/v1/models")
async def list_models(request: Request = None, provider: str = None, search: str = None):
    """List all available models across all providers in OpenAI-compatible format.
    
    Supports both GET and POST (some SDK clients send POST).
    """

    # Check if we have valid cached models
    if shared_model_cache.is_cache_valid():
        cached_models = shared_model_cache.get_models()
        verbose_print(f"📦 Returning {len(cached_models)} models from cache")
    else:
        # No valid cache, discover models with threading
        verbose_print("🔍 Cache miss or expired, discovering models...")
        result = await discover_and_cache_models()
        cached_models = result.get("data", [])
    
    # Apply filters
    filtered_models = []
    for model_id in cached_models:
        # Filter by provider
        if provider and not model_id.startswith(provider + "/"):
            continue
        
        # Filter by search term
        if search and search.lower() not in model_id.lower():
            continue
        
        # Format model entry
        model_parts = model_id.split("/", 1)
        provider_name = model_parts[0] if len(model_parts) > 1 else "unknown"
        model_name = model_parts[1] if len(model_parts) > 1 else model_id
        
        filtered_models.append({
            "id": model_id,
            "object": "model",
            "created": int(datetime.now().timestamp()),
            "owned_by": provider_name
        })
    
    return {"object": "list", "data": filtered_models}
async def discover_and_cache_models():
    """Discover models from all providers and cache the results"""
    import concurrent.futures

    try:
        all_models = []
        enabled_providers = {name: config for name, config in AI_CONFIGS.items() if config.get('enabled', True)}

        if not enabled_providers:
            return {"object": "list", "data": []}

        verbose_print(f"🔍 Discovering models from {len(enabled_providers)} providers using threading...")

        def discover_provider_models_sync(provider_name):
            """Synchronous wrapper for model discovery"""
            try:
                # Use the internal discovery function
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    models_response = loop.run_until_complete(discover_provider_models_internal(provider_name))
                    return models_response
                finally:
                    loop.close()
            except Exception as e:
                verbose_print(f"❌ Error discovering models for {provider_name}: {e}")
                return None

        # Use threading for faster model discovery
        max_workers = min(len(enabled_providers), 8)

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all discovery tasks
            future_to_provider = {
                executor.submit(discover_provider_models_sync, provider_name): (provider_name, config)
                for provider_name, config in enabled_providers.items()
                if config.get('model_endpoint')  # Only for providers with model discovery
            }

            # Add providers without model discovery immediately
            for provider_name, config in enabled_providers.items():
                if not config.get('model_endpoint'):
                    current_model = config.get('model', 'unknown')
                    all_models.append(f"{provider_name}/{current_model}")

            # Collect results with proper timeout handling
            try:
                for future in concurrent.futures.as_completed(future_to_provider, timeout=30):
                    provider_name, config = future_to_provider[future]
                    try:
                        models_response = future.result(timeout=10)

                        if models_response and 'models' in models_response:
                            provider_models = models_response['models']

                            # Add models to the response - store complete model names as returned by provider
                            for model in provider_models:
                                # Store the complete model ID as returned by the provider
                                all_models.append(f"{provider_name}/{model}")  # Use | separator to distinguish provider from model ID
                            verbose_print(f"✅ {provider_name}: discovered {len(provider_models)} models")
                        else:
                            # Fallback to current configured model if discovery fails
                            current_model = config.get('model', 'unknown')
                            all_models.append(f"{provider_name}/{current_model}")
                            verbose_print(f"⚠️ {provider_name}: fallback to default model")

                    except Exception as e:
                        verbose_print(f"❌ Error processing {provider_name}: {e}")
                        # Fallback to current model
                        current_model = config.get('model', 'unknown')
                        all_models.append(f"{provider_name}/{current_model}")

            except concurrent.futures.TimeoutError:
                # Handle unfinished futures
                unfinished_count = 0
                for future in future_to_provider:
                    if not future.done():
                        provider_name, config = future_to_provider[future]
                        verbose_print(f"⏰ Timeout: {provider_name} - using fallback")
                        # Cancel and add fallback
                        future.cancel()
                        current_model = config.get('model', 'unknown')
                        all_models.append(f"{provider_name}/{current_model}")
                        unfinished_count += 1
                verbose_print(f"⚠️ {unfinished_count} providers timed out, used fallbacks")

        verbose_print(f"✅ Model discovery completed. Found {len(all_models)} models total.")

        # Cache the discovered models in optimized format
        shared_model_cache.save_cache(all_models)

        # Convert to API format for endpoint response
        api_models = []
        for model_id in all_models:
            provider = model_id.split("/", 1)[0] if "/" in model_id else "unknown"
            api_models.append({
                "id": model_id,
                "object": "model",
                "created": int(datetime.now().timestamp()),
                "owned_by": provider
            })

        return {
            "object": "list",
            "data": api_models
        }

    except Exception as e:
        verbose_print(f"❌ Error in threaded model listing: {e}")
        # Fallback to basic model list
        basic_models = []
        for provider_name, config in AI_CONFIGS.items():
            if config.get('enabled', True):
                current_model = config.get('model', 'unknown')
                basic_models.append(f"{provider_name}/{current_model}")

        # Cache the basic models too
        shared_model_cache.save_cache(basic_models)

        # Convert to API format for endpoint response
        api_models = []
        for model_id in basic_models:
            provider = model_id.split("/", 1)[0] if "/" in model_id else "unknown"
            api_models.append({
                "id": model_id,
                "object": "model",
                "created": int(datetime.now().timestamp()),
                "owned_by": provider
            })

        return {
            "object": "list",
            "data": api_models
        }

@app.get("/api/statistics")
async def get_statistics():
    """Get comprehensive statistics"""
    try:
        # Get statistics from stats manager
        stats_summary = stats_manager.get_stats_summary()

        # Load actual key statistics from file
        key_statistics = {}
        try:
            with open("key_statistics.json", "r") as f:
                key_statistics = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # If no statistics file exists, create empty structure
            key_statistics = {}

        # Format provider reports with actual data for dashboard
        provider_reports = {}
        total_keys = 0
        total_requests = 0
        total_successes = 0

        for provider_name, provider_data in key_statistics.items():
            provider_reports[provider_name] = {}
            for key_name, key_stats in provider_data.items():
                total_keys += 1
                requests = key_stats.get("requests", 0)
                successes = key_stats.get("successes", 0)
                failures = key_stats.get("failures", 0)
                total_requests += requests
                total_successes += successes

                provider_reports[provider_name][key_name] = {
                    "requests": requests,
                    "successes": successes,
                    "failures": failures,
                    "last_used": key_stats.get("last_used"),
                    "rate_limited": key_stats.get("rate_limited", False),
                    "weight": key_stats.get("weight", 1.0),
                    "total_response_time": key_stats.get("total_response_time", 0),
                    "successful_response_time": key_stats.get("successful_response_time", 0),
                    "success_rate": f"{(successes / max(requests, 1) * 100):.1f}%"
                }

        # Enhanced summary for dashboard
        enhanced_summary = {
            "total_keys": total_keys,
            "total_requests": total_requests,
            "total_successes": total_successes,
            "overall_success_rate": f"{(total_successes / max(total_requests, 1) * 100):.1f}%",
            **stats_summary
        }

        return {
            "summary": enhanced_summary,
            "providers": provider_reports,
            "key_statistics": key_statistics,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/status")
async def get_status():
    """Get comprehensive engine status"""
    try:
        # Count enabled vs disabled providers
        total_providers = len(AI_CONFIGS)
        enabled_providers = sum(1 for config in AI_CONFIGS.values() if config.get('enabled', True))
        disabled_providers = total_providers - enabled_providers

        # Get available providers (enabled and working)
        available_providers = engine._get_available_providers() if hasattr(engine, '_get_available_providers') else []
        available_count = len(available_providers)

        # Get flagged providers (have keys but are failing)
        flagged_providers = getattr(engine, 'flagged_keys', {})
        flagged_count = len(flagged_providers)

        # Build provider lists (show all, not limited)
        enabled_provider_list = [name for name, config in AI_CONFIGS.items() if config.get('enabled', True)]
        disabled_provider_list = [name for name, config in AI_CONFIGS.items() if not config.get('enabled', True)]
        available_provider_list = [p[0] for p in available_providers] if available_providers else []
        flagged_provider_list = list(flagged_providers.keys())

        status = {
            'total_providers': total_providers,
            'enabled_providers': enabled_providers,
            'disabled_providers': disabled_providers,
            'available_providers': available_count,
            'flagged_providers': flagged_count,
            'current_provider': getattr(engine, 'current_provider', None),
            'enabled_provider_list': enabled_provider_list,  # All enabled providers
            'disabled_provider_list': disabled_provider_list,  # All disabled providers
            'available_provider_list': available_provider_list,  # All available providers
            'flagged_provider_list': flagged_provider_list,  # All flagged providers
            'explanation': {
                'enabled': 'Providers that are configured and turned on',
                'disabled': 'Providers that are manually disabled in config',
                'available': 'Enabled providers that are currently working (not flagged)',
                'flagged': 'Enabled providers with API key or rate limit issues'
            }
        }

        # Add detailed flagged information
        status['flagged_details'] = []
        for provider_name, reason in flagged_providers.items():
            status['flagged_details'].append({
                'provider': provider_name,
                'reason': reason,
                'description': 'Provider temporarily disabled due to errors'
            })

        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/cdn-config")
async def get_cdn_config_status():
    """Get CDN config sync status"""
    from core.config_sync import config_fetcher
    return config_fetcher.get_status()

@app.post("/api/cdn-config/refresh")
async def refresh_cdn_config():
    """Force refresh CDN config (bypasses TTL cache)"""
    from core.config_sync import config_fetcher, CACHE_META, CACHE_FILE
    try:
        CACHE_META.unlink(missing_ok=True)
        CACHE_FILE.unlink(missing_ok=True)
        result = config_fetcher.fetch_and_apply()
        if result:
            return {"success": True, "providers": len(result), "message": "CDN config refreshed"}
        return {"success": False, "message": "CDN fetch failed"}
    except Exception as e:
        return {"success": False, "message": str(e)}

@app.get("/api/providers")
async def get_providers():
    """Get all providers with their configurations (sanitized)"""
    try:
        providers = {}
        for name, config in AI_CONFIGS.items():
            # Create sanitized config for this provider
            providers[name] = {
                "id": config.get('id'),
                "priority": config.get('priority', 999),
                "endpoint": config.get('endpoint', ''),
                "model_endpoint": config.get('model_endpoint'),
                "model": config.get('model', 'auto'),
                "method": config.get('method', 'POST'),
                "auth_type": config.get('auth_type'),
                "max_tokens": config.get('max_tokens'),
                "temperature": config.get('temperature'),
                "timeout": config.get('timeout', 60),
                "retries": config.get('retries', 3),
                "backoff": config.get('backoff', 1),
                "format": config.get('format'),
                "enabled": config.get('enabled', True),
                "keys_count": len([k for k in config.get('api_keys', []) if k]),  # Count only non-empty keys
                "has_keys": bool(config.get('api_keys') and any(config.get('api_keys')))
                # Deliberately exclude api_keys and other sensitive data
            }

        return providers
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/capabilities")
async def get_capabilities():
    """Get provider and model capabilities"""
    return {
        "providers": capability_manager.get_all_capabilities(),
        "vision_providers": capability_manager.get_vision_providers(),
        "models": capability_manager.get_model_list(),
    }

@app.get("/api/capabilities/check-image/{provider}")
async def check_image_compatibility(provider: str, model: str = None):
    """Check if a provider/model supports image uploads"""
    return capability_manager.check_image_compatibility(provider, model)

@app.post("/api/providers/{provider_name}/toggle")
async def toggle_provider(provider_name: str, request: Request, x_api_key: str = Header(None, alias="X-API-Key")):
    """Toggle a provider's enabled status (requires API key)"""
    verify_admin_api_key(x_api_key)
    try:
        verbose_print(f"🔄 Toggle request for provider: {provider_name}")
        body = await request.json()
        enabled = body.get('enabled', True)
        verbose_print(f"📝 Request body: {body}")
        verbose_print(f"✅ Enabled setting: {enabled}")

        if provider_name not in AI_CONFIGS:
            verbose_print(f"❌ Provider '{provider_name}' not found in AI_CONFIGS")
            verbose_print(f"📋 Available providers: {list(AI_CONFIGS.keys())}")
            raise HTTPException(status_code=404, detail="Provider not found")

        # Update the provider's enabled status
        old_status = AI_CONFIGS[provider_name].get('enabled', True)
        AI_CONFIGS[provider_name]['enabled'] = enabled
        verbose_print(f"🔄 Changed {provider_name} enabled status: {old_status} -> {enabled}")

        # Save the configuration change to config.py file
        await save_config_to_file(provider_name, 'enabled', enabled)

        # If disabling, also remove from engine's active providers
        if not enabled and hasattr(engine, 'providers'):
            verbose_print(f"🔍 Current engine.providers structure: {type(engine.providers)}")
            if engine.providers:
                if isinstance(engine.providers, dict):
                    verbose_print(f"🔍 Provider dict keys: {list(engine.providers.keys())[:5]}...")  # Show first 5 keys
                    # For dict structure, remove the provider key
                    if provider_name in engine.providers:
                        del engine.providers[provider_name]
                        verbose_print(f"🗑️ Removed {provider_name} from engine providers dict")
                elif isinstance(engine.providers, list):
                    verbose_print(f"🔍 First provider example: {engine.providers[0] if len(engine.providers) > 0 else 'None'}")
                    # Try to handle different provider structures
                    try:
                        if isinstance(engine.providers[0], tuple) and len(engine.providers[0]) == 2:
                            # Original expected format: [(name, config), ...]
                            engine.providers = [(name, config) for name, config in engine.providers if name != provider_name]
                        else:
                            # Different format, try to filter differently
                            engine.providers = [p for p in engine.providers if getattr(p, 'name', p) != provider_name]
                    except Exception as filter_error:
                        verbose_print(f"⚠️ Could not filter providers: {filter_error}")
            else:
                verbose_print(f"🔍 engine.providers is empty")
        elif enabled:
            # If enabling, reinitialize the engine (simplified approach)
            if hasattr(engine, '_load_enabled_providers'):
                verbose_print(f"🔄 Reloading engine providers for {provider_name}")
                engine._load_enabled_providers()
            else:
                verbose_print(f"⚠️ Engine does not have _load_enabled_providers method")

        verbose_print(f"✅ Toggle operation completed for {provider_name}")

        return {"message": f"Provider {provider_name} {'enabled' if enabled else 'disabled'} successfully"}

    except Exception as e:
        verbose_print(f"❌ Error in toggle_provider: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/providers/{provider_name}/roll-key")
async def roll_provider_key(provider_name: str, x_api_key: str = Header(None, alias="X-API-Key")):
    """Roll to the next API key for a provider (requires API key)"""
    verify_admin_api_key(x_api_key)
    try:
        verbose_print(f"🔑 Roll key request for provider: {provider_name}")

        if provider_name not in AI_CONFIGS:
            verbose_print(f"❌ Provider '{provider_name}' not found in AI_CONFIGS")
            verbose_print(f"📋 Available providers: {list(AI_CONFIGS.keys())}")
            raise HTTPException(status_code=404, detail="Provider not found")

        # Check if provider has multiple keys
        api_keys = AI_CONFIGS[provider_name].get('api_keys', [])
        verbose_print(f"🔑 Found {len(api_keys)} keys for {provider_name}")

        if len(api_keys) <= 1:
            return {"message": f"Provider {provider_name} has only one key, no rolling needed"}

        # Use the engine's key rolling functionality if available
        if hasattr(engine, 'roll_api_key'):
            result = engine.roll_api_key(provider_name)
            verbose_print(f"✅ Key rolling result: {result}")
            return {"message": f"API key rolled for {provider_name}: {result}"}
        else:
            verbose_print(f"⚠️ Engine does not have roll_api_key method")
            return {"message": f"Key rolling not supported for {provider_name}"}

    except Exception as e:
        print(f"❌ Error in roll_provider_key: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

async def discover_provider_models_internal(provider_name: str):
    """Internal function to discover models for a provider - returns data directly"""
    try:
        if provider_name not in AI_CONFIGS:
            return None

        provider_config = AI_CONFIGS[provider_name]

        if not provider_config.get('enabled', True):
            return None

        models_endpoint = provider_config.get('model_endpoint')
        if not models_endpoint:
            return {
                'models': [provider_config.get('model', 'unknown')],
                'total_models': 1
            }

        api_keys = provider_config.get('api_keys', [])
        model_endpoint_auth = provider_config.get('model_endpoint_auth', True)

        if model_endpoint_auth and (not api_keys or not api_keys[0]):
            return None

        # Prepare headers
        headers = {'Content-Type': 'application/json'}

        if model_endpoint_auth and api_keys and api_keys[0]:
            auth_type = provider_config.get('auth_type', 'bearer')
            if auth_type.lower() == 'bearer':
                api_key = api_keys[0]
                key_preview = api_key[:8] + "..." if len(api_key) > 8 else api_key
                headers['Authorization'] = f'Bearer {api_key}'
            elif auth_type.lower() == 'api_key':
                headers['X-API-Key'] = api_keys[0]

        # Make the request
        timeout = provider_config.get('timeout', 60)

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
            async with session.get(models_endpoint, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()

                    # Parse different response formats
                    models = []
                    if 'data' in data and isinstance(data['data'], list):
                        # OpenAI format
                        models = [model.get('id', 'unknown') for model in data['data']]
                    elif 'models' in data:
                        # Custom format
                        if isinstance(data['models'], list):
                            models = data['models']
                        else:
                            models = list(data['models'].keys()) if isinstance(data['models'], dict) else []
                    elif isinstance(data, list):
                        # Direct list
                        models = [str(model) for model in data]

                    return {
                        'models': models,
                        'total_models': len(models)
                    }
                else:
                    return None
    except Exception as e:
        return None

@app.get("/api/providers/{provider_name}/models")
async def discover_provider_models(provider_name: str):
    """Discover available models for a specific provider"""
    import requests  # Import at function level to handle exceptions properly

    try:
        verbose_print(f"🔍 Discovering models for provider: {provider_name}")

        if provider_name not in AI_CONFIGS:
            verbose_print(f"❌ Provider '{provider_name}' not found in AI_CONFIGS")
            raise HTTPException(status_code=404, detail="Provider not found")

        provider_config = AI_CONFIGS[provider_name]
        verbose_print(f"📋 Provider config: enabled={provider_config.get('enabled')}, model_endpoint={provider_config.get('model_endpoint')}")

        # Check if provider supports model discovery
        if not provider_config.get('enabled', True):
            verbose_print(f"⚠️ Provider '{provider_name}' is disabled")
            raise HTTPException(status_code=400, detail="Provider is disabled")

        # Check if provider has model endpoint configured
        models_endpoint = provider_config.get('model_endpoint')
        if not models_endpoint:
            verbose_print(f"⚠️ Provider '{provider_name}' has no model_endpoint configured")
            return {
                'provider': provider_name,
                'models': [{
                    'id': provider_config.get('model', 'unknown'),
                    'name': provider_config.get('model', 'unknown'),
                    'owned_by': provider_name,
                    'note': 'Manual configuration only - no model discovery available'
                }],
                'endpoint': 'N/A',
                'total_models': 1,
                'discovery_available': False
            }

        api_keys = provider_config.get('api_keys', [])
        model_endpoint_auth = provider_config.get('model_endpoint_auth', True)

        verbose_print(f"🔑 API keys available: {len([k for k in api_keys if k])}, Auth required: {model_endpoint_auth}")

        # Check if authentication is required but no keys available
        if model_endpoint_auth and (not api_keys or not api_keys[0]):
            verbose_print(f"❌ Provider '{provider_name}' requires auth but no API key configured")
            raise HTTPException(status_code=400, detail="API key required but not configured")

        # Prepare headers
        headers = {'Content-Type': 'application/json'}

        # Add authentication if required
        if model_endpoint_auth and api_keys and api_keys[0]:
            auth_type = provider_config.get('auth_type', 'bearer')
            verbose_print(f"🔐 Using auth type: {auth_type}")

            if auth_type == 'bearer':
                headers['Authorization'] = f'Bearer {api_keys[0]}'
            elif auth_type == 'bearer_lowercase':
                headers['authorization'] = f'Bearer {api_keys[0]}'
            elif auth_type == 'query_param':
                # For providers like Gemini that use ?key= parameter
                if '?' in models_endpoint:
                    models_endpoint += f'&key={api_keys[0]}'
                else:
                    models_endpoint += f'?key={api_keys[0]}'
            elif provider_name.lower() in ['anthropic', 'claude']:
                headers['x-api-key'] = api_keys[0]
            else:
                headers['Authorization'] = f'Bearer {api_keys[0]}'

        verbose_print(f"🌐 Making request to: {models_endpoint}")
        verbose_print(f"📤 Headers: {dict((k, v[:20] + '...' if len(str(v)) > 20 else v) for k, v in headers.items())}")

        # Make request to discover models
        response = requests.get(models_endpoint, headers=headers, timeout=10)

        verbose_print(f"📥 Response status: {response.status_code}")
        verbose_print(f"📥 Response headers: {dict(response.headers)}")

        if response.status_code == 200:
            try:
                models_data = response.json()
                verbose_print(f"📊 Raw response data type: {type(models_data)}")
                verbose_print(f"📊 Raw response keys: {list(models_data.keys()) if isinstance(models_data, dict) else 'Not a dict'}")
            except Exception as json_error:
                verbose_print(f"❌ Failed to parse JSON response: {json_error}")
                verbose_print(f"📝 Raw response text: {response.text[:500]}")
                raise HTTPException(status_code=500, detail=f"Invalid JSON response from provider: {str(json_error)}")

            models = []

            if 'data' in models_data:
                # OpenAI format
                verbose_print("✅ Using OpenAI format (data key)")
                for model in models_data['data']:
                    models.append({
                        'id': model.get('id', ''),
                        'name': model.get('id', ''),
                        'owned_by': model.get('owned_by', provider_name),
                        'created': model.get('created', 0)
                    })
            elif 'models' in models_data:
                # Some providers return {models: [...]}
                verbose_print("✅ Using models key format")
                models_list = models_data['models']
                if isinstance(models_list, list):
                    for model in models_list:
                        if isinstance(model, dict):
                            models.append({
                                'id': model.get('id', model.get('name', '')),
                                'name': model.get('name', model.get('id', '')),
                                'owned_by': provider_name
                            })
                        else:
                            models.append({
                                'id': str(model),
                                'name': str(model),
                                'owned_by': provider_name
                            })
            elif isinstance(models_data, list):
                # Direct list of models
                verbose_print("✅ Using direct list format")
                for model in models_data:
                    if isinstance(model, dict):
                        models.append({
                            'id': model.get('id', model.get('name', '')),
                            'name': model.get('name', model.get('id', '')),
                            'owned_by': provider_name
                        })
                    else:
                        models.append({
                            'id': str(model),
                            'name': str(model),
                            'owned_by': provider_name
                        })

            verbose_print(f"✅ Successfully discovered {len(models)} models")
            return {
                'provider': provider_name,
                'models': models,
                'endpoint': models_endpoint,
                'total_models': len(models),
                'discovery_available': True
            }
        else:
            error_text = response.text[:500]
            print(f"❌ Request failed with status {response.status_code}")
            print(f"❌ Error response: {error_text}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to fetch models: {error_text}"
            )

    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Network error: {str(e)}")
    except Exception as e:
        print(f"❌ Unexpected error in model discovery: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/providers/{provider_name}/change-model")
async def change_provider_model(provider_name: str, request: Request, x_api_key: str = Header(None, alias="X-API-Key")):
    """Change the model for a specific provider (requires API key)"""
    verify_admin_api_key(x_api_key)
    try:
        body = await request.json()
        new_model = body.get('model')

        if not new_model:
            raise HTTPException(status_code=400, detail="Model name required")

        if provider_name not in AI_CONFIGS:
            raise HTTPException(status_code=404, detail="Provider not found")

        # Update the model in the configuration
        old_model = AI_CONFIGS[provider_name].get('model', 'unknown')
        AI_CONFIGS[provider_name]['model'] = new_model

        # Save the configuration back to config.py
        await save_config_to_file(provider_name, 'model', new_model)

        # Reload the engine to use the new model
        if hasattr(engine, '_load_enabled_providers'):
            engine._load_enabled_providers()

        return {
            'message': f'Model changed for {provider_name} from {old_model} to {new_model}',
            'provider': provider_name,
            'old_model': old_model,
            'new_model': new_model
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def save_config_to_file(provider_name: str, field: str, new_value):
    """Save a specific configuration change to config.py file"""
    try:
        # Read the current config file
        with open('config.py', 'r', encoding='utf-8') as f:
            config_content = f.read()

        # Find the provider section and update the specific field
        import re

        # Pattern to find the provider section
        provider_pattern = rf'"{provider_name}":\s*\{{([^}}]*)}}'

        # Create field pattern based on value type
        if isinstance(new_value, bool):
            # Boolean field pattern
            field_pattern = rf'"{field}":\s*(True|False)'
            replacement = f'"{field}": {new_value}'
        else:
            # String field pattern
            field_pattern = rf'"{field}":\s*"[^"]*"'
            replacement = f'"{field}": "{new_value}"'

        # Find the provider section
        provider_match = re.search(provider_pattern, config_content, re.DOTALL)
        if provider_match:
            provider_section = provider_match.group(1)

            # Update the field in the provider section
            if re.search(field_pattern, provider_section):
                updated_section = re.sub(field_pattern, replacement, provider_section)
                updated_config = config_content.replace(provider_section, updated_section)

                # Write the updated config back to file
                with open('config.py', 'w', encoding='utf-8') as f:
                    f.write(updated_config)

                verbose_print(f"✅ Config updated: {provider_name}.{field} = {new_value}")
            else:
                verbose_print(f"⚠️ Field '{field}' not found in provider '{provider_name}'")
        else:
            print(f"⚠️ Provider '{provider_name}' not found in config file")

    except Exception as e:
        print(f"❌ Error saving config to file: {e}")
        # Don't raise the error to avoid breaking the API response
        # The in-memory config is already updated, file persistence is a bonus

@app.post("/api/test-model")
@limiter.limit("5/minute")
async def test_model(request: Request):
    """Test a specific model with a provider"""
    try:
        body = await request.json()
        provider_name = body.get('provider')
        model_name = body.get('model')
        test_message = body.get('message', 'Hello! Please respond with a simple test message to confirm you are working correctly.')

        if not provider_name or not model_name:
            raise HTTPException(status_code=400, detail="Provider and model names required")

        # Test the model using the AI Engine
        start_time = datetime.now()

        # Create a simple test message
        messages = [
            {"role": "user", "content": test_message}
        ]

        # Make request to AI Engine with specific provider and model
        verbose_print(f"🧪 Starting test for {provider_name} with model {model_name}")
        verbose_print(f"🔍 DEBUG: Requesting provider='{provider_name}', model='{model_name}'")
        test_start_time = time.time()

        result = engine.chat_completion(
            messages=messages,
            model=model_name,
            preferred_provider=provider_name
        )

        test_end_time = time.time()
        total_test_time = test_end_time - test_start_time
        verbose_print(f"⏱️ Total test time: {total_test_time:.2f}s")
        verbose_print(f"🔍 DEBUG: Result provider_used='{result.provider_used}', model_used='{result.model_used}'")

        end_time = datetime.now()
        response_time = (end_time - start_time).total_seconds()

        if result.success:
            return JSONResponse(status_code=200, content={
                'success': True,
                'provider': result.provider_used,
                'model': result.model_used or model_name,
                'response': result.content[:200] + "..." if len(result.content) > 200 else result.content,
                'response_time': round(response_time, 2),
                'timestamp': start_time.isoformat()
            })
        else:
            return JSONResponse(status_code=502, content={
                'success': False,
                'provider': provider_name,
                'model': model_name,
                'error': result.error_message,
                'response_time': round(response_time, 2),
                'timestamp': start_time.isoformat()
            })

    except Exception as e:
        return JSONResponse(status_code=500, content={
            'success': False,
            'provider': provider_name if 'provider_name' in locals() else 'unknown',
            'model': model_name if 'model_name' in locals() else 'unknown',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        })

# Autodecide API Endpoints
@app.get("/api/autodecide/{model}")
async def discover_model_providers(model: str):
    """Discover which providers have a specific model"""
    try:
        # Check if autodecide is enabled
        if not engine.autodecide_config.get("enabled", True):
            return {
                'model': model,
                'autodecide_enabled': False,
                'providers': [],
                'message': 'Autodecide feature is disabled'
            }

        # Check cache first
        if not engine._is_cache_valid(model):
            providers_with_model = engine._discover_model_providers(model)
        else:
            providers_with_model = shared_model_cache.find_providers_for_model(model) if shared_model_cache.is_cache_valid() else []

        # Format response
        provider_list = []
        for provider_name, actual_model in providers_with_model:
            provider_config = engine.providers.get(provider_name, {})
            provider_list.append({
                'provider': provider_name,
                'model': actual_model,
                'priority': provider_config.get('priority', 999),
                'enabled': provider_config.get('enabled', False),
                'flagged': engine._is_key_flagged(provider_name)
            })

        # Sort by priority
        provider_list.sort(key=lambda x: x['priority'])

        return {
            'model': model,
            'autodecide_enabled': True,
            'providers': provider_list,
            'total_providers': len(provider_list),
            'cache_valid': engine._is_cache_valid(model),
            'timestamp': datetime.now().isoformat()
        }

    except Exception as e:
        print(f"❌ Error in autodecide discovery: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/autodecide/test")
async def test_autodecide_model(request: Request):
    """Test autodecide functionality with a specific model"""
    try:
        body = await request.json()
        model_name = body.get('model')
        test_message = body.get('message', 'Hello! This is a test of the autodecide feature.')

        if not model_name:
            raise HTTPException(status_code=400, detail="Model name required")

        # Test the model using autodecide
        messages = [{"role": "user", "content": test_message}]

        start_time = datetime.now()
        result = engine.chat_completion(
            messages=messages,
            model=model_name,
            autodecide=True  # Enable autodecide
        )
        end_time = datetime.now()

        response_time = (end_time - start_time).total_seconds()

        if result.success:
            return {
                'success': True,
                'requested_model': model_name,
                'provider_used': result.provider_used,
                'actual_model': result.model_used if hasattr(result, 'model_used') else model_name,
                'response': result.content[:200] + "..." if len(result.content) > 200 else result.content,
                'response_time': round(response_time, 2),
                'autodecide_used': True,
                'timestamp': start_time.isoformat()
            }
        else:
            return {
                'success': False,
                'requested_model': model_name,
                'error': result.error_message,
                'response_time': round(response_time, 2),
                'autodecide_used': True,
                'timestamp': start_time.isoformat()
            }

    except Exception as e:
        return {
            'success': False,
            'requested_model': model_name if 'model_name' in locals() else 'unknown',
            'error': str(e),
            'autodecide_used': True,
            'timestamp': datetime.now().isoformat()
        }

# Web Dashboard Routes
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/providers", response_class=HTMLResponse)
async def providers_page(request: Request):
    """Providers management page"""
    return templates.TemplateResponse("providers.html", {"request": request})

@app.get("/statistics", response_class=HTMLResponse)
async def statistics_page(request: Request):
    """Statistics page"""
    return templates.TemplateResponse("statistics.html", {"request": request})

@app.get("/models", response_class=HTMLResponse)
async def models_page(request: Request):
    """Models page"""
    return templates.TemplateResponse("models.html", {"request": request})

@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    """Chat interface page"""
    return templates.TemplateResponse("chat.html", {"request": request})

# Background tasks
async def save_statistics_async():
    """Save statistics asynchronously"""
    try:
        from core.statistics_manager import save_statistics_now
        save_statistics_now()
    except Exception as e:
        logger.warning(f"Failed to save statistics: {e}")

# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# Prometheus metrics endpoint
@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

# Request metrics middleware
@app.middleware("http")
async def track_metrics(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time

    REQUEST_COUNT.labels(
        endpoint=request.url.path,
        method=request.method,
        status=response.status_code
    ).inc()
    REQUEST_LATENCY.labels(endpoint=request.url.path).observe(duration)

    return response

@app.get("/api/providers/health")
async def get_provider_health():
    """Get health status of all providers"""
    try:
        health_status = {}

        for provider_name, config in AI_CONFIGS.items():
            if not config.get('enabled', True):
                health_status[provider_name] = {"status": "disabled", "healthy": None}
                continue

            # Check if provider has API keys
            api_keys = config.get('api_keys', [])
            valid_keys = [k for k in api_keys if k]

            if not valid_keys and config.get('auth_type'):
                health_status[provider_name] = {"status": "no_keys", "healthy": False}
                continue

            # Check if provider is flagged
            if hasattr(engine, '_is_key_flagged') and engine._is_key_flagged(provider_name):
                health_status[provider_name] = {"status": "flagged", "healthy": False}
                continue

            # Check usage stats
            if provider_name in engine.usage_stats:
                stats = engine.usage_stats[provider_name]
                consecutive_failures = stats.get('consecutive_failures', 0)
                if consecutive_failures > 0:
                    health_status[provider_name] = {
                        "status": "degraded",
                        "healthy": True,
                        "consecutive_failures": consecutive_failures
                    }
                else:
                    health_status[provider_name] = {"status": "healthy", "healthy": True}
            else:
                health_status[provider_name] = {"status": "unknown", "healthy": None}

        healthy_count = sum(1 for h in health_status.values() if h.get('healthy') is True)
        total_enabled = sum(1 for c in AI_CONFIGS.values() if c.get('enabled', True))

        return {
            "providers": health_status,
            "summary": {
                "total_enabled": total_enabled,
                "healthy": healthy_count,
                "unhealthy": total_enabled - healthy_count
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/capabilities/vision")
async def get_vision_providers():
    """Get all providers that support vision"""
    return {"providers": capability_manager.get_vision_providers()}

@app.get("/api/cache/stats")
async def get_cache_stats():
    """Get cache statistics"""
    return {
        "lru_cache": lru_cache.get_stats(),
        "deduplicator": request_deduplicator.get_stats()
    }

@app.get("/api/cache/clear")
async def clear_cache():
    """Clear all caches"""
    lru_cache.clear()
    return {"status": "cleared"}

@app.get("/api/metrics/summary")
async def get_metrics_summary():
    """Get request metrics summary"""
    return metrics_collector.get_overall_stats()

@app.get("/api/metrics/endpoints")
async def get_endpoint_metrics():
    """Get per-endpoint metrics"""
    endpoints = metrics_collector.get_overall_stats().get("endpoints", [])
    return {ep: metrics_collector.get_endpoint_stats(ep) for ep in endpoints}

@app.get("/api/sla/status")
async def get_sla_status():
    """Get SLA monitoring status"""
    return sla_monitor.get_status()

@app.post("/api/health/{provider_name}/ping")
async def ping_provider(provider_name: str):
    """Actually ping a provider to check if it's alive (sends a minimal request)"""
    import time as _time
    if provider_name not in AI_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_name}' not found")

    config = AI_CONFIGS[provider_name]
    endpoint = config.get("endpoint", "")
    if not endpoint:
        return {"provider": provider_name, "status": "no_endpoint", "alive": False}

    api_keys = [k for k in config.get("api_keys", []) if k]
    headers = {"Content-Type": "application/json"}
    auth_type = config.get("auth_type")
    if auth_type in ("bearer", "bearer_lowercase") and api_keys:
        headers["Authorization"] = f"Bearer {api_keys[0]}"

    model = config.get("model", "gpt-4")
    payload = {"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}

    start = _time.time()
    try:
        import requests as _requests
        resp = _requests.post(endpoint, json=payload, headers=headers, timeout=15)
        elapsed = _time.time() - start
        alive = resp.status_code == 200
        return {
            "provider": provider_name,
            "alive": alive,
            "status_code": resp.status_code,
            "latency_ms": round(elapsed * 1000),
            "error": None if alive else resp.text[:200],
        }
    except Exception as e:
        elapsed = _time.time() - start
        return {
            "provider": provider_name,
            "alive": False,
            "status_code": None,
            "latency_ms": round(elapsed * 1000),
            "error": str(e)[:200],
        }

@app.get("/api/health/providers")
async def get_provider_health_status():
    """Get provider health monitoring status"""
    from core.health_monitor import health_monitor
    return health_monitor.get_all_health()

@app.get("/api/health/summary")
async def get_health_summary():
    """Get overall health summary"""
    from core.health_monitor import health_monitor
    return health_monitor.get_summary()

@app.get("/api/health/checks")
async def run_health_checks():
    """Run all health checks"""
    return health_checker.run_checks()

@app.get("/api/errors")
async def get_error_messages():
    """Get all available error messages"""
    return {"errors": error_message_manager.get_all_errors()}

@app.get("/api/health/{provider_name}")
async def get_provider_health_detail(provider_name: str):
    """Get detailed health for a specific provider"""
    from core.health_monitor import health_monitor
    return health_monitor.get_provider_health(provider_name)

@app.get("/api/latency")
async def get_latency_stats():
    """Get latency statistics for all providers"""
    from core.latency_tracker import latency_tracker
    return latency_tracker.get_stats()

@app.get("/api/latency/{provider_name}")
async def get_provider_latency(provider_name: str):
    """Get latency statistics for a specific provider"""
    from core.latency_tracker import latency_tracker
    return latency_tracker.get_stats(provider_name)

@app.get("/api/rate-limits")
async def get_rate_limits():
    """Get rate limit status for all providers"""
    from core.rate_limit_manager import rate_limit_manager
    return rate_limit_manager.get_stats()

@app.get("/api/rate-limits/{provider_name}")
async def get_provider_rate_limit(provider_name: str):
    """Get rate limit status for a specific provider"""
    from core.rate_limit_manager import rate_limit_manager
    provider = rate_limit_manager.get_provider(provider_name)
    return {
        "provider": provider_name,
        "is_rate_limited": provider.is_rate_limited,
        "requests_made": provider.requests_made,
        "requests_limit": provider.requests_limit,
        "retry_after": provider.retry_after if provider.is_rate_limited else 0,
        "available": provider.is_available()
    }

@app.post("/api/rate-limits/{provider_name}/reset")
async def reset_rate_limit(provider_name: str):
    """Reset rate limit for a provider"""
    from core.rate_limit_manager import rate_limit_manager
    rate_limit_manager.reset_provider(provider_name)
    return {"status": "reset", "provider": provider_name}

@app.get("/api/usage")
async def get_usage_stats():
    """Get usage statistics"""
    from core.usage_tracker import usage_tracker
    return usage_tracker.get_stats(hours=24)

@app.get("/api/usage/{provider_name}")
async def get_provider_usage(provider_name: str):
    """Get usage statistics for a specific provider"""
    from core.usage_tracker import usage_tracker
    return usage_tracker.get_provider_stats(provider_name, hours=24)

# === Batch Processing ===
from core.batch import get_batch_processor

@app.post("/v1/batch")
@limiter.limit("5/minute")
async def batch_completions(request: Request, background_tasks: BackgroundTasks):
    """Process multiple chat completions in parallel"""
    try:
        body = await request.json()
        requests_list = body.get("requests", [])
        model = body.get("model")
        provider = body.get("provider")
        
        if not requests_list:
            return JSONResponse(
                status_code=400,
                content={"error": {"message": "requests array is required", "type": "invalid_request_error"}}
            )
        
        if len(requests_list) > 100:
            return JSONResponse(
                status_code=400,
                content={"error": {"message": "Maximum 100 requests per batch", "type": "invalid_request_error"}}
            )
        
        processor = get_batch_processor(engine)
        results = await processor.process_batch(requests_list, model=model, provider=provider)
        
        background_tasks.add_task(save_statistics_async)
        
        return {"results": results, "total": len(results)}
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": {"message": str(e), "type": "server_error"}}
        )

# === Workflow Endpoints ===
from core.workflow_engine import workflow_engine

@app.get("/api/workflows")
async def list_workflows():
    """List all workflows"""
    return {"workflows": workflow_engine.list_workflows()}

@app.post("/api/workflows")
async def create_workflow(request: Request):
    """Create a new workflow"""
    body = await request.json()
    wf = workflow_engine.create_workflow(
        name=body.get("name", "Untitled"),
        description=body.get("description", ""),
        steps=body.get("steps", [])
    )
    return {"workflow_id": wf.id, "name": wf.name}

@app.post("/api/workflows/{workflow_id}/execute")
async def execute_workflow(workflow_id: str, request: Request):
    """Execute a workflow"""
    body = await request.json()
    exec = workflow_engine.execute_workflow(workflow_id, body.get("input", {}))
    return {
        "execution_id": exec.id,
        "status": exec.status,
        "output": exec.output_data
    }

@app.get("/api/workflows/{workflow_id}/executions/{execution_id}")
async def get_execution(workflow_id: str, execution_id: str):
    """Get workflow execution status"""
    exec = workflow_engine.get_execution(execution_id)
    if not exec:
        raise HTTPException(status_code=404, detail="Execution not found")
    return {
        "execution_id": exec.id,
        "status": exec.status,
        "output": exec.output_data,
        "current_step": exec.current_step,
        "error": exec.error
    }

# === API Versioning ===
from core.api_versioning import get_version_info

@app.get("/api/version")
async def get_version():
    """Get API version information"""
    return get_version_info()

@app.post("/api/config/reload")
async def reload_config():
    """Reload configuration from config.py or CDN"""
    try:
        import sys

        # Try CDN refresh first if enabled
        from core.config_sync import config_fetcher
        if config_fetcher._enabled:
            try:
                config_fetcher.fetch_and_apply()
            except Exception:
                pass

        # Force reload local config
        for mod_name in list(sys.modules.keys()):
            if mod_name == 'config' or mod_name.startswith('config.'):
                del sys.modules[mod_name]

        from config import AI_CONFIGS as new_configs, ENGINE_SETTINGS as new_settings

        global AI_CONFIGS, ENGINE_SETTINGS
        AI_CONFIGS = new_configs
        ENGINE_SETTINGS = new_settings

        engine.providers = engine._load_enabled_providers()

        return {
            "status": "reloaded",
            "providers": len(AI_CONFIGS),
            "enabled": sum(1 for c in AI_CONFIGS.values() if c.get('enabled', True)),
            "cdn_refreshed": config_fetcher._enabled,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reload config: {str(e)}")

def create_directories():
    """Create necessary directories for templates and static files"""
    os.makedirs("templates", exist_ok=True)
    os.makedirs("static/css", exist_ok=True)
    os.makedirs("static/js", exist_ok=True)
    os.makedirs("static/img", exist_ok=True)

def create_templates():
    """Create HTML templates for the dashboard (only if they don't exist)"""
    import os

    # Check if templates already exist
    template_files = [
        "templates/dashboard.html",
        "templates/providers.html",
        "templates/statistics.html",
        "templates/models.html"
    ]

    # If any template files exist, skip template creation to preserve manual edits
    if any(os.path.exists(file) for file in template_files):
        verbose_print("📄 Templates already exist - preserving manual edits")
        return

    verbose_print("📄 Creating default templates...")

# Billing API endpoints
@app.get("/api/billing/usage")
async def get_billing_usage(tenant_id: str = None, hours: int = 24):
    """Get billing usage for a tenant"""
    from core.billing import BillingManager
    billing = BillingManager()
    if tenant_id:
        return billing.get_tenant_usage(tenant_id)
    return {"message": "Provide tenant_id parameter"}

@app.get("/api/billing/invoices")
async def get_invoices(tenant_id: str):
    """Get invoices for a tenant"""
    from core.billing import BillingManager
    billing = BillingManager()
    invoices = billing.get_invoices(tenant_id)
    return {"invoices": [{"id": inv.id, "total_cost": inv.total_cost, "status": inv.status, "period": f"{inv.period_start} to {inv.period_end}"} for inv in invoices]}

@app.get("/api/billing/alerts")
async def get_cost_alerts(tenant_id: str, threshold: float = 100.0):
    """Get cost alerts for a tenant"""
    from core.billing import BillingManager
    billing = BillingManager()
    return {"alerts": billing.get_cost_alerts(tenant_id, threshold)}

def main():
    """Main function to run the server"""
    import logging
    import signal
    import sys

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('ai_engine_server.log')
        ]
    )

    # Set uvicorn logging level
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)

    # Graceful shutdown handler
    def shutdown_handler(signum, frame):
        verbose_print("🛑 Shutting down gracefully...")
        # Save statistics
        try:
            from core.statistics_manager import save_statistics_now
            save_statistics_now()
        except Exception:
            pass
        # Stop auto-refresh
        shared_model_cache.stop_auto_refresh()
        verbose_print("✅ Cleanup complete")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    print("🚀 Starting AI Engine FastAPI Server...")
    print("📊 Dashboard: http://localhost:8000")
    print("📚 API Docs: http://localhost:8000/docs")
    print("🔴 ReDoc: http://localhost:8000/redoc")
    print("📝 Server logs: ai_engine_server.log")

    # Create necessary directories and files
    create_directories()
    create_templates()

    # Run server with detailed logging
    uvicorn.run(
        app,  # Pass app object directly instead of string to avoid re-import
        host="0.0.0.0",
        port=8000,
        reload=False,  # Disabled auto-reload to prevent restart loops
        log_level="info",
        access_log=True
    )

if __name__ == "__main__":
    main()
