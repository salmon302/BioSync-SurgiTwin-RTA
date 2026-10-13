Title: SurgiTwin-RTA SRS v1.0.0 baseline validation audit
Date: 2026-10-13T22:20:16Z
Author: Seth Nenninger (MiMo-V2.6-Pro Agent)
Contribution Type: Implementation
Ticket/Context: ad-hoc (repo preparation for initial development)
Summary: Audited SRS.md v1.0.0 (100 lines): 31 requirement IDs defined, only 10 carry VTM rows, 4 Blocker / 12 Major / 9 Minor findings; the "Baseline Validated" claim does not hold as written and the document is fit only as an unvalidated draft until the VTM, the protocol register, and the run-time deadline are completed.

## Scope and method

Target of the audit: `BioSync-SurgiTwin-RTA\SRS.md`, "Document Version: 1.0.0 (Baseline Validated)" (line 4), read end to end. The audit checked five things: requirement ID coverage against the Section 5 Verification and Traceability Matrix (VTM, lines 87-100), measurability of every Target Acceptance Metric, numeric and semantic consistency across Sections 2 through 5, coherence of each standards citation, and inheritance risk from the completed BioSync-Gateway project referenced by FR-DAT-001 (line 58).

Method: a regex sweep of the SRS for every requirement ID prefix (FR-MS, FR-RTA, FR-DAT, FR-VV, NFR-PERF, NFR-SEC, NFR-REL) produced 41 matches, which resolve to 31 definitions in Sections 3 and 4 plus 10 VTM rows in Section 5. Each VTM row was matched back to its definition. Each Target Acceptance Metric was tested for a quantity, a unit, a test condition, and a measurement procedure. External citations were checked against published sources: the eCFR text of 21 CFR 11.10, the ASAM XIL port list, MISRA C++:2023 language coverage, the FMI-LS-BUS release record, FDA guidance status, and QA Systems product pages. The Gateway cross-check used `BioSync-Gateway\SRS.md` v1.1 (2026-07-24) and `BioSync-Gateway\REMAINING_WORK_v1.1.md` (re-audit 2026-07-28, executive summary and top items R2, R3, R5-R8 plus the approved SciChart deviation).

In the tables below, "acceptance metric" means the Target Acceptance Metric cell of the VTM row for that ID.

## ID coverage

Counts: 31 IDs defined (7 FR-MS, 6 FR-RTA, 7 FR-DAT, 5 FR-VV, 4 NFR-PERF, 1 NFR-SEC, 1 NFR-REL). VTM rows: 10. PASS: every ID the VTM references exists in Section 3 or 4, so there are no dangling references. FAIL: 21 of 31 defined IDs appear nowhere in the VTM, including all six NFRs.

| Requirement ID | Defined at (line) | VTM row | Acceptance metric present | Metric measurable as written |
|:---|:---|:---|:---|:---|
| FR-MS-001 | 39 | NO | NO | n/a |
| FR-MS-002 | 40 | YES (line 91) | YES | NO |
| FR-MS-003 | 41 | NO | NO | n/a |
| FR-MS-004 | 42 | NO | NO | n/a |
| FR-MS-005 | 43 | NO | NO | n/a |
| FR-MS-006 | 44 | YES (line 92) | YES | NO |
| FR-MS-007 | 45 | YES (line 93) | YES | NO |
| FR-RTA-001 | 49 | YES (line 94) | YES | PARTIAL |
| FR-RTA-002 | 50 | YES (line 95) | YES | NO |
| FR-RTA-003 | 51 | NO | NO | n/a |
| FR-RTA-004 | 52 | NO | NO | n/a |
| FR-RTA-005 | 53 | NO | NO | n/a |
| FR-RTA-006 | 54 | YES (line 96) | YES | PARTIAL |
| FR-DAT-001 | 58 | NO | NO | n/a |
| FR-DAT-002 | 59 | NO | NO | n/a |
| FR-DAT-003 | 60 | NO | NO | n/a |
| FR-DAT-004 | 61 | YES (line 97) | YES | PARTIAL |
| FR-DAT-005 | 62 | YES (line 98) | YES | NO |
| FR-DAT-006 | 63 | NO | NO | n/a |
| FR-DAT-007 | 64 | YES (line 99) | YES | PARTIAL |
| FR-VV-001 | 68 | NO | NO | n/a |
| FR-VV-002 | 69 | NO | NO | n/a |
| FR-VV-003 | 70 | NO | NO | n/a |
| FR-VV-004 | 71 | NO | NO | n/a |
| FR-VV-005 | 72 | YES (line 100) | YES | PARTIAL |
| NFR-PERF-001 | 78 | NO | NO | n/a |
| NFR-PERF-002 | 79 | NO | NO | n/a |
| NFR-PERF-003 | 80 | NO | NO | n/a |
| NFR-PERF-004 | 81 | NO | NO | n/a |
| NFR-SEC-001 | 82 | NO | NO | n/a |
| NFR-REL-001 | 83 | NO | NO | n/a |

