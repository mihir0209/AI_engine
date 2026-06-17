# HTTPS & Security Configuration Guide

## Overview

This guide covers security configuration for AI Engine v3.0 in production deployments.

## Environment Variables

### Required Security Variables

```bash
# API Key for admin endpoints (toggle, roll-key, change-model)
ADMIN_API_KEY=your-secure-api-key-here

# CORS origins (comma-separated for multiple)
CORS_ORIGINS=https://yourdomain.com,https://admin.yourdomain.com

# Rate limiting is built-in (slowapi)
# - Chat completions: 10 requests/minute
# - Test model: 5 requests/minute
```

## HTTPS Setup

### Option 1: Nginx Reverse Proxy (Recommended)

```nginx
server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
    }
}

server {
    listen 80;
    server_name api.yourdomain.com;
    return 301 https://$host$request_uri;
}
```

### Option 2: Traefik (Docker)

```yaml
# docker-compose.yml
version: '3.8'
services:
  traefik:
    image: traefik:v2.10
    command:
      - "--providers.docker=true"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.letsencrypt.acme.tlschallenge=true"
      - "--certificatesresolvers.letsencrypt.acme.email=you@email.com"
      - "--certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json"
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - letsencrypt:/letsencrypt

  ai-engine:
    build: .
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.ai-engine.rule=Host(`api.yourdomain.com`)"
      - "traefik.http.routers.ai-engine.entrypoints=websecure"
      - "traefik.http.routers.ai-engine.tls.certresolver=letsencrypt"

volumes:
  letsencrypt:
```

### Option 3: Cloudflare Tunnel

```bash
# Install cloudflared
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
chmod +x cloudflared

# Create tunnel
./cloudflared tunnel create ai-engine

# Configure DNS
./cloudflared tunnel route dns ai-engine api.yourdomain.com

# Run tunnel
./cloudflared tunnel run --url http://localhost:8000 ai-engine
```

## API Key Authentication

Management endpoints require API key authentication:

```bash
# Toggle provider
curl -X POST http://localhost:8000/api/providers/openai/toggle \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-admin-api-key" \
  -d '{"enabled": false}'

# Roll API key
curl -X POST http://localhost:8000/api/providers/openai/roll-key \
  -H "X-API-Key: your-admin-api-key"

# Change model
curl -X POST http://localhost:8000/api/providers/openai/change-model \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-admin-api-key" \
  -d '{"model": "gpt-4-turbo"}'
```

### Endpoints Requiring API Key

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/providers/{name}/toggle` | POST | Enable/disable provider |
| `/api/providers/{name}/roll-key` | POST | Rotate API key |
| `/api/providers/{name}/change-model` | POST | Change provider model |

### Endpoints Without API Key

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/chat/completions` | POST | Chat completions (rate limited) |
| `/v1/models` | GET | List models |
| `/api/status` | GET | Engine status |
| `/api/providers` | GET | List providers (sanitized) |
| `/api/statistics` | GET | Usage statistics |
| `/health` | GET | Health check |

## Rate Limiting

Built-in rate limiting via slowapi:

- **Chat completions**: 10 requests/minute per IP
- **Test model**: 5 requests/minute per IP
- **Other endpoints**: No limit (add if needed)

## Input Validation

- Message content sanitized (null bytes removed, length limited to 100KB)
- Role validation (must be system/user/assistant)
- Provider names validated against configuration

## Production Checklist

- [ ] Set `ADMIN_API_KEY` environment variable
- [ ] Configure `CORS_ORIGINS` for your domain
- [ ] Enable HTTPS (Nginx/Traefik/Cloudflare)
- [ ] Set secure `COOKIE_SECRET` if using sessions
- [ ] Review rate limiting limits for your use case
- [ ] Monitor rate limit hits in logs

## Security Notes

- API keys are never exposed in API responses
- Provider configurations are sanitized before returning
- Rate limiting prevents abuse
- Input validation prevents injection attacks
- CORS restricts cross-origin requests in production
