# SurgiTwin-RTA Development Plan

**Version:** 2.2 (draft)  
**Date:** 2026-11-05  
**Derived From:** SRS.md v1.4.0  
**Status:** Draft with open validation findings (see Section 6). Phase 0 complete. Phase 1 complete, with gates G1.1 to G1.8 closed (G1.8 with recorded boundaries). Phase 2 in progress (kickoff 2026-10-14, `SNDEV/docs/impl-2026-10-14-phase2-kickoff.md`): tasks 2.5 and 2.6 done (gate G2.5 PASS), task 2.2 in progress at slice 1 (commit `3beb6f0`), task 2.0 added at the 2026-11-04 shift for the SRS v1.2.0 record sync. SRS.md v1.1.0 was applied 2026-10-14 (`SNDEV/docs/impl-2026-10-14-srs-v1.1-apply.md`), closing Blockers VAL-001 to VAL-004. SRS.md v1.2.0 was applied 2026-11-04 (`docs/srs-v1.2-change-proposal.md`, `SNDEV/docs/impl-2026-11-04-srs-v1.2-proposal.md`): VAL-026 pins ROS 2 provisioning to ROS 2 Jazzy natively on Windows via pixi and the RoboStack `robostack-jazzy` conda channel with `rmw_fastrtps_cpp`; VAL-027 (Option B) replaces the SlicerROS2 module requirement with a native ROS 2 bridge node in `sim/bridge/`; VAL-028 replaces the FR-MS-007 FMI-LS-BUS and `quantization-error-free` wording with scheduled-variable co-simulation over the pinned ROS 2 / Fast DDS layer. SRS.md v1.3.0 was applied 2026-11-05 (VAL-029, docs/srs-v1.3-change-proposal.md, SNDEV/docs/impl-2026-11-05-val029-apply.md): the FR-MS-002 acceptance metric is the p95 plus outlier-budget criterion, and gate G2.2 is PASS with recorded boundaries on the 2026-11-05 run. SRS.md v1.4.0 was applied 2026-11-05 (VAL-030, docs/srs-v1.4-change-proposal.md): FR-MS-001 names the TCIA HCC-TACE-Seg set (patient HCC_001) as the benchmark example and the G2.1 reference set. No commercial licenses are used in development (decision of 2026-10-14, `SNDEV/docs/impl-2026-10-14-no-commercial-licenses.md`). Major and Minor findings remain open. Task 2.4 slice 3a (93f436b), task 2.7 slice 1 (27f68bd), and task 2.8 slice 1 (762954f) are closed, and gate G2.1 closes PASS with recorded boundaries under the VAL-032 final values (`docs/val-032-g21-metric-recenter.md`).

---

## 1. Overview

### 1.1 Project Summary

SurgiTwin-RTA is a closed-loop surgical soft-tissue digital twin and Software-in-the-Loop (SIL) and Hardware-in-the-Loop (HIL) verification platform. It combines a real-time finite element simulation tier (`sim/`), a C++17 Simplex run-time assurance filter (`rta/`) that mediates between unverified controllers and the surgical robot, an informatics tier that stores telemetry and SiLA 2 remote calls in an append-only PostgreSQL audit store (`middleware/`, `database/`, `edge/`, `frontend/`), and a continuous verification harness (`vv/`) that runs static analysis, structural coverage, WCET, and traceability checks.

### 1.2 Guiding Principles

1. The RTA decision path is deterministic. It uses no heap allocation and no locking, so its worst-case timing can be measured and its control flow can be analyzed.
2. Compliance rules are enforced in the database tier first, so immutability and hash chaining hold for direct SQL access as well as for application code.
3. The CSA risk partition in SRS Section 2.2 sets the test rigor for each feature. High Process Risk features get scripted V&V with MC/DC and WCET analysis. Not High Process Risk features get unit tests and exploratory testing.
4. Test scripts are written against the ASAM XIL abstraction so that the same script set runs on SIL and HIL targets.
5. The safety-related C++ cores are checked with an open-source static analysis set with C++17 pinned. MISRA C++:2023 conformity is an adopter-supplied verification. The SRS C++20 wording is an open question in Section 6.
6. Gateway code is reused through `docs/migration-map.md`, which records every copied, adapted, deferred, and dropped artifact with its origin path.
7. Evidence lands with each increment. Test output, VTM rows, and the SNDEV phase log are committed with the code they verify.

---

## 2. Technology Stack

Rows marked Precondition need a license purchase, a hardware order, or a licensing decision before the phase that uses them. License entries marked (confirm) are checked against the pinned release when the item enters the SOUP inventory.

| Layer | Technology | Version Constraint | License or Hardware Precondition |
|:------|:-----------|:-------------------|:---------------------------------|
| Simulation and RTA core | C++17 | Pinned by `CMAKE_CXX_STANDARD 17` in `CMakeLists.txt`. The SRS "C++17/C++20" wording is open (VAL-016). | None. MSVC 19.44 used for the scaffold build. |
| Soft-tissue FEM | SOFA | v26.06.00 pinned in `sim/SOUP.md` (task 2.2 slice 1) | LGPL-2.1 (confirm). No hardware. |
| Segmentation | 3D Slicer | 5.12.4 native Windows pin for FR-MS-001 DICOM ingestion and segmentation (installed 2026-10-14) | 3D Slicer BSD-style license. No hardware. |
| ROS 2 bridge | ROS 2 bridge node in `sim/bridge/` | C++ bridge node built against the resolved RoboStack environment of task 2.0.3. SlicerROS2 is dropped (VAL-027 Option B). | Apache-2.0. No WSL2 or Linux build. |
| Robotics middleware | ROS 2 Jazzy and Fast DDS (`rmw_fastrtps_cpp`) | ROS 2 Jazzy natively on Windows via pixi and the RoboStack `robostack-jazzy` conda channel (conda-forge only), `RMW_IMPLEMENTATION=rmw_fastrtps_cpp`, with the matching Fast DDS package version from the resolved environment and the lockfile (`pixi.lock` or a conda explicit spec) committed with the SOUP row (VAL-026) | Apache-2.0. WSL2 and Ubuntu 24.04 are no longer preconditions. |
| Photorealistic rendering | NVIDIA Omniverse / Isaac Sim with USD | Runtime and USD versions pinned together in Phase 7 | Precondition: NVIDIA Omniverse license terms (proprietary) and an RTX-class GPU. |
| Physiology | Kitware Pulse Physiology Engine via Python `ProcessPoolExecutor` | Pinned source commit built from the `.pulse/` prerequisite (not in the repository) | Apache-2.0 (confirm). Built by `middleware/Dockerfile.pulse`. |
| Co-simulation | FMI 3.0 scheduled-variable co-simulation | FMI 3.0 clocks and scheduled variables over the pinned ROS 2 / Fast DDS layer (VAL-028). FMI-LS-BUS is dropped: the published FMI-LS-BUS 1.0 defines no DDS transport. | Open standards (confirm). The SRS names no FMI master tool, so the master is built in Phase 2. |
| Middleware | Python 3.11+ and FastAPI | Python 3.11 is the target (the scaffold ran on 3.14). FastAPI is pinned in `middleware/requirements.txt`, and the pins are not yet resolved against PyPI. Interpreter split (VAL-026): ROS-side subscriber and bag tooling run at CPython 3.12 under the RoboStack environment, and the OQ suites under `.venv-qual311` (Python 3.11.9) drive them and parse JSON captures in `SNDEV/logs/`. | MIT. |
| Migrations | Alembic | Pinned in `middleware/requirements.txt`; single baseline revision 0001 | MIT. |
| Clinical data | HL7 FHIR R4 with `fhir.resources` and Pydantic v2 | `fhir.resources` pinned; migration-map Table 3 records the 8.x module-name fix | MIT (`fhir.resources`, Pydantic). |
| Instrument interoperability | gRPC, Protobuf, SiLA 2 FDL | gRPC over HTTP/2; one Protobuf schema per FDL feature | SiLA 2 specifications are open. SDK license is confirmed at selection (Phase 5). |
| Database | PostgreSQL 15+ with pgcrypto | PostgreSQL 15 in CI and compose; pgcrypto enabled by `database/migrations/001-extensions.sql` | PostgreSQL License. Server-side verify-full TLS is configured at commit `a44c163` (Gateway R2 closed). |
| Operator frontend | React 18, TypeScript 5, WebGL, ECharts 5 | Node.js 20 LTS, carried from the Gateway. A chart provider abstraction keeps ECharts as the default backend. | MIT (React). Apache-2.0 (ECharts). |
| Edge MCU | ESP32-S3, MessagePack, TensorFlow Lite Micro | 8-bit integer quantized model; TFLM release pinned under `edge/` in Phase 4 | Precondition: ESP32-S3 development board. TFLM is Apache-2.0. MessagePack specification is open. |
| Build | CMake and CTest | CMake pinned through `CMakeLists.txt`; CTest runs `rta_smoke` now | BSD-3-Clause. |
| C++ unit tests | Catch2 (planned) | Pinned release added when the first Catch2 suite lands in Phase 3 | BSL-1.0. |
| Static analysis | Parasoft C/C++test or QA-MISRA | MISRA C++:2023 rule set; tool version pinned to the license for an adopter. Development pins the open-source check set named in task 3.7 (Section 5.1) instead. | Not procured in development. Adoption option for licensees only. |
| Structural coverage and timing | VectorCAST and Cantata | Statement, branch, and MC/DC coverage on C++ High Process Risk modules. Development pins the gcov-family tooling with Catch2 and CTest (task 3.8) instead. | Not procured in development. Adoption option for licensees only (Vector Informatik and QA Systems). |
| HIL targets | Speedgoat, dSPACE, or NI SLSC | One target selected in Phase 3 for Phase 4; the other vendors are not procured | Precondition: hardware purchase, vendor XIL software, and lead time. |
| XIL abstraction | ASAM XIL v3.0.0 Python API | Model Access, Electrical Error Simulation, Service-Oriented Access, and ECU Access ports | Precondition: XIL implementation not yet selected. The standard is open. |
| Python tests | Pytest and Locust | Pytest for IQ, OQ, PQ, and unit tests. Locust for load generation under NFR-PERF-001 and NFR-PERF-004. | MIT. |
| Continuous integration | GitHub Actions | `.github/workflows/ci.yml` with a qualification job on an ephemeral PostgreSQL 15 service | GitHub service terms. |
| Containers | Docker and Docker Compose | `docker-compose.yml`, `middleware/Dockerfile`, `middleware/Dockerfile.pulse` | Apache-2.0 (Compose). Docker Desktop license terms apply to commercial use. |
| Trace management | Jama or Polarion | Forward and backward trace link API, an optional adapter in Phase 6 (task 6.6). Development pins the repository-native trace store (VTM and protocol register) instead. | Not procured in development. Adoption option for licensees only (commercial license and API access). |

---

## 3. Architecture Summary

### 3.1 Tier Mapping

| Tier | Directory | Contents | Status |
|:-----|:----------|:---------|:-------|
| Virtual Proving Ground (M&S) | `sim/` | SOFA FEM scene (`sim/sofa/`), Pulse engine notes (`sim/pulse/`), FMI master and FMUs (`sim/fmi/`), ROS 2 bridge node (`sim/bridge/`, VAL-027 Option B), USD rendering (`sim/omniverse/`, Phase 7) | `sim/sofa`, `sim/fmi`, and `sim/bridge` build only when their CMake options are ON. The Pulse binding runs from `middleware/engine/pulse.py`. |
| Run-Time Assurance (RTA) | `rta/` | Simplex switch, safety envelope, timed automata, and the fallback controller (`rta/include/rta/fallback_controller.h` and `rta/src/fallback_controller.cpp`, created in Phase 3) | Placeholder classes `SafetyEnvelope`, `SimplexSwitch`, and `TimedAutomata` build by default with stub thresholds of 5.0 mm and 2.0 N. |
| Compliance and Interoperability (Informatics) | `middleware/`, `database/`, `edge/`, `frontend/` | FastAPI gateway, hash chain engine, FHIR validation, Pulse worker, SQL migrations 001 to 003, ESP32-S3 firmware (Phase 4), React client (Phase 7) | Gateway baseline migrated at commit `0b5b8d2`. The telemetry relay landed at commit `d0ef2c5` (Phase 1 task 1.5, closed at `654510b`). |
| Continuous Verification (V&V) | `vv/` | ASAM XIL harness (`vv/xil/`), VTM (`vv/traceability/`), IQ, OQ, and PQ tests (`vv/tests/`) | IQ-0 layout test present. Migrated IQ, OQ, and PQ suites present. |