Of the 10 metrics that exist, 5 are not measurable as written and 5 are measurable only in part. No metric outside the VTM exists anywhere else in the document.

## Findings

| ID | Severity | SRS section and line | What is wrong | Recommendation |
|:---|:---|:---|:---|:---|
| VAL-001 | Blocker | Section 5 (lines 87-100) vs Sections 3/4 (lines 39-83) | Only 10 of 31 defined IDs have VTM rows. All six NFRs (lines 78-83) and 15 FRs have no verification method and no acceptance metric, yet line 4 labels the document "Baseline Validated". | Add VTM rows for all 31 IDs, at minimum for every NFR and every High Process Risk FR, before the version label is re-issued. |
| VAL-002 | Blocker | FR-VV-005 (line 72), NFR-REL-001 (line 83), VTM row (line 92) | "19 distinct IQ/OQ/PQ validation protocols" is asserted three times, but the document contains no protocol list and no protocol section. The count matches the Gateway real-engine test tally (IQ-4 4/4, OQ-16 5/5, PQ-2 5/5, PQ-6 5/5 = 19) rather than a protocol register; the Gateway protocol register itself holds 7 IQ + 23 OQ + 8 PQ = 38 protocols. | Publish a protocol register with protocol IDs and trace each requirement to specific protocols, or remove the count. |
| VAL-003 | Blocker | FR-RTA-002 (line 50), FR-RTA-003 (line 51), VTM row (line 95) | The row is named "Timed Automata (TA) Envelope Monitor" while FR-RTA-002 is named "Timed Automata State Prediction". The envelope function belongs to FR-RTA-003, which has no VTM row, so the tissue wrench/shear limits and vascular keep-out distance checks have no verification path. | Rename the FR-RTA-002 row to state prediction and add a separate FR-RTA-003 row with numeric envelope thresholds and a test method. |
| VAL-004 | Blocker | FR-RTA-004 (line 52), VTM metric (line 95) | No numeric deadline appears anywhere in the document. "Hard real-time deadline" (line 52) and "verified WCET hard real-time deadlines" (line 95) reference an unstated bound, so the fallback trigger and the containment metric cannot be tested. | State the RTA decision-loop deadline with unit and test conditions, and name the WCET method and target platform in FR-VV-004. |
| VAL-005 | Major | FR-MS-007 (line 45), VTM (line 93) | "Zero quantization error" and "quantization-error-free synchronization" name no quantity, resolution, reference clock, tolerance, or measurement procedure. Exact zero error across a network boundary is untestable. | Replace with bounded clock-skew and message-jitter limits plus a stated test setup. |
| VAL-006 | Major | FR-MS-002 (line 40), FR-MS-004 (line 42), NFR-PERF-003 (line 80), VTM (line 91) | The row's numbers are absent from FR-MS-002: 60 FPS duplicates NFR-PERF-003, ">=500 Hz wrench publish" appears nowhere else (FR-MS-004 says only "high frequencies"), and "without solver divergence" has no definition, load case, or run duration. | Move each number to the requirement that owns it and define the divergence check. |
| VAL-007 | Major | FR-MS-006 (line 44), VTM (line 92) | "Zero main-loop blocking" has no observation window, blocking threshold, or instrumentation method, and the second half of the metric depends on VAL-002's undefined protocol count. | Define a measurable proxy, such as a maximum event-loop heartbeat gap under a stated load. |
| VAL-008 | Major | Header (line 5), VTM (lines 91, 92, 100) | IEC 62304 class attribution is inconsistent: the header declares Class C, the FR-MS-002 row declares "Class B/C" (an undecided range), and the FR-MS-006 and FR-VV-005 rows cite IEC 62304 with no class. The standard assigns one class per software item from risk analysis. | Assign a single class per software item, cite the risk file behind it, and align the header. |
| VAL-009 | Major | Header (line 5), VTM (lines 94, 95) | DO-178C DAL A and ISO 26262 ASIL D are aviation and automotive certification levels applied to a surgical robot; line 94 states DAL A while line 95 names DO-178C with no DAL, and ISO 26262 does not appear in the header standards list at all. | Drop both citations, or declare them as borrowed rigor tiers with a written mapping to IEC 62304 Class C activities, and make the DAL consistent. |
| VAL-010 | Major | FR-DAT-004 (line 61), VTM (line 97) | The requirement rejects every UPDATE and DELETE outright, while the metric demands "complete old/new value capture". With no mutation ever applied there are no post-change values to capture. The Gateway base implementation rejects mutations and stores no before/after images. | Split the requirement into immutable-row rejection plus an append-only change log for permitted edits, or drop the capture clause. |
| VAL-011 | Major | FR-RTA-004 (line 52) | "Formally verified fallback controller (PID/LQR)" names no verification method, tool, model abstraction, or proof scope, and the requirement has no VTM row. | Name the method and tool (for example model checking of a discrete plant abstraction, or a Lyapunov stability argument) or reword to a bounded analysis claim. |
| VAL-012 | Major | Sections 3.1-3.2 (lines 39-54), Section 2.2 (line 30) | No requirement covers SOUP evaluation. SOFA, 3D Slicer, SlicerROS2, Pulse, Fast DDS, TFLM, Omniverse/Isaac Sim and FMI tooling enter a Class C system with no inventory, version pinning, anomaly monitoring, or integration risk analysis, all of which IEC 62304 Class C requires. | Add SOUP requirements (inventory, version pinning, evaluation, anomaly response) and give them VTM rows. |
| VAL-013 | Major | NFR-SEC-001 (line 82) | "OAuth" appears with no grant type, token profile, or resource server model. The client-certificate database isolation claim repeats Gateway NFR-S5, which Gateway marks partial with R2 OPEN (default DB_SSLMODE=prefer, server-side verify-full not demonstrated). The requirement has no VTM row. | Specify the OAuth profile, require verify-full as the default, and add a VTM row with a test method. |
| VAL-014 | Major | NFR-PERF-002 (line 79), FR-RTA-006 (line 54), VTM (line 96) | The latency numbers state no measurement point, message size, network condition, or statistic (worst case, p99, mean). "Sub-10 ms over MessagePack" treats a serialization format as a transport. The same 10 ms figure appears three times with one undefined test behind it, and the Gateway counterpart (NFR-P3, 50 ms relay) is marked unverified with R3 OPEN. | Define one latency test with method and conditions, and close the Gateway R3 pattern (uvloop absent, synchronous database writes on the relay path) in Phase 1. |
| VAL-015 | Major | FR-DAT-005 (line 62), VTM (line 98) | "100% detection of below-application-layer database tampering" is a universal claim over an unenumerated attack set; an actor with direct database access can rebuild the chain, and no fault-injection scope or detection window is defined. | Restate as detection of all tampering in a defined injection suite with stated row counts and tamper types. |
| VAL-016 | Major | FR-VV-001 (line 68), architecture (line 26), VTM (line 94) | MISRA C++:2023 is written against C++17 (ISO/IEC 14882:2017). The document commits the cores to C++17/C++20 and requires the rule set across all C++17/C++20 files, so part of the code cannot be checked and "Zero MISRA violations" is not achievable as specified. | Pin the safety-related cores to C++17 or define a documented deviation set for C++20 constructs. |
| VAL-017 | Minor | VTM (line 99) vs FR-DAT-002 (line 59) | The FR-DAT-007 row is labeled "HL7 FHIR R4 / SiLA 2 Gateway", but FR-DAT-007 says nothing about SiLA 2. SiLA 2 belongs to FR-DAT-002, which has no row. | Correct the row label and add an FR-DAT-002 row. |
| VAL-018 | Minor | VTM (line 99), Section 2.2 (line 31) | FR-DAT-007 is classified Not High Process Risk, where exploratory testing is permitted, yet its metric sets a numeric throughput gate (>100,000 pts/sec) borrowed from NFR-PERF-001, a requirement with no row of its own. | Move the throughput check to an NFR-PERF-001 row and keep the FR-DAT-007 metric to schema validity. |
| VAL-019 | Minor | FR-RTA-006 (line 54), VTM (line 96) | ">=70% payload compression" names no payload corpus or baseline. "Deterministic offline fallback" has no behavioral criterion. "Shrunk by 75%" has no baseline model, and the 8-bit quantized network has no accuracy floor. | Name the model, the corpus, the memory budget, and the post-quantization accuracy threshold. |
| VAL-020 | Minor | FR-VV-005 (line 72), VTM (line 100) | "Cryptographic forward and backward trace links" does not say what is hashed or signed, and "zero unlinked dead code" does not define dead code or name a tool. | Specify the trace-link hashing scheme and the dead-code analysis definition and tool. |
| VAL-021 | Minor | FR-DAT-003 (line 60) | The ALCOA+ expansion lists only the five original attributes. The "+" set (Complete, Consistent, Enduring, Available) is not stated, so compliance with ALCOA+ cannot be audited as written. | Enumerate all nine attributes and reference them in the FR-DAT-004 and FR-DAT-005 metrics. |
| VAL-022 | Minor | FR-MS-004 (line 42), VTM (line 91) | "At high frequencies" has no numeric target, and the only wrench publish frequency in the document (>=500 Hz) sits inside the FR-MS-002 row where it does not belong. | State the publish rate inside FR-MS-004 and give FR-MS-004 a VTM row. |
| VAL-023 | Minor | NFR-REL-001 (line 83) | "Zero unresolved SIGSEGV memory defects" states no measurement window and no definition of unresolved (open at release, or found during a soak run), and the requirement has no VTM row. | Define the window and instrumentation (for example a 24-hour run with sanitizers enabled) and add a row. |
| VAL-024 | Minor | FR-VV-001 (line 68) | "Guarantee freedom from interference" asks more of static analysis than the technique provides; freedom from interference requires partitioning and memory-isolation evidence at Class C. | Reword to the specific defect classes static analysis shall detect and add a partitioning requirement. |
| VAL-025 | Minor | Section 2.2 (lines 28-31) | The CSA risk partitioning and the IEC 62304 class both depend on hazard analysis, but no requirement links either one to a risk management file or an ISO 14971 process. | Add a requirement that ties both classifications to the risk management file, and reference it in the VTM. |

