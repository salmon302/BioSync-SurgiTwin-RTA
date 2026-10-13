# Architecture Overview

SurgiTwin-RTA has four operational tiers. Each tier maps to one top-level directory.

| Tier | Directory | Role |
| :--- | :--- | :--- |
| Virtual Proving Ground (M&S) | `sim/` | Real-time FEM soft-tissue physics and physiology simulation |
| Run-Time Assurance (RTA) | `rta/` | C++ Simplex safety switch with timed automata monitoring |
| Compliance and Interoperability (Informatics) | `middleware/`, `database/`, `edge/`, `frontend/` | Telemetry gateway, audit store, edge bridge, visualization client |
| Continuous Verification (V&V) | `vv/` | ASAM XIL test harness, traceability, IQ/OQ/PQ tests |

## Data Flow

Simulation publishes tool-tip pose, tissue state, and wrench data. A primary controller, either a learned policy or a teleoperator, proposes commands. The RTA switch checks each command against the safety envelope and passes either the primary or the fallback command to the robot. The Informatics tier records each telemetry sample and each switch decision in the audit store, and the V&V tier replays these records against the requirements.

## Build Targets

* `rta/` builds by default through the top-level `CMakeLists.txt`.
* `sim/sofa`, `sim/fmi`, and `sim/bridge` are gated by `SRTA_BUILD_SOFA`, `SRTA_BUILD_FMI`, and `SRTA_BUILD_BRIDGE`, which default to OFF.
* `middleware/` runs with `python -m pytest middleware/tests` from the repo root.