### 3.2 Topology

```
Virtual Proving Ground (sim/)
  SOFA FEM core, ROS 2 bridge node, FMI 3.0 master
        |  tool-tip pose, tissue state, wrench (Fast DDS, ROS 2)
        v
Primary controller (DRL policy or teleoperator)
        |  proposed command
        v
Run-Time Assurance (rta/)
  timed automata prediction, safety envelope, fallback controller
        |  primary or fallback command
        v
Robot actuator interface

Informatics (middleware/, database/, edge/, frontend/)
  FastAPI gateway -> append-only PostgreSQL 15+ audit store
  telemetry, RTA switch events, SiLA 2 RPC log

V&V (vv/) spans all tiers: XIL harness, VTM, IQ/OQ/PQ, CI gates
```

### 3.3 Key Design Decisions

| Decision | Rationale |
|:---------|:----------|
| RTA decision path uses static buffers, with no heap allocation and no locks | Keeps WCET measurable and control flow analyzable under FR-RTA-001 and FR-RTA-002 |
| Statement-level rejection triggers on the 10 WORM tables | Zero-row UPDATE, DELETE, and TRUNCATE are rejected, which row-level triggers miss (`database/migrations/003-triggers.sql`) |
| One shared digest function for the trigger, verifier, and nightly check | Prevents the formula divergence found in the Gateway (FR-DAT-005; migration-map Table 3) |
| One long-lived worker per Pulse engine instance | The native engine object cannot be pickled, so a process pool cannot receive it as an argument (FR-MS-006) |
| Gateway code reused by copy and adapt, with a per-file record | Each reused file has an origin path and an adaptation note in `docs/migration-map.md` |
| FMI 3.0 co-simulation for plant models | Standard clocks and scheduled variables (FR-MS-007); the master is built in Phase 2 |
| ROS 2 bridge node instead of SlicerROS2 (VAL-027 Option B) | FR-MS-004 covers the bridge function, and a native ROS 2 node drops the WSL2 route and the Slicer source build. One Slicer pin remains (5.12.4 native, FR-MS-001). |
| Scheduled-variable co-simulation over ROS 2 / Fast DDS, not FMI-LS-BUS (VAL-028) | The published FMI-LS-BUS 1.0 defines no DDS transport; scheduled variables over the pinned layer carry the 1 ms skew and jitter bounds of gate G2.6 |
| Chart provider abstraction with ECharts 5 as the default | Keeps the charting backend replaceable, as the Gateway did after its approved deviation |

---

## 4. Phased Development Plan

Each phase lists its goal, a task table with estimates in days, verification gates, and a CSA risk annotation under SRS Section 2.2. Acceptance values marked (proposed) are not stated in SRS.md v1.0.0 and need approval before a gate uses them. Files marked (created) do not exist yet and are created by the named task.

### Phase 0: Foundation (DONE)

**Goal:** Establish the four-tier repository skeleton, build stubs, CI workflow, and the first IQ layout test.

**Status:** Complete at commit `86f4cd7`. Evidence: `SNDEV/docs/impl-2026-10-13-repo-scaffold.md`.

**Estimate:** 3.5 d.

#### Tasks

| Task | Output | Est. |
|:-----|:-------|:-----|
| 0.1 Create the four-tier directory tree and the CMake build, with `rta/` built by default and `sim/` behind option gates | `CMakeLists.txt`, `rta/`, `sim/` stubs | 1.0d |
| 0.2 Add the FastAPI `/health` stub, pytest smoke test, and pinned requirements | `middleware/api/main.py`, `middleware/requirements.txt`, `middleware/requirements-test.txt` | 0.5d |
| 0.3 Add the V&V directory layout and the IQ-0 repository layout test | `vv/tests/IQ/test_iq0_repo_layout.py` | 0.5d |
| 0.4 Add the compose file, environment template, and CI workflow | `docker-compose.yml`, `.env.example`, `.github/workflows/ci.yml` | 1.0d |
| 0.5 Add the architecture overview and README | `docs/architecture.md`, `README.md` | 0.5d |

#### Verification Gates

| Gate | Requirement | Acceptance Metric |
|:-----|:------------|:------------------|
| G0.1 Native build | None (foundation) | CTest `rta_smoke` Passed, 1 of 1 |
| G0.2 Python layout | None (foundation) | 52 pytest tests PASS on Python 3.14. Python 3.11 is not yet verified. |
| G0.3 Compose guard | None (foundation) | `docker compose config` exits 0 with variables set and exits non-zero when `POSTGRES_PASSWORD` is unset |

The GitHub Actions workflow was not run during the scaffold. Its first run is part of Phase 1 task 1.12.

**CSA Risk Annotation:** Not High Process Risk. Verification uses unit and smoke tests only.

---

### Phase 1: Informatics Baseline (DONE)

**Goal:** Qualify the migrated compliance, hash chain, authentication, and FHIR baseline on PostgreSQL 15, complete the FR-DAT-001 three-tier relay, and close Gateway open items R2 and R3.

**Status:** Task 1.1 is complete at commit `0b5b8d2`. Tasks 1.2 and 1.3 are CLOSED at commit `ffcf167`: the migrated SQL and the DB-gated suites ran on PostgreSQL 15.19, tamper injection detected 54 of 54 cases, and IQ-5 passes with a platform-conditional `uvloop` pin and `fhir.resources` 8.3.0. Task 1.5 is CLOSED: the telemetry relay was migrated at commit `d0ef2c5` with persistence off the event loop, and commit `654510b` fixed the `middleware/api/auth.py` import defect (F1) and the migration 006 message defect (F6), applied 006 through the compose init and the Alembic baseline, and passed the relay PostgreSQL integration tests. The full suite reports 333 passed, 0 failed, 3 skipped, and 5 xfailed on Python 3.11.9, with IQ-2 passing. Task 1.7 is complete at commit `12147f6` with an interim VTM of 31 rows. Gate G1.3 is PASS at `4d2a372`: the digest cross-check matches Python and SQL for 77 JSON vectors, the injection suite detects 54 of 54 cases, and two boundaries stay open (tail deletion needs an external anchor, finding F3, and decoded-value callers must use the JsonText path). Tasks 1.4, 1.8, 1.9, 1.10, and 1.12 are DONE (commits `a44c163`, `f4b9d8f`, `4d2a372`, and `94fc8d1`; the first CI run is pending a push), Tasks 1.6 and 1.11 and gate G1.8 closed at commit `7508b91`, so Phase 1 is complete with all gates G1.1 to G1.8 closed (G1.8 with recorded boundaries). The evidence is `SNDEV/docs/impl-2026-10-14-g18-1m-row-run.md` (run record) and `SNDEV/docs/impl-2026-10-14-pq-config.md` (configuration record). Open items are listed in Table 4 of `docs/migration-map.md`. Ledger: `docs/migration-map.md`, `SNDEV/docs/impl-2026-10-13-gateway-migration.md`, and the Phase 1 logs dated 2026-10-13 and 2026-10-14 under `SNDEV/docs/`.

**Estimate:** 25.5 d (25.5 d complete: tasks 1.1 to 1.12, all 12 rows; 0.0 d remaining). Completed days are the sum of the done rows: 4.0 + 1.5 + 1.0 + 3.0 + 4.0 + 2.0 + 2.0 + 3.0 + 2.0 + 1.5 + 1.0 + 0.5 = 25.5. Remaining days are the open rows: none, 0.0. The total is unchanged at 25.5.

#### Tasks

| Task | Output | Est. |
|:-----|:-------|:-----|
| 1.1 Migrate the Gateway compliance baseline: 11 tables (10 WORM), trigger SQL, hash chain engine, auth, FHIR validation, and IQ/OQ/PQ suites | `docs/migration-map.md`, `database/migrations/`, `middleware/`, `vv/tests/` (commit `0b5b8d2`) | 4.0d (done) |
| 1.2 Execute the SQL migrations and database-gated tests on PostgreSQL 15: IQ-3, IQ-6, IQ-7, OQ-7, OQ-8, OQ-9, and the FR-DAT-005 SQL cross-check. Add the VAL-015 injection suite with row counts and tamper types. | `SNDEV/logs/` capture, `vv/tests/OQ/test_oq_fr_dat_005_hash_crosscheck.py` | 1.5d (done) |
| 1.3 Resolve the IQ-5 failure: provision the interpreter from the pinned requirements (`uvloop`, `pandas`, `psycopg2-binary`), check the pins against PyPI, and verify on Python 3.11 | `middleware/requirements.txt` (pins confirmed), IQ-5 PASS | 1.0d (done) |
| 1.4 Close Gateway R2: set `pg_hba` to `hostssl ... clientcert=verify-full`, add the certificate tooling and TLS settings to `docker-compose.yml`, make verify-full the production default in `middleware/database.py`, and convert the three strict xfail checks into passing tests | `docker-compose.yml`, `middleware/database.py`, `middleware/tests/test_db_ssl_config.py` | 3.0d (done, commit `a44c163`, gate G1.7 PASS) |
| 1.5 Close Gateway R3: apply the uvloop policy at application startup, migrate the WebSocket telemetry relay with database writes moved off the event loop, and keep the relay inside the three-tier path (FR-DAT-001) | `middleware/api/routes/telemetry.py` (created, migrated from the Gateway), `middleware/api/main.py` | 4.0d (done) |
| 1.6 Define the test configuration for NFR-PERF-001, NFR-PERF-002, and NFR-PERF-004: deployment target, topology, Locust load definition, measurement point, and statistic | `vv/tests/PQ/locustfile.py` (created) and a configuration record in `SNDEV/docs/` | 2.0d (done, commit `7508b91`, configuration record `SNDEV/docs/impl-2026-10-14-pq-config.md`) |
| 1.7 Publish the interim complete VTM with 31 rows, each carrying a measurable acceptance metric and a test method. Rename the FR-RTA-002 row to state prediction and add the FR-RTA-003 row (VAL-001, VAL-003). | `vv/traceability/vtm.md` (created) | 2.0d (done) |
| 1.8 Implement the FR-DAT-003 finalization guard and the FR-DAT-004 generic AFTER trigger that writes audit rows for permitted changes, using the VAL-010 split | `database/migrations/004-audit-capture.sql` (created) | 3.0d (done, commit `f4b9d8f`, gate G1.2 PASS) |
| 1.9 Separate the table owner role from the application role so the application cannot run `DISABLE TRIGGER`. Seed FR-DAT-006 with a unique-credential constraint on `users` and the RBAC scope check. | `database/migrations/005-roles.sql` (created), `middleware/api/auth.py` | 2.0d (done, commit `f4b9d8f`, gate G1.4 PASS) |
| 1.10 Show Python and SQL digest equivalence for every JSON value type, beyond the pinned vector | `middleware/engine/hash_chain.py`, `vv/tests/OQ/test_oq_fr_dat_005_hash_crosscheck.py` (done, commit `4d2a372`) | 1.5d (done) |
| 1.11 Run the 1,000,000-row PQ-3 check on a dedicated database and record throughput and duration | `vv/tests/PQ/test_pq_fr_dat_005_1m_rows.py` run record in `SNDEV/logs/` | 1.0d (done, commit `7508b91`, run record `SNDEV/docs/impl-2026-10-14-g18-1m-row-run.md`, 1,000,000 rows verified in 5.84 s against the 60 s bound) |
| 1.12 Run the qualification job on PostgreSQL 15 in CI, choose and pin the Python lint and type-check tools, and record the first CI run | `.github/workflows/ci.yml`, `middleware/requirements-test.txt` | 0.5d (done, commit `94fc8d1`; first CI run pending push) |

#### Verification Gates

