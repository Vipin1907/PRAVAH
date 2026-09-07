Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "      Starting PravahAI Full Stack System          " -ForegroundColor Yellow
Write-Host "===================================================" -ForegroundColor Cyan

# 1. Master AI/ML & Routing Backend (Port 5000)
Write-Host "[1/2] Starting Unified AI/ML & Routing Backend (Port 5000)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "python src/backend_api/main.py"

Start-Sleep -Seconds 2

# 2. Web Application & API Gateway (Port 3000)
Write-Host "[2/2] Starting Web Application & API Gateway (Port 3000)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd src/backend_api; node SERVER.JS"

Write-Host "`nAll services connected and running! Opening http://localhost:3000..." -ForegroundColor Cyan
Start-Sleep -Seconds 2
Start-Process "http://localhost:3000"
