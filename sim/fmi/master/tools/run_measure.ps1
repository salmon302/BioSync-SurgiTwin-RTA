# SPDX-License-Identifier: MIT
# Metadata header (AGENTS.md section 3)
# Title: single-node master skew and jitter run (plan task 2.8 slice 1)
# Date: 2026-11-05T21:00:00Z
# Author: Seth Nenninger (Claude Haiku 5.5 Agent)
# Contribution Type: Implementation
# Ticket/Context: plan task 2.8 slice 1
# Summary: Extracts thermal_pennes.fmu, starts the rclpy harness, runs fmi_master_node against it, records host state before and after, and writes the JSON record and the per-message sidecar to SNDEV/logs/.
#
# Usage (after build.ps1 and sim\fmi\build.ps1): powershell -ExecutionPolicy Bypass -File sim\fmi\master\tools\run_measure.ps1 [-Duration 600]
# Defaults: 600 s at the 100 Hz planned publish rate. Use -Duration 5 for a smoke run.

param(
    [int]$Duration = 600,
    [ValidateSet('high_resolution', 'sleep')][string]$TimerMode = 'high_resolution',
    [string]$FmuPath = '',
    [string]$LogDir = ''
)

$ErrorActionPreference = 'Stop'

$toolsDir = $PSScriptRoot
$masterDir = Split-Path -Parent $toolsDir
$repoDir = (Resolve-Path (Join-Path $masterDir '..\..\..')).Path
$manifest = Join-Path $repoDir 'env\ros2-jazzy\pixi.toml'
$pixi = 'C:\Users\salmo\AppData\Local\pixi\bin\pixi.exe'
$install = Join-Path $masterDir 'build\install'
$masterExe = Join-Path $install 'srtra_fmi_master\lib\srtra_fmi_master\fmi_master_node.exe'
$measure = Join-Path $toolsDir 'measure_master.py'
if (-not $FmuPath) { $FmuPath = Join-Path $repoDir 'sim\fmi\build\fmu\thermal_pennes.fmu' }
if (-not $LogDir) { $LogDir = Join-Path $repoDir 'SNDEV\logs' }
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

if (-not (Test-Path $masterExe)) { throw "fmi_master_node not found at $masterExe. Run sim\fmi\master\build.ps1 first." }
if (-not (Test-Path $FmuPath)) { throw "FMU not found at $FmuPath. Run sim\fmi\build.ps1 first." }

$stamp = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHHmmssZ')
$tag = "fmi-master-measure-$($Duration)s-$TimerMode-$stamp"
$json = Join-Path $LogDir "$tag.json"
$ready = Join-Path $LogDir "$tag-ready.flag"
$harnessOut = Join-Path $LogDir "$tag-harness.txt"
$harnessErr = Join-Path $LogDir "$tag-harness-stderr.txt"
$masterOut = Join-Path $LogDir "$tag-master.txt"
$masterErr = Join-Path $LogDir "$tag-master-stderr.txt"

# Host state (Get-Process and a 5 s CPU sample). The record shows the state before and after the run.
function Get-HostState([string]$label) {
    $names = 'runSofa', 'colcon', 'Slicer', 'ninja', 'cmake'
    $procs = Get-Process | Where-Object { $names -contains $_.ProcessName -or $_.ProcessName -like 'Slicer*' }
    $cpu = (Get-Counter '\Processor(_Total)\% Processor Time' -SampleInterval 5 -MaxSamples 1).CounterSamples[0].CookedValue
    $lines = @("label=$label utc=$((Get-Date).ToUniversalTime().ToString('o')) total_cpu_percent_5s=$([math]::Round($cpu,1)) logical_processors=$([Environment]::ProcessorCount)")
    foreach ($p in $procs) {
        $lines += "process=$($p.ProcessName) pid=$($p.Id) threads=$($p.Threads.Count) cpu_seconds_total=$([math]::Round($p.CPU,1))"
    }
    if (-not $procs) { $lines += 'process=none (no matching processes)' }
    return $lines
}

$hostBefore = Join-Path $LogDir "$tag-host-before.txt"
Get-HostState 'before' | Set-Content -Path $hostBefore -Encoding utf8

# Unzip the FMU to a scratch directory and read the instantiation token from modelDescription.xml.
$scratch = Join-Path 'C:\Users\salmo\AppData\Local\Temp\opencode' "fmi-master-$stamp"
New-Item -ItemType Directory -Force -Path $scratch | Out-Null
$zip = Join-Path $scratch 'thermal_pennes.zip'
Copy-Item -Path $FmuPath -Destination $zip
Expand-Archive -Path $zip -DestinationPath (Join-Path $scratch 'fmu') -Force
$fmuDir = Join-Path $scratch 'fmu'
[xml]$md = Get-Content -Raw -Path (Join-Path $fmuDir 'modelDescription.xml')
$token = $md.fmiModelDescription.instantiationToken
if (-not $token) { throw 'instantiationToken not found in modelDescription.xml' }

$env:RMW_IMPLEMENTATION = 'rmw_fastrtps_cpp'
. (Join-Path $install 'local_setup.ps1')

$harnessArgs = @('run', '--manifest-path', $manifest, '--', 'python', $measure,
    '--rate-hz', '100', '--duration', "$Duration", '--base-step-ms', '10', '--fmu-step-ms', '100',
    '--timer-mode', $TimerMode, '--out', $json, '--ready-file', $ready)
$harness = Start-Process -FilePath $pixi -ArgumentList $harnessArgs -NoNewWindow -PassThru `
    -RedirectStandardOutput $harnessOut -RedirectStandardError $harnessErr

$waited = 0
while (-not (Test-Path $ready) -and $waited -lt 120 -and -not $harness.HasExited) {
    Start-Sleep -Milliseconds 250
    $waited += 0.25
}
if (-not (Test-Path $ready)) { throw "harness did not become ready: $harnessErr" }

$ErrorActionPreference = 'Continue'
& $pixi run --manifest-path $manifest -- $masterExe --ros-args `
    -p "fmu_dir:=$fmuDir" -p "instantiation_token:=$token" -p "duration_s:=$Duration" `
    -p 'base_step_ms:=10' -p 'fmu_step_ms:=100' -p "timer_mode:=$TimerMode" `
    -p 'model_identifier:=thermal_pennes' -p 'participant_name:=thermal_pennes' `
    > $masterOut 2> $masterErr
$masterExit = $LASTEXITCODE
$ErrorActionPreference = 'Stop'

$harness.WaitForExit(($Duration + 180) * 1000) | Out-Null
Remove-Item -Force -ErrorAction SilentlyContinue $ready

$hostAfter = Join-Path $LogDir "$tag-host-after.txt"
Get-HostState 'after' | Set-Content -Path $hostAfter -Encoding utf8

$recordWritten = Test-Path $json
"master_exit=$masterExit harness_exit=$($harness.ExitCode) record_written=$recordWritten json=$json"
if ($masterExit -ne 0 -or -not $recordWritten) { exit 1 }
exit 0
