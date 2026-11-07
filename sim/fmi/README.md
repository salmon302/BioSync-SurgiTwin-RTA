# FMI 3.0 FMU Packaging for the Plant Models

Status: slice 1 of plan task 2.7 (SRS FR-MS-007, VAL-028). The thermal ablation plant model is packaged as an FMI 3.0 Co-Simulation FMU and passes the unit-level import checks in `check_fmu.py`. The mechanical (SOFA) FMU was added in task 2.7 slice 2 (`mechanical/`). The physiology (Pulse) FMU is not built. The co-simulation master is task 2.8 and is not in this directory yet. Gate G2.6 (clock skew and message jitter) is not measured here.

## Files

* `CMakeLists.txt`: FMU target `thermal_pennes`. Compiles the shared library, stages the FMI 3.0 layout, and zips `<name>.fmu`.
* `build.ps1`: one command that configures, builds, and stages the FMU under MSVC (Visual Studio 2022, x64).
* `src/thermal_pennes.c`: the model and the FMI 3.0 Co-Simulation entry points.
* `src/fmi3_unsupported.c`: exported stubs for FMI 3.0 functions the FMU does not implement (see below).
* `model/modelDescription.xml`: the FMI 3.0 model description (variables, units, start values, step size, defaults).
* `include/fmi3/`: the FMI 3.0 standard C headers, pinned to the `modelica/fmi-standard` tag `v3.0.2`. Pins and hashes are in `sim/SOUP.md`.
* `check_fmu.py`: FMPy 0.3.32 import checks. Default `--model thermal` writes `SNDEV/logs/fmi-thermal-pennes-check-2026-11-05.json`. `--model mechanical` checks the SOFA FMU (see `mechanical/README.md`).
* `mechanical/`: the mechanical SOFA FMU (`mechanical_sofa`, task 2.7 slice 2): C++17 proxy DLL, SofaPython3 worker, its README (variables, archive decision, cut contract boundary).
* `pulse/`: the Pulse physiology FMU (`pulse_physiology`, task 2.7 slice 3): C++17 TCP proxy with MessagePack frames, container-side worker, its README (container route, transport contract, ownership and reset rules, variables, known limits).
* `requirements.txt`: exact pins for FMPy 0.3.32 and its installed dependency closure.

## Build and Check

From the repository root:

```
powershell -ExecutionPolicy Bypass -File sim\fmi\build.ps1
python -m pip install -r sim\fmi\requirements.txt
python sim\fmi\check_fmu.py
```

`build.ps1` accepts `-Config Release` (default) or `-Config RelWithDebInfo`. The output is `sim\fmi\build\fmu\thermal_pennes.fmu`. The archive holds `modelDescription.xml` and `binaries/x86_64-windows/thermal_pennes.dll`. The build tree and the FMU are gitignored. The warning level is `/W4 /WX`.

## Model

The model is the Pennes bioheat equation on a cubic lattice with 16 x 16 x 16 cells (4096 cells) and spacing dx = 1 mm:

rho c dT/dt = k lap(T) + w_b c_b (T_a - T) + Q_met + P_abl q(x) + nb(x) h_bc (T_env - T) / dx

* T is the tissue temperature (K). State is held in K throughout, so no offset appears in the equations.
* The Laplacian is the 7-point stencil over interior faces. A face on the lattice boundary has no neighbor term, so the default boundary is zero-flux.
* nb(x) is the number of lattice faces on the boundary of cell x (0 to 3). h_bc is a convective coefficient on all six faces.
* q(x) is the applicator deposition: P_abl is spread uniformly over the cells whose centers lie inside a sphere of radius r_app centered on the lattice center, normalized so the discrete integral equals P_abl exactly (q = 1/(N_sphere dx^3) inside the sphere, 0 outside).

### Parameters

| Symbol | Value | Unit | Source |
|:---|:---|:---|:---|
| rho | 1078.8 | kg/m3 | Liver density, IT'IS database (Hasgall et al. 2018), as tabulated in Vicentini, Ferrero, and Manzin (INRiM, 2024), Supplementary Table S1. Confirm against the IT'IS database download (confirm). |
| c | 3540.2 | J/(kg K) | Liver specific heat, same source as rho (confirm). |
| k | 0.519 | W/(m K) | Liver thermal conductivity, same source as rho (confirm). Cross-check: 0.512 W/(m K) at 37 C in human liver (Valvano, Cochran, and Diller 1985), as quoted in the ex vivo liver literature. |
| w_b | 16.24 | kg/(m3 s) | Liver blood perfusion, same source as rho (confirm). Cross-check: healthy liver perfusion 14 to 18 kg/(m3 s) (Fat Quantification Imaging and Biophysical Modeling, Frontiers in Physiology 2022, PMC8850958). |
| c_b | 3617 | J/(kg K) | Blood specific heat, IT'IS database (Hasgall et al. 2018). Not verified in this slice (confirm). |
| Q_met | 10712.9 | W/m3 | Liver metabolic heat generation, same source as rho (confirm). |
| T_a | 310.15 | K | Arterial blood temperature, 37 C, the Pennes convention (Pennes 1948). |
| T_init | 310.15 | K | Uniform normothermic start. Model choice. |
| dx | 1.0e-3 | m | Lattice spacing. Model choice. |
| r_app | 3.0e-3 | m | Radius of the spherical applicator deposition. Model choice. Not calibrated against a device. |

