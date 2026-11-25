@echo off
cd /d "%~dp0"
where node >nul 2>&1 || (echo Instale Node.js 20 ou superior. & pause & exit /b 1)
if not exist .env (copy .env.example .env >nul & notepad .env & echo Salve o arquivo .env e execute START novamente. & pause & exit /b 0)
call npm install
if errorlevel 1 (pause & exit /b 1)
start "" http://localhost:3000
call npm start
pause