Totals: 4 Blocker, 12 Major, 9 Minor.

## Standards mapping review

IEC 62304 class levels (VAL-008): the header Class C statement (line 5) agrees with the Class C rows for FR-RTA-001 (line 94) and FR-RTA-006 (line 96), and Class C is a coherent choice for a safety filter that must prevent tissue injury. The mapping breaks at line 91 with the range "Class B/C" and at lines 92 and 100, which cite IEC 62304 with no class, because the standard requires one class per software item, assigned from risk analysis. A range and an absence are both unfinished assignments.

DO-178C DAL A (lines 5 and 94): DO-178C is an airborne software lifecycle standard, so citing it as a target standard for a surgical robot claims a certification context that does not exist for this device, and DAL A on line 94 with no DAL on line 95 leaves the intended rigor undefined. The citation is coherent only if the document says it borrows the DAL A objective set as an internal rigor tier mapped onto IEC 62304 Class C activities.

ISO 26262 ASIL D (line 95): ASIL D is a road-vehicle hazard integrity level, and applying it to the TA monitor in a medical device carries no standing in a submissions package; the citation also appears in one VTM row only, while the header standards list omits ISO 26262 entirely. Treat it the same way as DO-178C: remove it or document the mapping rationale and the row that justifies it.

MISRA C++:2023 (lines 5, 68, 94): the rule set is current for new safety-related C++ code and the paired tools (Parasoft C/C++test, QA-MISRA) can execute it, so the pairing is coherent. Two mismatches remain: MISRA C++:2023 targets C++17 while the document commits the cores to C++20 as well (VAL-016), and line 68's promise to "guarantee freedom from interference" claims a property that needs partitioning evidence rather than pattern, control-flow, and data-flow analysis (VAL-024).

