@echo off
echo ===================================================
echo       Starting PravahAI Full Stack System
echo ===================================================

echo [1/2] Starting Unified AI/ML and Routing Backend (Port 5000)...
start "PravahAI - Master Python Backend (5000)" cmd /k "python src/backend_api/main.py"

ping 127.0.0.1 -n 3 >nul

echo [2/2] Starting Web Application and API Gateway (Port 3000)...
start "PravahAI - Express Gateway (3000)" cmd /k "cd src\backend_api && node SERVER.JS"

echo.
echo ===================================================
echo  All services connected and launched successfully!
echo  Opening browser at: http://localhost:3000
echo ===================================================
start http://localhost:3000
