# PowerShell script to start the development environment
# Usage: .\scripts\dev-shell.ps1

Write-Host "Starting RAGstone Development Environment..." -ForegroundColor Cyan

# Check if Docker is running
$dockerRunning = docker info 2>&1 | Select-String "Server Version"
if (-not $dockerRunning) {
    Write-Host "Error: Docker is not running. Please start Docker Desktop first." -ForegroundColor Red
    exit 1
}

# Build and start the container
Write-Host "Building development container..." -ForegroundColor Yellow
docker-compose -f docker-compose.dev.yml build

Write-Host "Starting development shell..." -ForegroundColor Yellow
docker-compose -f docker-compose.dev.yml run --rm dev

Write-Host "Development session ended." -ForegroundColor Cyan
