"""Fixed synthetic unit regressions for the final Sonnet delta audit."""
import subprocess
import sys

TESTS = ['tests/unit/travel/test_trip_api_plugin_boundaries.py', 'tests/unit/travel/test_intake_resolve_dining.py', 'tests/unit/travel/test_plugin_read_boundaries.py', 'tests/unit/travel/test_dining_read_tool_availability.py', 'tests/unit/test_project_composition.py', 'tests/unit/test_plugin_composition_runtime.py', 'tests/unit/travel/test_itinerary_checks.py', 'tests/unit/travel/test_intake_review_units.py', 'tests/unit/travel/test_plugin_worker_availability.py']
command = [sys.executable, "-m", "pytest", *TESTS, "-q", "--tb=short"]
print("FIXED_PYTEST_COMMAND=" + subprocess.list2cmdline(command), flush=True)
result = subprocess.run(command, check=False)
print("PYTEST_EXIT=" + str(result.returncode), flush=True)
sys.exit(result.returncode)