ASAM XIL v3.0.0 ports (line 69): the four named ports match the published XIL port set, Model Access (MA), Electrical Error Simulation (EES), ECU Access, and Service-Oriented Access (SOC, added in v3.0.0), so the port names are correct and the version tag is right. The mapping is coherent; the gap is practical, since XIL originates in automotive test benches, the SOC port targets service-oriented middleware such as SOME/IP, and no XIL implementation or vendor framework is named anywhere in the document.

FMI 3.0 clocks and FMI-LS-BUS (lines 45 and 93): both citations check out, FMI 3.0 defines clocks and scheduled variable execution, and FMI-LS-BUS 1.0 (network communication over FMI 3.0) was released on 2025-07-21 by the FMI project. The problem sits with the metric rather than the citation, since the document demands zero quantization error (VAL-005) and names no FMI master tool, which leaves the project responsible for building the master itself.

21 CFR Part 11 sections (lines 60-62 and 97): the §11.10(e) audit-trail citation in FR-DAT-004 and in the VTM row is correct, the eCFR text of §11.10(e) covers secure, computer-generated, time-stamped audit trails for closed systems, so this citation passes. The gap sits with FR-DAT-006 (line 63), which describes access control and electronic signatures but cites no section, while limited system access falls under §11.10 and electronic signature controls fall under subpart C (§§11.100, 11.200, 11.300).

