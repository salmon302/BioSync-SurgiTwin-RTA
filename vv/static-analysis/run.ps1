# SPDX-License-Identifier: MIT
# Metadata header (AGENTS.md section 3)
# Title: vv/static-analysis runner (plan task 3.7 slice 1)
# Date: 2026-11-12T23:35:00Z
# Author: Seth Nenninger (Builder_Int38 Agent)
# Contribution Type: Implementation
# Ticket/Context: salmon302/BioSync-SurgiTwin-RTA#1
# Summary: Runs the pinned cppcheck and clang-tidy check set over rta/ at the C++17 pin,
# writes text and machine-readable reports, and exits nonzero when findings exceed the
# accepted-deviation set recorded in pins.json.
#
# Usage (from any directory): powershell -ExecutionPolicy Bypass -File vv\static-analysis\run.ps1 [-ReportDir <path>]
# Exit codes: 0 = every tool is within its accepted finding count;
#             1 = at least one tool reports more findings than pins.json accepts;
#             2 = a tool is missing, a version does not match its pin, or the configuration is invalid.

param(
    [string]$ReportDir = ''
)

$ErrorActionPreference = 'Stop'
$saDir = $PSScriptRoot
$repoRoot = (Resolve-Path (Join-Path $saDir '..\..')).Path

function Resolve-ToolPath {
    param([string]$EnvVar, [string]$PinnedPath, [string]$CommandName)
    $fromEnv = [Environment]::GetEnvironmentVariable($EnvVar)
    if ($fromEnv) {
        if (-not (Test-Path $fromEnv)) { throw "$EnvVar points to $fromEnv, which does not exist" }
        return $fromEnv
    }
    if ($env:OS -eq 'Windows_NT' -and $PinnedPath -and (Test-Path $PinnedPath)) { return $PinnedPath }
    $found = Get-Command $CommandName -ErrorAction SilentlyContinue
    if ($found) { return $found.Source }
    throw "tool not found: set $EnvVar or install $CommandName at the pinned path"
}

function Get-ToolVersionText {
    param([string]$ExePath, [string[]]$ToolArgs)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $lines = @(& $ExePath @ToolArgs 2>&1 | ForEach-Object { $_.ToString() })
        return ($lines -join "`n")
    } finally {
        $ErrorActionPreference = $previous
    }
}

function Assert-Version {
    param([string]$ToolName, [string]$Observed, [string]$Expected, [string]$Pattern)
    $m = [regex]::Match($Observed, $Pattern)
    if (-not $m.Success) { throw "${ToolName}: cannot parse a version from output: $Observed" }
    if ($m.Groups[1].Value -ne $Expected) {
        throw "${ToolName}: version $($m.Groups[1].Value) does not match the pin $Expected"
    }
    return $m.Groups[1].Value
}

