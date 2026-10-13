# SYSTEM REQUIREMENTS SPECIFICATION (SRS)
**Project Title:** SurgiTwin-RTA: Closed-Loop Surgical Soft-Tissue Digital Twin, Simplex Run-Time Assurance & 21 CFR Part 11 Verification Platform
**Author:** Seth Nenninger
**Document Version:** 1.0.0 (Baseline Validated)
**Target Regulatory & Interoperability Standards:** IEC 62304 (Class C), FDA QMSR (ISO 13485), FDA 21 CFR Part 11, FDA 2026 Computer Software Assurance (CSA) / GAMP 5 (2nd Ed.), MISRA C++:2023, DO-178C (DAL A), ASAM XIL v3.0.0, FMI 3.0, SiLA 2, HL7 FHIR R4.

---

## 1. INTRODUCTION & SYSTEM PURPOSE

### 1.1 Purpose
This document defines the functional, non-functional, regulatory, and verification requirements for **SurgiTwin-RTA**, a closed-loop surgical simulation and Software-in-the-Loop (SIL) / Hardware-in-the-Loop (HIL) verification platform. The system is architected to validate autonomous and teleoperated surgical robotics performing deformable solid-organ resection, hepatic lesion ablation, and needle puncture procedures while maintaining deterministic run-time safety and regulator-mandated data integrity.

### 1.2 System Scope
SurgiTwin-RTA eliminates the engineering bottleneck between real-time multi-physics biomechanical simulation, artificial intelligence control policies, and regulatory compliance. The platform integrates four core operational tiers:
1. **Virtual Proving Ground (M&S Tier):** Real-time non-linear Finite Element Method (FEM) soft-tissue physics and physiological simulation bridged to robotic middleware and photorealistic rendering pipelines.
2. **Run-Time Assurance (RTA Safety Tier):** A deterministic C++ Simplex safety filter governed by Timed Automata (TA) that mediates between unverified AI/teleoperated controllers and the surgical environment.
3. **Compliance & Interoperability Middleware (Informatics Tier):** A high-throughput telemetry and SiLA 2 hardware abstraction gateway decoupled from an immutable, cryptographically hashed FDA 21 CFR Part 11 audit database.
4. **Continuous Verification Harness (V&V Tier):** An ASAM XIL-compliant, CSA-aligned CI/CD test automation pipeline that enforces MISRA C++:2023 static analysis, structural coverage (MC/DC), and bidirectional requirements traceability on every code commit.

---

## 2. SYSTEM ARCHITECTURE & CSA RISK CLASSIFICATION

### 2.1 Architectural Topology
The platform utilizes a modular, distributed architecture linking C++17/C++20 real-time physics and safety cores with Python 3.11+ orchestration, gRPC/Protobuf hardware drivers, Fast DDS robotics middleware, and a React 18 / TypeScript WebGL visualization frontend.

### 2.2 FDA Computer Software Assurance (CSA) Risk Partitioning
In accordance with the February 2026 FDA CSA guidance and ISPE GAMP 5 Second Edition, system features are categorized by their foreseeable impact on patient safety and product quality:
* **High Process Risk (Scripted V&V Mandatory):** Features that directly control medical device kinematics, enforce safety envelopes, calculate biomechanical tissue rupture thresholds, or maintain legal electronic record immutability. These components require exhaustive scripted testing, 100% statement, branch, and Modified Condition/Decision Coverage (MC/DC), and formal Worst-Case Execution Time (WCET) analysis.
* **Not High Process Risk (Unscripted/Exploratory Verification Permitted):** Secondary operational features including 3D scene lighting, camera viewport adjustments, historical chart playback, and auxiliary developer CLI tooling. These components are verified using automated unit tests and exploratory heuristic testing.

---

## 3. FUNCTIONAL REQUIREMENTS (FR)

### 3.1 Biomechanical Soft-Tissue & Physiological Simulation Subsystem (M&S)

