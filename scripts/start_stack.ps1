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
        "nhmf-zabbix-agent"
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
Write-Host "Services:"
Write-Host "Grafana:       http://localhost:3000  admin/admin123"
Write-Host "Prometheus:    http://localhost:9090"
Write-Host "Alertmanager:  http://localhost:9093"
Write-Host "ML API:        http://localhost:8000/health"
Write-Host "Zabbix:        http://localhost:8080  Admin/zabbix"
