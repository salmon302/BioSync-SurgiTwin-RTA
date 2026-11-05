# SPDX-License-Identifier: MIT
# Metadata header (AGENTS.md section 3)
# Title: sim/bridge smoke measurement driver (plan task 2.4 slice 1)
# Date: 2026-11-05T15:53:25Z
# Author: Seth Nenninger (Builder_Int34 Agent)
# Contribution Type: Implementation
# Ticket/Context: plan task 2.4 slice 1
# Summary: Runs bridge_node at each requested rate with the rmw_fastrtps_cpp subscriber (measure_rate.py) and writes JSON and transcripts to SNDEV/logs/.
#
# Usage (after build.ps1): powershell -ExecutionPolicy Bypass -File sim\bridge\tools\run_smoke.ps1
# Defaults: rates 100 and 500 Hz, 60 s each. Slice 1 is a smoke run and is not the G2.4 gate.
# Optional: -Rates 500 -Duration 600 for the slice 2 gate run, -LogDir for scratch output.
# -Rates takes a comma-separated string because array arguments are not bound under powershell -File.

param(
    [string]$Rates = '100,500',
    [int]$Duration = 60,
    [string]$LogDir = ''
)

$ErrorActionPreference = 'Stop'

$toolsDir = $PSScriptRoot
$bridgeDir = Split-Path -Parent $toolsDir
$repoDir = (Resolve-Path (Join-Path $bridgeDir '..\..')).Path
$manifest = Join-Path $repoDir 'env\ros2-jazzy\pixi.toml'
$pixi = 'C:\Users\salmo\AppData\Local\pixi\bin\pixi.exe'
$install = Join-Path $bridgeDir 'build\install'
$bridgeExe = Join-Path $install 'srtra_bridge\lib\srtra_bridge\bridge_node.exe'
$measure = Join-Path $toolsDir 'measure_rate.py'

if (-not $LogDir) { $LogDir = Join-Path $repoDir 'SNDEV\logs' }
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

if (-not (Test-Path $bridgeExe)) { throw "bridge_node not found at $bridgeExe. Run sim\bridge\build.ps1 first." }

$env:RMW_IMPLEMENTATION = 'rmw_fastrtps_cpp'
. (Join-Path $install 'local_setup.ps1')

$rateList = @($Rates -split ',' | ForEach-Object { [int]$_.Trim() })
foreach ($rate in $rateList) {
    $stamp = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHHmmssZ')
    $tag = "bridge-smoke-$($rate)hz-$($Duration)s-$stamp"
    $json = Join-Path $LogDir "$tag.json"
    $subOut = Join-Path $LogDir "$tag-subscriber.txt"
    $subErr = Join-Path $LogDir "$tag-subscriber-stderr.txt"
    $nodeOut = Join-Path $LogDir "$tag-node.txt"
    $nodeErr = Join-Path $LogDir "$tag-node-stderr.txt"

    $ready = Join-Path $LogDir "$tag-ready.flag"
    $subArgs = @('run', '--manifest-path', $manifest, '--', 'python', $measure,
        '--rate', "$rate", '--duration', "$Duration", '--out', $json, '--ready-file', $ready)
    $sub = Start-Process -FilePath $pixi -ArgumentList $subArgs -NoNewWindow -PassThru `
        -RedirectStandardOutput $subOut -RedirectStandardError $subErr

    $waited = 0
    while (-not (Test-Path $ready) -and $waited -lt 120) {
        Start-Sleep -Milliseconds 250
        $waited += 0.25
    }
    if (-not (Test-Path $ready)) { throw "subscriber did not become ready: $subErr" }

    # Native stderr carries the rclcpp log lines. Continue avoids treating them as errors.
    $ErrorActionPreference = 'Continue'
    & $pixi run --manifest-path $manifest -- $bridgeExe --ros-args -p "rate_hz:=$rate" -p "duration_s:=$Duration" > $nodeOut 2> $nodeErr
    $nodeExit = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'

    $sub.WaitForExit()
    Remove-Item -Force $ready
    $subOk = Test-Path $json
    "rate=$rate node_exit=$nodeExit subscriber_record_written=$subOk json=$json"
    if ($nodeExit -ne 0 -or -not $subOk) { exit 1 }
}
exit 0
