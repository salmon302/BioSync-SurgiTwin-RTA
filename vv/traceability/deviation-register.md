# Deviation Register

Deviation register for the open-source static analysis gate of DEVELOPMENT_PLAN.md task 3.7, maintained alongside the VTM (`vv/traceability/vtm.md`). Gate G3.1 (FR-RTA-001) expects zero findings from the pinned check set on `rta/` with this register attached. The pinned check set and its versions are in `vv/static-analysis/pins.json` and `vv/static-analysis/README.md`. The baseline run evidence is `SNDEV/logs/static-analysis-baseline-2026-11-12/`.

Entries carry an id, the tool and version, the location, the rationale, and the disposition. An entry with disposition "accepted at baseline" allows the finding to exist in the runner's accepted set; gate G3.1 does not close while such an entry is open.

## Entries

| ID | Date | Tool and version | Location | Rationale | Disposition |
|:---|:-----|:-----------------|:---------|:----------|:------------|
| SA-001 | 2026-11-12 | Pinned check set: cppcheck 2.22.0 and clang-tidy 19.1.5, run with the C++17 pin (`--std=c++17`, `-std=c++17`) | `CMakeLists.txt` (`set(CMAKE_CXX_STANDARD 17)`) and the whole `rta/` analysis scope | VAL-016 context: SRS wording commits the C++ cores to C++17/C++20 while this gate and MISRA C++:2023 work at C++17, so a C++20 file could not be checked by this set as written. The plan records this as an open question (Section 6.2, VAL-016 row). | Recorded context. The gate runs at the C++17 pin on every run, and the runner asserts the language pin from `pins.json`. The C++17-versus-C++20 wording is settled before gate G3.1 closes. |
| SA-002 | 2026-11-12 | clang-tidy 19.1.5, check `bugprone-easily-swappable-parameters` | `rta/src/safety_envelope.cpp:6:32` (the `SafetyEnvelope` constructor parameters `minToolTipDistanceMm` and `maxTissueWrenchN`, both `double`, adjacent) | Two adjacent parameters of the same type are easily swapped by mistake. Removing the finding means changing the constructor signature or adding a justified inline suppression, and the envelope API is owned by Phase 3 tasks 3.1 and 3.4, which this slice does not edit. | Accepted at the 2026-11-12 baseline. The runner allows this finding through the accepted set in `pins.json` (clang-tidy accepted count 2). Resolved by API rework or a justified suppression before gate G3.1 closes. |
| SA-003 | 2026-11-12 | clang-tidy 19.1.5, check `performance-enum-size` | `rta/include/rta/simplex_switch.h:12:16` (`enum class Controller`, base type `int`) | The check suggests a one-byte base type such as `std::uint8_t`. Changing the base type of a public enum in the Simplex switch header is a Phase 3 task 3.2 code change, larger than the lint-level fixes allowed in this slice. | Accepted at the 2026-11-12 baseline. The runner allows this finding through the accepted set in `pins.json` (clang-tidy accepted count 2). Resolved before gate G3.1 closes. |
| SA-004 | 2026-11-13 | Coverage set of task 3.8 slice 1: clang++ 19.1.5 with `-fprofile-instr-generate -fcoverage-mapping`, llvm-profdata 19.1.5, llvm-cov 19.1.5 (gcov-family toolchain, plan Section 5.2 names gcov or llvm-cov) | `rta/` coverage scope, gate G3.1, plan Section 5.2 ("the MC/DC target is a recorded deviation in the risk file and the deviation register") | The gcov-family tooling reports statement and branch coverage and does not report MC/DC. The C++ High Process Risk target keeps the MC/DC deviation until a path is verified; otherwise an adopter with a conforming tool supplies the evidence. | Recorded deviation. Work item under task 3.8: evaluate the Clang 19 or newer llvm-cov MC/DC reporting path. One matching row was added to DEVELOPMENT_PLAN.md Section 7.1 on 2026-11-13. Statement and branch coverage is the measured baseline of task 3.8 slice 1. |

## Baseline counts (2026-11-12)

| Tool | Version | Findings | Accepted | Report |
|:-----|:--------|---------:|---------:|:-------|
| cppcheck | 2.22.0 | 0 | 0 | `SNDEV/logs/static-analysis-baseline-2026-11-12/cppcheck.xml` |
| clang-tidy | 19.1.5 | 2 | 2 | `SNDEV/logs/static-analysis-baseline-2026-11-12/clang-tidy.txt` |

Both task 3.7 candidates are available on this host and are selected, so no tool-unavailability deviation is carried.