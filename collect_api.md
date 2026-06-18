# How to Collect Free API Keys

This guide shows you step-by-step how to get free API keys from each provider.

---

## Category 1: Self-Hosted (Truly Free - No API Key Needed)

### GPT4Free (g4f) - RECOMMENDED

**What it is:** A self-hosted proxy that gives you access to GPT-4, Claude, Gemini for free.

**Setup:**
```bash
# Option A: Docker (easiest)
docker run -p 8080:8080 hlohaus789/g4f

# Option B: Python
pip install g4f
python -m g4f

# Option C: Docker Compose
git clone https://github.com/xtekky/gpt4free.git
cd gpt4free
docker-compose up
```

**After setup:**
- API available at: `http://localhost:8080/v1`
- No API key needed
- Models: GPT-4o, Claude 3.5, Gemini, etc.

---

### Ollama - Local Models

**What it is:** Run open-source models locally on your machine.

**Setup:**
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull llama3.1
ollama pull mistral

# Start server (runs on port 11434)
ollama serve
```

**After setup:**
- API available at: `http://localhost:11434`
- No API key needed
- Models: Llama 3.1, Mistral, CodeLlama, etc.

---

## Category 2: Free Tier APIs (Need Signup)

### Groq - RECOMMENDED

**Free tier:** 30 requests/minute, 14,400 requests/day

**Steps:**
1. Go to https://console.groq.com
2. Click "Sign Up" (use GitHub/Google)
3. Go to "API Keys" section
4. Click "Create API Key"
5. Copy the key
6. Add to `.env`: `GROQ_API_KEY=gsk_...`

**Models available:** Llama 3.3, Mixtral, Gemma

---

### SambaNova - RECOMMENDED

**Free tier:** Generous daily limits

**Steps:**
1. Go to https://cloud.sambanova.ai
2. Sign up with email
3. Go to "API Keys" in dashboard
4. Create a new key
5. Add to `.env`: `SAMBANOVA_API_KEY=...`

**Models available:** Llama 3.3, DeepSeek, CodeLlama

---

### Together AI

**Free tier:** $1 credit on signup

**Steps:**
1. Go to https://api.together.xyz
2. Sign up with email/GitHub
3. You get $1 free credit automatically
4. Go to "API Keys" in settings
5. Create a key
6. Add to `.env`: `TOGETHER_API_KEY=...`

**Models available:** Llama, Mixtral, CodeLlama

---

### DeepInfra

**Free tier:** $1 credit on signup

**Steps:**
1. Go to https://deepinfra.com
2. Sign up with GitHub/Google
3. You get $1 free credit
4. Go to "API Keys" in dashboard
5. Create a key
6. Add to `.env`: `DEEPINFRA_API_KEY=...`

**Models available:** Llama, Mistral, Stable Diffusion

---

### OpenRouter - RECOMMENDED

**Free tier:** 200 free credits + 23 free models

**Steps:**
1. Go to https://openrouter.ai
2. Sign up with GitHub/Google
3. You get free credits automatically
4. Go to "Keys" in settings
5. Create a key
6. Add to `.env`: `OPENROUTER_API_KEY=sk-or-...`

**Free models (no credit cost):**
- `meta-llama/llama-3.3-70b-instruct:free`
- `openai/gpt-4o-mini:free`
- `qwen/qwen3-coder:free`
- `nvidia/nemotron-nano-12b-v2-vl:free`

**Important:** Use `:free` suffix for free models!

---

### NVIDIA NIM

**Free tier:** 1000 credits/month

**Steps:**
1. Go to https://build.nvidia.com
2. Sign up with email/NVIDIA account
3. Go to "API Catalog"
4. Generate an API key
5. Add to `.env`: `NVIDIA_API_KEY=nvapi-...`

**Models available:** DeepSeek, Llama, Mixtral

---

### Cerebras

**Free tier:** 30 requests/minute

**Steps:**
1. Go to https://cloud.cerebras.ai
2. Sign up with email
3. Go to "API Keys" in dashboard
4. Create a key
5. Add to `.env`: `CEREBRAS_API_KEY=...`

**Models available:** Llama 3.3

---

### Google Gemini - RECOMMENDED

**Free tier:** 15 requests/minute, 1 million tokens/day

