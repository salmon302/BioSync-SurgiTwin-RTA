# SPDX-License-Identifier: MIT
# Author: Seth Nenninger (Builder_Int34 Agent). Plan task 2.1 slice 2 (gate G2.1 measurement).
# Runs evaluate_g21.py with the Slicer 5.12.4 bundled Python (SimpleITK 2.5.5) and captures the output to SNDEV/logs.
# Usage (from the repo root): powershell -ExecutionPolicy Bypass -File sim\segmentation\run_evaluation.ps1

$ErrorActionPreference = "Stop"
$PySlicer = "I:\Library\3D Slicer 5.12.4\bin\PythonSlicer.exe"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Script = Join-Path $PSScriptRoot "evaluate_g21.py"
$DatasetId = "tcia-hcc-tace-seg-hcc001"

if (-not (Test-Path $PySlicer)) { throw "Slicer Python not found at $PySlicer" }

$LogDir = Join-Path $Root "SNDEV\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$Log = Join-Path $LogDir "g21-evaluation-$DatasetId-$Stamp.log"

$t0 = Get-Date
& $PySlicer $Script *>&1 | Out-File -Encoding utf8 $Log
$exit = $LASTEXITCODE
$wall = ((Get-Date) - $t0).TotalSeconds
Get-Content $Log
Write-Output ("python_exit={0} wall_seconds={1:N1} log={2}" -f $exit, $wall, $Log)
if ($exit -ne 0) { throw "Evaluation failed; see $Log" }
