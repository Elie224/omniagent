@echo off
REM Bootstrap complet du dev env (Windows)
echo === 1. Lancement Docker (PostgreSQL + Redis) ===
cd /d "%~dp0\..\infrastructure\docker"
docker compose up -d
if errorlevel 1 goto :err

echo === 2. venv Python + dependances API ===
cd /d "%~dp0\..\apps\api"
if not exist .venv (
    python -m venv .venv
)
call .venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium

echo === 3. Installation frontend ===
cd /d "%~dp0\..\apps\web"
if not exist node_modules (
    call npm install
)

echo.
echo === 4. Copie des .env si manquants ===
if not exist ".env" copy ".env.example" ".env"
cd /d "%~dp0\..\apps\api"
if not exist ".env" copy ".env.example" ".env"

echo.
echo === Setup termine ! ===
echo   API   : http://localhost:8000/docs
echo   WEB   : http://localhost:3000
echo   Lance l''API avec : cd apps\api ^&^& .venv\Scripts\activate ^&^& uvicorn omniagent.main:app --reload
echo   Lance le WEB avec : cd apps\web ^&^& npm run dev
pause
exit /b 0

:err
echo ERREUR: Docker n''a pas pu demarrer. Verifie que Docker Desktop tourne.
pause
exit /b 1