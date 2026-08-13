# OpenWebUI Production Integration Guide

This project now includes a production-ready OpenWebUI integration using an OpenAI-compatible API bridge.

## Architecture

- OpenWebUI provides the professional user interface and chat experience.
- FastAPI bridge exposes this RAG pipeline at OpenAI-compatible endpoints.
- Existing RAG core in `rag_orchestrator.py` remains your intelligence layer.

Flow:

1. User chats in OpenWebUI
2. OpenWebUI calls `/v1/chat/completions`
3. API bridge calls `AdmissionsRAGOrchestrator.query_pipeline(...)`
4. Grounded answer returns to OpenWebUI

## New Files

- `openwebui_api.py`: OpenAI-compatible chat API for your RAG system
- `Dockerfile.api`: Production API image
- `docker-compose.openwebui.yml`: Full stack deployment (OpenWebUI + API)
- `.env.example`: Required environment variable template

## Production Startup

1. Create environment file:

   - Copy `.env.example` to `.env`
   - Set `API_AUTH_KEY` to a strong random value
   - Set `GEMINI_API_KEY` if you want Gemini generation enabled

2. Build and run:

   ```powershell
   docker compose -f docker-compose.openwebui.yml up -d --build
   ```

3. Access services:

   - OpenWebUI: http://localhost:3000
   - API health: http://localhost:8000/health

## OpenWebUI Defaults (already wired in compose)

- Model shown in UI: `admissions-rag`
- Base URL: `http://admissions-api:8000/v1`
- API key: from `API_AUTH_KEY`
- Signup disabled for safer production default

## Operational Notes

- Persistent UI state is stored in Docker volume `openwebui-data`.
- RAG evidence logs are mounted from host:
  - `review_log.jsonl`
  - `trace_log.jsonl`
- Vector DB and structured DB are mounted from host for durability.

## Security Hardening Checklist

- Keep `ENABLE_SIGNUP=false` unless needed.
- Use strong `API_AUTH_KEY`.
- Put a reverse proxy in front of OpenWebUI (TLS + auth).
- Restrict host firewall to required ports only.
- Rotate API keys periodically.

## Quick Validation

- Open OpenWebUI and run:
  - "What is the tuition fee and standard duration for Computer Science BSc?"
- Confirm grounded response appears and your logs update.

## Stop Services

```powershell
docker compose -f docker-compose.openwebui.yml down
```

## Oracle Cloud Deployment (Recommended)

Use this flow to run OpenWebUI as the main interface on Oracle Linux (VM instance).

### 1. Prepare Oracle Linux host

```bash
sudo dnf update -y
sudo dnf install -y git curl
```

Install Docker engine:

```bash
curl -fsSL https://get.docker.com | sh
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
```

Re-login, then verify:

```bash
docker --version
docker compose version
```

### 2. Clone and configure

```bash
git clone <your-repo-url> admissions-assistant-run
cd admissions-assistant-run
cp .env.example .env
```

Edit `.env` and set:

- `API_AUTH_KEY` to a strong random value
- `GEMINI_API_KEY` to your Gemini key

### 3. Run the stack

```bash
docker compose -f docker-compose.openwebui.yml up -d --build
```

### 4. Open firewall / security list

Allow inbound TCP:

- `3000` for OpenWebUI
- `8000` only if you want direct API access

Recommended: expose only `3000` publicly and keep `8000` private.

### 5. Validate

```bash
curl http://127.0.0.1:8000/health
```

Open in browser:

- `http://<oracle-public-ip>:3000`

### 6. Upgrade workflow

```bash
git pull
docker compose -f docker-compose.openwebui.yml up -d --build
```

### 7. Optional reverse proxy

Place Nginx or Caddy in front of port `3000` for TLS and domain routing.
