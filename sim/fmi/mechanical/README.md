# Mechanical SOFA FMU (mechanical_sofa)

Status: slice 2 of plan task 2.7 (SRS FR-MS-002 scene step behind FR-MS-007). The FMU is an FMI 3.0 Co-Simulation FMU whose DoStep is one SOFA solver step of the pinned reference organ at dt 0.001 s. It passes the mechanical import checks in `sim/fmi/check_fmu.py --model mechanical`. The cut path is outside its contract (see below). Gate G2.6 is not measured here.

## Files

* `src/mechanical_sofa.cpp`: the FMI 3.0 entry points (C++17). The DLL does not link SOFA. It starts the worker, exchanges one line per step over a named pipe, and restarts the worker on reset.
* `worker/mechanical_worker.py`: SofaPython3 scene run by `runSofa.exe -l SofaPython3`. It builds the reference organ from `sim/sofa/src/meshes/reference_organ.msh` with the parameters of `sim/sofa/src/reference_scene.scn`, adds the tool coupling, and advances one step per command.
* `model/modelDescription.xml`: the FMI 3.0 variable list (26 variables, see below).
* The build packages the DLL, `modelDescription.xml`, `resources/mechanical_worker.py`, and `resources/meshes/reference_organ.msh` into `sim/fmi/build/fmu/mechanical_sofa.fmu` (built by `sim/fmi/build.ps1`).

## Variables

| Name | Causality | Unit | Start | Meaning |
|:---|:---|:---|:---|:---|
| time | independent | s | 0 | FMU time |
| tool_stiffness | parameter (fixed) | N/m | 2000 | penalty stiffness of the tip-to-node coupling (0 gives gravity only) |
| tip_x, tip_y, tip_z | input | m | 0.1, 0.2, 0.1 | tool-tip position in the scene frame (scene y superior) |
| tip_qx, tip_qy, tip_qz, tip_qw | input | 1 | 0, 0, 0, 1 | tool-tip orientation (echoed to the pose output; no physical effect for a point coupling) |
| force_x, force_y, force_z | output | N | calculated | force on the tool from the organ, k (x_node - tip) |
| torque_x, torque_y, torque_z | output | N.m | calculated | torque on the tool about the tip (zero for a point coupling) |
| pose_x, pose_y, pose_z | output | m | calculated | tool-tip pose position (the applied input) |
| pose_qx, pose_qy, pose_qz, pose_qw | output | 1 | calculated | tool-tip pose orientation (the applied input) |
| max_disp | output | m | calculated | maximum nodal displacement magnitude from the initial state |
| mean_disp | output | m | calculated | mean nodal displacement magnitude |
| tip_node_disp | output | m | calculated | displacement magnitude of the organ coupling node |
| step_count | output | 1 | calculated | completed solver steps since the worker started |

The FMU step is fixed at 0.001 s (`fixedInternalStepSize`). A DoStep with another step size returns fmi3Error.

## Physical Model

The organ is the parenchyma of the budget-fit reference scene: 405 nodes, 1230 tetrahedra on the 20 mm grid, NeoHookean material with ParameterSet 1785.714286 7142.857143, total mass 1.640000 kg, gravity -9.81 along y, EulerImplicitSolver (rayleighMass 0.1, rayleighStiffness 0.1), PCG with 25 iterations and tolerance 1e-9, and the base fixation on the y = 0 plane (box from `reference_scene.scn`).

Tool coupling. The tool tip is a point spring to one organ node (the node nearest the top-center of the organ). The force on the organ node is k (tip - x_node), and the wrench on the tool is k (x_node - tip). The torque is zero for a point coupling. The spring uses the input tip position at each step. The worker sets the force before the step and reports the wrench after it.

Not modeled: the contact controller of `sim/sofa/src/contact_scene.py` (corridor culling, swept segment-triangle test, penalty normal force with damping, puncture force, and the scripted needle trajectory). The FMU is therefore not the contact suite's contact model. Its tool is a single elastic point coupling, and its wrench is the spring force.

## Process Structure and Archive Decision

The SOFA runtime is a host dependency. The archive does not contain it.

* Reason 1: the SOFA runtime is 115 MB of DLLs in `collections/bin` (98 import libraries). Shipping it would make the archive far larger than the 46 kB FMU.
* Reason 2: in-process linking was not possible in this slice. The SOFA headers need Boost (`boost/shared_ptr.hpp`, `boost/intrusive_ptr.hpp`, `boost/container/stable_vector.hpp`), and Boost is not in the SOFA install or in the ROS 2 pixi environment. A plain CPython import of the SofaPython3 binding also failed in the probe. The contact suite runs SOFA through `runSofa.exe -l SofaPython3`, which works, so the worker uses that path.
* Consequence: the mechanical FMU runs on a host that has the pinned SOFA v26.06.00 install (`SRTA_SOFA_ROOT`, default `C:\Users\salmo\SOFA\v26.06.00`) and the pixi CPython 3.12 environment (`SRTA_SOFAPY_ENV`, default `env/ros2-jazzy/.pixi/envs/default`). Both are pinned in `sim/SOUP.md`.

