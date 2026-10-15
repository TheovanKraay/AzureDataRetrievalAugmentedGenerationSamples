#Requires -Version 7.0
[CmdletBinding()]
param(
  [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
  [switch]$IncludeDotnet,
  [switch]$Prepare,
  [switch]$RegenerateInvalidName
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$sampleRoot = if ($IncludeDotnet) { Join-Path $ProjectRoot 'python' } else { $ProjectRoot }
$python = if ($IsWindows) {
  Join-Path $sampleRoot '.venv/Scripts/python.exe'
} else {
  Join-Path $sampleRoot '.venv/bin/python'
}
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
  throw 'Create the sample .venv and install requirements.txt before azd provision. See README.'
}
if ($RegenerateInvalidName -and -not $Prepare) {
  throw 'Name recovery is only available through the preprovision hook.'
}
$scriptName = if ($Prepare) { 'prepare_azd.py' } else { 'configure_azd.py' }
$arguments = @((Join-Path $PSScriptRoot $scriptName), '--project-root', $ProjectRoot)
if ($IncludeDotnet -and -not $Prepare) { $arguments += '--include-dotnet' }
if ($RegenerateInvalidName) { $arguments += '--regenerate-invalid-name' }
& $python @arguments
if ($LASTEXITCODE -ne 0) { throw 'Local azd configuration failed. Resolve the error and rerun this hook.' }
