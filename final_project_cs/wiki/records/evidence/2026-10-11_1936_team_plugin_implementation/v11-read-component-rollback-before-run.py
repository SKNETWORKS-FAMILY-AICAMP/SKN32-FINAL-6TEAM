"""읽기감사용 고정 합성 단위시험. 후보만 대상으로 DB/외부 API를 실행하지 않는다."""
from pathlib import Path
import os
import subprocess
import sys
root = Path(__file__).resolve().parents[4]
candidate = root / "legacy/deployment_candidates/2026-10-12_015017_plugin_v11"
command = [sys.executable, str(root / "wiki/records/evidence/2026-10-11_1936_team_plugin_implementation/v11-read-component-rollback-before.py")]

env = {k:v for k,v in os.environ.items() if not k.startswith("ACOP_")}
# 명시적 합성 설정: 후보의 실제 환경파일/키를 읽지 않고 Settings 생성 조건만 만족한다.
env.update({
    "ACOP_DATABASE_URL":"postgresql://synthetic:synthetic@127.0.0.1:1/synthetic",
    "ACOP_OPENAI_API_KEY":"synthetic-not-a-real-api-key",
    "ACOP_LLM_MODEL":"synthetic-unit-model",
    "ACOP_EMBEDDING_MODEL":"synthetic-unit-embedding",
    "ACOP_TENANT_ID":"travel-synthetic-audit",
    "ACOP_SECRET_KEY":"synthetic-unit-secret-32-characters-only",
    "ACOP_COMPOSER_JWT_SECRET":"synthetic-unit-jwt-32-characters-only",
    "ACOP_COMPOSER_ISSUER_SECRET":"synthetic-unit-issuer-32-characters-only",
})
env["PYTHONDONTWRITEBYTECODE"] = "1"
env["ACOP_MOBILITY_DATA_DIR"] = ""
print("CANDIDATE=legacy/deployment_candidates/2026-10-12_015017_plugin_v11", flush=True)
print("FIXED_PYTEST_COMMAND=" + subprocess.list2cmdline(command), flush=True)
result = subprocess.run(command, cwd=candidate, env=env, check=False)
print("PYTEST_EXIT=" + str(result.returncode), flush=True)
sys.exit(result.returncode)
