"""고정된 합성 unit 감사만 실행한다. DB·외부 서비스 시험을 추가하지 않는다."""
import subprocess
import sys

TESTS = [
    "tests/unit/travel/test_initial_retry_boundaries.py",
    "tests/unit/core/test_controller_resume_recovery.py",
    "tests/unit/travel/test_watch_recovery_race.py",
]
command = [sys.executable, "-m", "pytest", *TESTS, "-q", "--tb=short", "-o", "faulthandler_timeout=60"]
print("FIXED_PYTEST_COMMAND=" + subprocess.list2cmdline(command), flush=True)
result = subprocess.run(command, check=False)
print("PYTEST_EXIT=" + str(result.returncode), flush=True)
sys.exit(result.returncode)
