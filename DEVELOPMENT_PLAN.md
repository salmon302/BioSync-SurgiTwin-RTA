# SurgiTwin-RTA Development Plan

**Version:** 1.0 (draft)  
**Date:** 2026-10-13  
**Derived From:** SRS.md v1.0.0  
**Status:** Draft with open validation findings (see Section 6). Phase 0 complete. Phase 1 complete, with gates G1.1 to G1.8 closed (G1.8 with recorded boundaries). Phase 2 in progress (kickoff 2026-10-14, `SNDEV/docs/impl-2026-10-14-phase2-kickoff.md`). SRS.md v1.1.0 was applied 2026-10-14 (`SNDEV/docs/impl-2026-10-14-srs-v1.1-apply.md`), closing Blockers VAL-001 to VAL-004. No commercial licenses are used in development (decision of 2026-10-14, `SNDEV/docs/impl-2026-10-14-no-commercial-licenses.md`). Major and Minor findings remain open.

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
| Soft-tissue FEM | SOFA | One tagged release pinned in `sim/sofa/` in Phase 2 | LGPL-2.1 (confirm). No hardware. |
| Segmentation and ROS bridge | 3D Slicer and SlicerROS2 | Tagged releases pinned in `sim/bridge/` in Phase 2 | 3D Slicer BSD-style license. SlicerROS2 license (confirm). |
| Robotics middleware | ROS 2 and Fast DDS | One ROS 2 distribution and its matching Fast DDS version, pinned together | Apache-2.0. |
| Photorealistic rendering | NVIDIA Omniverse / Isaac Sim with USD | Runtime and USD versions pinned together in Phase 7 | Precondition: NVIDIA Omniverse license terms (proprietary) and an RTX-class GPU. |
| Physiology | Kitware Pulse Physiology Engine via Python `ProcessPoolExecutor` | Pinned source commit built from the `.pulse/` prerequisite (not in the repository) | Apache-2.0 (confirm). Built by `middleware/Dockerfile.pulse`. |
| Co-simulation | FMI 3.0 and FMI-LS-BUS | FMI 3.0 standard; FMI-LS-BUS 1.0 over Fast DDS | Open standards (confirm). The SRS names no FMI master tool, so the master is built in Phase 2. |
| Middleware | Python 3.11+ and FastAPI | Python 3.11 is the target (the scaffold ran on 3.14). FastAPI is pinned in `middleware/requirements.txt`, and the pins are not yet resolved against PyPI. | MIT. |
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
| Virtual Proving Ground (M&S) | `sim/` | SOFA FEM scene (`sim/sofa/`), Pulse engine notes (`sim/pulse/`), FMI master and FMUs (`sim/fmi/`), SlicerROS2 bridge (`sim/bridge/`), USD rendering (`sim/omniverse/`, Phase 7) | `sim/sofa`, `sim/fmi`, and `sim/bridge` build only when their CMake options are ON. The Pulse binding runs from `middleware/engine/pulse.py`. |
| Run-Time Assurance (RTA) | `rta/` | Simplex switch, safety envelope, timed automata, and the fallback controller (`rta/include/rta/fallback_controller.h` and `rta/src/fallback_controller.cpp`, created in Phase 3) | Placeholder classes `SafetyEnvelope`, `SimplexSwitch`, and `TimedAutomata` build by default with stub thresholds of 5.0 mm and 2.0 N. |
| Compliance and Interoperability (Informatics) | `middleware/`, `database/`, `edge/`, `frontend/` | FastAPI gateway, hash chain engine, FHIR validation, Pulse worker, SQL migrations 001 to 003, ESP32-S3 firmware (Phase 4), React client (Phase 7) | Gateway baseline migrated at commit `0b5b8d2`. The telemetry relay landed at commit `d0ef2c5` (Phase 1 task 1.5, closed at `654510b`). |
| Continuous Verification (V&V) | `vv/` | ASAM XIL harness (`vv/xil/`), VTM (`vv/traceability/`), IQ, OQ, and PQ tests (`vv/tests/`) | IQ-0 layout test present. Migrated IQ, OQ, and PQ suites present. |