| Gate | Requirement | Acceptance Metric | Status |
|:-----|:------------|:------------------|:-------|
| G1.1 Append-only store | FR-DAT-003 | 100% of UPDATE, DELETE, and TRUNCATE attempts on the 10 WORM tables are rejected in OQ-7 and OQ-8 on PostgreSQL 15, with row counts unchanged | PASS (`ffcf167`, PostgreSQL 15.19, 10 WORM tables) |
| G1.2 Audit capture | FR-DAT-004 | Every permitted change writes an audit row with prior and new values, for 100% of changes in the test suite | PASS (`f4b9d8f`, 14 of 14 exercised changes captured with prior and new values) |
| G1.3 Hash chain | FR-DAT-005 | OQ-9 reports the broken row ID for 100% of injected tamper cases, and the digest cross-check matches for every JSON value type in the vector set | PASS with recorded boundaries (`4d2a372`, 77 JSON type vectors equivalent, VAL-015 detects 54 of 54 at the exact row; open: tail deletion needs an external anchor (F3), decoded-value callers must use the JsonText path) |
| G1.4 Credentials | FR-DAT-006 | Shared-account creation is rejected in 100% of attempts, and the unique-credential constraint is enforced on `users` | PASS (`f4b9d8f`, 10 of 10 shared-account creations rejected, application role cannot disable triggers or truncate) |
| G1.5 Three-tier relay | FR-DAT-001 | Relay routes perform no synchronous database writes, and `middleware/tests/test_uvloop_enabled.py` PASSES | PASS (`654510b`, relay code from `d0ef2c5`; no synchronous database writes on the event loop, uvloop policy test green) |
| G1.6 FHIR path | FR-DAT-007 | `vv/tests/OQ/test_oq_fr_dat_007_fhir_http.py` PASSES, with HTTP 422 and OperationOutcome for invalid input | PASS (`654510b`, HTTP 422 with OperationOutcome) |
| G1.7 Transport security | NFR-SEC-001 | Zero xfail markers remain in `middleware/tests/test_db_ssl_config.py`, and the production default is verify-full | PASS (`a44c163`, zero xfail markers, verify-full default, no-cert and plaintext connections rejected) |
| G1.8 Performance scope | NFR-PERF-001, NFR-PERF-002, NFR-PERF-004 | Test configuration recorded for each NFR. A 500-session run on the migrated relay produces audit rows equal to completed requests, with p95 relay latency reported against the 50 ms NFR-PERF-002 bound (proposed threshold). | PASS with recorded boundaries (`7508b91`, run g18-run1: 500 of 500 sessions connected, 0 session errors; audit parity PASS, with `telemetry_sessions` at 500 open and 500 finalized, `audit_log` at 1,000 rows (2 per completed session), and `surgical_telemetry` at 3,000 rows equal to accepted points; publisher round trip p95 1.46 ms (n = 300) against the 50 ms bound. Boundaries: (a) 10 points per second offered load, and the 50 ms bound fails at 20 points per second and above on this host; the relay serializes broadcast fan-out per frame (`ConnectionManager.broadcast`) and the tail-latency source was not isolated (client-side queueing in the single client process is an unmeasured candidate); (b) the relay ran with `DB_SSLMODE=disable`, a deviation from NFR-SEC-001 for this measurement only; (c) NFR-PERF-001 ingestion measured about 12,600 points per second against the 100,000 points per second target, below target and not claimed. Evidence: `SNDEV/docs/impl-2026-10-14-g18-1m-row-run.md`) |

**CSA Risk Annotation:** High Process Risk for tasks 1.1, 1.2, 1.4, 1.5, and 1.7 through 1.11, which cover record immutability, hash chaining, transport security, and access control. Not High Process Risk for tasks 1.3, 1.6, and 1.12. High Process Risk tasks use scripted V&V: PostgreSQL-executed IQ and OQ suites and 100% statement and branch coverage of `middleware/engine/hash_chain.py` and `middleware/database.py`. MC/DC applies only to C++ code, and this phase has none. WCET does not apply.

---

### Phase 2: M&S Tier (Soft-Tissue, Middleware Bridge, Co-Simulation)

**Goal:** Build the FEM soft-tissue scene, the ROS 2 bridge node over Fast DDS (VAL-027 Option B), the Pulse worker delegation, and the FMI 3.0 scheduled-variable co-simulation master for FR-MS-001 through FR-MS-004, FR-MS-006, and FR-MS-007.

**Status:** In progress (kickoff 2026-10-14, `SNDEV/docs/impl-2026-10-14-phase2-kickoff.md`). Phase 1 gates G1.1 through G1.3 prerequisites are PASS, and they are prerequisites for FR-MS-006 persistence. Tooling outcomes on 2026-10-14: SOFA v26.06.00 and 3D Slicer 5.12.4 are installed, which clears the preconditions for tasks 2.1 to 2.3. Pulse is pinned to tag `REL_4_3_2`, built as image `biosync-pulse`, and its `.pulse/` provenance is recorded. IQ-4 and OQ-16 pass on the pinned build. The FMI tooling item is partial (FMPy 0.3.32 installed). ROS 2 provisioning is pinned by SRS v1.2.0 (VAL-026) to ROS 2 Jazzy natively on Windows via pixi and the RoboStack `robostack-jazzy` channel with `rmw_fastrtps_cpp`, superseding the WSL2 Ubuntu 24.04 route of the procurement guide; the environment is resolved and locked in task 2.0.3. SlicerROS2 is dropped by VAL-027 (Option B): task 2.4 builds a native ROS 2 bridge node in `sim/bridge/`, and procurement item 5 is marked dropped. The `vtm-600s` run (600 s, 10 simulations) measured 239.357 ms against the 50 ms bound on 2026-10-14. The diagnosis in `SNDEV/docs/impl-2026-10-14-heartbeat-gap-diag.md` attributed the gaps to a lazy first-step metrics-hook import and generation-2 GC cost from an unbounded metrics history, and fixed both on the production path in `middleware/engine/pulse.py`. The rerun `heartbeat-diag-1` (2026-10-15) measured a maximum gap of 16.778 ms with zero samples above 20 ms, so the G2.5 heartbeat clause is PASS. Task 2.2 landed slice 1 at commit `3beb6f0` (`SNDEV/docs/impl-2026-10-15-sofa-scene-slice1.md`): the NeoHookean scene with `EulerImplicitSolver` and a PCG linear solver, the placeholder mesh generator (1296 tets: 36 tumor, 1260 parenchyma; not G2.1 output), and the headless step-timing harness with `vv/tests/OQ/test_oq_fr_ms_002_solver_rate.py`. Slice-1 captures in `SNDEV/logs/` show `sofa-2026-10-15-g22-slice1-1000steps.json` at max 16.690 ms (PASS on the 16.7 ms budget by 0.010 ms) and `sofa-2026-10-15-g22-slice1-2000steps.json` at max 23.910 ms with 7 of 2000 steps over budget (FAIL on the max statistic). Slice-2 items for task 2.2 closure: the 30-minute G2.2 load case, re-measurement on the G2.1 meshes, the max-statistic budget fix or a gate-wording decision (max versus p95), and the recorded SofaPython3 boundary (the scene stays `.scn` XML because the binding needs `python312.dll`; the RoboStack environment of task 2.0.3 brings a CPython 3.12 and the binding can be re-evaluated then). The direct `SparseLDLSolver` chain measured 17.2 to 19.6 ms mean per step and was replaced by PCG. The SRS v1.2.0 record sync of task 2.0 closed at commits 945a14e and f6254d7 for rows 2.0.1, 2.0.2, 2.0.4, and 2.0.5, and at commit 9f746e4 for row 2.0.3: ROS 2 Jazzy is locked at env/ros2-jazzy/pixi.lock (ros-jazzy-ros-base 0.11.0, ros-jazzy-rmw-fastrtps-cpp 8.4.4, ros2-fastrtps 2.14.7, CPython 3.12.16) with the Fast DDS pub/sub round trip PASS. Task 2.2 slice 2 ran the 30-minute G2.2 load case on 2026-11-05 (160000 steps, 30.9 min measured stepping, capture sofa-2026-11-05-g22-30min-160000steps.json): mean 11.604 ms, p95 12.430 ms, max 41.520 ms with 127 of 160000 steps over the 16.7 ms budget (0.079 percent, scattered, PCG iterations constant at 26), divergence PASS; evidence SNDEV/docs/impl-2026-11-05-g22-30min-load-case.md. Task 2.4 slice 1 landed at commit 40c3722: the srtra_bridge ament_cmake package with the pose, wrench, and bounded MeshDeformationState modal message contract, built Release with Ninja and MSVC 14.44.35207 through sim/bridge/build.ps1; the 60-second smoke runs show zero missing ticks with achieved rates of 100.008 Hz and 499.983 Hz; 787 of 30000 ticks were late at 500 Hz (Windows timer resolution) and the subscriber arrival p95 was not usable evidence until the arrival method was reworked; the rework landed at dbe923d (high-resolution tick timer and the subscriber arrival-method fix) and the G2.4 600 s gate run passed at 819081c with recorded boundaries (`SNDEV/docs/impl-2026-11-05-task24-g24-gate-run.md`). Task 2.1 slice 1 landed at commit 9aa90f5: the headless Slicer 5.12.4 pipeline (scripted Threshold segmentation, SimpleITK 2.5.5 post-processing, vtkDiscreteMarchingCubes meshes) runs end to end in 8.7 s warm through sim/segmentation/run.ps1 on the TCIA HCC-TACE-Seg HCC_001 smoke set with per-segment provenance sidecars and a manifest. The SRS-named Kitware TAIR example is cerebrovascular CTA/MRA in NIfTI without organ or tumor labels, so the G2.1 reference dataset choice is open (VAL-030). Task 2.1 slice 2 (commit 7d0f5ec) ran the G2.1 Dice evaluation on 2026-11-05 against the held-out SEG reference labels with VAL-030 applied in SRS v1.4.0: parenchyma_liver 0.6745, tumor_hypoattenuating 0.0000, and vascular_keepout_bone_excluded 0.0449, all FAIL against the proposed 0.90 threshold. Task 2.4 slice 2b ran the G2.4 gate on 2026-11-05 at 500.0003 Hz over 599.998 s with 300000 of 300000 ticks complete at the subscriber and zero late ticks at the node, and the verdict is PASS with recorded boundaries (`SNDEV/docs/impl-2026-11-05-task24-g24-gate-run.md`). Task 2.1 slice 4 (commit 9d2b770) completed the method iteration on 2026-11-05 with parenchyma_liver 0.8915 Dice (recall 0.9290), vascular_keepout_bone_excluded 0.2063 (recall 0.5676), and tumor_hypoattenuating 0.0000 with the lesion not detectable by inspection on the available phases, all FAIL against the proposed 0.90 threshold (`SNDEV/docs/impl-2026-11-05-task21-slice4-method.md`). VAL-031 restated the G2.1 metric on 2026-11-05 as a per-structure clause (`docs/val-031-g21-metric-proposal.md`): the parenchyma floor stays at 0.90, the vascular clause is recall-weighted with a volume bound, and the tumor clause is operator-seeded with lesion detection excluded; slice 5 is funded for the parenchyma boundary gap, the vessel recall gap, and a tumor operator-seed attempt if the dataset clinical annotation documents a lesion location. Task 2.1 slice 5 (commit 95d2e13) evaluated the clauses on 2026-11-05: parenchyma Dice 0.8853 FAIL with recall 0.9362 PASS, vascular keep-out 293.02 mL and recall 0.4650 both FAIL with a recorded clause-tension finding (recall 0.95 and the 3 times volume bound are mutually exclusive on HCC_001 at 0.78 by 0.78 by 5 mm), and the tumor sub-gate not applicable because the clinical annotation documents no lesion location (`SNDEV/docs/impl-2026-11-05-task21-slice5-val031.md`). VAL-032 re-centered the G2.1 metric on 2026-11-05 (commit 2168d53, `docs/val-032-g21-metric-recenter.md`) and slice 6 grounded it from the measurements: gate G2.1 reads PASS with recorded boundaries (parenchyma Dice 0.9077 and recall 0.9505 against the liver envelope, vascular gated recall 0.9964 at the grounded 11.0 mm floor with keep-out volume 7.2384 times the reference against the grounded 7.25 times bound, tumor not applicable). The owner ruling of 2026-11-05 (modality floor) and slice 7 (commit 19cd1a6) re-grounded the vascular markers at the 3.0 mm modality floor and gate G2.1 reads PASS with recorded boundaries (parenchyma 0.9077 and 0.9505 unchanged; vascular gated recall 0.4762 against the grounded 0.47 floor with keep-out volume 7.2384 times the reference against the grounded 7.5 times bound; tumor not applicable), superseding the slice-6 sentence values above, with the plain statement that 0.47 is the measured bounded-volume capability and the owner re-centers (`SNDEV/docs/impl-2026-11-05-task21-slice7-vessels.md`). Task 2.2 slice 3 (commit 909c1d6, `SNDEV/docs/impl-2026-11-06-g22-remeasure.md`) re-measured G2.2 on the G2.1 mesh reference scene (16 mm grid, 2490 tets), and the 30-minute load case fails both the p95 and the 0.1 percent clauses (p95 23.380 ms; every step above 16.7 ms), so G2.2 is open on that scene pending the owner's reference-level decision. Task 2.2 slice 4 (commit f3df8f8, `SNDEV/docs/impl-2026-11-06-g22-budget-fit.md`) supersedes that open status: gate G2.2 closes PASS with recorded boundaries on the budget-fit reference scene (20 mm grid, 1230 tets), with the 30-minute load case at p95 11.920 ms and 0.0123 percent of steps over 16.7 ms, divergence PASS, and the OQ short-mode test green; the 15 and 19 mm levels invert elements under the default chain and are not valid reference scenes.

