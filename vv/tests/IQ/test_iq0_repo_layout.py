# SPDX-License-Identifier: MIT
import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]

REQUIRED_DIRECTORIES = [
    "sim/sofa",
    "sim/pulse",
    "sim/fmi",
    "sim/bridge",
    "rta/include/rta",
    "rta/src",
    "rta/tests",
    "middleware/api",
    "middleware/tests",
    "edge",
    "frontend",
    "vv/xil",
    "vv/traceability",
    "vv/tests/IQ",
    "vv/tests/OQ",
    "vv/tests/PQ",
    "database",
    "docs",
    "SNDEV/docs",
    "SNDEV/scripts",
    "SNDEV/logs",
]

REQUIRED_FILES = [
    "README.md",
    "SRS.md",
    "LICENSE",
    ".gitignore",
    ".env.example",
    "docker-compose.yml",
    "CMakeLists.txt",
    "docs/architecture.md",
    "sim/README.md",
    "rta/CMakeLists.txt",
    "rta/include/rta/safety_envelope.h",
    "rta/include/rta/simplex_switch.h",
    "rta/include/rta/timed_automata.h",
    "rta/src/safety_envelope.cpp",
    "rta/src/simplex_switch.cpp",
    "rta/src/timed_automata.cpp",
    "rta/tests/test_smoke.cpp",
    "middleware/api/main.py",
    "middleware/requirements.txt",
    "middleware/requirements-test.txt",
    "middleware/tests/test_smoke.py",
    "middleware/Dockerfile",
    "edge/README.md",
    "frontend/README.md",
    "vv/README.md",
    "vv/xil/README.md",
    "vv/traceability/README.md",
    "database/README.md",
    ".github/workflows/ci.yml",
]


@pytest.mark.parametrize("relative", REQUIRED_DIRECTORIES)
def test_required_directory_exists(relative):
    assert (REPO_ROOT / relative).is_dir(), f"missing directory: {relative}"


@pytest.mark.parametrize("relative", REQUIRED_FILES)
def test_required_file_exists(relative):
    assert (REPO_ROOT / relative).is_file(), f"missing file: {relative}"
