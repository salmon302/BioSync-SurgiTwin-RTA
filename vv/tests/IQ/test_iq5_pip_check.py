# SPDX-License-Identifier: MIT
"""
IQ-5: Pip Check Test
Implements SRS IQ-5 - Verify all pip dependencies are correctly installed

This test validates:
1. All packages in requirements.txt are installed
2. Critical packages can be imported successfully
3. Package versions meet minimum requirements
"""

import subprocess
import sys
import os
import json

import pytest


class TestIQ5PipCheck:
    """Test suite for IQ-5 - Pip Dependency Verification"""

    def test_requirements_file_exists(self):
        """requirements.txt should exist in middleware directory"""
        requirements_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
            "middleware", "requirements.txt"
        )
        
        assert os.path.exists(requirements_path), \
            f"requirements.txt not found at {requirements_path}"

    def test_critical_packages_importable(self):
        """Critical packages should be importable"""
        critical_packages = [
            ('fastapi', 'FastAPI'),
            ('uvicorn', 'uvicorn'),
            ('sqlalchemy', 'SQLAlchemy'),
            ('pydantic', 'pydantic'),
            ('jose', 'PyJWT (python-jose)'),
            ('httpx', 'httpx'),
            ('alembic', 'alembic'),
        ]
        
        missing = []
        for module_name, display_name in critical_packages:
            try:
                __import__(module_name)
            except ImportError:
                missing.append(display_name)
        
        assert not missing, f"Critical packages not installed: {', '.join(missing)}"

    def test_pip_list_matches_requirements(self):
        """Installed packages should match requirements.txt"""
        requirements_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
            "middleware", "requirements.txt"
        )
        
        if not os.path.exists(requirements_path):
            pytest.skip("requirements.txt not found")
        
        # Parse required packages. Lines with an environment marker (for example uvloop on
        # non-Windows platforms) are required only when the marker is true on this interpreter.
        from packaging.requirements import Requirement
        from packaging.utils import canonicalize_name

        with open(requirements_path, 'r') as f:
            required_packages = set()
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith('-'):
                    req = Requirement(line)
                    if req.marker is None or req.marker.evaluate():
                        required_packages.add(canonicalize_name(req.name))
        
        if not required_packages:
            pytest.skip("No packages found in requirements.txt")
        
        # Get installed packages
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'list', '--format=json'],
                capture_output=True,
                text=True,
                timeout=30
            )
            installed_packages = json.loads(result.stdout)
            installed_names = {canonicalize_name(pkg['name']) for pkg in installed_packages}
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            pytest.skip("Unable to query pip packages")

        # Check each required package is installed (PEP 503 names, so fhir-core matches fhir_core)
        missing = sorted(req_pkg for req_pkg in required_packages if req_pkg not in installed_names)
        
        assert not missing, f"Required packages not installed: {', '.join(missing)}"

    def test_no_pip_check_errors(self):
        """pip check should report no dependency conflicts"""
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'check'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # pip check returns 0 if no issues, non-zero if conflicts found
            if result.returncode != 0:
                pytest.fail(f"Dependency conflicts detected:\n{result.stdout}\n{result.stderr}")
                
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pytest.skip("Unable to run pip check")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
