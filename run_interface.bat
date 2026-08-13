@echo off
setlocal
cd /d "%~dp0"

set "VENV_PY=%~dp0.venv\Scripts\python.exe"
set "PY312=C:\Users\ANAS\AppData\Local\Programs\Python\Python312\python.exe"

if exist "%VENV_PY%" (
	"%VENV_PY%" -c "import uvicorn" >nul 2>nul
	if not errorlevel 1 (
		"%VENV_PY%" -m uvicorn openwebui_api:app --host 127.0.0.1 --port 8000
		goto :eof
	)
)

python -c "import uvicorn" >nul 2>nul
if not errorlevel 1 (
	python -m uvicorn openwebui_api:app --host 127.0.0.1 --port 8000
	goto :eof
)

if exist "%PY312%" (
	"%PY312%" -c "import uvicorn" >nul 2>nul
	if not errorlevel 1 (
		"%PY312%" -m uvicorn openwebui_api:app --host 127.0.0.1 --port 8000
		goto :eof
	)
)

echo ERROR: No Python interpreter with uvicorn found.
echo Install dependencies with:
echo   python -m pip install fastapi uvicorn[standard] pydantic python-dotenv
exit /b 1
