# SPDX-License-Identifier: MIT
# Metadata header (AGENTS.md section 3)
# Title: single-node multi-rate master run (plan task 2.8 slice 2)
# Date: 2026-11-11T09:00:00Z
# Author: Seth Nenninger (Claude Haiku 5.5 Agent)
# Contribution Type: Implementation
# Ticket/Context: plan task 2.8 slice 2
# Summary: Extracts the three FMUs into one root, starts the multi-stream harness, runs fmi_multirate_node for the given duration on this host, and records host state before and after.
#
# Usage (after sim\fmi\build.ps1 and sim\fmi\master\build.ps1): powershell -ExecutionPolicy Bypass -File sim\fmi\master\tools\run_multirate.ps1 -Duration 600
# The Pulse worker container must be running on 127.0.0.1:5055 (the Pulse FMU precondition).

param(
    [int]$Duration = 600,
    [string]$Tag = 'single-node',
    [string]$LogDir = ''
)

$ErrorActionPreference = 'Stop'

$toolsDir = $PSScriptRoot
$masterDir = Split-Path -Parent $toolsDir
$repoDir = (Resolve-Path (Join-Path $masterDir '..\..\..')).Path
$manifest = Join-Path $repoDir 'env\ros2-jazzy\pixi.toml'
$pixi = 'C:\Users\salmo\AppData\Local\pixi\bin\pixi.exe'
$install = Join-Path $masterDir 'build\install'
$nodeExe = Join-Path $install 'srtra_fmi_master\lib\srtra_fmi_master\fmi_multirate_node.exe'
$measure = Join-Path $toolsDir 'measure_multirate.py'
if (-not $LogDir) { $LogDir = Join-Path $repoDir 'SNDEV\logs' }
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

if (-not (Test-Path $nodeExe)) { throw "fmi_multirate_node not found at $nodeExe. Run sim\fmi\master\build.ps1 first." }
$fmuBuild = Join-Path $repoDir 'sim\fmi\build\fmu'
foreach ($n in 'thermal_pennes', 'mechanical_sofa', 'pulse_physiology') {
    if (-not (Test-Path (Join-Path $fmuBuild "$n.fmu"))) { throw "FMU missing: $n.fmu (run sim\fmi\build.ps1)" }
}

$stamp = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHHmmssZ')
$tag = "fmi-multirate-$Tag-$($Duration)s-$stamp"
$json = Join-Path $LogDir "$tag.json"
$ready = Join-Path $LogDir "$tag-ready.flag"
$harnessOut = Join-Path $LogDir "$tag-harness.txt"
$harnessErr = Join-Path $LogDir "$tag-harness-stderr.txt"
$nodeOut = Join-Path $LogDir "$tag-node.txt"
$nodeErr = Join-Path $LogDir "$tag-node-stderr.txt"

function Get-HostState([string]$label) {
    $procs = Get-Process | Where-Object { $_.ProcessName -match '^(Warhammer|Roblox|runSofa|colcon|Slicer|ninja|cmake|pixi|python)' }
    $cpu = (Get-Counter '\Processor(_Total)\% Processor Time' -SampleInterval 5 -MaxSamples 1).CounterSamples[0].CookedValue
    $lines = @("label=$label utc=$((Get-Date).ToUniversalTime().ToString('o')) total_cpu_percent_5s=$([math]::Round($cpu,1)) logical_processors=$([Environment]::ProcessorCount)")
    foreach ($p in $procs) { $lines += "process=$($p.ProcessName) pid=$($p.Id) threads=$($p.Threads.Count) cpu_seconds_total=$([math]::Round($p.CPU,1))" }
    if (-not $procs) { $lines += 'process=none (no matching processes)' }
    return $lines
}
Get-HostState 'before' | Set-Content -Path (Join-Path $LogDir "$tag-host-before.txt") -Encoding utf8

$scratch = Join-Path 'C:\Users\salmo\AppData\Local\Temp\opencode' "fmi-multirate-$stamp"
$root = Join-Path $scratch 'fmu'
foreach ($n in 'thermal_pennes', 'mechanical_sofa', 'pulse_physiology') {
    $dest = Join-Path $root $n
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    Copy-Item -Path (Join-Path $fmuBuild "$n.fmu") -Destination (Join-Path $dest "$n.zip")
    Expand-Archive -Path (Join-Path $dest "$n.zip") -DestinationPath $dest -Force
}

$env:RMW_IMPLEMENTATION = 'rmw_fastrtps_cpp'
. (Join-Path $install 'local_setup.ps1')

$harnessArgs = @('run', '--manifest-path', $manifest, '--', 'python', $measure,
    '--rate-hz', '1000', '--duration', "$Duration", '--out', $json, '--ready-file', $ready,
    '--scope', 'single-host-loopback-one-node')
$harness = Start-Process -FilePath $pixi -ArgumentList $harnessArgs -NoNewWindow -PassThru `
    -RedirectStandardOutput $harnessOut -RedirectStandardError $harnessErr

$waited = 0
while (-not (Test-Path $ready) -and $waited -lt 180 -and -not $harness.HasExited) {
    Start-Sleep -Milliseconds 250
    $waited += 0.25
}
if (-not (Test-Path $ready)) { throw "harness did not become ready: $harnessErr" }

# The node needs the pixi library directory and the package bin directory on PATH. Without them the process
# exits with 0xC0000135 (a missing DLL) and writes nothing. The same entries are used by the direct run.
$pixiEnv = Join-Path $repoDir 'env\ros2-jazzy\.pixi\envs\default'
$env:PATH = "$pixiEnv;$pixiEnv\Library\bin;$install\srtra_fmi_master\bin;" + $env:PATH
$ErrorActionPreference = 'Continue'
& $nodeExe --ros-args `
    -p "fmu_root:=$root" -p "duration_s:=$Duration" -p 'timer_mode:=high_resolution' -p 'pulse_port:=5055' `
    > $nodeOut 2> $nodeErr
$nodeExit = $LASTEXITCODE
$ErrorActionPreference = 'Stop'

$harness.WaitForExit(($Duration + 240) * 1000) | Out-Null
Remove-Item -Force -ErrorAction SilentlyContinue $ready
Get-HostState 'after' | Set-Content -Path (Join-Path $LogDir "$tag-host-after.txt") -Encoding utf8

$recordWritten = Test-Path $json
"node_exit=$nodeExit harness_exit=$($harness.ExitCode) record_written=$recordWritten json=$json"
if ($nodeExit -ne 0 -or -not $recordWritten) { exit 1 }
exit 0
