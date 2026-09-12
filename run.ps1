<#
  clipbin launcher for Windows (PowerShell).
    .\run.ps1              start server + clipboard watcher
    .\run.ps1 server       server only
    .\run.ps1 watch        clipboard watcher only
  Extra flags pass straight to run.py, e.g. .\run.ps1 --port 9000
#>
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$py = $null
foreach ($c in @("python", "python3", "py")) {
    if (Get-Command $c -ErrorAction SilentlyContinue) { $py = $c; break }
}
if (-not $py) {
    Write-Error "Python 3 is required but was not found. Install it from https://python.org"
    exit 1
}

& $py run.py @args
