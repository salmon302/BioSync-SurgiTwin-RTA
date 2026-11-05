# SPDX-License-Identifier: MIT
# Author: Seth Nenninger (Builder_Int34 Agent). Plan task 2.1 slice 2.
# Exports the held-out G2.1 reference labelmaps (export_reference_labels.py) on the pinned Slicer 5.12.4 install.
# Usage (from the repo root): powershell -ExecutionPolicy Bypass -File sim\segmentation\run_reference.ps1

$ErrorActionPreference = "Stop"
$SlicerExe = "I:\Library\3D Slicer 5.12.4\Slicer.exe"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$SegDir = $PSScriptRoot
$Script = Join-Path $SegDir "export_reference_labels.py"
$DatasetId = "tcia-hcc-tace-seg-hcc001"
$SeriesUid = "1.3.6.1.4.1.14519.5.2.1.1706.8374.302065206690360709343725942120"
$SegUid = "1.2.276.0.7230010.3.1.3.8323329.719.1600928570.399942"

$env:SURGITWIN_REF_ROOT = $SegDir
$env:SURGITWIN_CT_DIR = Join-Path $SegDir "data\HCC_001_CT_C-A-P_$SeriesUid"
$env:SURGITWIN_SEG_DIR = Join-Path $SegDir "data\HCC_001_SEG_$SegUid"
$env:SURGITWIN_REF_OUT = Join-Path $SegDir "output\$DatasetId\reference"
$env:SURGITWIN_DATASET_ID = $DatasetId

if (-not (Test-Path $SlicerExe)) { throw "Slicer not found at $SlicerExe" }

$LogDir = Join-Path $Root "SNDEV\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$Log = Join-Path $LogDir "reference-export-$DatasetId-$Stamp.log"

$t0 = Get-Date
cmd /c "`"$SlicerExe`" --no-splash --no-main-window --python-script `"$Script`" > `"$Log`" 2>&1"
$launcherExit = $LASTEXITCODE
Get-Process -Name "SlicerApp-real" -ErrorAction SilentlyContinue | Wait-Process -Timeout 1800 -ErrorAction SilentlyContinue
$wall = ((Get-Date) - $t0).TotalSeconds

$done = Select-String -Path $Log -Pattern "SURGITWIN_REF_DONE" -Quiet
$failed = Select-String -Path $Log -Pattern "SURGITWIN_REF_FAILED" -Quiet
Write-Output ("slicer_exit={0} wall_seconds={1:N1} log={2}" -f $launcherExit, $wall, $Log)
if ($failed -or -not $done) { throw "Reference export failed; see $Log" }
Write-Output "PASS reference export $DatasetId"
