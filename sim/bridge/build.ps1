# SPDX-License-Identifier: MIT
# Metadata header (AGENTS.md section 3)
# Title: sim/bridge colcon build script (plan task 2.4 slice 1)
# Date: 2026-11-05T15:53:25Z
# Author: Seth Nenninger (Builder_Int34 Agent)
# Contribution Type: Implementation
# Ticket/Context: plan task 2.4 slice 1
# Summary: Builds the srtra_bridge ament_cmake package with colcon inside the locked ROS 2 Jazzy pixi environment, using MSVC Release.
#
# Usage (from any directory): powershell -ExecutionPolicy Bypass -File sim\bridge\build.ps1
# Outputs go to sim\bridge\build\ (gitignored): b (colcon build base), install, and log.
# The build base name is kept short because CMake warns when object paths exceed the Windows limit.

$ErrorActionPreference = 'Stop'

$bridgeDir = $PSScriptRoot
$repoDir = (Resolve-Path (Join-Path $bridgeDir '..\..')).Path
$manifest = Join-Path $repoDir 'env\ros2-jazzy\pixi.toml'
$buildDir = Join-Path $bridgeDir 'build'

$pixi = 'C:\Users\salmo\AppData\Local\pixi\bin\pixi.exe'
if (-not (Test-Path $pixi)) {
    $found = Get-Command pixi -ErrorAction SilentlyContinue
    if (-not $found) { throw 'pixi is not installed (expected C:\Users\salmo\AppData\Local\pixi\bin\pixi.exe)' }
    $pixi = $found.Source
}

$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
$vcvars = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -find 'VC\Auxiliary\Build\vcvars64.bat' | Select-Object -First 1
if (-not $vcvars) { throw 'vcvars64.bat not found (Visual Studio C++ x64 tools are required)' }

New-Item -ItemType Directory -Force -Path $buildDir | Out-Null

# Import the MSVC variables that vcvars64.bat sets (PATH, INCLUDE, LIB, VCINSTALLDIR, and others).
$captureScript = Join-Path $buildDir 'msvc-env-capture.cmd'
$captureOutput = Join-Path $buildDir 'msvc-env.txt'
Set-Content -Path $captureScript -Value ('@call "' + $vcvars + '" >nul' + "`r`n" + '@set') -Encoding ascii
& cmd.exe /d /c $captureScript | Set-Content -Path $captureOutput -Encoding ascii
if ($LASTEXITCODE -ne 0) { throw 'vcvars64.bat failed' }
foreach ($line in Get-Content $captureOutput) {
    $idx = $line.IndexOf('=')
    if ($idx -le 0) { continue }
    $name = $line.Substring(0, $idx)
    $value = $line.Substring($idx + 1)
    $current = [Environment]::GetEnvironmentVariable($name)
    if ($current -ne $value) {
        Set-Item -Path ('env:' + $name) -Value $value
    }
}

$env:RMW_IMPLEMENTATION = 'rmw_fastrtps_cpp'

& $pixi run --manifest-path $manifest -- colcon --log-base (Join-Path $buildDir 'log') build `
    --base-paths $bridgeDir `
    --packages-select srtra_bridge `
    --build-base (Join-Path $buildDir 'b') `
    --install-base (Join-Path $buildDir 'install') `
    --cmake-args -G Ninja -DCMAKE_BUILD_TYPE=Release
exit $LASTEXITCODE
