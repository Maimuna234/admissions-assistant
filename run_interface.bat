@echo off
setlocal
cd /d "%~dp0"
"%~dp0.venv\Scripts\python.exe" -m uvicorn openwebui_api:app --host 127.0.0.1 --port 8000