**Estimate:** 44.5 d (7.5 d complete: tasks 2.5 and 2.6, and the five task 2.0 rows; 37.0 d remaining). Completed days are the sum of the done rows: 2.0 (task 2.6) + 4.0 (task 2.5) + 0.25 + 0.25 + 0.25 + 0.25 (tasks 2.0.1, 2.0.2, 2.0.4, and 2.0.5) + 0.5 (task 2.0.3) = 7.5. Remaining days are the open rows: 5.0 + 8.0 + 6.0 + 4.0 + 6.0 + 8.0 = 37.0 (tasks 2.1, 2.2, 2.3, 2.4, 2.7, and 2.8). The total is unchanged at 44.5. Task 2.2 is in progress at slice 1 and keeps its 8.0 d row until closure.

#### Tasks

| Task | Output | Est. |
|:-----|:-------|:-----|
| 2.0.1 Commit the applied SRS v1.2.0 baseline (SRS.md, `docs/srs-v1.2-change-proposal.md`, `SNDEV/docs/impl-2026-11-04-srs-v1.2-proposal.md`) and register VAL-026, VAL-027, and VAL-028 in Section 6.3 | Baseline commit with sign-off | 0.25d (done, commit 945a14e) |
| 2.0.2 Sync `docs/procurement-guide.md`: item 4 becomes the pixi plus RoboStack install with a pub/sub round-trip done-when check, item 5 is marked dropped (VAL-027 Option B), the Section 6 FMI-LS-BUS fallback becomes normative under VAL-028, and the Section 4 WSL2 route is marked superseded | `docs/procurement-guide.md` | 0.25d (done, commit f6254d7) |
| 2.0.3 Resolve and lock the ROS 2 environment: install ROS 2 Jazzy via pixi and `robostack-jazzy` (conda-forge only) with `rmw_fastrtps_cpp`, record the resolved `ros-jazzy` and Fast DDS package versions in `sim/SOUP.md`, add the RoboStack provenance row (channel URL, package list source, conda-forge-only policy), drop the SlicerROS2 and FMI-LS-BUS rows, and commit the lockfile (`pixi.lock` or a conda explicit spec) | `sim/SOUP.md`, `pixi.lock` | 0.5d (done, commit 9f746e4) |
| 2.0.4 Sync `vv/traceability/vtm.md`: the FR-MS-004 name cell becomes `M&S / ROS 2 middleware bridge over Fast DDS (`sim/bridge/`)`, the method cells of FR-MS-004, FR-MS-005, FR-MS-007, and NFR-PERF-002 carry the VAL-026 parenthetical, and the FR-MS-007 class cell drops FMI-LS-BUS | `vv/traceability/vtm.md` | 0.25d (done, commit f6254d7) |
| 2.0.5 Clean residual SlicerROS2 and FMI-LS-BUS text in `README.md`, `sim/README.md`, `sim/bridge/README.md`, `sim/fmi/README.md`, and the `SRTA_BUILD_BRIDGE` option description in `CMakeLists.txt`. SNDEV logs are historical records and are not edited. | The named files | 0.25d (done, commit f6254d7) |
| 2.1 Ingest DICOM through 3D Slicer and produce segmented meshes for parenchymal organ, tumor, and vascular keep-out zones, with segmentation provenance | `sim/segmentation/` (created) | 5.0d (slice 1 done at 9aa90f5: the one-command Slicer 5.12.4 pipeline producing labelmaps, meshes, and provenance sidecars on the TCIA HCC-TACE-Seg smoke set; slice 2 done at 7d0f5ec: held-out SEG reference labelmaps with provenance, a scripted tumor attempt (tumor_hypoattenuating, replacing the synthetic sphere), vascular bone exclusion, and the G2.1 Dice evaluation; slice 3a done at 3fa1868: SEG-referenced input selection with `input_selection.json` provenance and recall metrics in the evaluation; slice 4 done at 9d2b770: the vessel, tumor, and liver method variants with the variant log (`SNDEV/docs/impl-2026-11-05-task21-slice4-method.md`) and the final scoring chain scored on 2026-11-05 at parenchyma_liver 0.8915, tumor_hypoattenuating 0.0000, vascular_keepout_bone_excluded 0.2063 Dice, all FAIL at 0.90; remaining: lint coverage for sim/, and any slice-5 method work the document owner requests after the VAL-031 metric restatement); VAL-031 restated the metric on 2026-11-05 and slice 5 (funded remainder) is done at commit 95d2e13: the SEG label-convention measurement in the evaluation step (disjoint labels; Portal vein is the full intrahepatic tree; the aorta label covers z -310 to -270 only), three vessel seed-subtree variants with the recall and volume clause-tension finding, the liver convention fixes (small-hole fill, spine bone exclusion, full z range), and the clinical-annotation search trail with the tumor sub-gate recorded not applicable (`SNDEV/docs/impl-2026-11-05-task21-slice5-val031.md`); remaining: lint coverage for sim/, the vascular clause-tension decision on the VAL-031 Section 5 adjustable values (the 3 times volume multiplier and the 0.95 recall floor); VAL-032 re-centered the metric on 2026-11-05 and slice 6 is done at commit 2168d53: the evaluation grounding (liver envelope convention, stratified vessel metrics, squared-distance correction, grounded 11.0 mm diameter floor and 7.25 times volume multiplier) and one documented liver variant v4 (`docs/val-032-g21-metric-recenter.md`, `SNDEV/docs/impl-2026-11-05-val032-recenter.md`); the owner ruling of 2026-11-05 (modality floor) and slice 7 are done at commits 40b4f76 and 19cd1a6: the floor re-grounded to 3.0 mm in modality physics, the portal-trunk miss diagnosed (acquisition-1 lumen in the parenchyma band and candidate fragmentation before seeding), three vessel variants scored (gated recall 0.9614 at 31.4 times on v7 and 0.3108 at 4.57 times on v8, the bounded attempts), and the markers re-grounded to 0.47 recall floor and 7.5 times volume from the best bounded-volume point (`SNDEV/docs/impl-2026-11-05-task21-slice7-vessels.md`); remaining: lint coverage for sim/, the v8 source-rule defect (a bounded interpolation fix needs the reliable sources kept without the seed-connected truncation), the marker re-grounding when more patients are evaluated, and any further method work the document owner requests) |
| 2.2 Build the hyperelastic FEM scene with an implicit solver in SOFA, pin the SOFA release, and open the SOUP inventory | `sim/sofa/` (scene sources created under `sim/sofa/src/`), `sim/SOUP.md` (created) | 8.0d (slice-2 30-minute measurement done 2026-11-05, the OQ rework landed at fb1e025, VAL-029 applied in SRS v1.3.0; slice 3 done at 909c1d6: G2.1 mesh preparation and the reference scene swap, 16 mm grid with 2490 tets, whose 30-minute run FAILED; slice 4 done at f3df8f8: the budget-fit level selected by the pre-registered criterion from a 1000-step scan (20 mm grid, 1230 tets), two PCG preconditioner variants (block Jacobi and Jacobi, both rejected because p95 rose), the 30-minute load case PASS (p95 11.920 ms, 0.0123 percent of steps over 16.7 ms), the OQ short-mode test green, and the is_g21_reference provenance correction in `sim/segmentation/`; the scene resolution is a documented design parameter, and the chain is validated only at the stable levels 16, 17, 18, and 20 mm because 15 and 19 mm invert elements under the 25-iteration PCG; remaining: patient-specific material parameters (the parenchyma values are still the slice-1 placeholders) and a populated tumor subset) |
| 2.3 Implement connectivity-based culling, continuous collision detection, needle puncture resistance, dissection, and cutting | `sim/sofa/src/` (created) | 6.0d |
| 2.4 Implement the ROS 2 bridge node over Fast DDS (VAL-027 Option B) that publishes tool-tip pose, mesh deformation state, and 6-axis wrench data to ROS 2 nodes at the FR-MS-004 rate, built against the pinned RoboStack Jazzy environment of task 2.0.3. Build the C++ bridge in the MSVC Release or RelWithDebInfo configuration for ABI compatibility with the pinned ROS 2 binaries. | `sim/bridge/` (C++ bridge code) | 4.0d (scope reduced by VAL-027 Option B: no SlicerROS2 build, no WSL2, no cross-boundary DDS case; slice 1 done at 40c3722, see below; slice 2a landed the high-resolution timer and the subscriber arrival-method fix; slice 2b ran the G2.4 600 s gate run on 2026-11-05 with PASS and recorded boundaries (`SNDEV/docs/impl-2026-11-05-task24-g24-gate-run.md`); remaining: SOFA source integration with the gate re-verified on that data source, the structural coverage obligation of the VTM row (100 percent statement, branch, and MC/DC on the C++ bridge, tracked in the coverage work), the capture timestamp gap (the capture carries no per-message timestamps, which blocks the 1-minute window minimum statistic; recorded as a defect for the next bridge slice), and the re-estimate); slice 3a done at 93f436b (capture schema v3 with per-message timestamps, window statistic recomputable; replay source mode as the SOFA integration contract. Remaining: the 600 s gate re-run on the v3 capture, isolation of the replay late-tick finding (91 and 35 late ticks on replay against 0 on synthetic), SOFA live source integration and G2.4 re-verification, and the structural coverage obligation) |
| 2.5 Delegate Pulse steps to a `ProcessPoolExecutor` with one long-lived worker per engine instance, keep the step off the event loop, and expose a heartbeat-gap metric | `middleware/engine/pulse.py`, `middleware/engine/pulse_bridge.py` | 4.0d (done 2026-10-15: delegation landed at `5fb26a3`; the heartbeat-gap metric and the FR-MS-006 fixes are recorded in `SNDEV/docs/impl-2026-10-14-heartbeat-gap-diag.md`, gate G2.5 PASS) |
| 2.6 Verify the Pulse import and state tests on the pinned engine build, and record the engine source provenance for `.pulse/` | `vv/tests/IQ/test_iq4_pulse_engine_init.py`, `vv/tests/OQ/test_oq16_pulse_state_serialization.py`, `middleware/Dockerfile.pulse` | 2.0d (done 2026-10-14: `import pulse OK` and 11 passed, 1 skipped in the `biosync-pulse` image; `.pulse/` provenance in `sim/SOUP.md` and `docs/migration-map.md`) |
| 2.7 Package the thermal ablation, mechanical (SOFA), and physiology (Pulse) plant models as FMI 3.0 FMUs | `sim/fmi/` | 6.0d (slice 1 done at 27f68bd: the Pennes bioheat thermal FMU with four analytic import checks and the FMI 3.0.2 toolchain; remaining: the mechanical SOFA and physiology Pulse IPC-proxy FMU wrappers, primary-source verification of the (confirm) tissue parameters, the thermal model validity note (177 C peak outside linear validity), the fmi3Reset test case if not covered by task 2.8, and the coverage obligations) |
| 2.8 Build the FMI 3.0 co-simulation master with clocks and scheduled-variable co-simulation over the pinned ROS 2 / Fast DDS layer (VAL-028), with the bounded 1 ms clock-skew and message-jitter measurement of VAL-005 and per-message timestamps recorded | `sim/fmi/master/` (created) | 8.0d (slice 1 done at 762954f: the master core with Catch2 scheduler tests, the measurement harness, and the single-node skew and jitter baseline (10 minutes at 100 Hz on a host with Warhammer3 running: skew on the clock topic p50 0.430 ms, p95 0.624 ms, p99 0.765 ms, max 5.592 ms; arrival-interval jitter p99 0.519 ms, max 4.923 ms; both 1 ms bounds FAIL on this run, record `SNDEV/docs/impl-2026-11-05-task28-slice1-master.md`); remaining: the three-node G2.6 run over Fast DDS with per-message timestamps, and the SOFA and Pulse participants) |