* **FR-MS-001 (Anatomical Ingestion):** The system shall ingest patient-specific volumetric medical imaging (CT/MRI DICOM data) via the **3D Slicer** ecosystem to generate segmented 3D meshes of target parenchymal organs (liver/breast), tumors, and critical vascular keep-out zones.
* **FR-MS-002 (Non-Linear FEM Solver):** The physics backend shall utilize the **SOFA (Simulation Open Framework Architecture)** engine in C++ to execute real-time, non-linear Finite Element Method (FEM) calculations on hyper-elastic soft tissues, utilizing implicit equation solvers to handle large geometric deformations.
* **FR-MS-003 (Continuous Collision & Topological Alteration):** The SOFA scene graph shall implement connectivity-based culling and continuous collision detection pipelines to accurately resolve multi-point tool-to-tissue contact mechanics, anisotropic needle puncture resistance, dissecting, and cutting.
* **FR-MS-004 (SlicerROS2 Middleware Bridge):** The system shall deploy the **SlicerROS2** module over **Fast DDS** to publish real-time Cartesian tool-tip positions, volumetric mesh deformation states, and calculated 6-axis haptic force feedback (wrench data) to **ROS2** nodes at high frequencies.
* **FR-MS-005 (USD & Photorealistic Rendering Pipeline):** The digital twin frontend shall link ROS2 kinematic and deformation data streams into **NVIDIA Omniverse / Isaac Sim** via **Universal Scene Description (USD)** workflows to generate synthetic endoscopic camera data for robotic vision algorithms.
* **FR-MS-006 (Systemic Physiological Co-Simulation):** The middleware shall integrate the C++ **Kitware Pulse Physiology Engine** via a Python `ProcessPoolExecutor`, executing concurrent patient physiological simulations (hemodynamic pressure, flow rate, SpO2, and in silico PK/PD loops) in parallel with local organ interactions without blocking the main telemetry event loop.
* **FR-MS-007 (FMI 3.0 Distributed Co-Simulation):** All disparate subsystem plant models (thermal ablation dynamics, mechanical kinematics, physiological state) shall be packaged as **Functional Mock-up Units (FMUs)** compliant with the **FMI 3.0** standard, utilizing FMI 3.0 clocks, scheduled variables, and the **FMI-LS-BUS** layered standard over Fast DDS to guarantee quantization-error-free synchronization across distributed edge nodes.

### 3.2 Run-Time Assurance (RTA) Simplex Filter & Teleoperation Subsystem

* **FR-RTA-001 (Simplex Architecture Topology):** The system shall implement a deterministic **Simplex Architecture** in C++ that mediates between an unverified primary controller (a Deep Reinforcement Learning [DRL] autonomous flight/trajectory policy or human teleoperator) and the surgical robot actuator interface.
* **FR-RTA-002 (Timed Automata State Prediction):** The RTA decision switch shall utilize formal **Timed Automata (TA)** models to continuously monitor current system telemetry, predict forward state trajectories, and explicitly account for sensor acquisition lag, asynchronous network updates, and processing delays.
* **FR-RTA-003 (Biomechanical & Spatial Safety Envelope):** The RTA switch shall evaluate every proposed kinematic tool-tip command against mathematically defined safety bounds, including maximum allowable tissue wrench/shear thresholds and minimum Euclidean distance to segmented vascular no-go zones.
* **FR-RTA-004 (Verified Fallback Recovery):** If the primary controller proposes an action that breaches the safe biomechanical envelope—or if a temporal delay violates a hard real-time deadline—the RTA switch shall preemptively disable the primary controller and transfer execution to a formally verified fallback controller (PID/LQR) to execute a safe axial retraction or velocity-damped hold.
* **FR-RTA-005 (Multi-Modal 6-DOF Teleoperation & Signal Filtering):** For human-in-the-loop teleoperation modes, the system shall support 6 Degrees of Freedom (DOF) spatial control integrating **MANO** parametric biomechanical constraints, an adaptive first-order **One Euro low-pass filter**, and an **Adaptive Exponential Moving Average (EMA)** digital low-pass filter to smooth erratic input streams and prevent mechanical jitter from triggering false clinical alarms.
* **FR-RTA-006 (Embedded Edge HIL Fail-Safe):** When operating in Hardware-in-the-Loop (HIL) mode, the system shall interface with an **ESP32-S3 Microcontroller Unit (MCU)** bridge utilizing **MessagePack** binary serialization (achieving up to 70% payload compression and sub-10ms command latency) and running an 8-bit integer quantized **TensorFlow Lite Micro (TFLM)** neural network (shrunk by 75%) natively on the MCU for offline emergency processing.

### 3.3 Telemetry, SiLA 2 Hardware Abstraction & 21 CFR Part 11 Audit Subsystem

