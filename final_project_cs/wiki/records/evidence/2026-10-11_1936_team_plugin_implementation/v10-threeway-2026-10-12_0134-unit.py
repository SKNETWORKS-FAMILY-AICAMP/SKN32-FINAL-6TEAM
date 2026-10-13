"""읽기감사용 고정 합성 단위시험. 후보만 대상으로 DB/외부 API를 실행하지 않는다."""
from pathlib import Path
import os
import subprocess
import sys
root = Path(__file__).resolve().parents[4]
candidate = root / "legacy/deployment_candidates/2026-10-12_012943_plugin_v10"
tests = ["tests/unit/travel/test_fact_context.py", "tests/unit/travel/test_initial_retry_boundaries.py", "tests/unit/core/test_controller_resume_recovery.py"]
command = [sys.executable, "-m", "pytest", *tests, "-q", "--tb=short", "-p", "no:cacheprovider", "-o", "faulthandler_timeout=60"]
env = os.environ.copy()
env["PYTHONDONTWRITEBYTECODE"] = "1"
env["ACOP_MOBILITY_DATA_DIR"] = ""
print("CANDIDATE=legacy/deployment_candidates/2026-10-12_012943_plugin_v10", flush=True)
print("FIXED_PYTEST_COMMAND=" + subprocess.list2cmdline(command), flush=True)
result = subprocess.run(command, cwd=candidate, env=env, check=False)
print("PYTEST_EXIT=" + str(result.returncode), flush=True)
sys.exit(result.returncode)
