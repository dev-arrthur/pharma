@echo off
cd /d "%~dp0"
if not exist .env (copy .env.example .env >nul & notepad .env & echo Configure o banco e execute novamente. & pause & exit /b 1)
py -3 -m venv .venv
if errorlevel 1 (echo Instale Python 3. & pause & exit /b 1)
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (pause & exit /b 1)
.venv\Scripts\python.exe gerar_relatorio.py
if errorlevel 1 (pause & exit /b 1)
start "" "Maximum-Farmacia-Relatorio.pdf"
pause
