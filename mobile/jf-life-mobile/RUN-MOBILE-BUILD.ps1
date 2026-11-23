param(
    [ValidateSet("android", "ios", "all")]
    [string]$Platform = "android"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    throw "Node.js is required. Install Node.js LTS, then rerun."
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm is required. Install Node.js LTS, then rerun."
}

npm ci --ignore-scripts
npm run typecheck

$targets = if ($Platform -eq "all") { @("android", "ios") } else { @($Platform) }
foreach ($target in $targets) {
    Write-Host "Building JF LIFE native preview for $target..."
    npx eas-cli@latest build --platform $target --profile preview
    if ($LASTEXITCODE -ne 0) {
        throw "JF LIFE $target build failed with exit code $LASTEXITCODE"
    }
}
