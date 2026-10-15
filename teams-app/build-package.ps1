# Build Teams app package with environment-specific Bot ID
# Usage: .\build-package.ps1 -BotId <bot-app-id> [-Environment <dev|prod>]
#
# Examples:
#   .\build-package.ps1 -BotId "00000000-0000-0000-0000-000000000000"
#   .\build-package.ps1 -BotId "abc12345-..." -Environment prod
#
# Get Bot ID from terraform output:
#   cd infrastructure
#   terraform workspace select dev  # or prod
#   terraform output bot_app_id

param(
    [Parameter(Mandatory=$true)]
    [string]$BotId,

    [ValidateSet("dev", "prod")]
    [string]$Environment = "prod"
)

$files = @("color.png", "outline.png")
$packageName = "northwind-ai-$Environment.zip"

Write-Host "Building Teams app package for $Environment..." -ForegroundColor Cyan
Write-Host "Bot ID: $BotId" -ForegroundColor Cyan

# Check if all required files exist
foreach ($file in $files) {
    if (-not (Test-Path $file)) {
        Write-Host "Error: $file not found!" -ForegroundColor Red
        exit 1
    }
}

if (-not (Test-Path "manifest.json")) {
    Write-Host "Error: manifest.json not found!" -ForegroundColor Red
    exit 1
}

# Read and update manifest with the provided Bot ID
$manifest = Get-Content "manifest.json" -Raw | ConvertFrom-Json
$manifest.id = $BotId
$manifest.bots[0].botId = $BotId

# Teams requires the zip root to contain manifest.json (exact name), UTF-8 preferred
$buildDir = Join-Path $env:TEMP "northwind-teams-build-$([guid]::NewGuid().ToString('n'))"
New-Item -ItemType Directory -Path $buildDir | Out-Null
try {
    $manifestPath = Join-Path $buildDir "manifest.json"
    $jsonText = ($manifest | ConvertTo-Json -Depth 10)
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($manifestPath, $jsonText, $utf8NoBom)
    foreach ($file in $files) {
        Copy-Item -Path $file -Destination $buildDir
    }

    # Remove old package if exists
    if (Test-Path $packageName) {
        Remove-Item $packageName
    }

    Compress-Archive -Path (Join-Path $buildDir '*') -DestinationPath $packageName -Force
}
finally {
    Remove-Item -Path $buildDir -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Package created: $packageName" -ForegroundColor Green
Write-Host ""
Write-Host "Upload this file to Teams Admin Center:" -ForegroundColor Yellow
Write-Host "  https://admin.teams.microsoft.com/policies/manage-apps" -ForegroundColor Yellow
