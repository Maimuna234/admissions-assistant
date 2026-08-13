@echo off
setlocal
cd /d "%~dp0"
docker compose -f docker-compose.openwebui.yml up -d --build
echo OpenWebUI stack started.
echo UI: http://localhost:3000
echo API health: http://localhost:8000/health
