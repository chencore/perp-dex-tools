Param()
$ErrorActionPreference = 'Stop'

# Repo root
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Join-Path $scriptDir ".."
Set-Location $repoRoot

Write-Host "Scanning for bot processes (runbot.py) under: $repoRoot"

# Find Python processes executing runbot.py from this repo
$procs = Get-CimInstance Win32_Process |
  Where-Object {
    ($_.CommandLine -match "runbot.py") -and
    ($_.CommandLine -match [Regex]::Escape($repoRoot))
  }

if (-not $procs) {
  Write-Host "No matching bot processes found."
} else {
  $procs | ForEach-Object {
    try {
      $pid = $_.ProcessId
      $cmd = $_.CommandLine
      Write-Host "Stopping PID=$pid : $cmd"
      Stop-Process -Id $pid -Force -ErrorAction Stop
    } catch {
      Write-Host "Failed to stop PID=$pid: $_"
    }
  }
}

# Clean up common pid files if present
$pidFiles = @("bot.pid") + (Get-ChildItem -Path . -Filter "bot_*.pid" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
foreach ($pf in $pidFiles) { if (Test-Path $pf) { Remove-Item $pf -ErrorAction SilentlyContinue } }

Write-Host "Done."