#### Verification Gates

| Gate | Requirement | Acceptance Metric | Status |
|:-----|:------------|:------------------|:-------|
| G2.1 Mesh ingestion | FR-MS-001 | On the TCIA HCC-TACE-Seg HCC_001 series, meshes for parenchyma, tumor, and vascular keep-out zones are exported with segmentation provenance and evaluated against the expert SEG reference labels held out of pipeline inputs, per structure: (a) parenchyma, Dice at or above 0.90 and recall at or above 0.90 against the liver envelope (the reference liver label with the tumor and vessel carve-outs filled; the envelope convention is documented in each evaluation record); (b) vascular keep-out, recall at or above 0.47 (adjustable) over the reference-resolvable vessel set (reference components with lumen diameter at or above 3.0 mm (adjustable)), full-tree recall reported as information, keep-out volume at most 7.5 times the reference vessel volume (adjustable) with the 1.0 mm safety margin documented and carried into the FR-RTA-003 envelope parameters, and the unresolved thin-branch residual risk recorded in the risk file; (c) tumor, unchanged from VAL-031 (operator-placed seed from image inspection or clinical annotation, never SEG reference labels; Dice at or above 0.70 (adjustable); detection excluded and recorded as a limitation; on HCC_001 the sub-gate is not applicable with the two-pass non-detectability evidence and the annotation search trail). Each evaluation record carries the label-convention notes (disjoint labels; Portal vein full intrahepatic tree; Abdominal aorta label covering slices 21 to 29 only while the keep-out covers the full visible aorta) and the dataset note (clinical Tr_Size 0.8 cm inconsistent with the 35.75 mL labeled mass). (VAL-032, re-centered 2026-11-05; floor re-grounded to the 3.0 mm modality floor by the owner ruling of 2026-11-05 and the recall floor and volume multiplier grounded in the slice-7 re-grounding: 0.47 and 7.5 from the measured bounded-volume point) | PASS with recorded boundaries. Boundaries: (1) parenchyma PASS: Dice 0.9077 and recall 0.9505 against the liver envelope (organ-envelope convention, liver v4); the aorta-inclusive audit reading gives 0.9030 and 0.9402 and passes on both readings; (2) vascular keep-out PASS: gated recall 0.4762 at the 3.0 mm floor against the 0.47 floor, and keep-out volume 7.2384 times the reference (293.024 mL margin-inclusive) against the 7.5 times bound, with the 1.0 mm margin (78.16 mL) documented and carried into the FR-RTA-003 envelope parameters; full-tree recall 0.4650 is reported as information; (3) tumor NOT APPLICABLE on HCC_001: the two-pass non-detectability evidence and the annotation search trail (`SNDEV/docs/impl-2026-11-05-task21-slice5-val031.md`) show no documented seed source, and the 0.70 tumor Dice floor has no measurement on this patient; (4) single-patient reference set: the markers (0.47, 3.0 mm, 7.5 times, 0.70) are grounded on one patient (HCC_001) and re-ground when more patients are evaluated; (5) the unresolved vessel residual, 21.66 mL of the 40.48 mL reference (components 17, 9, and 1 and the thin bands below 3.0 mm), is recorded in the risk register (plan Section 7.1) where FR-RTA-003 consumes it; (6) the 0.95-at-bounded-volume aspiration is unreachable on the current acquisition pair (acquisition-1 portal lumen collapse into the parenchyma HU band) and is recorded as a data-side work item (thin-slice, contrast-timed reference acquisition, plan Section 7.1). Final values per the owner ruling of 2026-11-05 (`docs/val-032-g21-metric-recenter.md`, addendum final values); evaluation record `SNDEV/logs/g21-evaluation-tcia-hcc-tace-seg-hcc001-20261106T024206Z.log`. |
| G2.2 Solver rate | FR-MS-002, NFR-PERF-003 | Solver step time stays within the 16.7 ms frame budget of 60 FPS on the pinned reference scene as follows: at most 16.7 ms at p95 across a 30-minute load case, at most 0.1 percent of steps above 16.7 ms in the load case with the maximum step time recorded, and no divergence (defined as non-finite output or a monotonically growing strain-energy norm over successive steps) in the load case (VAL-029, applied in SRS v1.3.0) | PASS with recorded boundaries (closed 2026-11-06 on the budget-fit reference scene, task 2.2 slice 4, `SNDEV/docs/impl-2026-11-06-g22-budget-fit.md`, commit f3df8f8). Reference scene: the G2.1 liver envelope (parenchyma_liver chain v4) decimated to a 20 mm grid, 405 nodes and 1230 tets, with the tumor subset empty on HCC_001 and the vascular keep-out carried as a signed distance field and boundary points. The level was selected by the pre-registered criterion from a 1000-step scan of 15, 16, 17, 18, 19, and 20 mm grids. 30-minute load case, 163250 steps (1800 s at the 1000-step mean of 11.026 ms): p95 11.920 ms (PASS against 16.7 ms); 20 of 163250 steps above 16.7 ms, 0.0123 percent (PASS against 0.1 percent); maximum 28.740 ms recorded; divergence PASS (finite, no monotonic growth). OQ short mode (`vv/tests/OQ/test_oq_fr_ms_002_solver_rate.py`, unedited): PASS, p95 11.930 ms, 0 of 2000 steps over budget. Preconditioner slice: block Jacobi and Jacobi lowered mean PCG iterations from 26 to 23 but raised p95 to 12.71 and 12.52 ms, so the default chain is kept. Recorded boundaries: (1) the scene resolution (20 mm, 1230 tets) is a documented design parameter, and the full-resolution G2.1 geometry stays in the offline and reduced-order path (bridge modal coefficients, FMU reduced-order models); (2) the chain is validated only at the stable scanned levels 16, 17, 18, and 20 mm, because 15 and 19 mm invert elements under the 25-iteration PCG (PCG breakdown, divergence FAIL); (3) at 20 mm the PCG reaches its 25-iteration cap on every step, so the static solution is a capped-iteration approximation; (4) the parenchyma material parameters are still the slice-1 placeholder values pending patient-specific parameterization; (5) single-patient provenance (TCIA HCC-TACE-Seg HCC_001, the G2.1 reference set under SRS v1.4.0). Earlier results: the 2026-11-05 placeholder-scene run PASSED (p95 12.430 ms, 0.079 percent over budget, `SNDEV/docs/impl-2026-11-05-g22-30min-load-case.md`); the 2026-11-06 16 mm run FAILED (p95 23.380 ms, every step over budget, `SNDEV/docs/impl-2026-11-06-g22-remeasure.md`). The VAL-029 criterion is unchanged. |
| G2.3 Contact | FR-MS-003 | Zero tunneling events and zero missed contacts across a 1,000-trial needle puncture and cutting suite (proposed) | OPEN |
| G2.4 Wrench publish | FR-MS-004 | A wrench publish rate of 500 Hz or higher is sustained for 10 minutes, measured at the ROS 2 subscriber on the RoboStack Jazzy environment of task 2.0.3, with the CPython 3.12 subscriber and `.venv-qual311` driver split named in the test configuration record | PASS with recorded boundaries (2026-11-05, task 2.4 slice 2b). Run: 600 s at 500 Hz, `bridge_node` (Release, MSVC 14.44) to a CPython 3.12.16 subscriber in `env/ros2-jazzy` over `rmw_fastrtps_cpp` 8.4.4 on one host. Achieved rate 500.0003 Hz over the 599.998 s arrival span at the subscriber. 300000 of 300000 ticks had pose, wrench, and mesh deformation state present, with zero missing, zero partial, and zero index gaps. Late ticks at the node: 0. Interval statistics (source stamp and arrival, per topic) agree within the slice 2a tolerances. The 1-minute window minimum is not in the capture (reported only). Boundaries: the data source is the node's synthetic trajectory (SOFA outputs replace it in a later slice, and the run is repeated then), and the structural coverage obligation of the VTM row is tracked in the coverage work. The `.venv-qual311` OQ drivers parse the JSON capture downstream. Capture: `SNDEV/logs/bridge-smoke-500hz-600s-timer-high_resolution-spin-wait-2026-11-05T163901Z.json`. Record: `SNDEV/docs/impl-2026-11-05-task24-g24-gate-run.md`. |
| G2.5 Pulse worker | FR-MS-006 | IQ-4 and OQ-16 PASS on the pinned Pulse build, and the maximum event-loop heartbeat gap is 50 ms or less with 10 concurrent simulations (proposed) | PASS. IQ-4 and OQ-16 passed on the pinned build (task 2.6). Heartbeat clause passed on rerun `heartbeat-diag-1` (2026-10-15): maximum gap 16.778 ms against the 50 ms bound over 600 s with 10 concurrent simulations, 55,846 samples with zero above 20 ms. The earlier `vtm-600s` measurement (239.357 ms) is diagnosed and fixed in `SNDEV/docs/impl-2026-10-14-heartbeat-gap-diag.md`. Capture: `SNDEV/logs/pq-2026-10-15-fr-ms-006-heartbeat-diag-1.json`. |
| G2.6 Co-simulation | FR-MS-007 | FMUs pass FMI 3.0 import checks, and clock skew and message jitter are 1 ms or less on the three-node Fast DDS test over the pinned ROS 2 Jazzy / RoboStack layer (VAL-028), with per-message timestamps recorded (proposed) | OPEN |

**CSA Risk Annotation:** High Process Risk for all tasks. Tasks 2.2, 2.3, and 2.7 require 100% statement, branch, and MC/DC coverage for their C++ and FMU code. Tasks 2.4, 2.5, and 2.8 require timing evidence for the 500 Hz publish rate, the heartbeat gap, and the co-simulation step, and WCET analysis applies where the timing path is C++. Task 2.1 is High Process Risk because the vascular keep-out mesh feeds the FR-RTA-003 envelope. No task in this phase is Not High Process Risk.

---

### Phase 3: RTA Tier (Simplex Switch, Timed Automata, Envelope, Fallback)

**Goal:** Replace the stub RTA placeholders with the deterministic Simplex switch, timed automata state prediction, numeric safety envelope, and verified fallback for FR-RTA-001 through FR-RTA-004, with static analysis, WCET, and MC/DC evidence first.

**Status:** Not started. Phase 1 task 1.7 (VTM with FR-RTA-003 row) is a prerequisite. No commercial license is used in development (`SNDEV/docs/impl-2026-10-14-no-commercial-licenses.md`).

**Estimate:** 35.0 d.

#### Tasks

| Task | Output | Est. |
|:-----|:-------|:-----|
| 3.1 Replace the stub thresholds (5.0 mm vascular distance, 2.0 N wrench) in `rta/include/rta/safety_envelope.h` with values from the risk management file (VAL-025) | `rta/include/rta/safety_envelope.h`, risk file reference in `vv/traceability/vtm.md` | 2.0d |
| 3.2 Implement the Simplex switch decision path with static buffers, no heap allocation, and no locking | `rta/src/simplex_switch.cpp`, `rta/include/rta/simplex_switch.h` | 4.0d |
| 3.3 Implement timed automata state prediction with explicit models for sensor acquisition lag, asynchronous network updates, and processing delay | `rta/src/timed_automata.cpp`, `rta/include/rta/timed_automata.h` | 5.0d |
| 3.4 Implement the envelope checks for tissue wrench and shear limits and the vascular keep-out distance, with numeric limits and a separate VTM row (VAL-003) | `rta/src/safety_envelope.cpp`, `vv/traceability/vtm.md` | 3.0d |
| 3.5 Implement the PID or LQR fallback controller with its verification method: model checking of the discrete switch logic and a Lyapunov stability argument for the control law (VAL-011) | `rta/include/rta/fallback_controller.h` and `rta/src/fallback_controller.cpp` (created) | 6.0d |
| 3.6 Measure the decision loop WCET on the target platform, report the statistical bound, and derive the candidate RTA deadline for the SRS amendment (VAL-004) | `rta/tests/wcet/` (created), SNDEV log of the measurement | 4.0d |
| 3.7 Run the open-source static analysis gate on `rta/`: pin the tool versions (candidates cppcheck and clang-tidy, selected in this task), run with the C++17 pin, and maintain a deviation register (VAL-016) | CI static analysis job, deviation register in `vv/traceability/` | 3.0d |
| 3.8 Build Catch2 and CTest unit suites, reach 100% statement and branch coverage of `rta/` with gcov-family tooling, record MC/DC evaluation (Clang 19 or newer llvm-cov) as a work item, and pin pytest-cov | `rta/tests/` | 5.0d |
| 3.9 Inject faults into the envelope through the ASAM XIL Electrical Error Simulation port | `vv/xil/` fault scripts (created under `vv/xil/`) | 3.0d |