* **FR-DAT-001 (Decoupled Three-Tier Middleware):** Building upon the **BioSync-Gateway** architecture, the system shall utilize a three-tier **FastAPI (Python 3.11+)** gateway that decouples the real-time visualization path from the immutable regulatory compliance storage tier.
* **FR-DAT-002 (SiLA 2 Instrument Interoperability):** Physical and simulated peripheral laboratory/surgical instruments (e.g., peristaltic infusion pumps, ablation generators, robotic arms) shall be wrapped as **SiLA 2 Servers** using **gRPC over HTTP/2** and **Google Protocol Buffers (Protobuf)**, exposing strongly typed capabilities defined via the **SiLA Feature Definition Language (FDL)**.
* **FR-DAT-003 (21 CFR Part 11 & ALCOA+ Immutability):** All simulation runs, RTA switch overrides, SiLA 2 remote procedure calls, and surgical telemetry records shall be persisted in a **PostgreSQL 15+** Write Once, Read Many (WORM) database tier that enforces **FDA 21 CFR Part 11** and **ALCOA+** (Attributable, Legible, Contemporaneous, Original, Accurate) principles.
* **FR-DAT-004 (Tamper-Evident Triggers & §11.10(e) Audit Trails):** The PostgreSQL storage tier shall implement `BEFORE UPDATE OR DELETE` database triggers to prohibit trace-free overwriting or record deletion by any user, including system administrators, while automatically generating computer-generated, time-stamped audit trails under **21 CFR §11.10(e)** capturing user identity, action type, and both pre- and post-change parameter values.
* **FR-DAT-005 (Cryptographic Hash Chaining & Nightly Verification):** The database shall utilize the `pgcrypto` extension to generate continuous, append-only **SHA-256** hash chains across all finalized records, supported by automated nightly verification queries that recompute the entire hash chain to detect and flag any tamper attempts occurring below the application layer.
* **FR-DAT-006 (Electronic Signatures & Access Control):** The system shall enforce Role-Based Access Control (RBAC), unique individual credentials (strictly prohibiting shared accounts), automated inactivity session lockouts, and legally bound electronic signatures displaying the printed name of the signer, exact timestamp, and semantic meaning (authorship, review, or approval).
* **FR-DAT-007 (HL7 FHIR R4 Clinical Interoperability):** The gateway shall map raw surgical telemetry and physiological metrics into validated **HL7 FHIR R4** `Observation` and `DeviceMetric` resources utilizing `fhir.resources` and **Pydantic v2**.

### 3.4 Continuous Verification (CV), ASAM XIL & CSA Test Automation Subsystem

* **FR-VV-001 (MISRA C++:2023 Static Analysis):** The CI/CD pipeline shall execute automated static analysis (via **Parasoft C/C++test** or **QA-MISRA**) on every code commit across all C++17/C++20 source files against the **MISRA C++:2023** rule set, conducting pattern-based, control flow, and data flow analysis to guarantee freedom from interference, eliminate null pointer dereferencing, and prevent buffer overflows prior to dynamic execution.
* **FR-VV-002 (ASAM XIL v3.0.0 Test Abstraction Layer):** All automated verification scripts shall be authored in Python against the **ASAM XIL v3.0.0 API** standard, utilizing the **Model Access (MA) Port** for variable read/write and step control, the **Electrical Error Simulation (EES) Port** for hardware fault injection, the **Service-Oriented Access (SOC) Port** for middleware subscriptions, and the **ECU Access Port** for synchronized memory capture.
* **FR-VV-003 (SIL-to-HIL Script Portability):** The ASAM XIL abstraction layer shall guarantee that automated test scripts executed against the virtual SOFA/Pulse model in host PC Software-in-the-Loop (SIL) environments can be deployed without modification to physical Hardware-in-the-Loop (HIL) target machines (**Speedgoat**, **dSPACE**, or **NI SLSC** architectures).
* **FR-VV-004 (Automated Structural Coverage & WCET):** The CI pipeline shall orchestrate dynamic testing frameworks (**VectorCAST**, **Cantata**, **Catch2**, **CTest**, and **Pytest**) to automatically generate boundary/failure-mode test cases, enforce 100% statement, branch, and **MC/DC** structural coverage on High Process Risk modules, and execute formal statistical timing analysis to verify **Worst-Case Execution Time (WCET)** bounds.
* **FR-VV-005 (Bidirectional Traceability & Compliance-as-Code):** A custom reporting engine shall aggregate static analysis diagnostics, structural coverage metrics, and 19 distinct **IQ/OQ/PQ** validation protocol results, automatically pushing cryptographic forward and backward trace links to Application Lifecycle Management (ALM) tools (**Jama** or **Polarion**) to verify that no undocumented functionality, dead code, or rogue logic has been introduced.

---

## 4. NON-FUNCTIONAL & PERFORMANCE REQUIREMENTS (NFR)

