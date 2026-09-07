@echo off
echo ===================================================
echo       Starting PravahAI Full Stack System
echo ===================================================

echo [1/4] Starting ML Prediction Service (Port 5000)...
start "PravahAI - ML API (5000)" cmd /k "python src/ml_model/ml_api.py"

timeout /t 2 /nobreak >nul

echo [2/4] Starting AI Explainability Service (Port 5001)...
start "PravahAI - AI API (5001)" cmd /k "python src/backend_api/ai_api.py"

timeout /t 1 /nobreak >nul

echo [3/4] Starting Safe Routing Service (Port 5002)...
start "PravahAI - Route API (5002)" cmd /k "python src/backend_api/route_api.py"

timeout /t 1 /nobreak >nul

echo [4/4] Starting API Gateway & Web App (Port 3000)...
start "PravahAI - Web Server (3000)" cmd /k "cd src/backend_api && node SERVER.JS"

echo.
echo ===================================================
echo  All services launched successfully!
echo  Opening browser at: http://localhost:3000
echo ===================================================
start http://localhost:3000
