"""요식 확인기를 한 번에 띄운다.

DB 가 떠 있는지 보고, 안 떠 있으면 켜고, 확인기를 띄우고 브라우저를 연다.
파이참에서 이 파일 하나만 실행해도 되게 만들었다. 인자도 필요 없다.

    python scripts/dining/dev_up.py

    --no-browser   브라우저를 열지 않는다
    --port 8012    다른 자리에 띄운다
    --check        띄우지 않고 무엇이 준비됐는지만 본다

DB 를 못 켜면 켜지 못한 이유를 말하고 멈춘다. 반쯤 뜬 채로 두지 않는다.
"""
from __future__ import annotations

import argparse
import glob
import os
import socket
import subprocess
import sys
import time
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))          # final_project_cs
REPO = os.path.dirname(ROOT)                           # 저장소 뿌리

#: 여기 쓴 값은 이 PC 의 설정이다. 환경변수로 덮을 수 있다.
PG_PORT = int(os.environ.get("DINING_PG_PORT", "5433"))
PG_DATA = os.environ.get("DINING_PG_DATA",
                         os.path.join(os.path.dirname(REPO), "pgdata"))
DB_NAME = os.environ.get("DINING_DB", "dining_dev")
DB_USER = os.environ.get("DINING_DB_USER", "postgres")

#: pg_ctl 이 있을 만한 자리. 먼저 찾히는 것을 쓴다.
PG_BIN_HINTS = [
    os.path.join(os.path.expanduser("~"), "anaconda3", "envs", "*", "Library", "bin"),
    os.path.join(os.path.expanduser("~"), "miniconda3", "envs", "*", "Library", "bin"),
    os.path.join(os.path.expanduser("~"), "anaconda3", "Library", "bin"),
    r"C:\Program Files\PostgreSQL\*\bin",
]


def say(mark: str, text: str) -> None:
    print(f"  {mark} {text}")


def find_exe(name: str) -> str | None:
    """PATH 를 먼저 보고, 없으면 흔한 자리를 뒤진다."""
    from shutil import which
    got = which(name)
    if got:
        return got
    exe = name + (".exe" if os.name == "nt" else "")
    for pattern in PG_BIN_HINTS:
        for folder in glob.glob(pattern):
            candidate = os.path.join(folder, exe)
            if os.path.isfile(candidate):
                return candidate
    return None


def port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.7) -> bool:
    with socket.socket() as s:
        s.settimeout(timeout)
        return s.connect_ex((host, port)) == 0


