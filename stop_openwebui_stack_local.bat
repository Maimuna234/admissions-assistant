@echo off
setlocal
cd /d "%~dp0"
docker compose -f docker-compose.openwebui.yml down
echo OpenWebUI stack stopped.
