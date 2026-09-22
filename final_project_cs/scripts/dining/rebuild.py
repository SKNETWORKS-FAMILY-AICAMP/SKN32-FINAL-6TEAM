"""빈 DB 에서 요식 원장을 처음부터 세운다.

왜 필요한가.
    명령이 README 에 흩어져 있어서 순서가 맞는지 확인된 적이 없다.
    새 사람이 저장소를 받아 돌렸을 때 되는지도 모른다.
    한 번에 세워 보는 것이 「우리 것이 잘 돈다」의 진짜 시험이다.

무엇을 하는가.
    1  마이그레이션을 번호 순으로
    2  원문을 구조로 (parse_hours)
    3  적재 (load · holiday · attribute)
    4  정답셋과 검수 반영 (truth · operator)
    5  채점하고 결과를 보인다

코어 표가 없어도 된다.
    022 만 코어 `places` 를 참조한다. 없으면 건너뛴다.
    매칭기는 코어 DB 에 얹을 때만 필요하고, 원장 자체는 혼자 선다.

    python scripts/dining/rebuild.py                 dining_rebuild 에 세운다
    python scripts/dining/rebuild.py --db dining_dev --keep   있는 DB 위에
    python scripts/dining/rebuild.py --check         세우지 않고 준비물만 본다
"""
from __future__ import annotations

import argparse
import glob
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))          # final_project_cs
MIGRATIONS = os.path.join(ROOT, "app", "infrastructure", "db", "migrations")
BUILD = os.path.join(ROOT, "data", "dining", "_build")

PG_PORT = int(os.environ.get("DINING_PG_PORT", "5433"))
PG_USER = os.environ.get("DINING_DB_USER", "postgres")

#: 번호로 고르지 않는다. 030 을 더했을 때 02* 패턴이 못 잡아 적재가 깨졌다.
#: 요식 파일인지로 고르면 번호가 늘어도 따라온다.

#: 코어 `places` 표가 있어야 올라가는 것. 없으면 건너뛴다.
NEEDS_CORE = {"022_dining_matcher.sql"}

#: 만드는 것과 넣는 것의 짝. 순서가 곧 의존 관계다.
LOADS = [
    ("parse_hours.py",        None),
    ("make_load_sql.py",      "load_200.sql"),
    ("make_holiday_sql.py",   "holidays.sql"),
    ("make_attribute_sql.py", "attributes.sql"),
    ("make_truth_sql.py",     "truth.sql"),
    ("make_operator_sql.py",  "operator.sql"),
]


def say(mark: str, text: str) -> None:
    print(f"  {mark} {text}", flush=True)


def find_exe(name: str) -> str | None:
    from shutil import which
    got = which(name)
    if got:
        return got
    exe = name + (".exe" if os.name == "nt" else "")
    for pattern in (os.path.join(os.path.expanduser("~"), "anaconda3", "envs", "*", "Library", "bin"),
                    os.path.join(os.path.expanduser("~"), "miniconda3", "envs", "*", "Library", "bin"),
                    r"C:\Program Files\PostgreSQL\*\bin"):
        for folder in glob.glob(pattern):
            candidate = os.path.join(folder, exe)
            if os.path.isfile(candidate):
                return candidate
    return None


PSQL = find_exe("psql")


def run_sql(db: str, path: str | None = None, sql: str | None = None,
            stop_on_error: bool = True) -> tuple[bool, str]:
    """psql 로 돌린다. 한글은 파일로만 넘긴다 — -c 로 넘기면 인코딩이 깨진다."""
    env = dict(os.environ, PGCLIENTENCODING="UTF8", PGUSER=PG_USER)
    cmd = [PSQL, "-p", str(PG_PORT), "-d", db, "-q"]
    if stop_on_error:
        cmd += ["-v", "ON_ERROR_STOP=1"]
    if path:
        cmd += ["-f", path]
    else:
        cmd += ["-c", sql]
    done = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env, stdin=subprocess.DEVNULL)
    return done.returncode == 0, (done.stdout or "") + (done.stderr or "")


def run_py(script: str) -> tuple[bool, str]:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    done = subprocess.run([sys.executable, os.path.join(HERE, script)],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=ROOT, env=env,
                          stdin=subprocess.DEVNULL)
    return done.returncode == 0, (done.stdout or "") + (done.stderr or "")


def has_core_places(db: str) -> bool:
    ok, out = run_sql(db, sql="SELECT to_regclass('public.places')")
    return ok and "places" in out