def server_ready() -> bool:
    """자리가 열린 것과 답할 수 있는 것은 다르다.

    PostgreSQL 은 복구를 하는 동안에도 포트부터 연다. 그때 붙으면
    「the database system is starting up」 으로 거절당한다.
    컴퓨터를 껐다 켠 직후에는 거의 늘 이 상태를 거친다.
    """
    if not port_open(PG_PORT):
        return False

    ready = find_exe("pg_isready")
    if ready:
        # 0 준비됨, 1 아직 거절, 2 응답 없음
        done = subprocess.run([ready, "-h", "127.0.0.1", "-p", str(PG_PORT), "-q"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              stdin=subprocess.DEVNULL)
        return done.returncode == 0

    try:
        import psycopg
        with psycopg.connect(
                f"postgresql://{DB_USER}@localhost:{PG_PORT}/postgres",
                connect_timeout=3):
            return True
    except Exception:                                   # noqa: BLE001
        return False


def wait_ready(seconds: float = 60.0) -> bool:
    """답할 수 있을 때까지 기다린다. 복구가 길면 그만큼 걸린다."""
    said = False
    deadline = time.time() + seconds
    while time.time() < deadline:
        if server_ready():
            say("OK", "PostgreSQL 떴다")
            return True
        waited = seconds - (deadline - time.time())
        if waited > 5 and not said:
            # 오래 걸리면 멈춘 것처럼 보인다. 무엇을 기다리는지 말해 준다.
            say("..", "복구 중이라 조금 걸린다")
            said = True
        time.sleep(0.5)
    return False


def start_postgres() -> bool:
    """떠 있으면 그대로 두고, 아니면 켠다. 켜지 못하면 False."""
    if server_ready():
        say("OK", f"PostgreSQL 이 이미 {PG_PORT} 에 떠 있다")
        return True

    if port_open(PG_PORT):
        # 이미 떠 있는데 아직 복구 중이다. 새로 켜려 들면 안 된다.
        say("..", "PostgreSQL 이 기동 중이다. 기다린다")
        return wait_ready()

    pg_ctl = find_exe("pg_ctl")
    if not pg_ctl:
        say("!!", "pg_ctl 을 찾지 못했다. DINING_PG_DATA 와 PATH 를 확인해라")
        return False
    if not os.path.isdir(PG_DATA):
        say("!!", f"자료 폴더가 없다: {PG_DATA}")
        return False

    say("..", f"PostgreSQL 을 켠다 ({PG_PORT})")
    log = os.path.join(PG_DATA, "server.log")
    note = os.path.join(PG_DATA, "pg_ctl_last.txt")

    # pg_ctl 의 말을 파이프가 아니라 파일로 받는다.
    # 파이프로 받으면 자식인 postgres 가 그 파이프를 계속 물고 있어서
    # pg_ctl 이 끝난 뒤에도 이쪽이 영영 기다린다. 서버는 떠 있는데 화면은 멈춘다.
    with open(note, "w", encoding="utf-8", errors="replace") as sink:
        proc = subprocess.Popen(
            [pg_ctl, "-D", PG_DATA, "-o", f"-p {PG_PORT}", "-l", log, "start"],
            stdout=sink, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)

    # pg_ctl 은 먼저 돌아오고 서버가 뒤늦게 자리를 잡는다.
    # 기다리는 기준은 pg_ctl 이 끝났는지도, 자리가 열렸는지도 아니고
    # 물음에 답할 수 있는지다.
    if wait_ready():
        return True

    proc.terminate()
    say("!!", "PostgreSQL 이 뜨지 않았다")
    try:
        for line in open(note, encoding="utf-8", errors="replace").read().splitlines():
            if line.strip():
                say("  ", line.strip())
    except OSError:
        pass
    say("  ", f"자세한 것은 {log}")
    return False


def dsn() -> str:
    return os.environ.get(
        "DINING_DSN", f"postgresql://{DB_USER}@localhost:{PG_PORT}/{DB_NAME}")


def check_data() -> bool:
    """원장이 준비됐는지 본다. 비어 있어도 띄우기는 한다."""
    try:
        import psycopg
    except ImportError:
        say("!!", "psycopg 가 없다.  pip install \"psycopg[binary]==3.3.4\"")
        return False
    try:
        with psycopg.connect(dsn(), connect_timeout=5) as conn, conn.cursor() as cur:
            cur.execute("SELECT to_regclass('dining.dn_place')")
            if cur.fetchone()[0] is None:
                say("!!", f"{DB_NAME} 에 dining 스키마가 없다. 마이그레이션을 먼저 돌려라")
                say("  ", "app/infrastructure/db/migrations/020~026 을 차례로")
                return False
            cur.execute("SELECT count(*) FROM dining.dn_place")
            places = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM dining.v_hours_rule_active")
            rules = cur.fetchone()[0]
            cur.execute("SELECT to_regclass('dining.dn_live_check')")
            live = cur.fetchone()[0] is not None
    except Exception as exc:                            # noqa: BLE001
        say("!!", f"{DB_NAME} 에 붙지 못했다: {str(exc).splitlines()[0]}")
        return False

    if places == 0:
        say("!!", "장소가 0건이다. 적재를 먼저 해라 (make_load_sql.py)")
        return False
    say("OK", f"원장 {places}곳, 영업규칙 {rules}건")
    if not live:
        say("!!", "026 을 아직 안 돌렸다. 현장 확인 칸이 비어 보인다")
    return True


def serve(port: int, open_browser: bool) -> int:
    try:
        import uvicorn
    except ImportError:
        say("!!", "uvicorn 이 없다.  pip install -r requirements.txt")
        return 1

    if port_open(port):
        say("!!", f"{port} 가 이미 쓰이고 있다. --port 로 다른 자리를 골라라")
        return 1

    # uvicorn 이 scripts.dining.inspect_app 을 찾으려면 여기가 기준이어야 한다.
    os.chdir(ROOT)
    sys.path.insert(0, ROOT)
    os.environ.setdefault("DINING_DSN", dsn())
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    url = f"http://127.0.0.1:{port}"
    say("OK", f"확인기 {url}")
    print()
    print(f"  브라우저에서 {url} 을 열어라. 끝낼 때는 Ctrl+C.")
    print()
    if open_browser:
        # reload 를 쓰면 자식 과정이 다시 뜨므로 여기서 한 번만 연다.
        webbrowser.open(url)

    uvicorn.run("scripts.dining.inspect_app:app", host="127.0.0.1",
                port=port, reload=True, log_level="warning")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="요식 확인기를 한 번에 띄운다.")
    ap.add_argument("--port", type=int, default=8011)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--check", action="store_true", help="띄우지 않고 준비 상태만 본다")
    args = ap.parse_args()

    print("요식 확인기")
    if not start_postgres():
        return 1
    ready = check_data()
    if args.check:
        return 0 if ready else 1
    if not ready:
        say("..", "준비가 덜 됐지만 그대로 띄운다. 화면이 비어 보일 수 있다")
    try:
        return serve(args.port, not args.no_browser)
    except KeyboardInterrupt:
        print("\n  끝냈다. PostgreSQL 은 계속 떠 있다.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