ALCOA+ (lines 60 and 97): the mapping direction is right for a WORM audit tier, but the acronym is expanded with the five original attributes only, so the "+" half of the claim (Complete, Consistent, Enduring, Available) is unverifiable as written (VAL-021).

SiLA 2 FDL (line 59): the Feature Definition Language is the correct SiLA 2 artifact for defining capabilities, and gRPC over HTTP/2 with Protobuf is the correct SiLA 2 transport, so FR-DAT-002 is coherent on the technology. The mismatch is structural: SiLA 2 appears in the header standard list (line 5), FR-DAT-002 has no VTM row, and the SiLA 2 label was placed on the FR-DAT-007 row instead (VAL-017).

HL7 FHIR R4 (lines 64 and 99): mapping surgical telemetry into Observation and DeviceMetric resources with fhir.resources on Pydantic v2 is the correct R4 pattern and matches the Gateway implementation, which is complete for FR-3.7.1 through FR-3.7.5. The mismatches are the row's SiLA 2 tag and the Not High Process Risk classification carrying a numeric throughput acceptance (VAL-017, VAL-018).

Header regulatory list (line 5): FDA QMSR with ISO 13485, and the 2026 CSA guidance with GAMP 5 2nd Edition, are current and coherent for a production and quality system software document; no mismatch found. EU Annex 11 appears once, in the FR-DAT-005 row (line 98), and is absent from the header list, which is a documentation inconsistency for an otherwise defensible mapping.

## Gateway cross-check

Comparison basis: `BioSync-Gateway\SRS.md` v1.1 and `REMAINING_WORK_v1.1.md` (re-audit 2026-07-28). That audit reports R1 (real Pulse Engine deployment) and R4 (engine-rebased qualification) CLOSED, R5 (EMA tolerance), R6 (dilution branches), R7 (LLM provider config) and R8 (PQ-1/PQ-3/PQ-4 qualification) CLOSED by fix or approved deviation, and R2 (database client-cert TLS) and R3 (relay performance) OPEN.

