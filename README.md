# SurgiTwin-RTA

SurgiTwin-RTA is a closed-loop surgical soft-tissue digital twin and software-in-the-loop (SIL) and hardware-in-the-loop (HIL) verification platform. It simulates deformable organ resection, hepatic lesion ablation, and needle puncture, and it checks autonomous or teleoperated controllers against a Simplex run-time safety filter. Patient-facing data is recorded in a 21 CFR Part 11 audit store, and continuous verification runs on each commit.

## Tiers

* M&S tier: `sim/` (SOFA FEM, Pulse physiology, FMI 3.0, ROS 2 bridge node)
* RTA tier: `rta/` (C++17 Simplex switch, safety envelope, timed automata)
* Informatics tier: `middleware/` (FastAPI gateway, compliance API), `database/` (PostgreSQL 15+ WORM store), `edge/` (ESP32-S3 bridge), `frontend/` (React and WebGL client)
* V&V tier: `vv/` (ASAM XIL harness, traceability engine, IQ/OQ/PQ tests)

See `docs/architecture.md` for the data flow between tiers.

## Quickstart

These commands are placeholders for the current skeleton. Each stub reports no behavior beyond its smoke test.

C++ RTA tier:

```sh
cmake -S . -B build
cmake --build build
ctest --test-dir build --output-on-failure
```

Python middleware and V&V tests, run from the repo root:

```sh
python -m pip install -r middleware/requirements-test.txt
python -m pytest middleware/tests vv/tests
```

Docker stack (requires a populated `.env` copied from `.env.example`):

```sh
docker compose config -q
```

## Documentation

* `SRS.md`: system requirements baseline (v1.0.0)
* `DEVELOPMENT_PLAN.md`: phased development plan (added in a later commit)
* `docs/architecture.md`: four-tier overview
* `SNDEV/docs/`: contribution logs for conception and implementation work

## Status

Last updated 2026-11-12. The authoritative status is `DEVELOPMENT_PLAN.md`.

* Phase 2 (M&S tier) is in progress. Verification gates:
  * G2.1 Mesh ingestion: PASS with recorded boundaries (single patient, HCC_001)
  * G2.2 Solver rate: PASS with recorded boundaries (20 mm reference scene, placeholder material parameters)
  * G2.3 Contact: PASS with recorded boundaries (Liver 1 parameter set only)
  * G2.4 Wrench publish: PASS with recorded boundaries (synthetic trajectory source)
  * G2.5 Pulse worker: PASS
  * G2.6 Co-simulation: OPEN. The three-node run under the rebased VAL-033 clause is pending.
* Phase 3 (RTA tier) is not started. `rta/` contains stub thresholds, not clinical limits.

Contribution logs are in `SNDEV/docs/`, which is excluded from version control.
