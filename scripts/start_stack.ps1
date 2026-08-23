param(
    [switch]$Retrain,
    [switch]$SkipTrain,
    [switch]$NoCleanup
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

if (-not $env:COMPOSE_PROJECT_NAME) {
    $env:COMPOSE_PROJECT_NAME = "nhmf"
}

function Require-Command {
    param([string]$Name)

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Missing required command: $Name"
    }
}

function Ensure-EnvFile {
    if (Test-Path ".env") {
        return
    }

    Copy-Item -LiteralPath ".env.example" -Destination ".env"
    Write-Host "Created default .env file."
}

function Configure-BuildNetwork {
    if (-not $env:DOCKER_BUILD_NETWORK) {
        $env:DOCKER_BUILD_NETWORK = "default"
    }

    if (-not $env:PIP_RETRIES) {
        $env:PIP_RETRIES = "10"
    }

    if (-not $env:PIP_TIMEOUT) {
        $env:PIP_TIMEOUT = "120"
    }

    Write-Host "Docker build network: $env:DOCKER_BUILD_NETWORK"
    Write-Host "Pip retries/timeout: $env:PIP_RETRIES retries, $env:PIP_TIMEOUT seconds timeout"
}

function Cleanup-LegacyContainers {
    if ($NoCleanup) {
        return
    }

    $names = @(
        "nhmf-prometheus",
        "nhmf-alertmanager",
        "nhmf-grafana",
        "nhmf-node-exporter",
        "nhmf-blackbox-exporter",
        "nhmf-pushgateway",
        "nhmf-ml-anomaly",
        "nhmf-zabbix-db",
        "nhmf-zabbix-server",
        "nhmf-zabbix-web",
        "nhmf-zabbix-agent",
        "nhmf-suricata",
        "nhmf-suricata-exporter"
    )

    foreach ($name in $names) {
        $containerId = docker ps -aq --filter "name=^/$name$"
        if ($containerId) {
            Write-Host "Removing stale legacy container: $name"
            docker rm -f $containerId | Out-Null
        }
    }
}

function Ensure-UnswModel {
    $modelPath = Join-Path $ProjectRoot "ml-anomaly\models\unsw_nb15_model.joblib"
    $dataDir = Join-Path $ProjectRoot "Data\UNSW-NB15 dataset\CSV Files\Training and Testing Sets"
    $trainPath = Join-Path $dataDir "UNSW_NB15_training-set.csv"
    $testPath = Join-Path $dataDir "UNSW_NB15_testing-set.csv"

    if ((-not (Test-Path $trainPath)) -or (-not (Test-Path $testPath))) {
        throw "UNSW-NB15 train/test CSV files were not found in: $dataDir"
    }

    New-Item -ItemType Directory -Force -Path (Join-Path $ProjectRoot "ml-anomaly\models") | Out-Null

    if ($SkipTrain) {
        Write-Host "Skipping ML model training."
        return
    }

    if ($Retrain -or -not (Test-Path $modelPath)) {
        Write-Host "Training UNSW-NB15 model inside Docker. This can take several minutes..."
        docker compose build ml-anomaly
        docker compose run --rm --no-deps ml-anomaly python train_unsw_nb15.py
    } else {
        Write-Host "Using existing UNSW-NB15 model: $modelPath"
    }
}

function Test-Url {
    param(
        [string]$Name,
        [string]$Url,
        [int]$TimeoutSeconds = 90,
        [string]$ServiceName = $Name
    )

    Write-Host "Waiting for $Name at $Url " -NoNewline
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                Write-Host " OK"
                return
            }
        } catch {
            Start-Sleep -Seconds 3
            Write-Host "." -NoNewline
        }
    }

    Write-Host " FAILED"
    Write-Host "  Check logs: docker compose logs --tail 120 $ServiceName"
}

Require-Command docker
docker compose version | Out-Null
docker info | Out-Null

Ensure-EnvFile
Configure-BuildNetwork
Cleanup-LegacyContainers
Ensure-UnswModel

Write-Host "Starting Network Health Monitoring Framework..."
docker compose up -d --build

Write-Host ""
docker compose ps

Write-Host ""
Test-Url -Name "Prometheus" -Url "http://localhost:9090/-/healthy" -TimeoutSeconds 60 -ServiceName "prometheus"
Test-Url -Name "Grafana" -Url "http://localhost:3000/api/health" -TimeoutSeconds 120 -ServiceName "grafana"
Test-Url -Name "ML anomaly API" -Url "http://localhost:8000/health" -TimeoutSeconds 90 -ServiceName "ml-anomaly"
Test-Url -Name "Operations Portal" -Url "http://localhost:8088" -TimeoutSeconds 90 -ServiceName "portal"
Test-Url -Name "Zabbix Web" -Url "http://localhost:8080" -TimeoutSeconds 180 -ServiceName "zabbix-web"
Test-Url -Name "Suricata Exporter" -Url "http://localhost:9517/health" -TimeoutSeconds 60 -ServiceName "suricata-exporter"

$pythonCommand = Get-Command python3 -ErrorAction SilentlyContinue
if (-not $pythonCommand) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
}

if ($pythonCommand) {
    Write-Host ""
    Write-Host "Reconciling the four Zabbix monitored servers..."
    & $pythonCommand.Path (Join-Path $PSScriptRoot "zabbix_api_manager.py") setup-demo-hosts
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Zabbix host reconciliation did not complete. Re-run: python scripts\zabbix_api_manager.py setup-demo-hosts"
    }
} else {
    Write-Warning "Python is unavailable; Zabbix host reconciliation was skipped."
}

Write-Host ""
Write-Host "============================================================"
Write-Host " NHMF Services Ready"
Write-Host "============================================================"
Write-Host "Main Portal:          http://localhost:8088"
Write-Host "Grafana:              http://localhost:3000  (admin/admin123)"
Write-Host "ML Dashboard:         http://localhost:3000/d/nhmf-ml/ml-anomaly-detection-dashboard"
Write-Host "Suricata IDS:         http://localhost:3000/d/nhmf-suricata/suricata-ids-dashboard"
Write-Host "Zabbix Dashboard:     http://localhost:3000/d/nhmf-zabbix/zabbix-infrastructure-host-dashboard"
Write-Host "Prometheus:           http://localhost:9090"
Write-Host "Alertmanager:         http://localhost:9093"
Write-Host "ML API:               http://localhost:8000/health"
Write-Host "Suricata Metrics:     http://localhost:9517/metrics"
Write-Host "Zabbix:               http://localhost:8080  (Admin/zabbix)"
Write-Host "Demo scenarios:       scripts/fault_injection/demo_scenarios.sh list"
Write-Host "============================================================"
