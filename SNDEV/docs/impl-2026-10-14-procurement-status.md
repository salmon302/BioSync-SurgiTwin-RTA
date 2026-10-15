Title: Procurement status update for Phase 2 tooling (guide items 1, 2, 3, 6)
Date: 2026-10-15T03:32:33Z
Author: Seth Nenninger (MiMo-V2.6-Pro Agent)
Contribution Type: Implementation
Ticket/Context: procurement update 2026-10-14 (user-executed guide sequence items 1, 2, 3, 6)
Summary: Records the user-executed procurement results in the SOUP inventory, the procurement guide, the plan, and the migration map, and logs the FR-MS-006 heartbeat failure under G2.5.

## Task Reference

`docs/procurement-guide.md`, Section 7 (procurement sequence). Items 1, 2, 3, and 6 were executed by the user on 2026-10-14. Items 4 and 5 are deferred by the user.

The heartbeat diagnosis is owned by a parallel agent and is recorded in `SNDEV/docs/impl-2026-10-14-heartbeat-gap-diag.md`. This log cites that file read-only.

## Specification Summary

Record the outcome of each procurement item in the files that track it:

* `sim/SOUP.md`: pin, evaluation, and anomaly-response cells for the Pulse, PyPulse, SOFA, 3D Slicer, ROS 2, and SlicerROS2 rows, plus a new FMPy row.
* `docs/procurement-guide.md`: a status for each of the six rows in the Section 7 table.
* `DEVELOPMENT_PLAN.md`: the Phase 2 status paragraph, task 2.6 marked done, gate G2.5 marked FAIL measured, and the Phase 2 estimate recomputed for the completed task.
* `docs/migration-map.md`: a row for the `.pulse/` source copy.

Scope limits: no code, test, or Docker change. Files owned by the parallel agent are not touched.

## Implementation Notes

Files changed (five files only):

* `sim/SOUP.md`: Pulse, PyPulse, SOFA, 3D Slicer, ROS 2, and SlicerROS2 rows updated. FMPy row added after the FMI-LS-BUS row.
* `docs/procurement-guide.md`: Section 7 table gained a Status column with one status per row.
* `DEVELOPMENT_PLAN.md`: Phase 2 status paragraph extended, Phase 2 estimate updated, task 2.6 marked done, Phase 2 gate table gained a Status column (G2.5 FAIL measured, other rows OPEN).
* `docs/migration-map.md`: Table 1 row added for the `.pulse/` copy, placed after the existing `middleware/Dockerfile.pulse` row.
* `SNDEV/docs/impl-2026-10-14-procurement-status.md`: this log (new).

Source facts recorded:

* Pulse origin: `I:\Documents\GitHub\BioSync\BioSync-Gateway\.pulse`, Gateway HEAD `babc6323baa9738b8838df754cff4aba63b3ee91` (`git rev-parse HEAD`, read today). Destination `.pulse/` at the repository root, gitignored by `.gitignore` line 28.
* Pulse version: `project(Pulse VERSION 4.3.2 LANGUAGES C CXX)` in `.pulse/CMakeLists.txt`, line 46. Pin tag `REL_4_3_2`.
* SOFA: `C:\Users\salmo\SOFA\v26.06.00\collections\bin\runSofa.exe`. The guide's Section 2 names the binary directory as the executable location, so the path is under `collections\bin`.
* 3D Slicer: `I:\Library\3D Slicer 5.12.4\Slicer.exe`, version 5.12.4 instead of the guide's recommended 5.12.0.
* FMPy: 0.3.32 in the host Python 3.14 user site, `C:\Users\salmo\AppData\Roaming\Python\Python314\site-packages`. Not a repository venv.

## Verification

Checks run on 2026-10-15 UTC against the working tree after the edits.

