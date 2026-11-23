<#
  Starts the GTFS-RT collector with the repo venv and restarts it after a crash.
  Usage:  powershell -ExecutionPolicy Bypass -File collector\start.ps1 -ArchiveDir D:\gtfsrt-archive
          [-Feeds warsaw,krakow_t] [-TripUpdates]
  Stop with Ctrl+C (the collector flushes its buffers on shutdown).
#>
param(
    [Parameter(Mandatory = $true)][string]$ArchiveDir,
    [string]$Feeds = "",
    [switch]$TripUpdates,
    [int]$RestartDelayS = 15
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$Py = Join-Path $Repo ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { throw "venv python not found: $Py" }
New-Item -ItemType Directory -Force -Path $ArchiveDir | Out-Null

$argsList = @("-m", "collector.run", "--archive-dir", $ArchiveDir)
if ($Feeds) { $argsList += @("--feeds", $Feeds) }
if ($TripUpdates) { $argsList += "--trip-updates" }

Set-Location $Repo
while ($true) {
    Write-Host "$(Get-Date -Format s) starting collector"
    & $Py @argsList
    $code = $LASTEXITCODE
    if ($code -eq 0 -or $code -eq 2 -or $code -eq -1073741510) { break }   # clean exit, config error (2) or Ctrl+C: do not restart
    Write-Host "$(Get-Date -Format s) collector exited with code $code; restarting in $RestartDelayS s"
    Start-Sleep -Seconds $RestartDelayS
}
