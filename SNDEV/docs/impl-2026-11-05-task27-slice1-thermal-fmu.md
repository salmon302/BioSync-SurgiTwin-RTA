Title: Pennes bioheat thermal ablation FMU and FMI 3.0 toolchain (plan task 2.7 slice 1)
Date: 2026-11-05T19:00:00Z
Author: Seth Nenninger (Claude Haiku 5.5 Agent)
Contribution Type: Implementation
Ticket/Context: plan task 2.7 slice 1
Summary: Adds the FMI 3.0.2 header pin, a CMake and PowerShell FMU build (MSVC, Release and RelWithDebInfo), a Pennes bioheat thermal ablation Co-Simulation FMU on a 16 x 16 x 16 lattice, and an FMPy 0.3.32 import check with three analytic and boundary cases and one error-path case. All checks pass.

## Task Reference

Plan task 2.7 in `DEVELOPMENT_PLAN.md` (Phase 2 table: "2.7 Package the thermal ablation, mechanical (SOFA), and physiology (Pulse) plant models as FMI 3.0 FMUs", `sim/fmi/`, 6.0 d). This slice covers the thermal plant model and the toolchain that the mechanical and physiology wrappers reuse. Requirement FR-MS-007 in `SRS.md` v1.2.0 (VAL-028: scheduled-variable co-simulation over the pinned ROS 2 / Fast DDS layer, clock skew and message jitter at most 1 ms). Gate G2.6 is a later slice and is not closed by this record. `DEVELOPMENT_PLAN.md` is not edited here, because another builder holds it. The row update is left for consolidation.

## Specification Summary

* Pin the FMI 3.0 standard C headers from `modelica/fmi-standard` at a tagged release.
* Build the thermal model as a shared library and package it as an FMI 3.0 FMU with `modelDescription.xml`, through one command (`sim/fmi/build.ps1`), under the MSVC toolchain, in Release or RelWithDebInfo.
* Solve the Pennes bioheat equation on a documented lattice (1e3 to 1e4 cells) with literature-pinned tissue parameters and a parameterized ablation applicator source. Fix the explicit or implicit scheme and its stability bound.
* Declare parameters, inputs, and outputs with units and start values, plus step-size guidance and FMI version 3.0.
* Check the FMU with FMPy 0.3.32 (`sim/fmi/check_fmu.py`): an analytic cooling case, an ablation case (lesion dose rises and stabilizes after power-off), and a JSON result under `SNDEV/logs/`.
* Record every pin in `sim/SOUP.md`. Document equations, grid, solver, stability bound, and the build and check commands in `sim/fmi/README.md`.

## Implementation Notes

Preflight. `sim/fmi/` held a placeholder `CMakeLists.txt` (no targets) and `README.md`. The root `CMakeLists.txt` option `SRTA_BUILD_FMI` (default OFF) already calls `add_subdirectory(sim/fmi)`, and the root configure is unchanged. Host tools: CMake 3.31.6, MSVC 14.44.35207 (Visual Studio 2022 Community), Git, Python 3.14.3 with FMPy 0.3.32. The latest FMI 3.0 release tag in `modelica/fmi-standard` is `v3.0.2` (`git ls-remote --tags`). The record was created before any source change.

Files changed (all new or replaced in `sim/fmi/` except where noted):

* `sim/fmi/include/fmi3/fmi3Functions.h`, `fmi3FunctionTypes.h`, `fmi3PlatformTypes.h`: FMI 3.0.2 headers from the tag, unchanged.
* `sim/fmi/src/thermal_pennes.c`: model and the FMI 3.0 Co-Simulation entry points (about 430 lines, SPDX MIT).
* `sim/fmi/src/fmi3_unsupported.c`: 64 exported stubs for FMI 3.0 symbols the FMU does not implement (FMPy 0.3.32 binds every symbol at load time).
* `sim/fmi/model/modelDescription.xml`: FMI 3.0 model description (18 variables including `time`, unit definitions, start values, `fixedInternalStepSize="0.1"`, DefaultExperiment).
* `sim/fmi/CMakeLists.txt`: replaces the placeholder. Builds `thermal_pennes` (SHARED, C99, `/W4 /WX`) and stages and zips `thermal_pennes.fmu` through `cmake -E tar --format=zip`.
* `sim/fmi/build.ps1`: one command (`-Config Release` default, or `RelWithDebInfo`) that runs CMake configure (Visual Studio 2022, x64), build, and reports the FMU path and size.
* `sim/fmi/check_fmu.py`: FMPy import checks (cases A1, A2, B1, N1 below). Writes the JSON result.
* `sim/fmi/requirements.txt`: exact pins for FMPy 0.3.32 and its installed dependency closure (20 packages).
* `sim/fmi/.gitignore`: `build/`, `__pycache__/`, `*.fmu`.
* `sim/fmi/README.md`: replaces the placeholder. Equations, parameter table with sources, solver and stability bound, interface, validity limits, check results, and wrapper notes.
* `sim/SOUP.md`: updated the FMI 3.0 standard row and the FMPy row. Added rows: FMPy dependency closure, FMI 3.0.2 standard C headers, FMU build tooling (CMake and MSVC), IT'IS tissue property values.
* `SNDEV/docs/impl-2026-11-05-task27-slice1-thermal-fmu.md`: this record.
* `SNDEV/logs/`: build captures, check captures, and the JSON result (listed below).

