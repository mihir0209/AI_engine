# Deployment Guide

## Quick Start

### Local Development

```bash
# Clone and setup
git clone <repo-url>
cd AI_engine

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt -r requirements_server.txt

# Create .env file with your API keys
cp .env.example .env
# Edit .env with your keys

# Run server
python server.py
```

### Docker Deployment

```bash
# Build image
docker build -t ai-engine .

# Run container
docker run -d \
  --name ai-engine \
  -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/key_statistics.json:/app/key_statistics.json \
  -v $(pwd)/chat_data.db:/app/chat_data.db \
  ai-engine

# Or use docker-compose
docker-compose up -d
```

## Environment Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `*_API_KEY` | Provider API keys | `OPENAI_API_KEY=sk-...` |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `ADMIN_API_KEY` | API key for management endpoints | (empty = no auth) |
| `CORS_ORIGINS` | Allowed CORS origins | `*` |
| `VERBOSE_MODE` | Enable verbose logging | `False` |

## Production Configuration

### 1. Security

```bash
# Generate secure API key
ADMIN_API_KEY=$(openssl rand -hex 32)

# Set CORS for your domain
CORS_ORIGINS=https://yourdomain.com,https://admin.yourdomain.com
```

### 2. Performance

```bash
# Run with multiple workers (recommended: 2-4 per CPU core)
uvicorn server:app --host 0.0.0.0 --port 8000 --workers 4

# Or use gunicorn
gunicorn server:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

### 3. Monitoring

```bash
# Health check
curl http://localhost:8000/health

# Statistics
curl http://localhost:8000/api/statistics

# Provider status
curl http://localhost:8000/api/status
```

## Docker Compose (Production)

```yaml
version: '3.8'

services:
  ai-engine:
    build: .
    container_name: ai-engine
    restart: always
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '2'
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

## Reverse Proxy Configuration

### Nginx

```nginx
upstream ai_engine {
    server 127.0.0.1:8000;
}

server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.yourdomain.com/privkey.pem;

    location / {
        proxy_pass http://ai_engine;
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
```

## Systemd Service

```ini
[Unit]
Description=AI Engine Server
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/ai-engine
Environment=PATH=/opt/ai-engine/venv/bin
ExecStart=/opt/ai-engine/venv/bin/python server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
# Install service
sudo cp ai-engine.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ai-engine
sudo systemctl start ai-engine
```

## Backup & Recovery

### Database Backup

```bash
# Backup chat database
sqlite3 chat_data.db .backup backup_$(date +%Y%m%d).db

# Backup statistics
cp key_statistics.json key_statistics_$(date +%Y%m%d).json
```

### Restore

```bash
# Restore database
cp backup_20240115.db chat_data.db

# Restore statistics
cp key_statistics_20240115.json key_statistics.json
```

## Troubleshooting

### Common Issues

1. **Port already in use**
   ```bash
   lsof -i :8000
   kill -9 <PID>
   ```

2. **Database locked**
   ```bash
   # Check for concurrent access
   fuser chat_data.db
   ```

3. **API key errors**
   ```bash
   # Verify environment variables
   env | grep API_KEY
   ```

### Logs

```bash
# View server logs
tail -f ai_engine_server.log

# Docker logs
docker logs -f ai-engine
```

## Scaling

### Horizontal Scaling

1. Use load balancer (Nginx, HAProxy, cloud LB)
2. Share database (use PostgreSQL instead of SQLite)
3. Share statistics via Redis

### Vertical Scaling

- Increase workers: `--workers 8`
- Increase memory limit
- Use faster storage (SSD)

## Security Checklist

- [ ] Set `ADMIN_API_KEY`
- [ ] Configure `CORS_ORIGINS`
- [ ] Enable HTTPS
- [ ] Review rate limits
- [ ] Monitor access logs
- [ ] Regular backups