def check() -> bool:
    ready = True
    if PSQL is None:
        say("!!", "psql 을 찾지 못했다")
        ready = False
    else:
        say("OK", f"psql {PSQL}")
    files = sorted(glob.glob(os.path.join(MIGRATIONS, "[0-9]*_dining_*.sql")))
    say("OK" if files else "!!", f"마이그레이션 {len(files)}개")
    for script, _ in LOADS:
        path = os.path.join(HERE, script)
        if not os.path.isfile(path):
            say("!!", f"없는 스크립트 {script}")
            ready = False
    data = os.path.join(ROOT, "data", "dining")
    for name in ("tourapi_음식점_소개정보.json", "tourapi_서울_음식점_목록.json",
                 "holidays_2026_2027.json"):
        if not os.path.isfile(os.path.join(data, name)):
            say("!!", f"없는 원본 {name}")
            ready = False
    if os.path.isfile(os.path.join(data, "truth", "대조표100_검수_2026-09-21.csv")):
        say("OK", "검수 대조표 있음")
    else:
        say("!!", "검수 대조표가 없다. 정답셋 단계가 비게 된다")
    return ready


def main() -> int:
    ap = argparse.ArgumentParser(description="빈 DB 에서 요식 원장을 세운다.")
    ap.add_argument("--db", default="dining_rebuild")
    ap.add_argument("--keep", action="store_true", help="있는 DB 를 지우지 않는다")
    ap.add_argument("--check", action="store_true", help="세우지 않고 준비물만 본다")
    args = ap.parse_args()

    print("요식 원장 세우기")
    if not check():
        return 1
    if args.check:
        return 0

    started = time.time()

    if not args.keep:
        # 지우고 다시 만든다. 남은 것 위에 얹으면 「처음부터」가 아니다.
        ok, out = run_sql("postgres", sql=f'DROP DATABASE IF EXISTS "{args.db}"')
        if not ok:
            say("!!", f"{args.db} 를 지우지 못했다. 누가 쓰고 있을 수 있다")
            say("  ", out.strip().splitlines()[0] if out.strip() else "")
            return 1
        run_sql("postgres", sql=f'CREATE DATABASE "{args.db}"')
        say("OK", f"{args.db} 새로 만들었다")
    else:
        run_sql("postgres", sql=f'CREATE DATABASE "{args.db}"', stop_on_error=False)
        say("OK", f"{args.db} 위에 얹는다")

    core = has_core_places(args.db)
    say("OK" if core else "..",
        "코어 places 있음 — 매칭기도 올린다" if core else
        "코어 places 없음 — 022 매칭기는 건너뛴다")

    for path in sorted(glob.glob(os.path.join(MIGRATIONS, "[0-9]*_dining_*.sql"))):
        name = os.path.basename(path)
        if name in NEEDS_CORE and not core:
            say("..", f"{name} 건너뜀")
            continue
        ok, out = run_sql(args.db, path=path)
        if not ok:
            say("!!", f"{name} 실패")
            for line in out.strip().splitlines()[:6]:
                say("  ", line)
            return 1
        say("OK", name)

    for script, produced in LOADS:
        ok, out = run_py(script)
        if not ok:
            say("!!", f"{script} 실패")
            for line in out.strip().splitlines()[-6:]:
                say("  ", line)
            return 1
        tail = [l for l in out.strip().splitlines() if l.strip()]
        say("OK", f"{script}  {tail[-2] if len(tail) > 1 else ''}".rstrip())
        if produced:
            sql_path = os.path.join(BUILD, produced)
            ok, out = run_sql(args.db, path=sql_path)
            if not ok:
                say("!!", f"{produced} 적재 실패")
                for line in out.strip().splitlines()[:6]:
                    say("  ", line)
                return 1
            say("OK", f"  {produced} 적재")

    env = dict(os.environ, PYTHONIOENCODING="utf-8",
               DINING_DSN=f"postgresql://{PG_USER}@localhost:{PG_PORT}/{args.db}")
    done = subprocess.run([sys.executable, os.path.join(HERE, "run_quality.py")],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=ROOT, env=env,
                          stdin=subprocess.DEVNULL)
    print()
    print(done.stdout.strip())
    if done.returncode != 0:
        say("!!", "채점 실패")
        return 1

    print()
    say("OK", f"{time.time() - started:.0f}초 걸렸다")
    print()
    print(f"  확인기로 보려면:  python scripts/dining/dev_up.py")
    print(f"  다른 DB 를 보려면 DINING_DB={args.db} 를 함께 준다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