| Check | Result | Evidence |
|:------|:-------|:---------|
| SOFA executable | PASS | `Test-Path C:\Users\salmo\SOFA\v26.06.00\collections\bin\runSofa.exe` returned True |
| 3D Slicer executable | PASS | `Test-Path "I:\Library\3D Slicer 5.12.4\Slicer.exe"` returned True |
| Pulse source copy | PASS | `Test-Path .pulse\CMakeLists.txt` returned True; `project(Pulse VERSION 4.3.2 LANGUAGES C CXX)` at line 46 |
| Pulse ignore rule | PASS | `.gitignore` line 28 is `.pulse/` |
| Gateway origin commit | PASS | `git -C BioSync-Gateway rev-parse HEAD` returned `babc6323baa9738b8838df754cff4aba63b3ee91` |
| WSL2 Ubuntu absence | PASS | `wsl -l -v` lists only `docker-desktop-data` and `docker-desktop` |
| Status string, SOUP | PASS | `FMPy \| 0.3.32` matches once; the Gateway hash matches once; Pulse heartbeat numbers in the evaluation and anomaly cells (239.357 ms in two cells) |
| Status string, guide | PASS | `DONE with alternate pin` matches once; `PENDING` in items 4 and 5; `PARTIAL` in item 6 |
| Status string, plan | PASS | `FAIL measured` matches once; `41.0 d remaining` matches once; `OPEN` occurs in the Status column of G2.1 to G2.4 and G2.6 |
| Gate G2.5 status cell | PASS | The Status cell begins `FAIL measured` and contains no OPEN. The unchanged Requirement cell still reads "IQ-4 and OQ-16 PASS on the pinned Pulse build", as the instruction required |
| Migration-map row | PASS | One new row for `.pulse/` (repo root, gitignored); the existing Dockerfile row is not duplicated |
| Git scope | PASS | `git diff --name-only` lists DEVELOPMENT_PLAN.md, docs/migration-map.md, docs/procurement-guide.md, and sim/SOUP.md; the log is the one untracked file. No file under `middleware/`, `vv/`, or any code path changed |
| Banned words, dashes, curly quotes | PASS | Sweep of the five files for the banned list, em dashes, en dashes, and curly quotes: zero matches |

Phase 2 estimate arithmetic. Before this update: 43.0 d total, task 2.6 open at 2.0 d. After: task 2.6 is done.

* Completed: 2.0 d (task 2.6).
* Remaining open rows: 2.1 at 5.0, 2.2 at 8.0, 2.3 at 6.0, 2.4 at 4.0, 2.5 at 4.0, 2.7 at 6.0, 2.8 at 8.0. Sum = 5.0 + 8.0 + 6.0 + 4.0 + 4.0 + 6.0 + 8.0 = 41.0 d.
* Completed plus remaining = 2.0 + 41.0 = 43.0 d, so the total is unchanged.

Task 2.5 is not marked done. Its heartbeat clause fails, so its row keeps its estimate and carries no done marker.

Commit: see the commit subject in `git log -1`. The commit body references this log.

## Follow-ups

* Heartbeat diagnosis pending: `SNDEV/docs/impl-2026-10-14-heartbeat-gap-diag.md` (parallel agent). The G2.5 failure stays open until that diagnosis is recorded and a decision (accept, pin back, or upgrade) is logged.
* FMI item 6 partial: Reference FMU build and fmi4c clone not reported. FMPy is not in a tracked requirements file or a repository venv, so a `.venv-fmi` with an exact pin is still needed.
* WSL2 items 4 and 5 pending at the user decision of 2026-10-14. No Ubuntu 24.04 WSL2 distribution is present.
* HIL decision open (guide "Remaining board", task 4.5).
* Stale provenance row: `docs/migration-map.md` Table 3 row "Pulse engine source provenance and build" still reads OPEN. It is left unchanged in this update.
* SOFA scene run and CMake find check, and Slicer DICOM load and labelmap export, are not reported by the user. The done-when checks in the guide still need evidence.