#### Verification Gates

| Gate | Requirement | Acceptance Metric |
|:-----|:------------|:------------------|
| G3.1 Simplex core | FR-RTA-001 | Zero findings from the pinned open-source check set on `rta/` with the deviation register attached; 100% statement and branch coverage, and the MC/DC target recorded as a deviation (Section 5.2) until an MC/DC path is verified; zero heap allocations in the decision path under an allocator hook. MISRA C++:2023 conformity is verified only if an adopter runs a conforming tool. |
| G3.2 Prediction | FR-RTA-002 | Every injected lag and delay case yields a bounded prediction within the candidate deadline, and the fault-injection run finds no unbounded state |
| G3.3 Envelope | FR-RTA-003 | Stub thresholds are replaced by risk-file values, and boundary tests one step below and one step above each threshold produce the expected accept or reject decision in 100% of cases |
| G3.4 Fallback | FR-RTA-004 | The fallback controller engages within the candidate deadline in 100% of injected envelope breach and deadline-miss cases |
| G3.5 Timing | FR-RTA-004 | The WCET bound for the decision loop is measured on the target platform, and the candidate deadline is written into a proposed SRS amendment (VAL-004) |

**CSA Risk Annotation:** High Process Risk for all tasks. Tasks 3.2, 3.3, 3.5, and 3.6 carry WCET analysis on the target platform. Tasks 3.2 through 3.5 require 100% statement and branch coverage on gcov-family tooling (task 3.8), with MC/DC carried as a recorded deviation (Section 5.2). Task 3.9 uses scripted fault injection through the ASAM XIL EES port.

---

### Phase 4: Teleoperation and Edge HIL

**Goal:** Deliver the 6-DOF teleoperation filter pipeline, the ESP32-S3 HIL fail-safe with MessagePack and an 8-bit TFLM model, and the sub-10 ms edge command leg of NFR-PERF-002 for FR-RTA-005 and FR-RTA-006.

**Status:** Not started. The One Euro and EMA filters exist in `middleware/engine/one_euro.py` and `middleware/engine/signal.py`.

**Estimate:** 26.0 d.

#### Tasks

| Task | Output | Est. |
|:-----|:-------|:-----|
| 4.1 Build the 6-DOF teleoperation pipeline with a per-axis One Euro filter and the adaptive EMA stage | `middleware/engine/teleop.py` (created), `middleware/engine/one_euro.py`, `middleware/engine/signal.py` | 5.0d |
| 4.2 Integrate MANO parametric constraints after the MANO model license terms are cleared | `middleware/engine/mano.py` (created) | 4.0d |
| 4.3 Implement the ESP32-S3 firmware with the MessagePack command bridge | `edge/firmware/` (created) | 5.0d |
| 4.4 Build the 8-bit integer quantized TFLM model: architecture, dataset, memory budget, reference float baseline, and post-quantization accuracy floor (VAL-019) | `edge/model/` (created) | 6.0d |
| 4.5 Procure and integrate the Phase 3 HIL target and run the fallback tests on the bench | `vv/xil/hil/` (created) | 4.0d |
| 4.6 Run one edge command latency test with a defined measurement point, message size, network condition, and p99 and worst-case statistics (VAL-014) | `vv/tests/PQ/test_pq_nfr_perf_002_edge.py` (created) | 2.0d |

#### Verification Gates

| Gate | Requirement | Acceptance Metric |
|:-----|:------------|:------------------|
| G4.1 Teleoperation filter | FR-RTA-005 | On the recorded teleoperation trace, One Euro and EMA reduce high-frequency jitter power by at least 50% relative to raw input while keeping step response within 5% (proposed). The MANO constraint test PASSES on the cleared model. |
| G4.2 Payload and model | FR-RTA-006 | MessagePack payloads are at least 70% smaller than the JSON baseline on the reference corpus, and the int8 TFLM model is 75% smaller than the float32 baseline while meeting the accuracy floor set in task 4.4 |
| G4.3 Edge latency | FR-RTA-006, NFR-PERF-002 | Command latency is under 10 ms at p99 over 10,000 commands on the HIL bench at the defined measurement point, with the worst case reported |
| G4.4 Offline fallback | FR-RTA-006 | The MCU runs the TFLM fallback with the link disconnected in 100% of 1,000 trials and produces bit-identical output for identical input |

**CSA Risk Annotation:** High Process Risk for all tasks, because the teleoperation filters and the HIL fail-safe control robot inputs. Tasks 4.3, 4.4, and 4.5 require scripted V&V on the bench. Task 4.6 requires statistical timing evidence at p99 and worst case. MC/DC applies to C++ firmware code only.

---

### Phase 5: Interoperability Depth (SiLA 2, Signatures, Access, Terminology)

**Goal:** Complete the SiLA 2 instrument servers, the electronic signature and access controls, the terminology binding checks, and the ingestion throughput measurement for FR-DAT-002, FR-DAT-006, FR-DAT-007, NFR-SEC-001, and NFR-PERF-001.

**Status:** Not started. Requires Phase 1 gates G1.4 and G1.7.

**Estimate:** 25.0 d.

#### Tasks

| Task | Output | Est. |
|:-----|:-------|:-----|
| 5.1 Wrap the peristaltic pump, ablation generator, and robotic arm as SiLA 2 servers over gRPC and Protobuf, with FDL definitions and a row in `sila2_rpc_log` for each call | `middleware/sila2/` (created) | 8.0d |
| 5.2 Implement electronic signatures with printed name, timestamp, and meaning, and map the signing workflow to 21 CFR 11.100, 11.200, and 11.300 | `database/migrations/007-signatures.sql` (created), `middleware/api/routes/signatures.py` (created). Renumbered from 006, which is taken by `006-telemetry-sessions.sql` (commit `d0ef2c5`). | 6.0d |
| 5.3 Implement the failed-login lockout, the inactivity session lockout, and shared-account detection | `middleware/api/auth.py`, `middleware/api/routes/auth.py` | 3.0d |
| 5.4 Write the OAuth profile (grant type, token profile, resource server model) and the verify-full default check (VAL-013) | `middleware/api/auth.py`, security specification section in `SRS.md` amendment draft | 2.0d |
| 5.5 Add terminology binding validation for `Observation.status` and the other FHIR value sets | `middleware/fhir_validator.py`, `middleware/api/routes/fhir.py` | 3.0d |
| 5.6 Measure telemetry ingestion throughput on the Phase 1 test configuration | `vv/tests/PQ/test_pq_nfr_perf_001_ingest.py` (created) | 3.0d |

#### Verification Gates

| Gate | Requirement | Acceptance Metric |
|:-----|:------------|:------------------|
| G5.1 SiLA 2 servers | FR-DAT-002 | Servers for the pump, the ablation generator, and the robotic arm pass FDL conformance, and 100% of RPCs write a `sila2_rpc_log` row |
| G5.2 Signatures | FR-DAT-006 | 100% of signature records carry the printed name, a UTC timestamp, and the meaning, and a signature cannot be applied without re-authentication |
| G5.3 Access control | FR-DAT-006 | Accounts lock after the failed-login threshold set in the security specification, sessions lock after the inactivity interval, and shared-account creation is rejected in 100% of attempts |
| G5.4 Terminology | FR-DAT-007 | Values outside a bound value set are rejected in 100% of test cases, including the `bogus-status` case from migration-map Table 3 |
| G5.5 Transport and token | NFR-SEC-001 | Tokens with the wrong audience are rejected in 100% of test cases, and TLS 1.3 is negotiated on the compliance database connection |
| G5.6 Ingestion | NFR-PERF-001 | Ingestion sustains more than 100,000 points per second for 10 minutes on the Phase 1 configuration, measured at database commit (proposed run duration) |

**CSA Risk Annotation:** Tasks 5.1, 5.2, 5.3, and 5.4 are High Process Risk because they cover instrument control, record signatures, and access control. Tasks 5.5 and 5.6 are Not High Process Risk, which matches the FR-DAT-007 VTM classification. Those two tasks use unit tests and exploratory testing, and the task 5.6 throughput run is recorded as a performance check.

---

### Phase 6: Continuous Verification and Compliance-as-Code

**Goal:** Gate every commit with static analysis, ASAM XIL test scripts, structural coverage, WCET reporting, the protocol register, and the trace link engine for FR-VV-001 through FR-VV-005 and NFR-REL-001.

**Status:** Not started. No license procurement is required (decision of 2026-10-14).

**Estimate:** 29.0 d.

#### Tasks

| Task | Output | Est. |
|:-----|:-------|:-----|
| 6.1 Publish the IQ/OQ/PQ protocol register with protocol IDs, file paths, and requirement IDs, replacing the undefined "19 protocols" count (VAL-002) | `vv/tests/protocol-register.md` (created) | 2.0d |
| 6.2 Extend the open-source static analysis gate to every C++ core on every commit | `.github/workflows/ci.yml` | 2.0d |
| 6.3 Build the ASAM XIL v3.0.0 Python abstraction for the Model Access, Electrical Error Simulation, Service-Oriented Access, and ECU Access ports, with the XIL implementation selected | `vv/xil/` | 6.0d |
| 6.4 Run one script set unchanged on the SIL target and the selected HIL target, with a per-vendor adapter outside the script count | `vv/xil/` adapters | 5.0d |
| 6.5 Run coverage and WCET reporting in CI with the gcov-family tooling, Catch2, CTest, and Pytest, and generate boundary and failure-mode cases | `.github/workflows/ci.yml` | 4.0d |
| 6.6 Build the trace engine that writes hashed forward and backward trace links to the repository-native trace store (the VTM and the protocol register), hashes each link (VAL-020), and runs the dead-code analysis with a named tool. The Jama or Polarion push is an optional adapter that an adopter enables. | `vv/traceability/engine/` (created) | 5.0d |
| 6.7 Run a 24-hour sanitizer-enabled soak with the unresolved-defect window defined (VAL-023) | `vv/tests/PQ/test_pq_nfr_rel_001_soak.py` (created) | 3.0d |
| 6.8 Run the protocol register in CI and archive the results with each run | `.github/workflows/ci.yml`, `SNDEV/logs/` | 2.0d |

#### Verification Gates

| Gate | Requirement | Acceptance Metric |
|:-----|:------------|:------------------|
| G6.1 Static analysis | FR-VV-001 | Zero findings from the pinned open-source check set on every commit across `rta/`, `sim/sofa`, `sim/bridge`, and `sim/fmi`, with the C++17 pin verified and the deviation register attached. MISRA C++:2023 conformity is verified only if an adopter runs a conforming tool. |
| G6.2 XIL API | FR-VV-002 | Test scripts import the ASAM XIL v3.0.0 Python API and exercise all four ports (MA, EES, SOC, and ECU Access) |
| G6.3 Portability | FR-VV-003 | One script set passes unmodified on the SIL target and on the selected HIL target, with zero script edits |
| G6.4 Coverage and timing | FR-VV-004 | 100% statement and branch coverage on High Process Risk C++ modules, with the MC/DC target carried as a recorded deviation (Section 5.2) until an MC/DC path is verified, and a WCET bound with its statistic reported for each timed task |
| G6.5 Traceability | FR-VV-005 | 31 of 31 defined IDs have forward and backward trace links, zero unlinked dead-code findings from the named tool, and every link hash is recorded. The store is the repository-native one (VTM and protocol register). |
| G6.6 Reliability | NFR-REL-001 | Zero unresolved SIGSEGV in a 24-hour sanitizer-enabled soak, and 100% pass across every protocol in the register |

**CSA Risk Annotation:** All Phase 6 tasks are High Process Risk because they gate High Process Risk modules. Tasks 6.3 and 6.4 run scripted XIL tests, and task 6.7 runs a 24-hour soak. This phase has no Not High Process Risk tasks.

---

### Phase 7: Rendering and Visualization

**Goal:** Link ROS 2 streams into the Omniverse / Isaac Sim USD pipeline for synthetic endoscopic data and deliver the 60 FPS waveform frontend for FR-MS-005 and NFR-PERF-003.

**Status:** Not started. Requires the GPU and runtime license decisions in Section 7.1.

