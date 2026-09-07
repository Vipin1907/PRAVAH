Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "      Starting PravahAI Full Stack System          " -ForegroundColor Yellow
Write-Host "===================================================" -ForegroundColor Cyan

# 1. ML Model (Port 5000)
Write-Host "[1/4] Starting ML Prediction Service (Port 5000)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "python src/ml_model/ml_api.py"

Start-Sleep -Seconds 2

# 2. AI Service (Port 5001)
Write-Host "[2/4] Starting AI Explainability Service (Port 5001)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "python src/backend_api/ai_api.py"

Start-Sleep -Seconds 1

# 3. Route API (Port 5002)
Write-Host "[3/4] Starting Safe Routing Service (Port 5002)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "python src/backend_api/route_api.py"

Start-Sleep -Seconds 1

# 4. Node Web Gateway (Port 3000)
Write-Host "[4/4] Starting API Gateway & Web App (Port 3000)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd src/backend_api; node SERVER.JS"

Write-Host "`nAll services started! Opening http://localhost:3000..." -ForegroundColor Cyan
Start-Sleep -Seconds 2
Start-Process "http://localhost:3000"