**Steps:**
1. Go to https://aistudio.google.com
2. Sign in with Google account
3. Click "Get API Key"
4. Create a key in your project
5. Add to `.env`: `GEMINI_API_KEY=AIza...`

**Models available:** Gemini 2.0 Flash, Gemini 1.5 Pro

---

### GitHub Models

**Free tier:** 15 requests/minute

**Steps:**
1. Go to https://github.com/settings/tokens
2. Generate a Personal Access Token (fine-grained)
3. Select "GitHub Models" permission
4. Add to `.env`: `GITHUB_API_KEY=ghp_...`

**Models available:** GPT-4o-mini, Phi-3, Llama

---

### Cloudflare Workers AI

**Free tier:** 10,000 neurons/day

**Steps:**
1. Go to https://dash.cloudflare.com
2. Sign up / Log in
3. Go to "AI" in the sidebar
4. Get your Account ID from the URL
5. Go to "API Tokens" and create one
6. Add to `.env`:
   ```
   CLOUDFLARE_API_KEY=your_api_token
   CLOUDFLARE_ACCOUNT_ID=your_account_id
   ```

**Models available:** Llama 3.1, Mistral, Stable Diffusion

---

### Vercel AI Gateway

**Free tier:** Available

**Steps:**
1. Go to https://vercel.com
2. Sign up with GitHub/Google
3. Go to "Settings" → "Tokens"
4. Create a token
5. Add to `.env`: `VERCEL_API_KEY=...`

---

## Category 3: Discord-Based Free APIs

### How Discord-Based APIs Work

1. Join the Discord server
2. Read the rules/welcome channel
3. Find the bot or channel for API keys
4. Follow instructions to get your key
5. Some require you to be a member for X days
6. Some give free credits for joining

### NagaAI

**Discord:** https://discord.gg/8ywEPhnJy4

**Steps:**
1. Join Discord server
2. Read #welcome and #rules channels
3. Go to #api-keys or #get-started channel
4. Follow bot instructions to get key
5. Key format: `sk-...`

**Note:** May require minimum balance after trial.

---

### NavyAPI

**Discord:** https://discord.gg/ezXZ8wpprc

**Steps:**
1. Join Discord server
2. Read #welcome channel
3. Go to #api or #get-api-key channel
4. Use bot commands to generate key
5. Key format: `Bearer ...`

---

### ElectronHub

**Discord:** https://discord.gg/4xg2TM3mNP

**Steps:**
1. Join Discord server
2. Read #rules and #announcements
3. Go to #api-keys channel
4. Follow instructions to get key
5. Check for free credits/limits

---

### MNN AI

**Discord:** https://discord.gg/xKmsCCzUFW

**Steps:**
1. Join Discord server
2. Read #welcome channel
3. Go to #api or #support channel
4. Ask for API key or follow bot instructions

---

### ZanityAI

**Discord:** https://discord.gg/8GgUak8KrK

**Steps:**
1. Join Discord server
2. Read #rules channel
3. Go to #api-access channel
4. Follow instructions to get key

---

### VoidAI

**Discord:** https://discord.gg/2nQwkvFFj6

**Steps:**
1. Join Discord server
2. Read #welcome channel
3. Go to #api-keys channel
4. Follow bot instructions

---

## Quick Setup Summary

After getting your keys, add them to `.env`:

```bash
# Self-hosted (no key needed)
G4F_ENDPOINT=http://localhost:8080/v1/chat/completions

# Free tier APIs
GROQ_API_KEY=gsk_...
SAMBANOVA_API_KEY=...
OPENROUTER_API_KEY=sk-or-...
GEMINI_API_KEY=AIza...

# Discord-based APIs
NAGAAI_API_KEY=...
NAVY_API_KEY=...
```

Then restart the AI Engine server.

---

## Troubleshooting

### "Invalid API Key"
- Double-check the key was copied correctly
- Make sure there are no extra spaces
- Check if the key has expired

### "Rate Limit Exceeded"
- Free tiers have limits
- Wait before retrying
- Rotate to another provider

### "Model Not Found"
- Check available models at provider's docs
- Use the exact model name from their list

### Discord Key Not Working
- Make sure you're in the correct channel
- Some keys take time to activate
- Try generating a new key
