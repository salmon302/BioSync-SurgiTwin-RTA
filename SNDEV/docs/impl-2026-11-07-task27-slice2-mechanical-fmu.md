Title: mechanical SOFA FMU wrapper with import checks (plan task 2.7 slice 2)
Date: 2026-11-07T09:00:00Z
Author: Seth Nenninger (Claude Haiku 5.5 Agent)
Contribution Type: Implementation
Ticket/Context: plan task 2.7 slice 2
Summary: Adds an FMI 3.0 Co-Simulation FMU (C++17 proxy DLL) for the SOFA reference organ, driven by a SofaPython3 worker process over a named pipe, with tip-to-node tool coupling, a displacement summary, a documented cut boundary, and mechanical import checks (static load, step cost, reset, error paths).

## Task Reference

Plan task 2.7 in `DEVELOPMENT_PLAN.md` (Phase 2 row "2.7 Package the thermal ablation, mechanical (SOFA), and physiology (Pulse) plant models as FMI 3.0 FMUs"). This slice is the mechanical FMU. Requirement FR-MS-007 in `SRS.md` v1.2.0. Gate G2.6 is later. `DEVELOPMENT_PLAN.md` is not edited (another builder holds it). Slice 1 record: `SNDEV/docs/impl-2026-11-05-task27-slice1-thermal-fmu.md`.

## Specification Summary

* Mechanical FMU, FMI 3.0 Co-Simulation, C++17 target in `sim/fmi/`, exporting the fmi3 C entry points. One DoStep is one SOFA solver step at dt 0.001 s (the scene dt).
* Inputs: tool-tip position and orientation (structured as scalar inputs). Outputs: tool-tip wrench (6-axis), tool-tip pose, and a deformation summary.
* Cut events are outside the FMU contract. The boundary is recorded for the task 2.8 master.
* Build: extend `sim/fmi/build.ps1`. Record whether the SOFA runtime ships in the archive or is a host dependency, with the archive contents and size.
* Import checks in `sim/fmi/check_fmu.py`: static load, step cost against the 11.0 ms measured mean and the 16.7 ms budget, fmi3Reset, and an error-path case.

## Preflight (2026-11-07 record)

* Scene: `sim/sofa/src/reference_scene.scn` (budget-fit 20 mm grid, 405 nodes, 1230 tets, EulerImplicitSolver with PCG 25 iterations, gravity -9.81, dt 0.001, base fixation on y = 0, parenchyma NeoHookean ParameterSet 1785.714286 7142.857143, total mass 1.640000 kg). Commits `909c1d6` and `f3df8f8` are present.
* Contact and cut: `sim/sofa/src/contact_scene.py` computes contact in a Python ContactController with a scripted needle trajectory, and it writes bridge captures and exits with code 10 at a cut. `sim/sofa/src/run_contact_suite.py` runs it through `runSofa.exe -l SofaPython3`.
* SOFA runtime: `C:\Users\salmo\SOFA\v26.06.00` (collections/bin 115 MB of DLLs; 98 import libraries; headers under `include\Sofa.*`).

## Design Decisions

1. In-process C++ linking was tried and not used. The SOFA C++ headers need Boost (`boost/shared_ptr.hpp`, `boost/intrusive_ptr.hpp`, `boost/container/stable_vector.hpp`). Boost is not in the SOFA install or in the ROS 2 pixi environment, so an in-process build would also need a Boost tree with its own pin. The probe is recorded in this log.
2. A Python import of the SofaPython3 binding from a plain CPython process also failed in the probe (the binding DLL did not load under the pixi interpreter, with SOFA_ROOT and SOFAPYTHON3_ROOT set). The contact suite works through `runSofa.exe -l SofaPython3`, so that path is the one used.
3. The FMU is a C++17 proxy DLL. It starts `runSofa.exe -l SofaPython3` with a worker scene (`sim/fmi/mechanical/worker/mechanical_worker.py`), and it exchanges one command line and one reply line per DoStep over a named pipe. This is the same pattern planned for the Pulse IPC proxy in slice 1. The SOFA runtime is a host dependency: the DLL does not link SOFA, and the archive carries only the worker script and the mesh. Reason: the runtime is 115 MB of DLLs and would make the archive large, and the Windows host already has the pinned install (`sim/SOUP.md`, SOFA row).
4. The worker scene reproduces the parameters of `reference_scene.scn` (same mesh file, material, solver, mass, base fixation). The check compares the gravity-only state against the pinned reference scene run, so the organ setup is validated against the pinned scene.
5. The tool is a penalty spring from the input tip position to one organ coupling node (the node nearest the organ top center at scene build). The spring force on the organ node is k (tip - x_node). The wrench on the tool is k (x_node - tip), with zero torque for a point coupling. This is not the ContactController contact model (no corridor culling, no swept test, no puncture). That gap is recorded.
6. Cut events are out of scope (see the boundary text in the README).

