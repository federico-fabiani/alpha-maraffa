# AZ pipeline launcher — ISMCTS + distillation Marafone training.
#
# Usage:
#   .\train_az.ps1                                # default: 1 iter, 1000 rounds, curriculum
#   .\train_az.ps1 -Iters 10                      # 10 iters
#   .\train_az.ps1 -Iters 30 -Rounds 1500 -PureSelfPlay
#   .\train_az.ps1 -Iters 5  -Rounds 500 -Workers 4 -TourneyGames 1000
#
# All flags are optional; defaults match docs/az-runbook.md "Promotion" phase.

[CmdletBinding()]
param(
    [int]    $Iters         = 1,
    [int]    $Rounds        = 1000,
    [int]    $Workers       = 8,
    [int]    $TourneyGames  = 4000,
    [string] $Device        = "cuda",
    # When set, runs pure self-play (no heuristic team).
    [switch] $PureSelfPlay,
    # Override heuristic team (1 or 2). Ignored when -PureSelfPlay is set.
    [int]    $HeuristicTeam = 2,
    [string] $LogLevel      = "INFO"
)

$ErrorActionPreference = "Stop"
Set-Location -Path "$PSScriptRoot\game\backend"

$cmd = @(
    "run", "python", "-m", "aimaraffa.ai.az_pipeline",
    "--iters",         $Iters,
    "--rounds",        $Rounds,
    "--workers",       $Workers,
    "--tourney-games", $TourneyGames,
    "--device",        $Device,
    "--log-level",     $LogLevel
)

if (-not $PureSelfPlay) {
    $cmd += @("--heuristic-team", $HeuristicTeam)
}

Write-Host "Running: uv $($cmd -join ' ')" -ForegroundColor Cyan
& uv @cmd
exit $LASTEXITCODE