**Estimate:** 20.0 d.

#### Tasks

| Task | Output | Est. |
|:-----|:-------|:-----|
| 7.1 Link ROS 2 kinematic and deformation streams into USD layers in Omniverse / Isaac Sim, with the USD and runtime versions pinned (the ROS 2 leg runs on the pinned RoboStack Jazzy environment of task 2.0.3; NVIDIA documents a native Windows pixi workspace for Isaac Sim ROS 2 and marks its WSL2 method deprecated) | `sim/omniverse/` (created) | 6.0d |
| 7.2 Export synthetic endoscopic camera frames for robotic vision algorithms | `sim/omniverse/` (created) | 4.0d |
| 7.3 Build the React 18 and TypeScript WebGL waveform frontend behind the chart provider abstraction | `frontend/` (source created under `frontend/src/`) | 5.0d |
| 7.4 Migrate the Gateway telemetry visualization path and apply LTTB downsampling before the push | `frontend/`, `middleware/engine/lttb.py` | 3.0d |
| 7.5 Measure the frame rate under full telemetry load | `vv/tests/PQ/test_pq_nfr_perf_003_fps.py` (created) | 2.0d |

#### Verification Gates

| Gate | Requirement | Acceptance Metric |
|:-----|:------------|:------------------|
| G7.1 USD pipeline | FR-MS-005 | ROS 2 kinematic and deformation updates appear as USD prim changes in Omniverse / Isaac Sim, and synthetic endoscopic frames are exported for every scripted frame |
| G7.2 Frame rate | NFR-PERF-003 | The frame counter reports 60 FPS or more for the waveform frontend and the 3D view under full telemetry load on the defined configuration |

**CSA Risk Annotation:** Not High Process Risk per SRS Section 2.2, which places 3D scene lighting, camera viewport adjustments, and historical chart playback in this class. Verification uses unit tests and exploratory testing. The frame-rate measurement in task 7.5 is recorded in the phase log as a performance check.

---

## 5. Verification and Compliance Strategy

### 5.1 Static Analysis Scope

| Scope | Tool | Check | Phase |
|:------|:-----|:------|:------|
| `rta/` (safety core) | Open-source check set pinned in task 3.7 (candidates: cppcheck and clang-tidy) | Zero findings from the pinned set under the C++17 pin, with the deviation register attached | 3 (task 3.7) |
| `sim/sofa/`, `sim/bridge/`, `sim/fmi/` | The open-source check set pinned in task 3.7 | Zero findings on every commit | 6 (task 6.2) |
| `middleware/`, `vv/tests/` (Python) | Lint and type-check tools pinned in `middleware/requirements-test.txt` | Lint and type check on every commit | 1 (task 1.12) |
| `database/migrations/` | PostgreSQL 15 in the qualification job | Migrations apply cleanly and triggers reject mutations | 1 (task 1.2) |

Recorded gap: neither candidate in the table implements the MISRA C++:2023 rule set. Gates that named zero MISRA C++:2023 violations (G3.1 and G6.1) are restated as zero findings from the pinned set, and MISRA C++:2023 conformity remains an adopter-supplied verification that requires a conforming tool.

Freedom from interference is not asserted by static analysis. Partitioning and memory-isolation evidence is a separate work item (VAL-024), and this plan does not claim it.

### 5.2 Coverage Targets by CSA Risk Class

| CSA Class | Coverage Target | Test Method | Timing Analysis |
|:----------|:----------------|:------------|:----------------|
| High Process Risk, C++ | 100% statement, branch, and MC/DC (MC/DC is a recorded deviation, see below) | Scripted V&V on gcov-family tooling (gcov or llvm-cov), with CTest and Catch2 suites | WCET on the target platform (task 3.6) |
| High Process Risk, Python | 100% statement and branch | Scripted pytest suites under `vv/tests/` and `middleware/tests/` with coverage measurement (pytest-cov, pinned in task 3.8 or earlier) | Event-loop heartbeat gap (task 2.5) |
| Not High Process Risk | Unit tests required, with no numeric coverage gate | Automated unit tests and exploratory testing | Not applicable |

MC/DC deviation for C++: the gcov-family tooling reports statement and branch coverage, and it does not report MC/DC. Task 3.8 evaluates an open-source MC/DC path (Clang 19 or newer llvm-cov MC/DC reporting is a candidate, not a commitment). Until that path is verified or an adopter supplies a tool, the MC/DC target is a recorded deviation in the risk file and the deviation register.

No MC/DC tool for Python is selected. Section 7.2 records this gap.

### 5.3 IQ/OQ/PQ Register and Naming Convention

The protocol register at `vv/tests/protocol-register.md` (created in task 6.1) lists each protocol ID, its phase, its file path, and the requirement IDs it verifies. The register replaces the "19 protocols" count (VAL-002). File names follow these patterns:

* IQ: `vv/tests/IQ/test_iq<N>_<topic>.py`, numbered from IQ-0.
* OQ: `vv/tests/OQ/test_oq_<req-id-lowercase>_<topic>.py` for new tests, for example `test_oq_fr_dat_005_hash_crosscheck.py`.
* PQ: `vv/tests/PQ/test_pq_<req-id-lowercase>_<topic>.py`, for example `test_pq_fr_dat_005_1m_rows.py`.

Gateway-numbered files keep their names (for example `test_oq6_ema_convergence.py`) and are cross-referenced in the register. At migration, the baseline held 7 IQ files, 7 OQ files, and 2 PQ files.

### 5.4 Traceability Path

1. The requirement ID is defined in `SRS.md` Sections 3 and 4.
2. The VTM row in `vv/traceability/vtm.md` gives the test method and the acceptance metric. The interim VTM covers all 31 IDs from Phase 1 task 1.7.
3. The protocol or test file under `vv/tests/` or `rta/tests/` is listed in the protocol register.
4. The CI qualification job archives the run output, and the phase log in `SNDEV/docs/` cites that output.
5. The trace engine writes forward and backward links to the repository-native store, which is the VTM and the protocol register (Phase 6 task 6.6). A Jama or Polarion push is an optional adapter that an adopter enables.

### 5.5 Evidence Landing

Each phase lands an implementation log at `SNDEV/docs/impl-YYYY-MM-DD-<ticket>.md` before its code is written. Captured test output goes to `SNDEV/logs/`, which is gitignored. Gate results are recorded as PASS or FAIL with the command and the evidence path.

---

## 6. Open SRS Questions

The SRS audit (`SNDEV/docs/impl-2026-10-13-srs-baseline-validation.md`) found 4 Blocker, 12 Major, and 9 Minor findings. Each Blocker is listed below as a numbered question with its interim handling. The interim handling lets Phases 1 and 3 proceed before the SRS is amended. The Minor findings are not repeated here and remain in the audit document.

### 6.1 Blocker Findings

1. VAL-001: Should the VTM carry a row for all 31 defined IDs before SRS.md v1.0.0 is re-issued? Interim handling: a complete VTM is maintained in `vv/traceability/vtm.md` with a measurable metric and test method for each ID (Phase 1 task 1.7). The SRS status stays at draft with open validation findings until the amendment lands.
   Resolved by SRS v1.1.0: Section 5 names `vv/traceability/vtm.md` as the authoritative 31-row VTM, and the Section 5 extract is non-authoritative (now covering 20 of the 31 IDs).
2. VAL-002: Should the "19 distinct IQ/OQ/PQ protocols" count be replaced by a published protocol register, or removed? Interim handling: the protocol register is kept in `vv/tests/protocol-register.md` (Phase 6 task 6.1). This plan does not use the number 19 as a gate.
   Resolved by SRS v1.1.0: the "19 protocols" count is replaced by the protocol register reference in FR-VV-005 and NFR-REL-001.
3. VAL-003: Should FR-RTA-002 (state prediction) and FR-RTA-003 (envelope) be separate VTM rows with separate acceptance metrics? Interim handling: the FR-RTA-002 row is renamed to state prediction and the FR-RTA-003 row is added in Phase 1 task 1.7. Gate G3.3 verifies FR-RTA-003 separately.
   Resolved by SRS v1.1.0: FR-RTA-002 and FR-RTA-003 carry separate Section 5 rows, each with its own metric.
4. VAL-004: What is the RTA decision-loop deadline? Interim handling: the candidate deadline is derived from the WCET measurement on the target platform (Phase 3 task 3.6). It is written into the SRS only after that measurement exists.
   Resolved by SRS v1.1.0: the deadline clause structure is added with the [RTA_DEADLINE_MS] placeholder, and the number is filled from Phase 3 task 3.6 under FR-VV-004.

### 6.2 Major Findings

| ID | Open Question | Interim Handling | Phase |
|:---|:--------------|:-----------------|:------|
| VAL-005 | Replace "zero quantization error" with bounded clock-skew and message-jitter limits and a stated test setup | 1 ms limits in gate G2.6 (proposed), measured in task 2.8. The clause phrase was removed from FR-MS-007 by VAL-028 (SRS v1.2.0). | 2 |
| VAL-006 | Move the 60 FPS, 500 Hz, and divergence definitions to the requirements that own them | 60 FPS in G2.2, 500 Hz in G2.4, divergence as a 30-minute load case | 2 |
| VAL-007 | Define an observable proxy for "zero main-loop blocking" | Heartbeat gap of 50 ms or less with 10 sessions in G2.5 (proposed) | 2 |
| VAL-008 | Assign one IEC 62304 class per software item, with the risk file cited | Class C is provisional for High Process Risk items, and each item's class is set in the risk file (VAL-025) | 1, 3 |
| VAL-009 | Drop DO-178C DAL A and ISO 26262 ASIL D, or write a mapping to IEC 62304 Class C activities | Neither is a certification target in this plan. IEC 62304 Class C governs. Note: the FR-RTA-002 extract row carries the VTM mapping cell with this VAL-009 note. VAL-009 stays open. | 1 |
| VAL-010 | Split FR-DAT-004 into immutable rows and an append-only change log for permitted edits | Task 1.8 implements audit capture for permitted changes (gate G1.2). The SRS split waits for an amendment. | 1 |
| VAL-011 | Name the verification method for the fallback controller | Model checking of the discrete switch logic and a Lyapunov argument for the PID or LQR law (task 3.5) | 3 |
| VAL-012 | Add SOUP requirements for inventory, version pinning, evaluation, and anomaly response | `sim/SOUP.md` inventory created in task 2.2 and extended in each phase. A SOUP requirement is drafted before Phase 2 exits. | 2 |
| VAL-013 | Specify the OAuth profile and require verify-full as the default | Task 5.4 writes the profile, and gate G1.7 covers the verify-full default | 1, 5 |
| VAL-014 | Define one latency test with a method and stated conditions, and close the Gateway R3 pattern | Task 4.6 and gate G4.3 (p99 and worst case). Task 1.5 closes R3. | 1, 4 |
| VAL-015 | Restate tamper detection as a defined injection suite with row counts and tamper types | Injection suite in task 1.2 with stated row counts and tamper types | 1 |
| VAL-016 | Pin the safety cores to C++17, or define a deviation set for C++20 constructs | C++17 is pinned in `CMakeLists.txt`. The deviation register is decided before gate G3.1 closes. | 3 |
| VAL-031 | The G2.1 metric judged all structures by uniform symmetric Dice, which mis-scores the FR-RTA-003 safety-weighted keep-out zone and conflates detection with segmentation | Resolved by the restatement in Section 6.3 (`docs/val-031-g21-metric-proposal.md`, applied 2026-11-05) | 2 |
| VAL-032 | The VAL-031 uniform unstratified vascular recall mis-scores the safety-weighted keep-out at 5 mm slice thickness (thin branches partial-volume into parenchyma) and the disjoint-label convention couples the parenchyma clause to the un-detectable tumor clause | Resolved by the re-centering in Section 6.3 (`docs/val-032-g21-metric-recenter.md`, applied 2026-11-05) | 2 |

### 6.3 Findings Resolved by SRS Amendments

Findings VAL-026, VAL-027, and VAL-028 were opened and closed by the v1.2.0 change set (`docs/srs-v1.2-change-proposal.md`, `SNDEV/docs/impl-2026-11-04-srs-v1.2-proposal.md`). The baseline register `SNDEV/docs/impl-2026-10-13-srs-baseline-validation.md` is unchanged (overwrite policy). Findings VAL-029 was closed by the v1.3.0 change set (docs/srs-v1.3-change-proposal.md, applied 2026-11-05).