## Host State

Recorded at the start of the timing run in `SNDEV/logs/` (see the results section).

## Pre-Registered Checks (fixed before the mechanical check run)

* M1 organ setup (gravity only, tool stiffness 0, 40 steps): the worker positions at step 40 agree with the pinned `reference_scene.scn` run at T = 0.04 (positions.out) within 1e-6 m (the dump is written with about six significant digits). The FMU maximum displacement at step 40 agrees with the reference maximum displacement (T = 0.04 minus T = 0) within 1e-6 m.
* M2 static load (tool tip at (0.10, 0.195, 0.10) m, tool stiffness 2000 N/m, 500 steps): the FMU wrench at every step agrees with the standalone worker run of the same command list within 1e-6 N. The final-100-step drift of the force is recorded (not a pass criterion).
* M3 step cost (1000 DoSteps of the coupled scene, wall time per fmi3DoStep): pass when the mean is at most 13.2 ms (11.0 ms measured reference mean plus 20 percent) and the p95 is at most 16.7 ms. Mean, p95, and max are reported. The max is not a pass criterion, because the G2.2 record shows tail steps above the budget for the bare scene.
* M4 reset: 200 steps, `fmi3Reset` (worker restart), re-initialization, 200 steps. The second run agrees with the first within 1e-9 for every output.
* M5 error paths: a communicationStepSize of 0.002 s and a non-finite tip input each return fmi3Error.

Reference scene run (for M1): `sim/sofa/src/reference_scene.scn` copied to a temporary directory with its meshes, run through `runSofa.exe -g batch -n 52`, positions.out read at T = 0, 0.01, ..., 0.05.

## Implementation Notes

Status: in progress. Results and deviations are appended below as each item completes.

Worker and proxy smoke test (2026-11-07). The worker scene in script mode matches the pinned reference scene at T = 0.04 within 5e-7 m (the T = 0.04 frame of the reference equals worker step 40, and T = 0.05 equals step 50). The FMU built with MSVC (Release): `sim/fmi/build/fmu/mechanical_sofa.fmu` (45977 bytes), archive contents modelDescription.xml, binaries/x86_64-windows/mechanical_sofa.dll (69120 bytes), resources/mechanical_worker.py, and resources/meshes/reference_organ.msh. FMPy validation passes. Ten DoSteps took 0.126 s through the pipe.

Final build and FMU (2026-11-07). `sim/fmi/build.ps1` (Release, MSVC 19.44.35217, Visual Studio generator x64) builds both FMUs with no warnings under `/W4 /WX`. Sizes: `sim/fmi/build/fmu/mechanical_sofa.fmu` 46010 bytes (sha256 `fb8fa29c13fe2685736c43c0b6cf1ef79d1d6d402ec11f0b22a2eab7c33d279e`), `sim/fmi/build/fmu/thermal_pennes.fmu` 11520 bytes. Archive contents of the mechanical FMU: modelDescription.xml (8191 bytes), binaries/x86_64-windows/mechanical_sofa.dll (69120 bytes), resources/mechanical_worker.py (10194 bytes), resources/meshes/reference_organ.msh (51401 bytes). The model description lists 26 variables (time, one fixed parameter, seven inputs, 17 outputs; see `sim/fmi/mechanical/README.md`). Validation with FMPy 0.3.32 passes.

Archive decision: the SOFA runtime (115 MB) is a host dependency, and the archive carries the worker script and the mesh only. The reasons are in the README (archive decision section). The thermal FMU check was re-run after the shared CMake change: all five cases pass (`SNDEV/logs/fmi-thermal-pennes-check-slice2-2026-11-07.json`).

Import checks, official run (`SNDEV/logs/fmi-mechanical-check-2026-11-07.json`, stdout `fmi-mechanical-check-stdout-2026-11-07.txt`, host snapshots `fmi-mechanical-host-before-2026-11-07.txt` at 0 percent total CPU and no watched process, and `fmi-mechanical-host-after-2026-11-07.txt` at 4.5 percent and no watched process):

