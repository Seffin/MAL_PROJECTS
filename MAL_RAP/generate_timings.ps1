# generate_timings.ps1 — Generate timing & USFM files for Malayalam Rap songs
param (
    [string]$track = "",
    [switch]$force = $false
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir

$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = Join-Path $scriptDir "align_venv\Scripts\python.exe"
}
if (-not (Test-Path $python)) {
    $python = "python"
}

$script = Join-Path $scriptDir "generate_all_timings.py"

$cmdArgs = @($script)
if ($track) { $cmdArgs += @("--track", $track) }
if ($force) { $cmdArgs += "--force" }

& $python $cmdArgs