function Invoke-NativeToFile {
    param([string]$ExePath, [string[]]$ToolArgs, [string]$StdOutPath, [string]$StdErrPath)
    # Arguments that contain spaces are wrapped in quotes so the joined command line
    # parses as one argument on Windows (CommandLineToArgvW) and on Unix (.NET argv parsing).
    $quoted = foreach ($a in $ToolArgs) {
        if ($a -match '\s') { '"' + $a + '"' } else { $a }
    }
    $proc = Start-Process -FilePath $ExePath -ArgumentList $quoted -NoNewWindow -Wait -PassThru `
        -RedirectStandardOutput $StdOutPath -RedirectStandardError $StdErrPath
    return $proc.ExitCode
}

$exitCode = 2
try {
    $pinsPath = Join-Path $saDir 'pins.json'
    if (-not (Test-Path $pinsPath)) { throw "pins.json not found at $pinsPath" }
    $pins = Get-Content $pinsPath -Raw | ConvertFrom-Json

    if (-not $ReportDir) {
        $ReportDir = Join-Path $repoRoot $pins.defaultReportDir.Replace('/', [IO.Path]::DirectorySeparatorChar)
    }
    New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null
    $ReportDir = (Resolve-Path $ReportDir).Path

    $cppcheckExe = Resolve-ToolPath -EnvVar $pins.tools.cppcheck.pathEnvVar `
        -PinnedPath $pins.tools.cppcheck.windows.path -CommandName 'cppcheck'
    $clangTidyExe = Resolve-ToolPath -EnvVar $pins.tools.'clang-tidy'.pathEnvVar `
        -PinnedPath $pins.tools.'clang-tidy'.windows.path -CommandName 'clang-tidy'

    $cppcheckVersion = Assert-Version -ToolName 'cppcheck' `
        -Observed (Get-ToolVersionText -ExePath $cppcheckExe -ToolArgs @('--version')) `
        -Expected $pins.tools.cppcheck.version -Pattern 'Cppcheck\s+([0-9.]+)'
    $clangTidyVersion = Assert-Version -ToolName 'clang-tidy' `
        -Observed (Get-ToolVersionText -ExePath $clangTidyExe -ToolArgs @('--version')) `
        -Expected $pins.tools.'clang-tidy'.version -Pattern 'LLVM version\s+([0-9.]+)'

    $targetDir = Join-Path $repoRoot $pins.checks.target
    if (-not (Test-Path $targetDir)) { throw "target directory not found: $targetDir" }
    $sources = @(Get-ChildItem -Path $targetDir -Recurse -File -Filter '*.cpp' | Sort-Object -Property FullName)
    if ($sources.Count -eq 0) { throw "no .cpp sources found under $targetDir" }

    Push-Location $repoRoot
    try {
        # cppcheck: one run, XML on standard error and progress on standard text output.
        $xmlPath = Join-Path $ReportDir 'cppcheck.xml'
        $progressPath = Join-Path $ReportDir 'cppcheck.progress.txt'
        $cppcheckArgs = @($pins.checks.cppcheckArgs) + @('--xml', '--xml-version=2', $pins.checks.target)
        $cppcheckExit = Invoke-NativeToFile -ExePath $cppcheckExe -ToolArgs $cppcheckArgs `
            -StdOutPath $progressPath -StdErrPath $xmlPath
        if ($cppcheckExit -ne 0) { throw "cppcheck exited with code $cppcheckExit" }

        [xml]$cppcheckXml = Get-Content $xmlPath -Raw
        # Guard against the empty <errors/> case: .error is $null there, and @($null) would count as one.
        $cppcheckErrors = @($cppcheckXml.results.errors.error | Where-Object { $null -ne $_ })
        if ($cppcheckXml.results.cppcheck.version -ne $cppcheckVersion) {
            throw "cppcheck report version $($cppcheckXml.results.cppcheck.version) does not match the pin"
        }

        # Text report derived from the same XML so both reports carry identical findings.
        # The file is always written, with zero lines when there are no findings.
        $textLines = @(foreach ($err in $cppcheckErrors) {
            $loc = $err.location | Select-Object -First 1
            '{0}:{1}:{2}: {3}: {4}: {5}' -f $loc.file, $loc.line, $loc.column, $err.severity, $err.id, $err.msg
        })
        Set-Content -Path (Join-Path $ReportDir 'cppcheck.txt') -Value ($textLines -join "`n")

        # clang-tidy: one invocation over all translation units so header diagnostics are
        # reported once; config, header filter, and checks come from the pinned .clang-tidy.
        $tidyLogPath = Join-Path $ReportDir 'clang-tidy.txt'
        $tidyProgressPath = Join-Path $ReportDir 'clang-tidy.progress.txt'
        $fixesPath = Join-Path $ReportDir 'clang-tidy-fixes.yaml'
        $tidyArgs = @()
        foreach ($src in $sources) { $tidyArgs += $src.FullName }
        $tidyArgs += ('--config-file=' + (Join-Path $saDir '.clang-tidy'))
        $tidyArgs += ('--export-fixes=' + $fixesPath)
        $tidyArgs += '--'
        foreach ($a in $pins.checks.clangTidyCompilerArgs) { $tidyArgs += $a }
        $tidyExit = Invoke-NativeToFile -ExePath $clangTidyExe -ToolArgs $tidyArgs `
            -StdOutPath $tidyLogPath -StdErrPath $tidyProgressPath
        if ($tidyExit -ne 0) { throw "clang-tidy exited with code $tidyExit" }

        $tidyText = (Get-Content $tidyLogPath -Raw) + "`n" + (Get-Content $tidyProgressPath -Raw)
        Set-Content -Path (Join-Path $ReportDir 'clang-tidy.txt') -Value $tidyText
        $tidyFindings = ([regex]::Matches($tidyText, [regex]::Escape(': warning: '))).Count
    } finally {
        Pop-Location
    }

    $cppcheckFindings = $cppcheckErrors.Count
    $results = [ordered]@{
        generatedAt  = [DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')
        target       = $pins.checks.target
        cppStandard  = $pins.cppStandard
        reportDir    = $ReportDir
        tools        = [ordered]@{
            'cppcheck'   = [ordered]@{
                version     = $cppcheckVersion
                findings    = $cppcheckFindings
                accepted    = [int]$pins.acceptedFindings.'cppcheck'
                withinLimit = ($cppcheckFindings -le [int]$pins.acceptedFindings.'cppcheck')
            }
            'clang-tidy' = [ordered]@{
                version     = $clangTidyVersion
                findings    = $tidyFindings
                accepted    = [int]$pins.acceptedFindings.'clang-tidy'
                withinLimit = ($tidyFindings -le [int]$pins.acceptedFindings.'clang-tidy')
            }
        }
        register     = $pins.deviationRegister
    }
    $withinAll = $results.tools.'cppcheck'.withinLimit -and $results.tools.'clang-tidy'.withinLimit
    $results['result'] = $(if ($withinAll) { 'PASS' } else { 'FAIL' })
    $results | ConvertTo-Json -Depth 5 | Set-Content -Path (Join-Path $ReportDir 'summary.json')

    Write-Output ('cppcheck {0}: {1} findings (accepted {2}) {3}' -f `
        $cppcheckVersion, $cppcheckFindings, $results.tools.'cppcheck'.accepted, `
        $(if ($results.tools.'cppcheck'.withinLimit) { 'PASS' } else { 'FAIL' }))
    Write-Output ('clang-tidy {0}: {1} findings (accepted {2}) {3}' -f `
        $clangTidyVersion, $tidyFindings, $results.tools.'clang-tidy'.accepted, `
        $(if ($results.tools.'clang-tidy'.withinLimit) { 'PASS' } else { 'FAIL' }))
    Write-Output ('reports: {0}' -f $ReportDir)

    $exitCode = $(if ($withinAll) { 0 } else { 1 })
} catch {
    Write-Output ('ERROR: {0}' -f $_.Exception.Message)
    $exitCode = 2
}
exit $exitCode