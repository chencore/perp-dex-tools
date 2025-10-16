Param()
$ErrorActionPreference = 'Stop'

# Repo root
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Join-Path $scriptDir ".."
Set-Location $repoRoot

$pidFile = Join-Path $repoRoot "bot.pid"
if (-not (Test-Path $pidFile)) {
  Write-Host "bot.pid not found. Is the bot running?"
  exit 0
}

$pid = Get-Content $pidFile | Select-Object -First 1
if (-not $pid) {
  Write-Host "Empty bot.pid."
  exit 0
}

try {
  $proc = Get-Process -Id $pid -ErrorAction Stop
  Write-Host "Stopping bot (PID=$pid)..."
  Stop-Process -Id $pid -Force
  Start-Sleep -Seconds 1
} catch {
  Write-Host "Process $pid not found."
}

Remove-Item $pidFile -ErrorAction SilentlyContinue
Write-Host "Bot stopped."
