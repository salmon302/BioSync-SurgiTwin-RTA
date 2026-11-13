# SPDX-License-Identifier: MIT
# Metadata header (AGENTS.md section 3)
# Title: rta coverage runner (plan task 3.8 slice 1)
# Date: 2026-11-13T03:00:00Z
# Author: Seth Nenninger (Builder_Int38 Agent)
# Contribution Type: Implementation
# Ticket/Context: salmon302/BioSync-SurgiTwin-RTA#2
# Summary: Configures and builds rta/ with the pinned clang 19.1.5 at the C++17 pin with
# llvm-cov instrumentation, runs the full CTest suite, and writes statement (line) and
# branch coverage per rta/ file from llvm-cov 19.1.5 report and export output.
#
# Usage (from any directory): powershell -ExecutionPolicy Bypass -File rta\tests\coverage.ps1
#   [-ReportDir <path>] [-BuildDir <path>]
# Exit codes: 0 = configure, build, tests, and report all succeeded;
#             1 = the build or the CTest suite failed;
#             2 = a pinned tool is missing or does not match its pin, or the configuration is invalid.

param(
    [string]$ReportDir = '',
    [string]$BuildDir = ''
)

$ErrorActionPreference = 'Stop'
$testsDir = $PSScriptRoot
$rtaDir = (Resolve-Path (Join-Path $testsDir '..')).Path
$repoRoot = (Resolve-Path (Join-Path $rtaDir '..')).Path

function Invoke-ToolToFile {
    # Runs a native tool with stderr merged into the captured output. The temporary
    # EAP switch keeps developer warnings on stderr from terminating the script.
    param([string]$FilePath, [string[]]$ToolArgs, [string]$LogPath)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $output = @(& $FilePath @ToolArgs 2>&1 | ForEach-Object { $_.ToString() })
        $code = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
    $output | Set-Content -Path $LogPath
    return $code
}