Pinned FMI 3.0.2 headers, SHA-256 (computed after download from the tag): `fmi3PlatformTypes.h` 1AA81EFDDEB84B0D9425F9226969525BD034CB63848C086B6696655179500616; `fmi3FunctionTypes.h` D247D1C5FBF58E32379F1D38E7F73990709E0501FC4A9B3901CE3F9638503A0F; `fmi3Functions.h` 038358FB0209C3547FE8C6F03B80582960C93CE0A7D342B0D9348C8CE6137784. The tag peels to commit `b8778deaf5b746ba4a2f6c155d53f8a33eebbd33`. FMPy ships copies with different hashes, and those are not used.

Model (summary; full equations and sources in `sim/fmi/README.md`). Explicit forward Euler on a 16 x 16 x 16 cubic lattice (4096 cells, dx = 1 mm), fixed step dt = 0.1 s, zero-flux default boundary with an optional convective face term h_bc to T_env. Applicator: P_abl spread uniformly over the cells inside a sphere of radius r_app = 3 mm at the lattice center, normalized so the discrete integral equals P_abl exactly. Outputs: T_max, T_mean (K), V60 (volume at or above 60 C, mm3), and V_lesion (cumulative volume of cells with CEM43 at or above 240 min, mm3, monotone). CEM43 uses R = 0.5 at or above 43 C and 0.25 below (Sapareto and Dewey 1984).

Stability bound (checked at every DoStep with the current h_bc): S = dt (12 alpha/dx^2 + w_b c_b/(rho c) + 3 h_bc/(rho c dx)) <= 1. At the defaults S = 0.1646. The largest h_bc that keeps S <= 1 is about 1.06e4 W/(m2 K). A violation returns fmi3Error.

Parameters (values and sources are in the README table). Liver density 1078.8 kg/m3, specific heat 3540.2 J/(kg K), conductivity 0.519 W/(m K), perfusion 16.24 kg/(m3 s), metabolic heat 10712.9 W/m3 are taken from the IT'IS database (Hasgall et al. 2018) as tabulated in the INRiM supplementary Table S1 (Vicentini, Ferrero, Manzin 2024). Blood specific heat 3617 J/(kg K) is the IT'IS value and was not verified in this slice. Arterial temperature 37 C is the Pennes convention. Lattice spacing and applicator radius are model choices. Every tissue value is marked (confirm) in the README and SOUP, because the IT'IS download was not reachable as a table in this session.

## Verification

Build (`sim/fmi/build.ps1`, MSVC 19.44.35217, Visual Studio generator, x64). Release and RelWithDebInfo both build with zero warnings under `/W4 /WX`. Evidence: `SNDEV/logs/fmi-build-release-2026-11-05.txt` (FMU 11520 bytes), `SNDEV/logs/fmi-build-relwithdebinfo-2026-11-05.txt` (FMU 12595 bytes). The FMU archive holds `modelDescription.xml` and `binaries/x86_64-windows/thermal_pennes.dll`. Build status: PASS.

Model description. `read_model_description(validate=True)` in FMPy 0.3.32 accepts the file (fmiVersion 3.0, one CoSimulation element, fixedInternalStepSize 0.1). Three schema errors were fixed during the build: element order (`UnitDefinitions` before `LogCategories`), the `InitialUnknown` form in `ModelStructure`, and the missing `time` independent variable. Status: PASS.

Import checks (`python sim\fmi\check_fmu.py`, FMPy 0.3.32). Evidence: `SNDEV/logs/fmi-thermal-pennes-check-2026-11-05.json` and `SNDEV/logs/fmi-thermal-pennes-check-stdout-2026-11-05.txt`.

