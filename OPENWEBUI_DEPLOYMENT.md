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
