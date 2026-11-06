# SPDX-License-Identifier: MIT
# Metadata header (AGENTS.md section 3)
# Title: sim/fmi FMU build script (plan task 2.7 slice 1)
# Date: 2026-11-05T19:00:00Z
# Author: Seth Nenninger (Claude Haiku 5.5 Agent)
# Contribution Type: Implementation
# Ticket/Context: plan task 2.7 slice 1
# Summary: Configures, builds, and packages the thermal_pennes FMI 3.0 Co-Simulation FMU with the MSVC toolchain (Visual Studio 2022 x64 generator).
#
# Usage (from any directory):
#   powershell -ExecutionPolicy Bypass -File sim\fmi\build.ps1 [-Config Release|RelWithDebInfo]
# Output: sim\fmi\build\fmu\thermal_pennes.fmu (gitignored). The check script is sim\fmi\check_fmu.py.

param(
    [ValidateSet('Release', 'RelWithDebInfo')]
    [string]$Config = 'Release'
)

$ErrorActionPreference = 'Stop'

$fmiDir = $PSScriptRoot
$buildDir = Join-Path $fmiDir 'build'

$cmake = Get-Command cmake -ErrorAction SilentlyContinue
if (-not $cmake) { throw 'cmake is not on PATH (expected C:\Program Files\CMake\bin\cmake.exe)' }

& $cmake.Source -S $fmiDir -B $buildDir -A x64
if ($LASTEXITCODE -ne 0) { throw "cmake configure failed with exit code $LASTEXITCODE" }

& $cmake.Source --build $buildDir --config $Config --target thermal_pennes
if ($LASTEXITCODE -ne 0) { throw "cmake build failed with exit code $LASTEXITCODE" }

$fmu = Join-Path $buildDir 'fmu\thermal_pennes.fmu'
if (-not (Test-Path $fmu)) { throw "FMU was not produced: $fmu" }
$size = (Get-Item $fmu).Length
Write-Output "FMU: $fmu ($size bytes), configuration $Config"
exit 0