| SurgiTwin ID (line) | Gateway requirement or NFR | Gateway implementation status |
|:---|:---|:---|
| FR-DAT-001 (58) | Three-tier architecture, Section 2.1; FR-3.8.1-3.8.5 | Complete per Gateway v1.1 (scorecard marks FR-3.8.1-5 done; triggers and hash chain verified). The shared WebSocket relay path carries the OPEN R3 defect. |
| FR-DAT-002 (59) | None; SiLA 2 is absent from the Gateway SRS | Absent (new scope) |
| FR-DAT-003 (60) | FR-3.8.1, FR-3.8.3, NFR-S6 | Complete for append-only storage and SHA-256 chaining. The WORM label and the ALCOA+ wording are new. |
| FR-DAT-004 (61) | FR-3.8.1, FR-3.8.2, NFR-S1, OQ-7, OQ-8 | Complete for mutation rejection. The old/new value capture element has no Gateway counterpart and conflicts with the inherited trigger design (VAL-010), so that part is new and inconsistent. |
| FR-DAT-005 (62) | FR-3.8.3, FR-3.8.4, OQ-9, NFR-P4, PQ-3 | Complete (nightly chain recomputation implemented; PQ-3 promoted to a real 1M-row run under R8). |
| FR-DAT-006 (63) | FR-3.8.5, NFR-S2, NFR-S3 | Partially complete: JWT authentication with role scope and short token lifetime exist. Electronic signatures, inactivity lockout, and unique-credential enforcement are absent from the Gateway. |
| FR-DAT-007 (64) | FR-3.7.1-3.7.5 | Complete (FHIR persistence gap B6 closed; OQ-10 through OQ-12 present). The row's throughput gate depends on NFR-PERF-001, which inherits an OPEN Gateway item. |
| NFR-SEC-001 (82) | NFR-S2, NFR-S4, NFR-S5 | Partially complete. NFR-S5 is OPEN as R2: wiring exists but DB_SSLMODE defaults to prefer and server-side verify-full is not demonstrated. The OAuth element is new and unspecified. |
| NFR-PERF-001 (78) | NFR-P1 (>=100,000 points/sec) | Partially complete / unverified: Gateway marks NFR-P1 unverified under OPEN item R3 (uvloop not configured, synchronous database writes on the relay path). |
| NFR-PERF-002 (79) | NFR-P3 (50 ms WebSocket relay) | Partially complete / unverified: same OPEN R3 defect. The sub-10 ms MessagePack element is new. |
| NFR-PERF-004 (81) | NFR-P6 (>=500 concurrent sessions) | Partially complete / unverified: Gateway marks NFR-P6 unverified under OPEN R3. |

Requirements that inherit Gateway claims the Gateway itself left OPEN or deviated:

- NFR-PERF-001, NFR-PERF-002 (sub-50 ms half), and NFR-PERF-004 all restate Gateway NFR-P1, NFR-P3, and NFR-P6, which the Gateway marks unverified because R3 (uvloop plus synchronous writes on the WebSocket path) remains OPEN. SurgiTwin re-asserts the same numbers with tighter or equal bounds and no closure plan.
- NFR-SEC-001 restates Gateway NFR-S5 client-certificate isolation, which the Gateway marks partial under OPEN R2. FR-DAT-001's promise to build on that architecture inherits the same default `sslmode=prefer` behavior unless the new project specifies verify-full explicitly.
- FR-DAT-007's ">100,000 pts/sec" acceptance rides on NFR-PERF-001, which rides on the OPEN R3 relay path, so one open Gateway item propagates into two SurgiTwin requirements.
- NFR-PERF-003 (60 FPS, line 80) matches Gateway NFR-P2 and FR-3.1.2, which the Gateway marks addressed via LTTB downsampling but unverified under load. The Gateway also removed SciChart.js by approved deviation (ECharts only, chart-provider abstraction retained), so any plan that assumed the SciChart backend would carry a license cost and no existing implementation.
- FR-MS-006 (line 44) mirrors Gateway FR-3.6.2 (ProcessPoolExecutor delegation for the Pulse Engine), which the Gateway closed with the real engine qualified 19/19. That 19 is a test-case tally for four qualification files, and it is the most likely origin of the undefined "19 IQ/OQ/PQ validation protocols" in FR-VV-005 and NFR-REL-001 (VAL-002).

## Scope and feasibility notes