| Case | Setup | Reference | Tolerance | Measured | Result |
|:---|:---|:---|:---|:---|:---|
| A1 no-perfusion, no-source conservation | w_b = 0, Q_met = 0, P_abl = 0, h_bc = 0, uniform 50 C, 60 s, 600 steps | uniform field stays constant | 1e-9 K | 6.3e-12 K | PASS |
| A2 perfusion cooling | Q_met = 0, P_abl = 0, h_bc = 0, uniform 50 C, 60 s, 600 steps | T(t) = T_a + (T0 - T_a) exp(-w_b c_b t/(rho c)), rate 0.015380 1/s | 0.01 K (continuous); 1e-9 K (discrete closed form (1 - rate dt)^n) | 3.67e-3 K (continuous); 3.5e-11 K (discrete); monotone | PASS |
| B1 ablation dose | P_abl = 5 W for 0 to 30 s, then 0 to 120 s, default parameters, 1200 steps | discrete energy balance (stored heat equals dt (P - w_b c_b V (T_mean - T_a) + Q_met V)) | 1e-6 J (input about 150 J) | residual 3.4e-10 J; V_lesion 0 to 432 mm3 by 30 s, 480 mm3 at 120 s, growth over the last 20 s 0 mm3; T_mean at or above T_a; T_max non-increasing after power off; T_max peak 450.3 K (177 C) | PASS |
| N1 error paths | h_bc = 1e6 W/(m2 K); communicationStepSize = 0.05 s | fmi3Error on both calls | status 3 | both return fmi3Error with a logged reason | PASS |

Overall: PASS (4 of 4 cases).

Style and encoding scan of the new files: no em dashes, no curly quotes, and no banned words in `sim/fmi/` or this record. Two README sentences were rewritten to remove a contrast construction and a "not X" construction. Status: PASS.

Gate status. Gate G2.6 is not measured in this slice (clock skew and message jitter are task 2.8 and the three-node Fast DDS test). The plan row for task 2.7 requires 100 percent statement, branch, and MC/DC coverage for the FMU code (`DEVELOPMENT_PLAN.md` CSA risk annotation). That coverage is not measured in this slice and remains open for the consolidation record.

## Decisions and Deviations

* Co-Simulation (type CS) with a fixed step, not Scheduled Execution. The thermal model has one rate and no clocks. FMPy 0.3.32 simulates the CS interface directly. The clock-based path needed for task 2.8 is not implemented here.
* The no-perfusion analytic reference is not a decay. A uniform field with no perfusion, no source, and zero-flux boundaries stays constant, so the no-perfusion check is a conservation check (A1). The exponential decay check is perfusion-driven (A2). The task text asked for a no-perfusion cooling case, and this split is the closest analytic form that holds exactly.
* The lesion indicator is V_lesion (CEM43 at or above 240 min), not the instantaneous V60 alone. V60 falls to zero after power off (65 s in B1), so it does not stabilize. V_lesion is monotone and stabilizes. V60 is reported too.
* The linear model gives 450.3 K (177 C) at the center in B1. Temperatures above about 100 C are outside the physical regime of a linear Pennes model without boiling or phase change. The README states this limit. The default power of 5 W is a scenario choice and is not calibrated to a device. A lower power or a temperature-dependent model is a later decision.
* `fmi3Reset` restores the instantiation defaults. It is implemented but not exercised by `check_fmu.py`.
* The stubs in `src/fmi3_unsupported.c` exist only so FMPy 0.3.32 can load the library. `modelDescription.xml` declares none of those capabilities.
* Approval gate (AGENTS.md section 6): this slice changes more than 5 files and more than 200 lines, and it creates a new public FMU interface. The parent session assigned the file set and the scope in the work order. The work proceeds on that direct instruction, and this record notes the gate.

## Open Items

* The (confirm) tissue values and the blood specific heat are not checked against the IT'IS download.
* CMake is a host install (3.31.6), and no tracked file pins it. The SOUP row records this as a pin gap.
* Visual Studio Community license terms need a check against the no-commercial-license decision (`SNDEV/docs/impl-2026-10-14-no-commercial-licenses.md`). The MSVC toolchain is already used by `sim/bridge/`.
* MC/DC coverage of the FMU code is not measured (see Gate status).
* `DEVELOPMENT_PLAN.md` task 2.7 row is not updated. The consolidation step records the slice-1 status.
* The mechanical (SOFA) and physiology (Pulse) FMUs are not built. The wrapper requirements are listed in `sim/fmi/README.md`.

## Evidence

* `SNDEV/logs/fmi-build-release-2026-11-05.txt`
* `SNDEV/logs/fmi-build-relwithdebinfo-2026-11-05.txt`
* `SNDEV/logs/fmi-thermal-pennes-check-2026-11-05.json`
* `SNDEV/logs/fmi-thermal-pennes-check-stdout-2026-11-05.txt`
