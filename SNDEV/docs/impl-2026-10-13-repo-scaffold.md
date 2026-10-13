Title: SurgiTwin-RTA repository scaffold
Date: 2026-10-13T22:09:49Z
Author: Seth Nenninger (MiMo-V2.6-Pro Agent)
Contribution Type: Implementation
Ticket/Context: ad-hoc (repo preparation for initial development)
Summary: Creates the four-tier directory skeleton, build stubs, CI workflow, and repo layout IQ test for SurgiTwin-RTA.

## Task Reference

Repo preparation instruction from the parent session. Scope is limited to the directory `I:\Documents\GitHub\BioSync\BioSync-SurgiTwin-RTA`. The neighboring `BioSync-Gateway` repo is read-only reference for house conventions.

Step 1 committed `SRS.md` alone as `docs(srs): add SurgiTwin-RTA SRS v1.0.0 baseline`.

## Specification Summary

Create the repository skeleton for the four operational tiers defined in SRS.md Section 1.2:

* M&S tier: `sim/` with SOFA, Pulse, FMI, and bridge subdirectories
* RTA tier: `rta/` with C++17 Simplex envelope, switch, and timed automata stubs and a CTest smoke test
* Informatics tier: `middleware/` with a FastAPI `/health` stub and pytest smoke test
* V&V tier: `vv/` with XIL, traceability, and IQ/OQ/PQ test directories

Also create top-level README, .gitignore, .env.example, docker-compose.yml, CI workflow, and docs/architecture.md. Do not create DEVELOPMENT_PLAN.md or docs/migration-map.md, and do not touch SNDEV/docs/impl-2026-10-13-srs-baseline-validation.md.

## Implementation Notes

### File tree created

```
BioSync-SurgiTwin-RTA/
├── README.md
├── .gitignore
├── .env.example
├── docker-compose.yml
├── CMakeLists.txt
├── .github/workflows/ci.yml
├── docs/architecture.md
├── sim/            README.md, sofa/ (README.md, CMakeLists.txt), pulse/README.md,
│                   fmi/ (README.md, CMakeLists.txt), bridge/ (README.md, CMakeLists.txt)
├── rta/            CMakeLists.txt, include/rta/{safety_envelope,simplex_switch,timed_automata}.h,
│                   src/{safety_envelope,simplex_switch,timed_automata}.cpp, tests/test_smoke.cpp
├── middleware/     api/main.py, requirements.txt, requirements-test.txt, tests/test_smoke.py, Dockerfile
├── edge/README.md
├── frontend/README.md
├── vv/             README.md, xil/README.md, traceability/README.md,
│                   tests/IQ/test_iq0_repo_layout.py, tests/OQ/.gitkeep, tests/PQ/.gitkeep
├── database/       README.md, init/.gitkeep
└── SNDEV/          docs/ (this log), scripts/.gitkeep, logs/.gitkeep
```

Design notes:

* `rta/` builds by default. `sim/sofa`, `sim/fmi`, and `sim/bridge` build only with `SRTA_BUILD_SOFA`, `SRTA_BUILD_FMI`, or `SRTA_BUILD_BRIDGE` set to ON.
* `rta/` stubs use stub thresholds (min tool-tip distance 5.0 mm, max wrench 2.0 N). They are placeholders, not clinical limits.
* No FetchContent, npm install, or pip install ran as part of the build files. CI installs `middleware/requirements-test.txt` at CI time.
* Python pins in `middleware/requirements.txt` were chosen without a network index lookup. Versions are unverified against PyPI and must be checked before the first install on the 3.11 target.
* `database/init/` is mounted into postgres as an init directory. It is empty until the pgcrypto script is added.

### Verification

Environment: Windows, CMake on PATH, MSVC 19.44 (Visual Studio 17 2022 generator), Python 3.14 at C:\Python314, Docker CLI present.

1. C++ build and CTest: PASS
   * Command: `cmake -S . -B build`, then `cmake --build build --config Release`, then `ctest --test-dir build -C Release --output-on-failure`
   * Configure, build of `srta_rta`, `srta_rta_test_smoke`, and test run completed without errors.
   * CTest output: `Test #1: rta_smoke ... Passed`, `100% tests passed, 0 tests failed out of 1`.
2. Python tests: PASS
   * Command: `python -m pytest middleware/tests vv/tests -q`, run from repo root with no installation step.
   * Output: `52 passed in 0.53s`. This covers the 2 middleware smoke tests and the 50 IQ layout checks (21 directories and 29 files).
   * Interpreter is Python 3.14, not the 3.11 target. Python 3.11 is not verified here.
3. Docker Compose config: PASS
   * `POSTGRES_PASSWORD` set to a dummy value for this check only: `docker compose config -q` exit 0.
   * `POSTGRES_PASSWORD` unset: exit 15 with "POSTGRES_PASSWORD is missing a value". This is the intended failure guard for the required variable.
4. GitHub Actions workflow: not run. Only local equivalents were executed.
5. Git status: `build/` is gitignored. Generated `__pycache__` and `.pytest_cache` are gitignored.