- FR-VV-001 (line 68) names Parasoft C/C++test and QA-MISRA. Both are commercial products, QA Systems sells QA-MISRA and Cantata under trial or paid licenses, and the requirement demands analysis on every commit, which needs a licensed seat in CI. No license, budget, or tool-selection precondition appears in the document.
- FR-VV-004 (line 71) names VectorCAST and Cantata, both proprietary, and demands 100% statement, branch and MC/DC coverage on High Process Risk modules. The document never enumerates which modules are High Process Risk beyond the prose categories in Section 2.2, so the coverage obligation has no defined scope.
- FR-VV-003 (line 70) commits to Speedgoat, dSPACE, or NI SLSC HIL targets and promises scripts run "without modification" on all of them. Each vendor sells its own XIL implementation and hardware, no lab or budget is stated, and a three-vendor portability guarantee cannot be met by the standard alone.
- FR-MS-005 (line 43) makes NVIDIA Omniverse / Isaac Sim a hard dependency of the rendering path. Runtime licensing, GPU class, USD pipeline version pinning, and the offline render node count are all unstated preconditions, and NFR-PERF-003's 60 FPS claim depends on that path.
- FR-RTA-004 (line 52) commits the project to a formally verified fallback controller with no verifier, prover, or analysis tool named (VAL-011), and no schedule allowance for the proof work.
- FR-MS-007 (line 45) requires every plant model to ship as an FMI 3.0 FMU with FMI-LS-BUS over Fast DDS. SOFA is not an FMI master and no FMI master tool is named, so the requirement obligates building a custom co-simulation master with clock-synchronization obligations, with no effort estimate.
- FR-RTA-006 (line 54) constrains an 8-bit quantized TFLM network to an ESP32-S3 with a "shrunk by 75%" claim against no baseline. Flash and RAM budgets, the model architecture, the dataset, and a post-quantization accuracy floor are all missing, so the requirement cannot be accepted or rejected at test time.
- NFR-PERF-001 through NFR-PERF-004 (lines 78-81) have no deployment target: no CPU/GPU classes, no network topology, no load-generation definition for "full telemetry load". The numbers are therefore aspirational until a test configuration section exists.
- FR-DAT-006 (line 63) requires legally bound electronic signatures, which presupposes identity proofing, credential issuance, and password or signature-coin controls under 21 CFR subpart C. No requirement defines any of those procedures.
- FR-DAT-002 (line 59) requires SiLA 2 servers but names no SiLA 2 SDK or code-generator, and FR-VV-002 (line 69) requires an ASAM XIL API in Python but names no XIL framework implementation. Both are tool selections that block Phase 1 test scaffolding.
- The document has no verification-protocol section at all, so the VTM is the only place a test could be recorded, which is the structural cause of VAL-001 and VAL-002.

## Verdict

The "Baseline Validated" label on line 4 does not hold as written. The document is a coherent draft of the intended system, its ID scheme is clean (31 IDs, no duplicates, no dangling VTM references), and most of its external standards citations are correct, but a baseline that has been validated must have a complete traceability path and testable acceptance criteria, and this one has a VTM that covers 10 of 31 requirements, leaves all six NFRs without a single verification row, misroutes the RTA envelope requirement onto the wrong ID, and carries two acceptance criteria (the 19-protocol pass rate and the zero-quantization-error claim) that cannot be executed as written. Before or during Phase 1, four things must be resolved: complete the VTM so every defined ID has a row with a measurable metric (VAL-001, VAL-003, VAL-004), publish the protocol register or drop the count of 19 (VAL-002), replace the untestable metrics with bounded, conditioned limits (VAL-005, VAL-007, VAL-014, VAL-015), and settle the classification and language-scope questions (one IEC 62304 class per item, a decision on DO-178C and ISO 26262, and C++17 versus C++20 under MISRA C++:2023). Two further items belong to Phase 1 planning rather than the document: the Gateway items R2 and R3 are still OPEN in the inherited architecture, and the proprietary tool licenses (Parasoft or QA-MISRA, VectorCAST, Cantata, Jama or Polarion), the HIL hardware (Speedgoat, dSPACE, NI SLSC), and the NVIDIA Omniverse runtime are preconditions the SRS commits to without stating them. Until the four document items are closed, the correct status for SRS.md v1.0.0 is "draft with open validation findings", not "Baseline Validated".
