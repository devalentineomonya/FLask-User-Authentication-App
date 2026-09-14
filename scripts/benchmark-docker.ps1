$ErrorActionPreference = "Stop"

$ResultsDir = "results/docker"
New-Item -ItemType Directory -Force -Path $ResultsDir | Out-Null

$RunId = Get-Date -Format "yyyyMMdd_HHmmss"
$ResultsFile = "$ResultsDir/run_$RunId.json"

Write-Host "============================================"
Write-Host "  DOCKER COMPOSE BENCHMARK - Run $RunId"
Write-Host "============================================"

Write-Host "[1/6] Cleaning previous state..."
docker compose -f docker-compose.benchmark.yml down -v --remove-orphans
docker system prune -f
Start-Sleep -Seconds 5

Write-Host "[2/6] Building images (no cache)..."
$BuildStart = Get-Date
docker compose -f docker-compose.benchmark.yml build --no-cache | Tee-Object -FilePath "$ResultsDir/build_log_$RunId.txt"
$BuildEnd = Get-Date
$BuildTimeMs = [math]::Round(($BuildEnd - $BuildStart).TotalMilliseconds)

Write-Host "[3/6] Starting containers..."
$StartStart = Get-Date
docker compose -f docker-compose.benchmark.yml up -d
$StartEnd = Get-Date
$StartTimeMs = [math]::Round(($StartEnd - $StartStart).TotalMilliseconds)

Write-Host "[4/6] Waiting for /health endpoint..."
$HealthStart = Get-Date
$HealthTimeout = 180
$Elapsed = 0
$HealthReached = $false

while ($Elapsed -lt $HealthTimeout) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 5
        if ($response.StatusCode -eq 200) {
            $HealthReached = $true
            break
        }
    } catch {}
    Start-Sleep -Seconds 2
    $Elapsed += 2
    Write-Host "       ... waiting ($Elapsed sec)"
}

$HealthEnd = Get-Date
$HealthTimeMs = [math]::Round(($HealthEnd - $HealthStart).TotalMilliseconds)
$TotalDeployTimeMs = [math]::Round(($HealthEnd - $BuildStart).TotalMilliseconds)

$DeploySuccess = $false
$FailureReason = "none"

if ($HealthReached) {
    $DeploySuccess = $true
    Write-Host "       Health check PASSED"
} else {
    $FailureReason = "health_timeout_after_${HealthTimeout}s"
    Write-Host "       TIMEOUT - app never became healthy"
}

Write-Host "[5/6] Collecting resource usage..."
Start-Sleep -Seconds 10

$DockerStats = docker stats --no-stream --format "{{ json . }}"
$ResourceSnapshot = @()
if ($DockerStats) {
    $ResourceSnapshot = $DockerStats | ForEach-Object { $_ | ConvertFrom-Json }
}

$RunningCount = (docker compose -f docker-compose.benchmark.yml ps --status running -q).Count
$TotalContainers = (docker compose -f docker-compose.benchmark.yml ps -q).Count

$ComposeLines = (Get-Content docker-compose.benchmark.yml).Count
$DockerfileLines = (Get-Content Dockerfile).Count
$DockerfileNotifLines = if (Test-Path Dockerfile.notification) { (Get-Content Dockerfile.notification).Count } else { 0 }

$TotalConfigLines = $ComposeLines + $DockerfileLines + $DockerfileNotifLines
$ConfigFileCount = if (Test-Path Dockerfile.notification) { 3 } else { 2 }

Write-Host "[6/6] Writing results..."

$result = @{
    run_id = $RunId
    orchestrator = "docker-compose"
    timestamp = (Get-Date).ToString("o")
    deployment = @{
        success = $DeploySuccess
        failure_reason = $FailureReason
        total_time_ms = $TotalDeployTimeMs
        build_time_ms = $BuildTimeMs
        start_time_ms = $StartTimeMs
        health_ready_time_ms = $HealthTimeMs
    }
    containers = @{
        total = $TotalContainers
        running = $RunningCount
    }
    complexity = @{
        config_files_count = $ConfigFileCount
        config_total_lines = $TotalConfigLines
        compose_file_lines = $ComposeLines
        dockerfile_lines = $DockerfileLines
        concepts_required = @("services", "volumes", "depends_on", "healthcheck")
        cli_tools_required = @("docker", "docker compose")
        cli_tools_count = 2
    }
    resources = $ResourceSnapshot
}

$result | ConvertTo-Json -Depth 6 | Set-Content $ResultsFile

Write-Host ""
Write-Host "RESULTS: $ResultsFile"
Write-Host "Success: $DeploySuccess"
Write-Host "Total time: $([math]::Round($TotalDeployTimeMs / 1000, 2)) seconds"

Write-Host "Tearing down..."
docker compose -f docker-compose.benchmark.yml down -v
Write-Host "Done."