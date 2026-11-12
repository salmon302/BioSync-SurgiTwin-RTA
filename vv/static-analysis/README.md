# Static Analysis Check Set (task 3.7)

Pinned open-source static analysis configuration for the C++ safety cores, created by DEVELOPMENT_PLAN.md task 3.7 (slice 1). The gate scope for this slice is `rta/` under the C++17 pin (`CMAKE_CXX_STANDARD 17`). Gate G3.1 expects zero findings from this set on `rta/` with the deviation register attached; this slice records the pinned set and the baseline, and does not close the gate.

Development uses no commercial tool (decision of 2026-10-14). MISRA C++:2023 conformity stays an adopter-supplied verification (plan Section 5.1).

## Contents

* `pins.json` - exact tool versions, per-platform install origins with hashes, the run arguments at the C++17 pin, the finding metrics, and the accepted baseline finding counts. The runner and the CI job both read this file.
* `.clang-tidy` - the clang-tidy check set (bugprone, clang-analyzer, concurrency, performance, portability) with the header filter that covers `rta/include`.
* `run.ps1` - the local and CI runner (PowerShell, house style like `sim/bridge/build.ps1`).

## Pinned tools

| Tool | Version | Windows host origin | CI (ubuntu-24.04) origin | Pin status |
|:-----|:--------|:--------------------|:-------------------------|:-----------|
| cppcheck | 2.22.0 | Official x64 installer `cppcheck-2.22.0-x64-Setup.msi` (sha256 `3929162bab7e71d1b9b18708ec054fb0188bfc8ea1660979ed95837f5a9f547b`) applied with `msiexec /a` to `C:\Users\salmo\tools\cppcheck-2.22.0` (no elevation, not added to PATH) | Built from `https://github.com/danmar/cppcheck.git` at tag `2.22.0`, commit `a436ca35ed1887bee789765122b65ed2d7a7e045`; the CI job asserts the commit before building | pinned |
| clang-tidy | 19.1.5 | `C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Tools\Llvm\bin\clang-tidy.exe` (Visual Studio 2022 Community LLVM component) | Official release binary `LLVM-19.1.5-Linux-X64.tar.xz` (sha256 `13e9975b026d431c945927960e5f8c0a47a155a2f605f75e85f4d1482620c65f`, the SLSA provenance digest published with the LLVM release), cached by `actions/cache` | pinned |

Both environments run the same tool versions, so a finding that appears on one side appears on the other. The runner refuses to run when a resolved tool does not match its pin (exit code 2), and the environment variables `CPPCHECK_EXE` and `CLANG_TIDY_EXE` override the resolution order (env, then the pinned Windows path, then PATH).

## Run configuration

The C++17 pin is passed on every run: cppcheck with `--std=c++17` and clang-tidy with `-std=c++17 -Irta/include`, both listed in `pins.json`. The clang-tidy check families and the header filter are in `.clang-tidy`. cppcheck enables the `warning`, `style`, `performance`, and `portability` severity groups.

## Running

```
powershell -ExecutionPolicy Bypass -File vv\static-analysis\run.ps1
```

Reports land under `SNDEV/logs/static-analysis-baseline-2026-11-12/` by default (`-ReportDir` overrides):

* `cppcheck.xml` - machine-readable cppcheck report (XML version 2, standard error of the run).
* `cppcheck.txt` - text report derived from the same XML, one line per finding.
* `cppcheck.progress.txt` - cppcheck progress output.
* `clang-tidy.txt` - combined clang-tidy diagnostics (standard output and standard error of one invocation over all translation units).
* `clang-tidy-fixes.yaml` - machine-readable suggested fixes (`--export-fixes`).
* `summary.json` - machine-readable per-tool versions, finding counts, accepted counts, and the PASS or FAIL result.

Finding metrics are fixed in `pins.json`: the count of `<error>` elements in `cppcheck.xml`, and the count of `: warning: ` diagnostics in the combined clang-tidy output.

## Exit codes and the accepted set

* `0` - every tool is at or below its accepted count in `pins.json` (`acceptedFindings`).
* `1` - at least one tool exceeds its accepted count. This is the gate failure signal.
* `2` - a tool is missing, a version does not match its pin, or the configuration is invalid.

The accepted counts are the recorded baseline of 2026-11-12: cppcheck 0, clang-tidy 2. Each accepted clang-tidy finding has an entry in `vv/traceability/deviation-register.md`. Lowering the accepted counts to zero for both tools is the remaining work before gate G3.1 closes.

## Upgrade policy

No floating versions. A version change is an intentional edit to `pins.json` and to the CI install steps, with the matching deviation register entry updated and the baseline re-run. The runner and CI both assert the pinned version at run time, so drift fails the job instead of silently changing the check set.