$exitCode = 2
try {
    $pinsPath = Join-Path $testsDir 'pins.json'
    if (-not (Test-Path $pinsPath)) { throw "pins.json not found at $pinsPath" }
    $pins = Get-Content $pinsPath -Raw | ConvertFrom-Json

    if (-not $ReportDir) {
        $ReportDir = Join-Path $repoRoot $pins.defaultReportDir.Replace('/', [IO.Path]::DirectorySeparatorChar)
    }
    if (-not $BuildDir) { $BuildDir = Join-Path $repoRoot 'build\coverage' }
    New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null
    $ReportDir = (Resolve-Path $ReportDir).Path
    $BuildDir = [IO.Path]::GetFullPath($BuildDir)

    # Pinned LLVM 19.1.5 toolchain (clang++, llvm-profdata, llvm-cov): user-path
    # extraction, no elevation (rta/tests/pins.json).
    $llvmBin = $pins.tools.llvmToolchain.binPath
    $clangxx = Join-Path $llvmBin 'clang++.exe'
    $llvmProfdata = Join-Path $llvmBin 'llvm-profdata.exe'
    $llvmCov = Join-Path $llvmBin 'llvm-cov.exe'
    foreach ($tool in @($clangxx, $llvmProfdata, $llvmCov)) {
        if (-not (Test-Path $tool)) { throw "tool not found at $tool (pinned LLVM $($pins.tools.llvmToolchain.version) extraction missing)" }
    }
    foreach ($tool in @($clangxx, $llvmProfdata, $llvmCov)) {
        $out = @(& $tool --version 2>&1 | ForEach-Object { $_.ToString() }) -join "`n"
        if ($out -notmatch [regex]::Escape($pins.tools.llvmToolchain.version)) {
            throw ("{0} version does not match the pin {1}: {2}" -f (Split-Path $tool -Leaf), $pins.tools.llvmToolchain.version, $out)
        }
    }

    # MSVC environment from vcvars64 (same capture as sim/bridge/build.ps1), plus the
    # pinned LLVM bin directory on PATH so clang++ finds the MSVC headers and link.exe.
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    $vcvars = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -find 'VC\Auxiliary\Build\vcvars64.bat' | Select-Object -First 1
    if (-not $vcvars) { throw 'vcvars64.bat not found (Visual Studio C++ x64 tools are required)' }

    New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null
    $captureScript = Join-Path $BuildDir 'msvc-env-capture.cmd'
    $captureOutput = Join-Path $BuildDir 'msvc-env.txt'
    Set-Content -Path $captureScript -Value ('@call "' + $vcvars + '" >nul' + "`r`n" + '@set') -Encoding ascii
    & cmd.exe /d /c $captureScript | Set-Content -Path $captureOutput -Encoding ascii
    if ($LASTEXITCODE -ne 0) { throw 'vcvars64.bat failed' }
    foreach ($line in Get-Content $captureOutput) {
        $idx = $line.IndexOf('=')
        if ($idx -le 0) { continue }
        $name = $line.Substring(0, $idx)
        $value = $line.Substring($idx + 1)
        if ([Environment]::GetEnvironmentVariable($name) -ne $value) {
            Set-Item -Path ('env:' + $name) -Value $value
        }
    }
    $env:PATH = $llvmBin + [IO.Path]::PathSeparator + $env:PATH

    # Configure and build at the C++17 pin with llvm-cov instrumentation
    # (-fprofile-instr-generate -fcoverage-mapping, the llvm-cov profdata mode).
    $configureArgs = @(
        '-S', $repoRoot,
        '-B', $BuildDir,
        '-G', 'Ninja',
        '-Wno-dev',
        '-DCMAKE_BUILD_TYPE=Debug',
        ('-DCMAKE_CXX_COMPILER=' + $clangxx),
        ('-DCMAKE_C_COMPILER=' + (Join-Path $llvmBin 'clang.exe')),
        '-DCMAKE_CXX_FLAGS=-fprofile-instr-generate -fcoverage-mapping',
        '-DCMAKE_EXE_LINKER_FLAGS=-fprofile-instr-generate'
    )
    $code = Invoke-ToolToFile -FilePath 'cmake' -ToolArgs $configureArgs -LogPath (Join-Path $ReportDir 'cmake-configure.txt')
    if ($code -ne 0) { throw "cmake configure failed with code $code" }

    $code = Invoke-ToolToFile -FilePath 'cmake' -ToolArgs @('--build', $BuildDir) -LogPath (Join-Path $ReportDir 'cmake-build.txt')
    if ($code -ne 0) { $exitCode = 1; throw "build failed with code $code" }

    # One profile per test binary (%p), merged after the run.
    $profrawDir = Join-Path $BuildDir 'profraw'
    New-Item -ItemType Directory -Force -Path $profrawDir | Out-Null
    Remove-Item (Join-Path $profrawDir '*.profraw') -Force -ErrorAction SilentlyContinue
    $env:LLVM_PROFILE_FILE = Join-Path $profrawDir '%p-%m.profraw'

    $code = Invoke-ToolToFile -FilePath 'ctest' -ToolArgs @('--test-dir', $BuildDir, '--output-on-failure') -LogPath (Join-Path $ReportDir 'ctest.txt')
    $env:LLVM_PROFILE_FILE = $null
    if ($code -ne 0) { $exitCode = 1; throw "ctest failed with code $code" }

    $profraw = @(Get-ChildItem -Path $profrawDir -Filter '*.profraw' -File)
    if ($profraw.Count -eq 0) { throw 'no .profraw profile was written by the test run' }
    $profdata = Join-Path $BuildDir 'merged.profdata'
    $profdataArgs = @('merge', '-sparse') + ($profraw | ForEach-Object { $_.FullName }) + @('-o', $profdata)
    $code = Invoke-ToolToFile -FilePath $llvmProfdata -ToolArgs $profdataArgs -LogPath (Join-Path $ReportDir 'llvm-profdata.txt')
    if ($code -ne 0) { throw "llvm-profdata merge failed with code $code" }

    # Both test binaries in one llvm-cov view; third-party sources (Catch2 under the
    # build tree, MSVC STL headers) are excluded so the report covers rta/ only.
    $unitExe = Join-Path $BuildDir 'rta\srta_rta_unit_tests.exe'
    $smokeExe = Join-Path $BuildDir 'rta\srta_rta_test_smoke.exe'
    foreach ($exe in @($unitExe, $smokeExe)) {
        if (-not (Test-Path $exe)) { throw "test binary not found at $exe" }
    }
    $ignoreRegex = 'catch2|_deps[\\/]|MSVC[\\/]14'

    $reportArgs = @('report', $unitExe, '-object', $smokeExe,
        ('-instr-profile=' + $profdata),
        ('-ignore-filename-regex=' + $ignoreRegex),
        '--show-branch-summary')
    $code = Invoke-ToolToFile -FilePath $llvmCov -ToolArgs $reportArgs -LogPath (Join-Path $ReportDir 'coverage-report.txt')
    if ($code -ne 0) { throw "llvm-cov report failed with code $code" }

    $exportArgs = @('export', $unitExe, '-object', $smokeExe,
        ('-instr-profile=' + $profdata),
        ('-ignore-filename-regex=' + $ignoreRegex))
    $code = Invoke-ToolToFile -FilePath $llvmCov -ToolArgs $exportArgs -LogPath (Join-Path $ReportDir 'coverage.json')
    if ($code -ne 0) { throw "llvm-cov export failed with code $code" }

    # Per-rta-file text table derived from the export JSON (statement and branch counts).
    $export = Get-Content (Join-Path $ReportDir 'coverage.json') -Raw | ConvertFrom-Json
    $rows = @()
    foreach ($entry in $export.data[0].files) {
        $path = $entry.filename
        if (-not $path) { $path = $entry.file }
        if ($path -notmatch 'rta[\\/]') { continue }
        # llvm-cov export 19.1.5 carries per-file summary objects.
        $lineTotal = [int]$entry.summary.lines.count
        $lineCovered = [int]$entry.summary.lines.covered
        $branchTotal = [int]$entry.summary.branches.count
        $branchCovered = [int]$entry.summary.branches.covered
        $rows += [pscustomobject]@{
            File           = $path.Replace('\', '/')
            LineCovered    = $lineCovered
            LineTotal      = $lineTotal
            LinePercent    = $(if ($lineTotal) { 100.0 * $lineCovered / $lineTotal } else { 100.0 })
            BranchCovered  = $branchCovered
            BranchTotal    = $branchTotal
            BranchPercent  = $(if ($branchTotal) { 100.0 * $branchCovered / $branchTotal } else { 100.0 })
        }
    }
    if ($rows.Count -eq 0) { throw 'the llvm-cov export contains no rta/ files' }

    $tl = ($rows | Measure-Object -Property LineTotal -Sum).Sum
    $tc = ($rows | Measure-Object -Property LineCovered -Sum).Sum
    $tb = ($rows | Measure-Object -Property BranchTotal -Sum).Sum
    $tbc = ($rows | Measure-Object -Property BranchCovered -Sum).Sum
    $text = @()
    $text += 'llvm-cov 19.1.5 statement and branch coverage for rta/ (profdata mode, C++17 pin)'
    $text += ('generated: ' + [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ'))
    $text += ''
    $text += ('{0,-44} {1,14} {2,8} {3,16} {4,8}' -f 'File', 'Lines (cov/total)', 'Cover', 'Branches (cov/tot)', 'Cover')
    foreach ($r in ($rows | Sort-Object File)) {
        $text += ('{0,-44} {1,14} {2,7:P1} {3,16} {4,7:P1}' -f $r.File,
            ("{0}/{1}" -f $r.LineCovered, $r.LineTotal), ($r.LinePercent / 100.0),
            ("{0}/{1}" -f $r.BranchCovered, $r.BranchTotal), ($r.BranchPercent / 100.0))
    }
    $text += ''
    $text += ('{0,-44} {1,14} {2,7:P1} {3,16} {4,7:P1}' -f 'TOTAL (rta/)',
        ("{0}/{1}" -f $tc, $tl), ($(if ($tl) { $tc / $tl } else { 1.0 })),
        ("{0}/{1}" -f $tbc, $tb), ($(if ($tb) { $tbc / $tb } else { 1.0 })))
    $text | Set-Content -Path (Join-Path $ReportDir 'coverage.txt')

    $exitCode = 0
} catch {
    Write-Output ('ERROR: {0}' -f $_.Exception.Message)
    if ($exitCode -ne 1) { $exitCode = 2 }
}

if ($exitCode -eq 0) {
    Write-Output ('coverage report: {0}' -f (Join-Path $ReportDir 'coverage.txt'))
    Get-Content (Join-Path $ReportDir 'coverage.txt') | ForEach-Object { Write-Output $_ }
} else {
    Write-Output ('exit code: {0}' -f $exitCode)
}
exit $exitCode