### 3.2 Topology

```
Virtual Proving Ground (sim/)
  SOFA FEM core, SlicerROS2 bridge, FMI 3.0 master
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

**Goal:** Build the FEM soft-tissue scene, the SlicerROS2 and Fast DDS bridge, the Pulse worker delegation, and the FMI 3.0 co-simulation master for FR-MS-001 through FR-MS-004, FR-MS-006, and FR-MS-007.

**Status:** In progress (kickoff 2026-10-14, `SNDEV/docs/impl-2026-10-14-phase2-kickoff.md`). Phase 1 gates G1.1 through G1.3 prerequisites are PASS, and they are prerequisites for FR-MS-006 persistence. Tooling outcomes on 2026-10-14: SOFA v26.06.00 and 3D Slicer 5.12.4 are installed, which clears the preconditions for tasks 2.1 to 2.3. Pulse is pinned to tag `REL_4_3_2`, built as image `biosync-pulse`, and its `.pulse/` provenance is recorded. IQ-4 and OQ-16 pass on the pinned build. The FMI tooling item is partial (FMPy 0.3.32 installed). ROS 2 and SlicerROS2 are deferred by the user decision of 2026-10-14. The `vtm-600s` run (600 s, 10 simulations) measured 239.357 ms against the 50 ms bound on 2026-10-14. The diagnosis in `SNDEV/docs/impl-2026-10-14-heartbeat-gap-diag.md` attributed the gaps to a lazy first-step metrics-hook import and generation-2 GC cost from an unbounded metrics history, and fixed both on the production path in `middleware/engine/pulse.py`. The rerun `heartbeat-diag-1` (2026-10-15) measured a maximum gap of 16.778 ms with zero samples above 20 ms, so the G2.5 heartbeat clause is PASS.

**Estimate:** 43.0 d (6.0 d complete: tasks 2.5 and 2.6; 37.0 d remaining). Completed days are the sum of the done rows: 2.0 (task 2.6) + 4.0 (task 2.5) = 6.0. Remaining days are the open rows: 5.0 + 8.0 + 6.0 + 4.0 + 6.0 + 8.0 = 37.0 (tasks 2.1, 2.2, 2.3, 2.4, 2.7, and 2.8). The total is unchanged at 43.0.

#### Tasks

| Task | Output | Est. |
|:-----|:-------|:-----|
| 2.1 Ingest DICOM through 3D Slicer and produce segmented meshes for parenchymal organ, tumor, and vascular keep-out zones, with segmentation provenance | `sim/segmentation/` (created) | 5.0d |
| 2.2 Build the hyperelastic FEM scene with an implicit solver in SOFA, pin the SOFA release, and open the SOUP inventory | `sim/sofa/` (scene sources created under `sim/sofa/src/`), `sim/SOUP.md` (created) | 8.0d |
| 2.3 Implement connectivity-based culling, continuous collision detection, needle puncture resistance, dissection, and cutting | `sim/sofa/src/` (created) | 6.0d |
| 2.4 Publish tool-tip pose, mesh deformation, and wrench data to ROS 2 nodes through SlicerROS2 over Fast DDS, with the wrench rate stated in FR-MS-004 | `sim/bridge/` | 4.0d |
| 2.5 Delegate Pulse steps to a `ProcessPoolExecutor` with one long-lived worker per engine instance, keep the step off the event loop, and expose a heartbeat-gap metric | `middleware/engine/pulse.py`, `middleware/engine/pulse_bridge.py` | 4.0d (done 2026-10-15: delegation landed at `5fb26a3`; the heartbeat-gap metric and the FR-MS-006 fixes are recorded in `SNDEV/docs/impl-2026-10-14-heartbeat-gap-diag.md`, gate G2.5 PASS) |
| 2.6 Verify the Pulse import and state tests on the pinned engine build, and record the engine source provenance for `.pulse/` | `vv/tests/IQ/test_iq4_pulse_engine_init.py`, `vv/tests/OQ/test_oq16_pulse_state_serialization.py`, `middleware/Dockerfile.pulse` | 2.0d (done 2026-10-14: `import pulse OK` and 11 passed, 1 skipped in the `biosync-pulse` image; `.pulse/` provenance in `sim/SOUP.md` and `docs/migration-map.md`) |
| 2.7 Package the thermal ablation, mechanical (SOFA), and physiology (Pulse) plant models as FMI 3.0 FMUs | `sim/fmi/` | 6.0d |
| 2.8 Build the FMI 3.0 co-simulation master with clocks, scheduled variables, and FMI-LS-BUS over Fast DDS, with a bounded clock-skew and jitter measurement (VAL-005) | `sim/fmi/master/` (created) | 8.0d |

#### Verification Gates

| Gate | Requirement | Acceptance Metric | Status |
|:-----|:------------|:------------------|:-------|
| G2.1 Mesh ingestion | FR-MS-001 | Meshes for parenchyma, tumor, and vascular keep-out zones are exported from the reference DICOM set with segmentation provenance, and overlap with reference labels is a Dice score of 0.90 or higher (proposed) | OPEN |
| G2.2 Solver rate | FR-MS-002, NFR-PERF-003 | Solver step completes within the 16.7 ms frame budget of 60 FPS on the reference scene, with no divergence over a 30-minute load case (proposed) | OPEN |
| G2.3 Contact | FR-MS-003 | Zero tunneling events and zero missed contacts across a 1,000-trial needle puncture and cutting suite (proposed) | OPEN |
| G2.4 Wrench publish | FR-MS-004 | A wrench publish rate of 500 Hz or higher is sustained for 10 minutes, measured at the ROS 2 subscriber | OPEN |
| G2.5 Pulse worker | FR-MS-006 | IQ-4 and OQ-16 PASS on the pinned Pulse build, and the maximum event-loop heartbeat gap is 50 ms or less with 10 concurrent simulations (proposed) | PASS. IQ-4 and OQ-16 passed on the pinned build (task 2.6). Heartbeat clause passed on rerun `heartbeat-diag-1` (2026-10-15): maximum gap 16.778 ms against the 50 ms bound over 600 s with 10 concurrent simulations, 55,846 samples with zero above 20 ms. The earlier `vtm-600s` measurement (239.357 ms) is diagnosed and fixed in `SNDEV/docs/impl-2026-10-14-heartbeat-gap-diag.md`. Capture: `SNDEV/logs/pq-2026-10-15-fr-ms-006-heartbeat-diag-1.json`. |
| G2.6 Co-simulation | FR-MS-007 | FMUs pass FMI 3.0 import checks, and clock skew and message jitter are 1 ms or less on the three-node Fast DDS test (proposed) | OPEN |

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
| 7.1 Link ROS 2 kinematic and deformation streams into USD layers in Omniverse / Isaac Sim, with the USD and runtime versions pinned | `sim/omniverse/` (created) | 6.0d |
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
| VAL-005 | Replace "zero quantization error" with bounded clock-skew and message-jitter limits and a stated test setup | 1 ms limits in gate G2.6 (proposed), measured in task 2.8 | 2 |
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

---

## 7. Risk Register

### 7.1 Technical Risks

| Risk | Impact | Likelihood | Mitigation |
|:-----|:-------|:-----------|:-----------|
| SOFA does not hold real-time determinism at the solver rate needed for 60 FPS and the 500 Hz wrench publish | Missed frame and publish targets. Envelope inputs go stale. | Medium | Gates G2.2 and G2.4 at Phase 2 exit. Reduce telemetry only through LTTB, which keeps peaks, and keep the scene within the measured budget. |
| FMI clock synchronization quantization across Fast DDS adds error to the co-simulation step | Step error exceeds the bounded skew and produces false envelope decisions | High | Replace the zero-error claim with bounded limits (VAL-005), measure in gate G2.6, and use FMI 3.0 scheduled variables and step-size control in the master |
| WCET tooling does not support the target CPU or MCU, or it yields loose bounds | The candidate RTA deadline cannot be stated, and FR-RTA-004 cannot be tested | Medium | Measure on the target with statistical timing (task 3.6), keep the decision path free of heap and locks, and record tool limits in `sim/SOUP.md` |
| Omniverse / Isaac Sim dependency (GPU class, runtime license, USD version drift) | Phase 7 is blocked, and the NFR-PERF-003 rendering path is unavailable | Medium | Pin the USD and runtime versions. Rendering is Not High Process Risk, so the M&S and RTA tiers do not depend on it. Record the GPU precondition before Phase 7 starts. |
| Kitware Pulse is single-threaded per patient and its engine object cannot be pickled | ProcessPoolExecutor delegation (FR-MS-006) fails, and the event loop blocks | High | One long-lived worker per engine instance (task 2.5) and heartbeat gate G2.5. The Gateway open item in migration-map Table 3 tracks the blocker. |
| Gateway R3 relay path: R3 is closed at task 1.5, and R2 is closed at `a44c163`. NFR-PERF-001 ingestion measured below target on the Phase 1 configuration. | NFR-PERF-001 is not met (about 12,600 points per second against 100,000). NFR-PERF-002 holds only at 10 points per second on this host, and the 50 ms bound fails at 20 points per second and above. The tail-latency source is not isolated: the relay serializes broadcast fan-out per frame (`ConnectionManager.broadcast`), and client-side queueing in the single client process is an unmeasured candidate. | Medium | Phase 1 task 1.5 (closed). Gate G1.8 PASS with recorded boundaries at `7508b91`. Revisit NFR-PERF-001 at Phase 5 task 5.6 and with relay tuning. |

### 7.2 Regulatory Risks

| Risk | Impact | Likelihood | Mitigation |
|:-----|:-------|:-----------|:-----------|
| Proprietary tool qualification for Parasoft, QA-MISRA, VectorCAST, and Cantata | Tool output cannot be relied on as validation evidence without qualification, which becomes an audit finding | High | No commercial tool is used in development (decision of 2026-10-14). Conformity claims are limited to the open-source check set, and deviations are recorded in this risk file and the deviation register. An adopter who selects a commercial tool selects one with a vendor qualification kit and records its version and qualification evidence in `SNDEV/docs/`. |
| DO-178C DAL A and ISO 26262 ASIL D citations apply to other certification contexts | Submission credibility and a rigor target that does not match the device | Medium | Remove both as certification targets, or write the mapping to IEC 62304 Class C activities (VAL-008, VAL-009) |
| C++17 pin versus the SRS C++17/C++20 wording | The static analysis gate cannot cover C++20 files, so "zero violations" cannot be achieved as written | Medium | Pin the safety cores to C++17 in `CMakeLists.txt`, and settle the C++20 deviation register before gate G3.1 closes (VAL-016) |
| Python High Process Risk modules have no MC/DC tool | Scripted V&V gap under SRS Section 2.2 | High | Record a deviation in the risk file that requires statement and branch coverage for Python. Move safety-critical logic into C++ modules where MC/DC applies. Decide before Phase 6 starts. |
| Electronic signature and identity controls under 21 CFR Part 11 subpart C are undefined | FR-DAT-006 cannot pass review | Medium | Draft the identity proofing procedure with the quality owner before task 5.2 starts |

### 7.3 Schedule Risks

| Risk | Impact | Likelihood | Mitigation |
|:-----|:-------|:-----------|:-----------|
| HIL hardware lead times for Speedgoat, dSPACE, or NI SLSC | Phase 4 task 4.5 and Phase 6 task 6.4 slip | High | Place the HIL purchase order at Phase 3 start. Run Phase 4 software tasks on the SIL target until the bench arrives. |
| The FMI master in Phase 2 task 2.8 has no effort estimate in the SRS | Phase 2 overruns and delays Phases 3 and 4 | High | Hold the 8-day estimate with weekly review, and scope the master to the three plant models only |
| MANO model license terms are not cleared | Task 4.2 is blocked | Medium | Clear the license before Phase 4 starts. Teleoperation proceeds with the One Euro and EMA filters alone. |
