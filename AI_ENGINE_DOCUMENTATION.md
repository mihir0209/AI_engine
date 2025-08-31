# AI Engine v3.0 Documentation

## Overview
AI Engine v3.0 is a clean, secure, and efficient AI provider management system with 22 configured providers, smart key rotation, and Python-based configuration using dotenv for security.

## Key Features
- **22 AI Providers**: Comprehensive provider ecosystem with automatic failover
- **Python Configuration**: Secure in-code configuration with dotenv integration
- **Smart Key Rotation**: Automatic error-based flagging and rotation
- **No Database Dependencies**: Lightweight, stateless operation
- **Live Stress Testing**: Real-time provider testing without result persistence
- **Priority-Based Selection**: Intelligent provider ordering

## Security
- API keys loaded from `.env` file using python-dotenv
- No JSON configuration files with exposed secrets
- Secure environment variable management
- No persistent storage of sensitive data

## Quick Start
```python
from ai_engine import AI_engine

# Initialize engine
engine = AI_engine(verbose=True)

# Make a request
messages = [{"role": "user", "content": "Hello!"}]
result = engine.chat_completion(messages)

if result.success:
    print(f"Response: {result.content}")
    print(f"Provider: {result.provider_used}")
else:
    print(f"Error: {result.error_message}")
```

## Required API Keys
Add these to your `.env` file for full functionality:

### Currently Working (19/22 providers):
- A4F_API_KEY
- CHI_API_KEY  
- PAXSENIX_API_KEY
- MANGO_API_KEY
- SAMURAI_API_KEY
- WOW_TYPEGPT_API_KEY
- GEMINI_API_KEY
- OPENAI_API_KEY
- GROQ_API_KEY
- CLOUDFLARE_API_KEY
- CLOUDFLARE_ACCOUNT_ID
- COHERE_API_KEY
- OPENROUTER_API_KEY
- NVIDIA_API_KEY
- VERCEL_API_KEY
- GITHUB_API_KEY
- PAWAN_API_KEY

### Missing Keys (3/22 providers):
- CEREBRAS_API_KEY (disabled due to server issues)
- FLOWITH_API_KEY
- MINIMAX_API_KEY

### No Keys Required (2/22 providers):
- A3Z (no auth required)
- OMEGATRON (no auth required)
- OFFLINE (local Ollama server)

## Stress Testing
```python
# Run comprehensive stress test
results = engine.stress_test_providers(test_iterations=3, ask_for_priority_change=True)

# Check results
for provider, result in results.items():
    if result['passed']:
        print(f"✅ {provider}: {result['success_rate']}% success")
    else:
        print(f"❌ {provider}: Failed")
```

## Provider Priority Order
1. **Paxsenix** (Priority 1) - gpt-4.1-mini
2. **Chi** (Priority 2) - gpt-4.1-mini  
3. **Gemini** (Priority 3) - gemini-2.5-flash
4. **Samurai** (Priority 4) - gpt-4.1-mini
5. **A4F** (Priority 5) - provider-6/gpt-4.1-mini
6. **Mango** (Priority 6) - gpt-4.1-mini
7. **A3Z** (Priority 7) - gpt-4.1-nano
8. **Omegatron** (Priority 7) - gpt-4.1-mini
9. **TypeGPT** (Priority 8) - compound-beta-mini
10. **Groq** (Priority 9) - openai/gpt-oss-20b
11. **OpenAI** (Priority 11) - gpt-4-turbo-preview
12. **Cloudflare** (Priority 12) - @cf/openai/gpt-oss-120b
13. **Cohere** (Priority 13) - command-a-03-2025
14. **OpenRouter** (Priority 14) - meta-llama/llama-3.1-405b-instruct:free
15. **NVIDIA** (Priority 15) - deepseek-ai/deepseek-v3.1
16. **Vercel** (Priority 16) - anthropic/claude-sonnet-4
17. **GitHub** (Priority 17) - openai/gpt-4o
18. **Flowith** (Priority 18) - gpt-4o-mini
19. **MiniMax** (Priority 19) - minimax-reasoning-01
20. **Pawan** (Priority 20) - gpt-4o-mini

## Error Handling
- **Rate Limits**: 1-hour flagging
- **Daily Limits**: Flagged until midnight
- **Auth Errors**: 1-hour flagging  
- **5 Consecutive Failures**: Auto-flagging
- **Server Errors**: Automatic retry with next provider

## Architecture Benefits
- ✅ Secure Python configuration
- ✅ No external JSON files
- ✅ Environment variable based security
- ✅ Smart error-based rotation
- ✅ Live testing without persistence
- ✅ 22 provider ecosystem
- ✅ Priority optimization
- ✅ Clean, maintainable codebase
