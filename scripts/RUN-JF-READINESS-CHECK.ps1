param(
    [string]$StateDir = "$(Join-Path $env:LOCALAPPDATA 'JF LIFE')",
    [int]$Port = 8712
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")
Set-Location $repoRoot

if (Get-Command py -ErrorAction SilentlyContinue) {
    py -3 scripts/jf_life_readiness.py --state-dir $StateDir --port $Port
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    python scripts/jf_life_readiness.py --state-dir $StateDir --port $Port
} else {
    throw "Python not found. Install Python 3, then rerun."
}

exit $LASTEXITCODE