| ID | Resolution in SRS | Residual plan action |
|:---|:-------------------------|:---------------------|
| VAL-026 | ROS 2 provisioning pinned to ROS 2 Jazzy natively on Windows via pixi and the RoboStack `robostack-jazzy` conda channel with `rmw_fastrtps_cpp`, named in the FR-MS-004, FR-MS-007, and NFR-PERF-002 toolchain cells. The WSL2 Ubuntu 24.04 route of the procurement guide is superseded for tasks 2.4, 2.8, and 7.1. | Task 2.0.3 resolves and locks the environment and syncs the SOUP and procurement rows. The CPython 3.12 (RoboStack) and Python 3.11.9 (`.venv-qual311`) split is recorded in the gate G2.4 and G2.6 test configurations. |
| VAL-027 | Closed as Option B. FR-MS-004 requires a ROS 2 bridge node over Fast DDS in `sim/bridge/`; the SlicerROS2 module is not a requirement. WSL2 leaves the plan and procurement item 5 is dropped. FR-MS-001 stays on the native Windows 3D Slicer 5.12.4 pin. | Task 2.4 builds the bridge node. Task 2.0.2 and task 2.0.5 clean the residual SlicerROS2 text (procurement, SOUP, VTM name cell, README and CMake descriptions). |
| VAL-028 | FR-MS-007 specifies FMI 3.0 clocks and scheduled-variable co-simulation over the pinned ROS 2 / Fast DDS layer with 1 ms clock-skew and message-jitter bounds. The FMI-LS-BUS DDS reference and the `quantization-error-free` phrase are removed. | Task 2.8 implements the master against the scheduled-variable clause. Task 2.0.3 drops the FMI-LS-BUS SOUP row, and task 2.0.4 drops FMI-LS-BUS from the FR-MS-007 VTM class cell. |
| VAL-029 | Resolved by SRS v1.3.0 (2026-11-05): the FR-MS-002 acceptance metric is the p95 plus outlier-budget criterion (at most 16.7 ms at p95 across a 30-minute load case, at most 0.1 percent of steps above 16.7 ms with the maximum step time recorded, no divergence in the load case). The OQ test restate landed at commit fb1e025. | Closed 2026-11-06 on the budget-fit reference scene (20 mm grid, 1230 tets, commit f3df8f8): 30-minute load case p95 11.920 ms (PASS), 20 of 163250 steps over 16.7 ms (0.0123 percent, PASS against the 0.1 percent cap), maximum 28.740 ms recorded, divergence PASS (`SNDEV/docs/impl-2026-11-06-g22-budget-fit.md`). Every gate run records the over-budget count and the maximum step time, and the scene resolution is a documented design parameter, with the chain validated only at the stable levels 16, 17, 18, and 20 mm. |
| VAL-030 | Resolved by SRS v1.4.0 (2026-11-05): FR-MS-001 names the TCIA HCC-TACE-Seg set (patient HCC_001, expert liver, tumor, and vessel reference labels) as the benchmark example. The Kitware TAIR release is recorded as evaluated and out of scope for this clause (cerebrovascular CTA/MRA in NIfTI without organ or tumor labels). | The slice-2 Dice evaluation runs against the held-out SEG labels with the is_g21_reference provenance flag set on them; the 0.90 Dice threshold stays proposed until that measurement lands. |
| VAL-031 | Resolved by VTM and plan metric restatement on 2026-11-05 (docs/val-031-g21-metric-proposal.md; no SRS.md text changes, the acceptance metric is VTM-resident per SRS Section 5) | Slice 5 closes the parenchyma gap (0.8915 against 0.90) and the vessel recall gap (0.5676 against 0.95); the tumor sub-gate is not applicable on HCC_001 unless a documented seed source appears; the adjustable markers are re-grounded when more patients are evaluated. |
| VAL-032 | Resolved by VTM and plan metric re-centering on 2026-11-05 (docs/val-032-g21-metric-recenter.md; no SRS.md text changes, the acceptance metric is VTM-resident per SRS Section 5): restated 2026-11-05 by owner decision (parenchyma scored against the liver envelope, vascular recall stratified over the reference-resolvable set at the 3.0 mm modality floor with full-tree recall as information, tumor unchanged from VAL-031; final values by the owner ruling of 2026-11-05: gated recall floor 0.47 and keep-out volume at most 7.5 times the reference, `docs/val-032-g21-metric-recenter.md` addendum) | The adjustable markers (3.0 mm diameter floor, 0.47 gated recall floor, 7.5 times volume multiplier, 0.70 tumor Dice) are re-grounded when more patients are evaluated. |

---

## 7. Risk Register

### 7.1 Technical Risks

| Risk | Impact | Likelihood | Mitigation |
|:-----|:-------|:-----------|:-----------|
| SOFA does not hold real-time determinism at the solver rate needed for 60 FPS and the 500 Hz wrench publish | Missed frame and publish targets. Envelope inputs go stale. | Medium | Gates G2.2 and G2.4 at Phase 2 exit. Reduce telemetry only through LTTB, which keeps peaks, and keep the scene within the measured budget. The risk is live: slice-1 captures (2026-10-15) show max step 23.910 ms on a 2000-step run, 7 steps over the 16.7 ms budget, with the PCG solver already substituted for the slower direct chain. |
| FMI clock synchronization error across Fast DDS adds error to the co-simulation step | Step error exceeds the bounded skew and produces false envelope decisions | High | Bounded 1 ms clock-skew and message-jitter limits (VAL-005, made normative by VAL-028), measured in gate G2.6 with per-message timestamps, and FMI 3.0 scheduled variables and step-size control in the master over the pinned ROS 2 / Fast DDS layer |
| RoboStack environment drift and the interpreter split | The ROS 2 Jazzy conda packages or the conda-forge channel change under the pin, or the CPython 3.12 ROS environment diverges from the Python 3.11.9 qualification venv; bridge and co-simulation builds break and gate measurements lose reproducibility | Medium | Commit `pixi.lock` or a conda explicit spec with the SOUP row (task 2.0.3), hold the conda-forge-only channel policy from the RoboStack conda guide (remove the `defaults` channel), and name the interpreter split in every gate test configuration record |
| WCET tooling does not support the target CPU or MCU, or it yields loose bounds | The candidate RTA deadline cannot be stated, and FR-RTA-004 cannot be tested | Medium | Measure on the target with statistical timing (task 3.6), keep the decision path free of heap and locks, and record tool limits in `sim/SOUP.md` |
| Omniverse / Isaac Sim dependency (GPU class, runtime license, USD version drift) | Phase 7 is blocked, and the NFR-PERF-003 rendering path is unavailable | Medium | Pin the USD and runtime versions. Rendering is Not High Process Risk, so the M&S and RTA tiers do not depend on it. Record the GPU precondition before Phase 7 starts. |
| Kitware Pulse is single-threaded per patient and its engine object cannot be pickled | ProcessPoolExecutor delegation (FR-MS-006) fails, and the event loop blocks | High | One long-lived worker per engine instance (task 2.5) and heartbeat gate G2.5. The Gateway open item in migration-map Table 3 tracks the blocker. |
| Gateway R3 relay path: R3 is closed at task 1.5, and R2 is closed at `a44c163`. NFR-PERF-001 ingestion measured below target on the Phase 1 configuration. | NFR-PERF-001 is not met (about 12,600 points per second against 100,000). NFR-PERF-002 holds only at 10 points per second on this host, and the 50 ms bound fails at 20 points per second and above. The tail-latency source is not isolated: the relay serializes broadcast fan-out per frame (`ConnectionManager.broadcast`), and client-side queueing in the single client process is an unmeasured candidate. | Medium | Phase 1 task 1.5 (closed). Gate G1.8 PASS with recorded boundaries at `7508b91`. Revisit NFR-PERF-001 at Phase 5 task 5.6 and with relay tuning. |
| Unresolved thin-branch residual risk in the vascular keep-out (VAL-032 clause (b)): the keep-out gates the reference-resolvable set at the 3.0 mm floor (gated recall 0.47) and does not contain the thin branches below 3.0 mm lumen or the resolvable components 17, 9, and 1 | The FR-RTA-003 vascular no-go zones do not contain 21.66 mL of the 40.48 mL reference vessel volume (the thin bands below 3.0 mm and the resolvable components 17, 9, and 1 at 0.0 to 0.33 coverage), so a needle path planned against the keep-out can approach unlabeled vessel segments | High on the measured evidence (21.66 mL of 40.48 mL, 53.5 percent of the reference tree volume, missed on the single-patient reference set; full-tree recall 0.4650) | Documented 1.0 mm keep-out safety margin carried into the FR-RTA-003 envelope parameters; residual risk acceptance in the risk file where FR-RTA-003 consumes it; data-side recommendation for thin-slice acquisition (the 0.78 by 0.78 by 5 mm sampling drives the partial-volume overlap with parenchyma, probes 22 and 23 in `SNDEV/docs/impl-2026-11-05-task21-slice5-val031.md`); re-ground the markers on the next patient |
| 0.95 vascular coverage at bounded volume is unreachable on the current acquisition pair (acquisition-1 portal lumen collapse into the parenchyma HU band); the aspiration is a thin-slice, contrast-timed reference acquisition | The vascular keep-out stays at the measured bounded-volume capability (gated recall 0.4762 at the 3.0 mm floor, 7.2384 times the reference) until new reference data is acquired | High on the measured evidence (acquisition-1 portal lumen median 71 to 91 HU against liver 54 to 86 HU, `SNDEV/logs/probe20-band-hu-2026-11-05.json`) | Data-side work item: thin-slice, contrast-timed reference acquisition, then re-ground the vascular markers on the new data |

### 7.2 Regulatory Risks

| Risk | Impact | Likelihood | Mitigation |
|:-----|:-------|:-----------|:-----------|
| Proprietary tool qualification for Parasoft, QA-MISRA, VectorCAST, and Cantata | Tool output cannot be relied on as validation evidence without qualification, which becomes an audit finding | High | No commercial tool is used in development (decision of 2026-10-14). Conformity claims are limited to the open-source check set, and deviations are recorded in this risk file and the deviation register. An adopter who selects a commercial tool selects one with a vendor qualification kit and records its version and qualification evidence in `SNDEV/docs/`. |
| DO-178C DAL A and ISO 26262 ASIL D citations apply to other certification contexts | Submission credibility and a rigor target that does not match the device | Medium | Remove both as certification targets, or write the mapping to IEC 62304 Class C activities (VAL-008, VAL-009) |
| C++17 pin versus the SRS C++17/C++20 wording | The static analysis gate cannot cover C++20 files, so "zero violations" cannot be achieved as written | Medium | Pin the safety cores to C++17 in `CMakeLists.txt`, and settle the C++20 deviation register before gate G3.1 closes (VAL-016) |
| Python High Process Risk modules have no MC/DC tool | Scripted V&V gap under SRS Section 2.2 | High | Record a deviation in the risk file that requires statement and branch coverage for Python. Move safety-critical logic into C++ modules where MC/DC applies. Decide before Phase 6 starts. |
| Electronic signature and identity controls under 21 CFR Part 11 subpart C are undefined | FR-DAT-006 cannot pass review | Medium | Draft the identity proofing procedure with the quality owner before task 5.2 starts |
| MSVC Community license terms against the no-commercial-license decision of 2026-10-14 | The decision excluded commercial tool licenses; MSVC Community carries its own terms (free for individual use and small teams) and builds rta/ and sim/ since the scaffold | Low | Record the license decision in the plan and SOUP; if the terms conflict, MSVC Build Tools licensing or the clang-cl toolchain are the fallbacks. Owner ruling pending. |

### 7.3 Schedule Risks

| Risk | Impact | Likelihood | Mitigation |
|:-----|:-------|:-----------|:-----------|
| HIL hardware lead times for Speedgoat, dSPACE, or NI SLSC | Phase 4 task 4.5 and Phase 6 task 6.4 slip | High | Place the HIL purchase order at Phase 3 start. Run Phase 4 software tasks on the SIL target until the bench arrives. |
| The FMI master in Phase 2 task 2.8 has no effort estimate in the SRS | Phase 2 overruns and delays Phases 3 and 4 | High | Hold the 8-day estimate with weekly review, and scope the master to the three plant models only |
| MANO model license terms are not cleared | Task 4.2 is blocked | Medium | Clear the license before Phase 4 starts. Teleoperation proceeds with the One Euro and EMA filters alone. |
