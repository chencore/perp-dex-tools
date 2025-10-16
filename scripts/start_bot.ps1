Param(
  [string]$Exchange = "lighter",
  [string]$Ticker = "ETH",
  [double]$Quantity = 0.01,
  [double]$TakeProfit = 0.02,
  [int]$MaxOrders = 40,
  [int]$WaitTime = 450,
  [double]$StopPrice = 5000
)

$ErrorActionPreference = 'Stop'

# Move to repo root
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Join-Path $scriptDir ".."
Set-Location $repoRoot

# Load .env into environment variables if present
$envPath = Join-Path $repoRoot ".env"
if (Test-Path $envPath) {
  Get-Content $envPath | ForEach-Object {
    $line = $_.Trim()
    if (-not [string]::IsNullOrWhiteSpace($line) -and -not $line.StartsWith('#') -and $line.Contains('=')) {
      $pair = $line.Split('=',2)
      $key = $pair[0].Trim()
      $val = $pair[1]
      [Environment]::SetEnvironmentVariable($key, $val)
    }
  }
}

# Prepare logs directory and file
$logsDir = Join-Path $repoRoot "logs"
if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir | Out-Null }
$timestamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$logFile = Join-Path $logsDir ("{0}_{1}_{2}.log" -f $Exchange,$Ticker,$timestamp)

# Choose python executable
$python = "python"
try { Get-Command $python -ErrorAction Stop | Out-Null } catch { $python = "python3" }

# Build arguments
$argsList = @(
  "runbot.py",
  "--exchange", $Exchange,
  "--ticker", $Ticker,
  "--quantity", $Quantity,
  "--take-profit", $TakeProfit,
  "--max-orders", $MaxOrders,
  "--wait-time", $WaitTime,
  "--stop-price", $StopPrice
)

# Start in background and redirect stdout/stderr to the same log
$startInfo = New-Object System.Diagnostics.ProcessStartInfo
$startInfo.FileName = $python
$startInfo.Arguments = [string]::Join(' ', ($argsList | ForEach-Object { if($_ -match ' ') { '"' + $_ + '"' } else { $_ } }))
$startInfo.RedirectStandardOutput = $true
$startInfo.RedirectStandardError = $true
$startInfo.UseShellExecute = $false
$startInfo.CreateNoWindow = $true
$startInfo.WorkingDirectory = $repoRoot

$process = New-Object System.Diagnostics.Process
$process.StartInfo = $startInfo

# Open log writer
$logStream = New-Object System.IO.StreamWriter($logFile, $true)
$logStream.AutoFlush = $true

# Data handlers to append output
$process.add_OutputDataReceived({ param($sender,$e) if ($e.Data) { $logStream.WriteLine($e.Data) } })
$process.add_ErrorDataReceived({ param($sender,$e) if ($e.Data) { $logStream.WriteLine($e.Data) } })

if (-not $process.Start()) { throw "Failed to start trading bot process" }
$process.BeginOutputReadLine()
$process.BeginErrorReadLine()

# Save PID
$pidFile = Join-Path $repoRoot "bot.pid"
[IO.File]::WriteAllText($pidFile, $process.Id.ToString())

Write-Host ("Started bot (PID={0}). Logs: {1}" -f $process.Id, $logFile)
Write-Host ("PID file: {0}" -f $pidFile)
