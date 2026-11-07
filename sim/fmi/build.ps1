# SPDX-License-Identifier: MIT
# Metadata header (AGENTS.md section 3)
# Title: sim/fmi FMU build script (plan tasks 2.7 slices 1 and 2)
# Date: 2026-11-07T09:00:00Z
# Author: Seth Nenninger (Claude Haiku 5.5 Agent)
# Contribution Type: Implementation
# Ticket/Context: plan task 2.7 slices 1 and 2
# Summary: Configures, builds, and packages the thermal_pennes (C) and mechanical_sofa (C++17) FMI 3.0 Co-Simulation FMUs with the MSVC toolchain (Visual Studio 2022 x64 generator).
#
# Usage (from any directory):
#   powershell -ExecutionPolicy Bypass -File sim\fmi\build.ps1 [-Config Release|RelWithDebInfo]
# Outputs: sim\fmi\build\fmu\thermal_pennes.fmu and sim\fmi\build\fmu\mechanical_sofa.fmu (gitignored).
# The mechanical FMU needs the SOFA runtime at run time (runSofa.exe with SofaPython3); it is not in the archive.

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

& $cmake.Source --build $buildDir --config $Config --target thermal_pennes mechanical_sofa pulse_physiology
if ($LASTEXITCODE -ne 0) { throw "cmake build failed with exit code $LASTEXITCODE" }

foreach ($name in 'thermal_pennes', 'mechanical_sofa', 'pulse_physiology') {
    $fmu = Join-Path $buildDir "fmu\$name.fmu"
    if (-not (Test-Path $fmu)) { throw "FMU was not produced: $fmu" }
    $size = (Get-Item $fmu).Length
    Write-Output "FMU: $fmu ($size bytes), configuration $Config"
}
exit 0