The rows marked (confirm) take their values from the tabulated source above and are not yet checked against the IT'IS download. Each tissue value is a fixed FMU parameter (`variability="fixed"`), so the values are set before initialization.

### Outputs and Inputs

| Name | Causality | Unit | Meaning |
|:---|:---|:---|:---|
| time | independent | s | FMU time. |
| P_abl | input | W | Applicator power, deposited during the next step. |
| h_bc | input | W/(m2 K) | Convective coefficient on the lattice faces. 0 is zero-flux. |
| T_env | input | K | Ambient temperature for the convective term. |
| T_max | output | K | Maximum cell temperature. |
| T_mean | output | K | Mean cell temperature. |
| V60 | output | mm3 | Volume of cells at or above 333.15 K (60 C) at the current time. |
| V_lesion | output | mm3 | Cumulative lesion volume: cells with CEM43 at or above 240 min. Monotone non-decreasing. |

CEM43 is the cumulative equivalent minutes at 43 C (Sapareto and Dewey 1984). Each cell accumulates dt/60 x R^(43 - T_C) minutes per step, where T_C is the cell temperature in Celsius at the start of the step, R = 0.5 for T_C >= 43, and R = 0.25 below 43. The 240 min threshold is a dosimetry convention for irreversible damage (Dewhirst et al. 2003). It is an indicator in this model and is not a validated lesion model.

### Solver

* Explicit forward Euler with fixed step dt = 0.1 s. One `fmi3DoStep` call is one solver step.
* The FMU accepts only `communicationStepSize = 0.1` s and returns `fmi3Error` for any other value. It also returns `fmi3Error` when `currentCommunicationPoint` does not match the FMU time.
* Stability bound, checked at every step with the current h_bc:

  S = dt (12 alpha / dx^2 + w_b c_b / (rho c) + 3 h_bc / (rho c dx)) <= 1, with alpha = k / (rho c).

  The 12 alpha / dx^2 term bounds the spectral radius of the zero-flux lattice Laplacian. The 3 h_bc term is the largest boundary term for a corner cell. The bound is half the forward Euler real-axis limit, so it has a factor-2 margin.
* At the default parameters, alpha = 1.3589e-7 m2/s, 12 alpha/dx^2 = 1.6307 s^-1, w_b c_b/(rho c) = 0.01538 s^-1, and S = 0.1646. The largest h_bc that keeps S <= 1 at this dt is about 1.06e4 W/(m2 K).
* The explicit scheme satisfies the discrete maximum principle under the same bound. With no source and T_a and T_env at or below T_max, T_max cannot rise.
* All arrays are allocated in `fmi3InstantiateCoSimulation` (about 130 kB). `fmi3DoStep` does not allocate, and the update uses two fixed buffers with a pointer swap.

### Why Co-Simulation and Not Scheduled Execution

The thermal model has one rate and no clocks, so the Co-Simulation interface with a fixed step is the simplest correct choice. FMPy 0.3.32 simulates FMI 3.0 CS with the same API the check uses. Scheduled Execution (`fmi3InstantiateScheduledExecution`) is the clock-based path that task 2.8 needs for the 1 ms clock-skew and message-jitter clauses. This FMU does not implement it.

### Declared Capabilities and Stubs

`modelDescription.xml` declares CoSimulation with `fixedInternalStepSize="0.1"`, no event mode, no FMU state, no directional derivatives, and no variable step size. FMPy 0.3.32 binds every FMI 3.0 symbol when it loads the library, so `src/fmi3_unsupported.c` exports the other 64 symbols and each returns `fmi3Error` (or a null instance). The implemented functions are `fmi3GetVersion`, `fmi3SetDebugLogging`, `fmi3InstantiateCoSimulation`, `fmi3FreeInstance`, `fmi3EnterInitializationMode`, `fmi3ExitInitializationMode`, `fmi3Terminate`, `fmi3Reset`, `fmi3DoStep`, `fmi3GetFloat64`, and `fmi3SetFloat64`.

## Import Checks

`check_fmu.py` validates the model description with `read_model_description(validate=True)`, extracts the FMU, instantiates it through FMPy, sets the parameters, and steps it. Every FMI call checks its status.