The DLL starts `runSofa.exe` with `-l SofaPython3 -g batch -n 1000000000`, the worker scene, and an environment that sets PATH and PYTHONPATH the same way `sim/sofa/src/run_contact_suite.py` does. The worker opens the named pipe `\\.\pipe\srta-mech-<pid>-<n>`.

## Protocol

One ASCII line per message. Every `STEP` command produces exactly one reply after its solver step.

* Command `STEP tx ty tz qx qy qz qw` (sent by fmi3DoStep before the step), reply `OK fx fy fz tx ty tz max_disp mean_disp tip_node_disp steps`.
* Command `QUIT` (sent by fmi3Terminate and by the free and reset paths), no reply. The worker closes the pipe and exits.
* A malformed command or a non-finite value makes the worker reply `ERR ...` and exit with status 3. The DLL then returns fmi3Error.
* A worker that exits or stops replying within 30 s makes the DoStep return fmi3Error.
* fmi3Reset stops the worker and sets the FMU to its configuration state. The next initialization starts a new worker, so the state after a reset equals a fresh instance. A SOFA step cannot be skipped inside a running scene, so reset is a worker restart and not a replayed command.

Worker start takes a few seconds (scene load). The DLL waits for the pipe connection for up to 120 s.

## Cut Contract Boundary (as written)

Cut events are outside the contract of `mechanical_sofa`. The FMU covers the elastic and contact-coupling step path only.

In the contact suite (`sim/sofa/src/contact_scene.py`), a cut ends the SOFA process with exit code 10 after writing a checkpoint. A numpy step then applies the cut to the topology, because SofaPython3 does not bind `removeTetrahedra`, and a new process resumes from the checkpoint. A single fmi3DoStep cannot express this. It would have to end the worker, change the organ state outside SOFA, and restart the scene inside one communication step, with the state, the time, and the tool trajectory crossing that boundary in the middle of a step. This FMU therefore has no cut input and does not simulate tissue separation. If the worker exits during a step for any reason, including exit code 10, the DoStep returns fmi3Error.

For the task 2.8 master, a co-simulation-level restart contract is required before cut events can run inside a master schedule. That contract has to define a checkpoint-and-resume event, the state hand-off between worker processes, the rule for FMU time after the restart, and the rule for the tool trajectory across the event. Until that contract exists, cut events run only in the standalone contact suite.

## Mapping Gap: Deformation Summary and Modal Coefficients

The bridge message contract (`sim/bridge/README.md`, `MeshDeformationState`) carries modal coefficients (at most 16 floats in `mode_coefficients`). This slice has no modal basis: the reference scene is not reduced, and the modal reduction does not exist yet. The FMU therefore exposes a displacement summary (`max_disp`, `mean_disp`, `tip_node_disp`) and not modal coefficients. The future mapping is a projection of the nodal displacement onto a modal basis, which belongs to the reduced-order path. This is a mapping gap, not an implemented mapping.

## Validation

Checks in `sim/fmi/check_fmu.py --model mechanical` (pre-registered in `SNDEV/docs/impl-2026-11-07-task27-slice2-mechanical-fmu.md`):

* M1 organ setup: the worker's gravity-only positions at step 40 agree with the pinned `reference_scene.scn` run at T = 0.04 s within 1e-6 m. The FMU's max displacement at step 40 agrees with the reference maximum within 1e-6 m.
* M2 static load: the FMU wrench for a fixed tip agrees with a standalone worker run of the same commands within 1e-6 N. This is a wiring check, because both runs execute the same worker code. The force was not at equilibrium after 500 steps (drift over the last 100 steps is recorded and is not a pass criterion).
* M3 step cost: wall time per DoStep over 1000 steps, against the 11.0 ms reference mean and the 16.7 ms budget.
* M4 reset: 200 steps, reset, 200 steps, exact agreement.
* M5 error paths: a wrong step size and a non-finite tip input return fmi3Error.

Results and numbers are in the implementation record `SNDEV/docs/impl-2026-11-07-task27-slice2-mechanical-fmu.md`.

## Build and Check

```
powershell -ExecutionPolicy Bypass -File sim\fmi\build.ps1
python sim\fmi\check_fmu.py --model mechanical
```

The runtime needs the SOFA install and the pixi environment described above. The worker's stderr contains a SOFA logger message about an uncleaned library at exit (`printLibraryNotCleanedUpWarning`, followed by an abort). The worker exits with `os._exit` after writing its replies, so the results are complete. The message is harmless to the results.

## Pulse Proxy Notes

The Pulse physiology FMU (task 2.7 plan item for the physiology model) needs the same structure: a thin DLL that talks to an out-of-process engine over a pipe, with the engine process started through the pinned environment. The Pulse engine lives in the `biosync-pulse` Linux container, so the worker is a container-side process reached through a host bridge (for example a named pipe bridged to the container), and the DLL cannot link the engine in-process on Windows. The design (transport, process ownership, and the reset rule) goes to the project owner before that slice is built.
