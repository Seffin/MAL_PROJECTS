# generate_timings.ps1 — Generate timing & USFM files for Malayalam Slow Songs
param (
    [string]$track = "",
    [switch]$force = $false
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir

$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = Join-Path $projectRoot "MAL_RAP\align_venv\Scripts\python.exe"
}
if (-not (Test-Path $python)) {
    $python = "python"
}

$script = Join-Path $scriptDir "generate_all_timings_slow.py"

$cmdArgs = @($script)
if ($track) { $cmdArgs += @("--track", $track) }
if ($force) { $cmdArgs += "--force" }

& $python $cmdArgs