| Case | Setup | Analytic reference | Tolerance | Result |
|:---|:---|:---|:---|:---|
| A1 no-perfusion, no-source conservation | w_b = 0, Q_met = 0, P_abl = 0, h_bc = 0, uniform 50 C, 60 s (600 steps) | Uniform field stays constant | 1e-9 K | Max deviation 6.3e-12 K. PASS |
| A2 perfusion cooling | Q_met = 0, P_abl = 0, h_bc = 0, uniform 50 C, 60 s (600 steps) | T(t) = T_a + (T0 - T_a) exp(-w_b c_b t / (rho c)), rate 0.015380 s^-1 | 0.01 K against the continuous solution. 1e-9 K against the discrete closed form (1 - rate dt)^n | Max error 3.67e-3 K against the continuous solution. Max error 3.5e-11 K against the discrete closed form. Monotone decrease. PASS |
| B1 ablation dose | P_abl = 5 W for 0 to 30 s, then 0, h_bc = 0, default parameters, 120 s (1200 steps) | Discrete energy balance, residual against dt (P - w_b c_b V (T_mean - T_a) + Q_met V) | 1e-6 J (input about 150 J) | Residual 3.4e-10 J. V_lesion monotone, rises during power on (0 to 432 mm3 by 30 s), and stabilizes (growth over the last 20 s 0 mm3, final 480 mm3). T_mean stays at or above T_a. T_max is non-increasing after power off. PASS |
| N1 error paths | h_bc = 1e6 W/(m2 K) and a 0.05 s step | fmi3Error at both calls | Status 3 | Both return fmi3Error with a logged reason. PASS |
| R1 reset | 200 steps at defaults, w_b = 0, fmi3Reset, re-initialize without setting parameters, 200 steps | the second run equals the first | 0 | Exact equality (added in task 2.8 slice 1) |

The numbers are copied from `SNDEV/logs/fmi-thermal-pennes-check-2026-11-05.json`, the log that `check_fmu.py` writes. The analytic error in A2 is dominated by the forward Euler discretization (about n (w dt)^2 / 2 in the exponent), which is why the 0.01 K tolerance is the continuous check and the discrete closed form is the 1e-9 K check.

### Validity Limits

* The model is linear. Tissue properties do not depend on temperature, and there is no vaporization, boiling, or coagulation feedback. In B1 the center reaches 450.3 K (177 C) at 30 s. Temperatures above about 100 C are outside the regime where this linear model is physically meaningful, and the dose values are indicators of the model behavior only.
* CEM43 grows steeply above 43 C. A cell at 60 C accumulates about 218 min per step, so it crosses the 240 min threshold within two steps.
* The applicator is a uniform sphere. It does not model an electrode, an antenna, or a device-specific deposition map.
* The parameters marked (confirm) and c_b have not been checked against the IT'IS download.
* `fmi3Reset` is exercised by case R1 of `check_fmu.py` (added in task 2.8 slice 1). The check restores the instantiation defaults and reproduces a 200-step run exactly.

## Notes for the Mechanical (SOFA) and Physiology (Pulse) Wrappers

The toolchain in this directory is reusable as follows:

* The CMake target pattern (one SHARED library, a stage directory, `cmake -E tar --format=zip` into `<name>.fmu`) and the FMI 3.0 header pin at `include/fmi3/` apply to any FMU.
* `build.ps1` builds only the `thermal_pennes` target. A new wrapper adds a target with its own model description and sources, plus a `build.ps1` target argument.
* `check_fmu.py` takes the FMU path as an argument, but the cases are specific to the thermal model. A wrapper needs its own cases and its own analytic references.
* The stub pattern in `src/fmi3_unsupported.c` is reusable. Any FMU must export the full FMI 3.0 symbol set for FMPy 0.3.32 to load it.
* The SOFA wrapper must run the FEM step inside `fmi3DoStep` with a fixed step, and the SOFA 26.06.00 install (`sim/SOUP.md`) must be linked into the DLL or loaded as a runtime dependency that the FMU archive declares. Neither path is built here.
* The Pulse wrapper must keep the engine in its worker process, because the Pulse core is single-threaded per patient (`sim/SOUP.md`, Pulse row). An FMU wrapper runs inside the master process, so it calls the worker over IPC and does not link the engine directly.
* Both wrappers need an analytic or conservation case in `check_fmu.py` style before task 2.8 uses them.

## References

* Pennes HH. Analysis of tissue and arterial blood temperatures in the resting human forearm. J Appl Physiol. 1948.
* Hasgall PA, Di Gennaro F, Baumgartner C, Neufeld E, Lloyd B, Gosselin MC, et al. IT'IS Database for Thermal and Electromagnetic Parameters of Biological Tissues, version 4.0 (2018). (confirm)
* Vicentini M, Ferrero R, Manzin A. Influence of coil geometry, supply conditions and nanoparticle heating properties on magnetic hyperthermia in mouse models. Supplementary Table S1 (INRiM, 2024). (confirm)
* Valvano JW, Cochran JR, Diller KR. Thermal conductivity and diffusivity of biomaterials measured with self-heated thermistors. Int J Thermophys. 1985. (confirm)
* Sapareto SA, Dewey WC. Thermal dose determination in cancer therapy. Int J Radiat Oncol Biol Phys. 1984.
* Dewhirst MW, Viglianti BL, Lora-Michiels M, Hanson M, Hoopes PJ. Basic principles of thermal dosimetry and thermal thresholds for tissue damage from hyperthermia. Int J Hyperthermia. 2003. (confirm)
* FMI Standard 3.0.2, Modelica Association Project FMI (`modelica/fmi-standard` tag `v3.0.2`).
