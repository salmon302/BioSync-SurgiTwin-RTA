# SPDX-License-Identifier: MIT
# Author: Seth Nenninger (Builder_Int34 Agent). Plan task 2.1 slice 1.
# One-command run of sim/segmentation/segment_reference.py on the pinned native 3D Slicer 5.12.4 install.
# Usage (from the repo root): powershell -ExecutionPolicy Bypass -File sim\segmentation\run.ps1

$ErrorActionPreference = "Stop"
$SlicerExe = "I:\Library\3D Slicer 5.12.4\Slicer.exe"
$PySlicer = "I:\Library\3D Slicer 5.12.4\bin\PythonSlicer.exe"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$SegDir = $PSScriptRoot
$Script = Join-Path $SegDir "segment_reference.py"
$DatasetId = "tcia-hcc-tace-seg-hcc001"
$SeriesUid = "1.3.6.1.4.1.14519.5.2.1.1706.8374.302065206690360709343725942120"

$env:SURGITWIN_CT_DIR = Join-Path $SegDir "data\HCC_001_CT_C-A-P_$SeriesUid"
$env:SURGITWIN_SEG_DIR = Join-Path $SegDir "data\HCC_001_SEG_1.2.276.0.7230010.3.1.3.8323329.719.1600928570.399942"
$env:SURGITWIN_DICOM_DIR = Join-Path $SegDir "output\$DatasetId\input"
$env:SURGITWIN_SERIES_UID = $SeriesUid
$env:SURGITWIN_DATASET_ID = $DatasetId
$env:SURGITWIN_OUTPUT_ROOT = Join-Path $SegDir "output"
$env:SURGITWIN_SCRIPT = $Script
$env:SURGITWIN_SOURCE_NOTE = "TCIA HCC-TACE-Seg HCC_001 CT, CC BY 4.0; smoke dataset, not G2.1 reference data"

if (-not (Test-Path $SlicerExe)) { throw "Slicer not found at $SlicerExe" }

$LogDir = Join-Path $Root "SNDEV\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$Log = Join-Path $LogDir "segment-run-$DatasetId-$Stamp.log"

$t0 = Get-Date
$SelectLog = Join-Path $LogDir "select-input-$DatasetId-$Stamp.log"
& $PySlicer (Join-Path $SegDir "select_seg_input.py") *>&1 | Out-File -Encoding utf8 $SelectLog
if ($LASTEXITCODE -ne 0) { throw "Input selection failed; see $SelectLog" }
cmd /c "`"$SlicerExe`" --no-splash --no-main-window --python-script `"$Script`" > `"$Log`" 2>&1"
$launcherExit = $LASTEXITCODE
Get-Process -Name "SlicerApp-real" -ErrorAction SilentlyContinue | Wait-Process -Timeout 1800 -ErrorAction SilentlyContinue
$wall = ((Get-Date) - $t0).TotalSeconds

$done = Select-String -Path $Log -Pattern "SURGITWIN_DONE" -Quiet
$failed = Select-String -Path $Log -Pattern "SURGITWIN_FAILED" -Quiet
Write-Output ("slicer_exit={0} wall_seconds={1:N1} log={2}" -f $launcherExit, $wall, $Log)
if ($failed -or -not $done) { throw "Segmentation run failed; see $Log" }
Write-Output "PASS $DatasetId manifest=$(Join-Path $SegDir "output\$DatasetId\manifest.json")"