* **NFR-PERF-001 (Telemetry Ingestion Throughput):** The middleware gateway shall stream and process high-frequency surgical device and physics telemetry at over **100,000 data points per second**.
* **NFR-PERF-002 (Network Relay Latency):** The WebSocket (WSS) and Fast DDS telemetry relay shall maintain an end-to-end transport latency of **sub-50 milliseconds** for remote visualization and **sub-10 milliseconds** over MessagePack serial/embedded bridges for real-time robotic command execution.
* **NFR-PERF-003 (Real-Time Rendering Frame Rate):** Both the custom **React 18 / TypeScript / WebGL / HTML5 Canvas** waveform frontend and the 3D surgical visualization pipeline shall sustain a minimum rendering performance of **60 Frames Per Second (FPS)** under full telemetry load.
* **NFR-PERF-004 (Concurrent Session Scale):** The system architecture shall support over **500 concurrent WebSocket sessions** without degradation of physics solver step times or audit logging integrity.
* **NFR-SEC-001 (Cryptographic Transport & Isolation):** All external API interactions shall be secured via strict **JSON Web Token (JWT)** authentication and **OAuth**, while the PostgreSQL 15+ compliance database tier shall be isolated behind client-certificate verification and **TLS 1.3** protocols.
* **NFR-REL-001 (Memory Safety & Defect Tolerance):** All C++ simulation cores (SOFA plugins, Simplex RTA switch, and Kitware Pulse Physiology Engine integrations) shall maintain zero unresolved `SIGSEGV` memory defects and achieve a **100% pass rate** across all 19 IQ/OQ/PQ validation protocols.

---

## 5. BIDIRECTIONAL VERIFICATION & TRACEABILITY MATRIX (VTM)

| Requirement ID | Subsystem / Module | Regulatory / Standard Mapping | CSA Risk Classification | Verification Method & Toolchain | Target Acceptance Metric |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **FR-MS-002** | SOFA Non-Linear FEM Core | IEC 62304 Class B/C | High Process Risk | Dynamic SIL Testing (CTest / Catch2 / ASAM XIL MA Port) | Sustained $\ge 60\text{ FPS}$ visual / $\ge 500\text{ Hz}$ wrench publish without solver divergence. |
| **FR-MS-006** | Kitware Pulse Physiology Bridge | IEC 62304 / FDA 21 CFR Part 11 | High Process Risk | ProcessPoolExecutor Integration Suite (Pytest) | Zero main-loop blocking; 100% pass rate across 19 IQ/OQ/PQ validation protocols. |
| **FR-MS-007** | FMI 3.0 Co-Simulation Master | FMI 3.0 / FMI-LS-BUS | High Process Risk | Multi-Node Distributed Clock Sync Test (Fast DDS) | Zero quantization error across discrete-event network boundaries. |
| **FR-RTA-001** | C++ Simplex RTA Safety Switch | DO-178C DAL A / IEC 62304 Class C / MISRA C++:2023 | High Process Risk | Static Analysis (Parasoft/QA-MISRA) + Dynamic Coverage (VectorCAST) | Zero MISRA violations; 100% Statement, Branch, and MC/DC coverage. |
| **FR-RTA-002** | Timed Automata (TA) Envelope Monitor | DO-178C / ISO 26262 ASIL D | High Process Risk | Formal Statistical Timing Analysis (VectorCAST/Timing) & Fault Injection (ASAM XIL EES Port) | 100% boundary containment within verified WCET hard real-time deadlines. |
| **FR-RTA-006** | ESP32-S3 TFLM HIL Fail-Safe | IEC 62304 Class C | High Process Risk | HIL Target Bench Testing (MessagePack / 8-bit TFLM) | $< 10\text{ ms}$ command latency; $\ge 70\%$ payload compression; deterministic offline fallback. |
| **FR-DAT-004** | PostgreSQL 15+ WORM Audit Store | FDA 21 CFR Part 11 (§11.10(e)) / ALCOA+ | High Process Risk | Automated SQL Tamper & Trigger Injection Suite (Pytest) | 100% rejection of `UPDATE`/`DELETE` attempts; complete old/new value capture. |
| **FR-DAT-005** | `pgcrypto` SHA-256 Hash Chain | FDA 21 CFR Part 11 / EU Annex 11 | High Process Risk | Nightly Automated Chain Recomputation Query | 100% detection of below-application-layer database tampering. |
| **FR-DAT-007** | HL7 FHIR R4 / SiLA 2 Gateway | HL7 FHIR R4 / SiLA 2 (gRPC/Protobuf) | Not High Process Risk | Schema Validation (`fhir.resources` / Pydantic v2) & Exploratory Testing | 100% schema validation compliance at $> 100,000\text{ pts/sec}$ ingestion. |
| **FR-VV-005** | Bidirectional ALM Trace Engine | IEC 62304 / ISO 13485 (QMSR) / GAMP 5 | High Process Risk | Automated CI/CD Traceability Audit (Jama / Polarion API) | 100% forward and backward trace coverage; zero unlinked dead code. |