# AI Engine v3.0 - Quick Start Guide

## Installation

1. **Clone the repository:**
```bash
git clone https://github.com/mihir0209/AI_engine.git
cd AI_engine
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
pip install -r requirements_server.txt  # Optional: for web server
```

3. **Set up API keys:**
Create a `.env` file in the project root:
```bash
# Essential providers (get these first)
OPENAI_API_KEY=your_openai_key
GEMINI_API_KEY=your_gemini_key
GROQ_API_KEY=your_groq_key

# Additional providers (add as needed)
PAXSENIX_API_KEY=your_paxsenix_key
CHI_API_KEY=your_chi_key
ANTHROPIC_API_KEY=your_anthropic_key
# ... see README.md for complete list
```

## Basic Usage

### Python Code

```python
from ai_engine import get_ai_engine

# Initialize the engine
engine = get_ai_engine(verbose=True)

# Simple chat completion
messages = [{"role": "user", "content": "Hello, world!"}]
result = engine.chat_completion(messages)

if result.success:
    print(f"Response: {result.content}")
    print(f"Provider: {result.provider_used}")
else:
    print(f"Error: {result.error_message}")
```

### Command Line

```bash
# Test with automatic provider selection
python ai_engine.py auto "Hello world"

# Test specific provider
python ai_engine.py groq "Explain quantum computing"

# Test autodecide feature
python ai_engine.py autodecide "gpt-4" "Hello from autodecide"

# System information
python ai_engine.py status
python ai_engine.py list
```

### Web Server

```bash
# Start the web server
python server.py

# Access the dashboard
# http://localhost:8000
```

## Key Features to Try

### 1. Autodecide (Smart Model Matching)
```python
# Automatically find providers for any model
result = engine.chat_completion(
    messages=[{"role": "user", "content": "Hello!"}],
    model="gpt-4",  # Engine finds best provider
    autodecide=True
)
```

### 2. Provider Management
```python
# Test specific provider
result = engine.test_specific_provider("groq", "Test message")

# Get engine status
status = engine.get_status()
print(f"Available providers: {status['available_providers']}")
```

### 3. Error Handling
The engine automatically handles:
- Rate limits with key rotation
- Provider failures with automatic fallback
- Network errors with retry logic

### 4. Performance Monitoring
```python
# Run stress test
results = engine.stress_test_all_providers(iterations=2)
```

## Complete Feature Demo

Run the comprehensive demonstration:
```bash
python demo_ai_engine.py
```

This will show you:
- Basic usage patterns
- Autodecide functionality
- Provider management
- Error handling
- Performance monitoring
- Configuration options

## Web Dashboard

Start the server and visit these pages:
- **Dashboard**: `http://localhost:8000/` - System overview
- **Providers**: `http://localhost:8000/providers` - Provider management
- **Models**: `http://localhost:8000/models` - Model configuration
- **API Docs**: `http://localhost:8000/docs` - Interactive API documentation

## Next Steps

1. **Read the Documentation:**
   - `README.md` - Complete feature overview
   - `AI_ENGINE_DOCUMENTATION.md` - Technical details
   - `SERVER_README.md` - Web server guide

2. **Configure More Providers:**
   See the README.md for the complete list of 24 supported providers

3. **Explore Advanced Features:**
   - Custom provider priorities
   - Multi-key rotation
   - Performance optimization
   - Production deployment

4. **Get Help:**
   - Check the GitHub issues
   - Review the troubleshooting sections
   - Run the demo file for examples

## Common Issues

**No providers available:**
- Check your `.env` file has valid API keys
- Verify environment variable names match config

**Slow responses:**
- Enable autodecide for faster provider selection
- Check provider health: `python ai_engine.py status`

**Import errors:**
- Ensure all dependencies installed: `pip install -r requirements.txt`
- Check Python version (3.8+ required)

Happy coding with AI Engine v3.0! 🚀
