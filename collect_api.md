# How to Collect Free API Keys

Step-by-step guide to get free API keys from each provider.

---

## Category 1: Self-Hosted (Truly Free - No API Key)

### GPT4Free (RECOMMENDED)

```bash
docker run -p 8080:8080 hlohaus789/g4f
```

- API: `http://localhost:8080/v1`
- Models: GPT-4o, Claude 3.5, Gemini, etc.
- Cost: FREE

### Ollama (Local)

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.1
```

- API: `http://localhost:11434`
- Models: Llama, Mistral, etc.
- Cost: FREE (needs GPU)

---

## Category 2: Free Tier APIs

### Groq (30 RPM, 14,400 RPD)

1. Go to https://console.groq.com
2. Sign up with GitHub/Google
3. Go to "API Keys"
4. Click "Create API Key"
5. Copy key → Add to `.env`: `GROQ_API_KEY=gsk_...`

### OpenRouter (23 free models)

1. Go to https://openrouter.ai
2. Sign up with GitHub/Google
3. Go to "Keys" in settings
4. Create a key → Add to `.env`: `OPENROUTER_API_KEY=sk-or-...`

**Important:** Use `:free` suffix for free models!

### Google Gemini (15 RPM, 1M tokens/day)

1. Go to https://aistudio.google.com
2. Sign in with Google
3. Click "Get API Key"
4. Create key → Add to `.env`: `GEMINI_API_KEY=AIza...`

### NVIDIA NIM (1000 credits/month)

1. Go to https://build.nvidia.com
2. Sign up with email/NVIDIA
3. Go to "API Catalog"
4. Generate key → Add to `.env`: `NVIDIA_API_KEY=nvapi-...`

### Cerebras (30 RPM)

1. Go to https://cloud.cerebras.ai
2. Sign up with email
3. Go to "API Keys"
4. Create key → Add to `.env`: `CEREBRAS_API_KEY=...`

### Cloudflare Workers AI (10K neurons/day)

1. Go to https://dash.cloudflare.com
2. Sign up / Log in
3. Go to "AI" → Get Account ID
4. Go to "API Tokens" → Create token
5. Add to `.env`:
   ```
   CLOUDFLARE_API_KEY=your_token
   CLOUDFLARE_ACCOUNT_ID=your_id
   ```

### GitHub Models (15 RPM)

1. Go to https://github.com/settings/tokens
2. Generate Personal Access Token
3. Select "GitHub Models" permission
4. Add to `.env`: `GITHUB_API_KEY=ghp_...`

### Vercel AI Gateway

1. Go to https://vercel.com
2. Sign up with GitHub/Google
3. Go to "Settings" → "Tokens"
4. Create token → Add to `.env`: `VERCEL_API_KEY=...`

---

## Adding Custom Providers

Use the CLI tool:

```bash
python cli.py
```

Then select "Add new provider" and follow the interactive wizard.

---

## Quick Setup

After getting keys:

```bash
cp .env.example .env
# Edit .env with your keys
python server.py
```