| Case | Result | Numbers and tolerance |
|:---|:---|:---|
| M1 organ setup vs pinned reference scene (gravity only, 40 steps, T = 0.04 s) | PASS | worker positions vs reference: max deviation 4.99e-7 m (tolerance 1e-6 m). Reference max displacement 8.246457e-3 m, FMU max displacement 8.246500e-3 m, deviation 4.2e-8 m (tolerance 1e-6 m) |
| M2 static load (tip (0.10, 0.195, 0.10) m, k = 2000 N/m, 500 steps) vs standalone worker | PASS | FMU vs standalone wrench: max deviation 0 N (tolerance 1e-6 N, same worker code path). Final force (-1.2593, -11.5103, 0.1006) N, norm 11.579 N. Drift over the last 100 steps 0.701 N (recorded, not a criterion: the force has not reached equilibrium after 0.5 s) |
| M3 step cost (1000 DoSteps, wall time per fmi3DoStep, pipe included) | PASS | mean 11.22 ms (reference 11.0 ms; pass limit 13.2 ms), p95 11.53 ms (budget 16.7 ms), p99 11.73 ms, min 10.86 ms, max 25.12 ms, 1 step over the 16.7 ms budget |
| M4 reset (200 steps, fmi3Reset with worker restart, 200 steps) | PASS | max deviation 0 (tolerance 1e-9) |
| M5 error paths | PASS | communicationStepSize 0.002 s: fmi3Error (status 3). NaN tool-tip input: fmi3Error (status 3) |

Interpretation. M1 validates the organ setup against the pinned scene. M2 checks the wiring of the proxy: because the FMU and the standalone run execute the same worker code, exact agreement is expected, and it does not validate the physics. The static-load case did not settle in 0.5 s, so a true equilibrium comparison (the task asked for "step to equilibrium") needs a longer run and is recorded as open. M3 is within the pre-registered limits; the single tail step above the budget is 25.1 ms, which is the same kind of tail the G2.2 record shows for the bare scene.

Gap record (mapping and contact).

* Tool contact: the FMU uses a point spring to one organ node. It does not reproduce the ContactController of `sim/sofa/src/contact_scene.py` (corridor culling, swept segment-triangle test, penalty normal with damping, puncture, scripted needle). The contact suite remains the reference for contact.
* Deformation: the bridge contract `MeshDeformationState` carries modal coefficients. No modal basis exists in this scene, so the FMU exposes displacement summaries (max, mean, tip node). The modal mapping is a later task on the reduced-order path.
* Cut path: outside the FMU contract (see the cut-contract boundary text in `sim/fmi/mechanical/README.md`).

Cut contract boundary (text as written in the README): "Cut events are outside the contract of `mechanical_sofa`. The FMU covers the elastic and contact-coupling step path only. In the contact suite, a cut ends the SOFA process with exit code 10 after writing a checkpoint. A numpy step then applies the cut to the topology, because SofaPython3 does not bind `removeTetrahedra`, and a new process resumes from the checkpoint. A single fmi3DoStep cannot express this, because it would have to end the worker, change the organ state outside SOFA, and restart the scene inside one communication step. This FMU therefore has no cut input and does not simulate tissue separation. If the worker exits during a step for any reason, including exit code 10, the DoStep returns fmi3Error. For the task 2.8 master, a co-simulation-level restart contract is required before cut events can run inside a master schedule. That contract has to define a checkpoint-and-resume event, the state hand-off between worker processes, the rule for FMU time after the restart, and the rule for the tool trajectory across the event. Until that contract exists, cut events run only in the standalone contact suite."

Pulse proxy note (for the owner, before that slice): the physiology FMU would use the same DLL-to-worker structure. The Pulse engine is in the `biosync-pulse` Linux container, so a Windows DLL cannot link it in-process. The worker would be a container-side process reached through a host bridge (a named pipe bridged into the container, or a TCP port). The design questions for the owner are the transport, which side owns the engine process, and the reset rule (a restart, as for SOFA, is the simplest and exact choice).

Engineering notes from the bring-up: (1) SofaPython3 crashed when the controller assigned Python containers (set, None) to its own attributes; the controller keeps its state in one plain object. (2) The worker's `os._exit` after QUIT prints a SOFA logger abort on exit; the replies are written before the exit, so the results are complete. (3) A SOFA step cannot be skipped, so fmi3Reset restarts the worker instead of replaying a reset command. (4) The FMU model description needs UnitDefinitions before LogCategories and DefaultExperiment (the schema order).
