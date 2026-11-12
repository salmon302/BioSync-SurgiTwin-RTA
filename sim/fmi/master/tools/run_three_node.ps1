# SPDX-License-Identifier: MIT
# Metadata header (AGENTS.md section 3)
# Title: three-node G2.6 run launcher (plan task 2.8 slice 2)
# Date: 2026-11-11T09:00:00Z
# Author: Seth Nenninger (Claude Haiku 5.5 Agent)
# Contribution Type: Implementation
# Ticket/Context: plan task 2.8 slice 2
# Summary: Starts the three participant processes (mechanical on node 2, Pulse on node 3) and the master (thermal on node 1) over rmw_fastrtps_cpp on loopback, runs the wall-clock duration, and records the per-message stream through the multi-stream harness.
#
# Node split (single host; each node is one process group):
#   node 1: fmi_multirate_node (master, scheduler, clock publisher, thermal FMU)
#   node 2: fmi_participant_node (mechanical_sofa FMU)
#   node 3: fmi_participant_node (pulse_physiology FMU, the container worker on 127.0.0.1:5055 is the precondition)
# Usage (after sim\fmi\build.ps1 and sim\fmi\master\build.ps1): powershell -ExecutionPolicy Bypass -File sim\fmi\master\tools\run_three_node.ps1 -Duration 600

param(
    [int]$Duration = 600,
    [string]$Tag = 'three-node',
    [string]$LogDir = ''
)

$ErrorActionPreference = 'Stop'

$toolsDir = $PSScriptRoot
$masterDir = Split-Path -Parent $toolsDir
$repoDir = (Resolve-Path (Join-Path $masterDir '..\..\..')).Path
$manifest = Join-Path $repoDir 'env\ros2-jazzy\pixi.toml'
$pixi = 'C:\Users\salmo\AppData\Local\pixi\bin\pixi.exe'
$pixiEnv = Join-Path $repoDir 'env\ros2-jazzy\.pixi\envs\default'
$install = Join-Path $masterDir 'build\install'
$libDir = Join-Path $install 'srtra_fmi_master\lib\srtra_fmi_master'
$masterExe = Join-Path $libDir 'fmi_three_node_master.exe'
$participantExe = Join-Path $libDir 'fmi_participant_node.exe'
$measure = Join-Path $toolsDir 'measure_multirate.py'
if (-not $LogDir) { $LogDir = Join-Path $repoDir 'SNDEV\logs' }
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

foreach ($exe in $masterExe, $participantExe) {
    if (-not (Test-Path $exe)) { throw "missing $exe (run sim\fmi\master\build.ps1)" }
}

$stamp = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHHmmssZ')
$tag = "fmi-three-node-$Tag-$($Duration)s-$stamp"
$json = Join-Path $LogDir "$tag.json"
$ready = Join-Path $LogDir "$tag-ready.flag"

$scratch = Join-Path 'C:\Users\salmo\AppData\Local\Temp\opencode' "fmi-three-node-$stamp"
$root = Join-Path $scratch 'fmu'
foreach ($n in 'thermal_pennes', 'mechanical_sofa', 'pulse_physiology') {
    $dest = Join-Path $root $n
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    Copy-Item -Path (Join-Path $repoDir "sim\fmi\build\fmu\$n.fmu") -Destination (Join-Path $dest "$n.zip")
    Expand-Archive -Path (Join-Path $dest "$n.zip") -DestinationPath $dest -Force
}

$env:PATH = "$pixiEnv;$pixiEnv\Library\bin;$libDir\..\..\bin;" + $env:PATH
$env:RMW_IMPLEMENTATION = 'rmw_fastrtps_cpp'
. (Join-Path $install 'local_setup.ps1')

