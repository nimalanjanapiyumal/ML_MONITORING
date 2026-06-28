param(
    [switch]$Retrain,
    [switch]$SkipTrain,
    [switch]$NoCleanup
)

$ErrorActionPreference = "Stop"

& "$PSScriptRoot\scripts\start_stack.ps1" `
    -Retrain:$Retrain `
    -SkipTrain:$SkipTrain `
    -NoCleanup:$NoCleanup
