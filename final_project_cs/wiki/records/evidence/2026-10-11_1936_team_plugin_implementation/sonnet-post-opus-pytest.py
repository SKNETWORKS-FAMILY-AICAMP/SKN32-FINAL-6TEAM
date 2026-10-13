"""Fixed synthetic regression command for read-only Claude review."""
import subprocess
import sys

TESTS = [
    "tests/unit/core/test_plugin_availability.py",
    "tests/unit/travel/test_dining_read_tool_availability.py",
    "tests/unit/test_project_composition.py",
    "tests/unit/test_plugin_composition_runtime.py",
    "tests/unit/travel/test_plugin_worker_availability.py",
    "tests/unit/travel/test_plugin_read_boundaries.py",
    "tests/integration/controller/test_unknown_route_availability.py",
    "tests/integration/controller/test_plugin_unavailable.py",
    "tests/integration/dining/test_catalog_state_plugin.py",
]
command = [sys.executable, "-m", "pytest", *TESTS, "-q", "--tb=short"]
print("FIXED_PYTEST_COMMAND=" + subprocess.list2cmdline(command), flush=True)
result = subprocess.run(command, check=False)
print("PYTEST_EXIT=" + str(result.returncode), flush=True)
sys.exit(result.returncode)
