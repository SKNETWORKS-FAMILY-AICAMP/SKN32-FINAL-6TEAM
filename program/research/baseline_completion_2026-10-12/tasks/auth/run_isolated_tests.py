"""독립 PostgreSQL 인스턴스에서 OAuth·MCP 회귀를 실행한다. 업무 DB는 연결하지 않는다."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import psycopg

sys.stdout.reconfigure(encoding="utf-8")
here = Path(__file__).resolve().parent
workspace = here.parents[4]
source = workspace / "program/research/migration_safety_2026-10-12/_runtime/postgres/bin"
assert (source / "postgres.exe").is_file(), "SQL 안전 시험에서 확보한 독립 PostgreSQL 바이너리가 필요합니다."
runtime = here / "_runtime"
runtime.mkdir(exist_ok=True)
cluster = runtime / "cluster"
flags = subprocess.CREATE_NO_WINDOW
if not cluster.exists():
    result = subprocess.run([str(source / "initdb.exe"), "-D", str(cluster), "-U", "oauth_test", "-A", "trust", "-E", "UTF8", "--no-locale"],
                            capture_output=True, text=True, creationflags=flags)
    (runtime / "initdb.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    result.check_returncode()
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
run_id = time.strftime("%Y%m%d_%H%M%S")
log = open(runtime / ("postgres-" + run_id + ".log"), "w", encoding="utf-8")
process = subprocess.Popen([str(source / "postgres.exe"), "-D", str(cluster), "-h", "127.0.0.1", "-p", str(port)],
                           stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
exit_code = 1
try:
    for _ in range(60):
        if process.poll() is not None:
            raise RuntimeError("시험 PostgreSQL 시작 실패: 비공개 runtime 로그를 확인하세요.")
        try:
            admin = psycopg.connect(host="127.0.0.1", port=port, user="oauth_test", dbname="postgres", autocommit=True, connect_timeout=1)
            break
        except psycopg.OperationalError:
            time.sleep(.25)
    else:
        raise RuntimeError("시험 PostgreSQL 시작 시간 초과")
    dbname = "personal_ai_isolated_" + run_id
    admin.execute('CREATE DATABASE "' + dbname + '"')
    env = os.environ.copy()
    env["ACOP_DATABASE_URL"] = f"postgresql+psycopg://oauth_test@127.0.0.1:{port}/{dbname}"
    env["ACOP_OAUTH_TEST_ISOLATED"] = "1"
    env["PYTHONPATH"] = str(workspace / "program/research/migration_safety_2026-10-12/_deps")
    env["TEMP"] = env["TMP"] = str(runtime)
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    migrate = subprocess.run([sys.executable, "-m", "app.infrastructure.db.migrate"], cwd=workspace / "final_project_cs", env=env,
                             capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=flags)
    (here / ("migration-" + run_id + ".log")).write_text(migrate.stdout + migrate.stderr, encoding="utf-8")
    migrate.check_returncode()
    seed = subprocess.run([sys.executable, "-m", "scripts.register_prompts"], cwd=workspace / "final_project_cs", env=env,
                          capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=flags)
    (here / ("seed-" + run_id + ".log")).write_text(seed.stdout + seed.stderr, encoding="utf-8")
    seed.check_returncode()
    args = [arg for arg in sys.argv[1:] if arg != "--with-dod"] or ["tests/security/test_personal_ai_oauth.py", "tests/e2e/test_personal_ai_oauth_db.py",
                          "tests/e2e/test_mcp_server.py", "tests/e2e/test_web_agent_keys.py"]
    command = [sys.executable, "-m", "pytest", *args, "-q", "--tb=short", "--basetemp=" + str(here / ("tmp-" + run_id)),
               "--junitxml=" + str(here / ("isolated-" + run_id + ".xml"))]
    result = subprocess.run(command, cwd=workspace / "final_project_cs", env=env, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", creationflags=flags)
    (here / ("isolated-" + run_id + ".log")).write_text(result.stdout + result.stderr, encoding="utf-8")
    print(result.stdout, flush=True)
    exit_code = result.returncode
    dod_code = None
    if "--with-dod" in sys.argv:
        dod = subprocess.run([sys.executable, "-m", "scripts.verify_dod_v11"], cwd=workspace / "final_project_cs", env=env,
                             capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=flags)
        (here / ("dod-" + run_id + ".log")).write_text(dod.stdout + dod.stderr, encoding="utf-8")
        print(dod.stdout, flush=True)
        dod_code = dod.returncode
        exit_code = exit_code or dod_code
    admin.execute('DROP DATABASE "' + dbname + '" WITH (FORCE)')
    admin.close()
    (here / ("runtime-" + run_id + ".json")).write_text(json.dumps({"scope": "task-owned loopback-only independent PostgreSQL",
        "exit_code": exit_code, "pytest_exit_code": result.returncode, "dod_exit_code": dod_code,
        "test_database_dropped": True, "command": command}, ensure_ascii=False, indent=2), encoding="utf-8")
finally:
    stopped = subprocess.run([str(source / "pg_ctl.exe"), "-D", str(cluster), "-m", "fast", "-w", "stop"],
        capture_output=True, text=True, creationflags=flags, timeout=30)
    process.wait(timeout=30)
    log.close()
    (here / ("stop-" + run_id + ".json")).write_text(json.dumps({"exit_code": stopped.returncode, "stopped": process.poll() is not None}))
sys.exit(exit_code)
