# Mirror the integration into the live Home Assistant config directory.
# Usage:  .\scripts\sync_to_ha.ps1 [-Target Z:\custom_components\ena_fuel_prices]

param(
    [string]$Target = "Z:\custom_components\ena_fuel_prices"
)

$source = Join-Path $PSScriptRoot "..\custom_components\ena_fuel_prices"
$source = (Resolve-Path $source).Path

robocopy $source $Target /MIR /XD __pycache__ /NFL /NDL /NJH /NJS /NP
if ($LASTEXITCODE -ge 4) {
    Write-Error "robocopy failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host "Synced $source -> $Target"