$harness = Start-Process -FilePath $pixi -ArgumentList @('run', '--manifest-path', $manifest, '--', 'python', $measure,
    '--rate-hz', '1000', '--duration', "$Duration", '--out', $json, '--ready-file', $ready,
    '--scope', 'single-host-loopback-three-nodes') -NoNewWindow -PassThru `
    -RedirectStandardOutput (Join-Path $LogDir "$tag-harness.txt") -RedirectStandardError (Join-Path $LogDir "$tag-harness-stderr.txt")
$waited = 0
while (-not (Test-Path $ready) -and $waited -lt 180 -and -not $harness.HasExited) { Start-Sleep -Milliseconds 250; $waited += 0.25 }
if (-not (Test-Path $ready)) { throw 'harness did not become ready' }

$mechArgs = @("--ros-args", "-p", "fmu_root:=$root", "-p", "model_identifier:=mechanical_sofa",
    "-p", "instantiation_token:=7c1e5a2b-94d0-4f63-b8a1-2e6d0f3c9a57",
    "-p", "resource_dir:=$root\mechanical_sofa\resources\", "-p", "output_value_references:=r0:20;r1:21;r2:22",
    "-p", "duration_s:=$Duration")
$pulseArgs = @("--ros-args", "-p", "fmu_root:=$root", "-p", "model_identifier:=pulse_physiology",
    "-p", "instantiation_token:=b3e1d7a4-5f20-4c8e-9a61-0d2f7c4e8b19",
    "-p", "resource_dir:=$root\pulse_physiology\resources\", "-p", "output_value_references:=r0:20;r1:24;r2:26",
    "-p", "duration_s:=$Duration")
$mech = Start-Process -FilePath $participantExe -ArgumentList $mechArgs -NoNewWindow -PassThru `
    -RedirectStandardOutput (Join-Path $LogDir "$tag-node2-mechanical.txt") -RedirectStandardError (Join-Path $LogDir "$tag-node2-mechanical-stderr.txt")
$pulse = Start-Process -FilePath $participantExe -ArgumentList $pulseArgs -NoNewWindow -PassThru `
    -RedirectStandardOutput (Join-Path $LogDir "$tag-node3-pulse.txt") -RedirectStandardError (Join-Path $LogDir "$tag-node3-pulse-stderr.txt")

$master = Start-Process -FilePath $masterExe -ArgumentList @("--ros-args", "-p", "fmu_root:=$root",
    "-p", "duration_s:=$Duration", "-p", "reply_timeout_ms:=5000") `
    -NoNewWindow -PassThru -RedirectStandardOutput (Join-Path $LogDir "$tag-node1-master.txt") `
    -RedirectStandardError (Join-Path $LogDir "$tag-node1-master-stderr.txt")

$masterWaited = $master.WaitForExit(($Duration + 240) * 1000)
$masterCode = if ($masterWaited) { $master.ExitCode } else { -1 }
$mechWaited = $mech.WaitForExit(60000)
$mechCode = if ($mechWaited) { $mech.ExitCode } else { -1 }
$pulseWaited = $pulse.WaitForExit(60000)
$pulseCode = if ($pulseWaited) { $pulse.ExitCode } else { -1 }
$harnessWaited = $harness.WaitForExit(($Duration + 240) * 1000)
$harnessCode = if ($harnessWaited) { $harness.ExitCode } else { -1 }
Remove-Item -Force -ErrorAction SilentlyContinue $ready

$recordWritten = Test-Path $json
# The process objects do not always report ExitCode under Windows PowerShell 5 after WaitForExit. The master writes
# its own exit_code in its summary line, which is the authoritative status of the run.
$masterOut = Get-Content (Join-Path $LogDir "$tag-node1-master.txt") -ErrorAction SilentlyContinue | Select-Object -Last 1
$masterSummaryOk = $masterOut -match '"exit_code":0'
"master_summary_ok=$masterSummaryOk record_written=$recordWritten master_exit=$masterCode mech_exit=$mechCode pulse_exit=$pulseCode harness_exit=$harnessCode"
if (-not $masterSummaryOk -or -not $recordWritten) { exit 1 }
exit 0
