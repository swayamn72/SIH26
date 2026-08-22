# MuleGuard Local — Windows Setup Script
Write-Host "=== MuleGuard Local Setup ===" -ForegroundColor Cyan

# Check prerequisites
$hasDocker = Get-Command docker -ErrorAction SilentlyContinue
if (-not $hasDocker) {
    Write-Host "ERROR: Docker is not installed. Please install Docker Desktop for Windows." -ForegroundColor Red
    exit 1
}

# Create data directories
$dataDirs = @("data\uploads", "data\db", "data\exports")
foreach ($dir in $dataDirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "Created $dir" -ForegroundColor Green
    }
}

# Copy env if not exists
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example" -ForegroundColor Green
}

Write-Host ""
Write-Host "Starting MuleGuard..." -ForegroundColor Cyan
Write-Host "This will build the Docker images and start the services." -ForegroundColor Yellow
Write-Host "The Ollama model will be pulled on first start (requires ~4.5GB download)." -ForegroundColor Yellow
Write-Host ""

docker-compose up --build

Write-Host ""
Write-Host "MuleGuard is ready at http://localhost:8000" -ForegroundColor Green
Write-Host "This application does not require, and will not use, an internet connection from this point forward." -ForegroundColor Green
