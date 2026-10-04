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

코어도 함께 세운다.
    요식 표는 코어 `places` 와 이어져야 쓸모가 있다(dn_core_place_link).
    그래서 먼저 코어 마이그레이션과 여행 시드를 올리고, 그 위에 요식을 얹은 뒤
    매칭기(022)로 코어 장소와 잇는다. develop CI 가 세우는 순서와 같다.
    코어 설정값은 CI 와 같은 가짜로 채운다. 이미 환경에 있으면 그 값을 쓴다.
    코어를 못 세우면 요식만 세우고 연결은 건너뛴다. 원장 자체는 혼자 선다.

    python scripts/dining/rebuild.py                 dining_rebuild 에 세운다
    python scripts/dining/rebuild.py --db dining_dev --keep   있는 DB 위에
    python scripts/dining/rebuild.py --no-core       요식만 세운다
    python scripts/dining/rebuild.py --check         세우지 않고 준비물만 본다
    python scripts/dining/rebuild.py --db acop --target core   코어 DB 의 요식 칸만 다시 채운다

코어 DB 에 채울 때(--target core).
    DB 를 지우지 않는다. 여행 · 고객 · 다른 팀 표가 같은 DB 에 있다.
    코어 마이그레이션과 시드도 다시 돌리지 않는다. 코어는 코어가 세운다.
    dining 스키마만 지우고(요식 표 · 함수 · 코어 장소 연결) 같은 순서로 다시 채운 뒤 코어 장소와 다시 잇는다.
    코어 표는 dining 을 참조하지 않는다. 그래서 dining 만 지워도 코어 행은 남는다.
    기본 방식(DB 를 지우고 새로)은 이름이 dining_ 으로 시작하는 DB 에만 쓴다. 코어 DB 를 실수로 지우지 않게.
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
DINING_DATA = os.environ.get("DINING_DATA") or os.path.join(  # 데이터는 git 밖(datasets/dining/processed)
    os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "datasets", "dining", "processed")
ROOT = os.path.dirname(os.path.dirname(HERE))          # final_project_cs
MIGRATIONS = os.path.join(ROOT, "app", "infrastructure", "db", "migrations")
BUILD = os.path.join(DINING_DATA, "_build")

PG_PORT = int(os.environ.get("DINING_PG_PORT", "5433"))
PG_USER = os.environ.get("DINING_DB_USER", "postgres")
#: ★`[2026-09-28 cs]` 코어 DB 에 적재할 때 쓰는 계정 — dining 칸만 쓰고 코어는 places 넣기·고치기까지(마이그레이션 223).
#:  코드 실수가 있어도 DB 가 코어 데이터를 지키게 한다
LOADER_USER = os.environ.get("DINING_LOADER_USER", "dining_loader")
#: 적재 전용 계정의 권한을 주는 마이그레이션. `--target core` 로 요식 칸을 새로 만들면 권한도 같이 사라져 다시 준다
LOADER_GRANTS = "223_ops_loader_role.sql"

#: 번호로 고르지 않는다. 030 을 더했을 때 02* 패턴이 못 잡아 적재가 깨졌다.
#: 요식 파일인지로 고르면 번호가 늘어도 따라온다.

#: 코어 `places` 표가 있어야 올라가는 것. 없으면 건너뛴다.
NEEDS_CORE = {"202_dining_matcher.sql", "221_dining_core_promote.sql", "222_dining_core_sync.sql"}

#: 코어를 세울 때 설정이 요구하는 값. develop CI 와 같은 가짜다. 실제 키를 넣지 않는다.
CORE_ENV = {
    "ACOP_LLM_PROVIDER": "mock",
    "ACOP_OPENAI_API_KEY": "sk-dummy-for-rebuild",
    "ACOP_LLM_MODEL": "gpt-4o-mini",
    "ACOP_EMBEDDING_MODEL": "text-embedding-3-small",
    "ACOP_TENANT_ID": "demo",
    "ACOP_SECRET_KEY": "dummy-secret-key-for-rebuild-0123456789abcdef",
    "ACOP_COMPOSER_JWT_SECRET": "dummy-composer-jwt-secret-for-rebuild-0123456789",
    "ACOP_COMPOSER_ISSUER_SECRET": "dummy-composer-issuer-secret-for-rebuild-0123456789",
}

#: 코어 세우기. 순서가 곧 의존 관계다.
CORE_STEPS = [
    ("코어 마이그레이션", "app.infrastructure.db.migrate"),
    ("여행 시드",         "scripts.seed_travel"),
]

#: 코어 장소와 잇는다. 후보가 하나일 때만 잇고 여럿이면 ambiguous 로 남긴다(022).
def link_sql(tenant: str) -> str:
    """★`[2026-09-28 cs]` 운영 테넌트만 잇는다 — 올리기(`promote_sql`)와 범위를 맞춘다. 전에는 `places` 의 모든 테넌트였다
    (운영 DB 의 시험 테넌트까지 짝 표가 늘었다 — 코덱스 구현 검토)."""
    if not re.fullmatch(r"[A-Za-z0-9_\-]+", tenant or ""):
        raise SystemExit(f"운영 테넌트 이름이 이상하다: {tenant!r}")
    return f"SELECT result, count(*) FROM dining.link_core_places('{tenant}', 0.75, 'rebuild', false) GROUP BY 1"


def promote_sql(tenant: str) -> str:
    """★`[2026-09-28 cs]` 짝 없는 원장 식당을 코어 공용 장소로 올린다(221) — **운영 테넌트 하나에만.**

    ☆처음엔 `places` 의 모든 테넌트에 올렸다. 운영 DB 에는 시험 테넌트가 9개 있어 다시 적재할 때마다
      1,209곳이 테넌트마다 복제될 뻔했다(코덱스 교차검증이 테넌트 정책을 물어 찾았다).
    """
    if not re.fullmatch(r"[A-Za-z0-9_\-]+", tenant or ""):
        raise SystemExit(f"운영 테넌트 이름이 이상하다: {tenant!r}")
    # ★올린 뒤 요식 원본으로 다시 쓴다(222 sync_core_places) — 이름·좌표·영업시간·식사 조건·폐업
    return (f"SELECT result, n FROM dining.promote_to_core('{tenant}', 'rebuild') "
            f"UNION ALL SELECT result, n FROM dining.sync_core_places('{tenant}')")


#: 만드는 것과 넣는 것의 짝. 순서가 곧 의존 관계다.
LOADS = [
    ("parse_hours.py",        None),
    ("make_load_sql.py",      "load_200.sql"),
    ("make_holiday_sql.py",   "holidays.sql"),
    ("make_attribute_sql.py", "attributes.sql"),
    ("make_truth_sql.py",     "truth.sql"),
    ("make_operator_sql.py",  "operator.sql"),
    ("make_vegan_sql.py",     "vegan.sql"),
    ("make_halal_sql.py",     "halal.sql"),
    ("make_michelin_sql.py",  "michelin.sql"),
    ("make_closure_sql.py",   "closure.sql"),     # 가게가 다 들어온 뒤. 폐업 · 이전 확인분
    ("make_gap_sql.py",       "gaps.sql"),        # 빈칸 검수 확인분(영업시간 · 전화 · 좌표)
    ("google_link.py --to-sql", "google_links.sql"),  # 구글 place_id 연결(구글_연결.csv)
]

#: 적재가 끝난 뒤 가게를 보고 계산하는 것. 영문 SQL 만 둔다 — -c 로 넘긴다.
AFTER_LOADS = [
    ("대표 분류", "SELECT dining.refresh_category()"),
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
    name, *args = script.split()
    done = subprocess.run([sys.executable, os.path.join(HERE, name), *args],
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=ROOT, env=env,
                          stdin=subprocess.DEVNULL)
    return done.returncode == 0, (done.stdout or "") + (done.stderr or "")


def build_core(db: str) -> bool:
    """코어 마이그레이션과 시드를 올린다. 하나라도 실패하면 False."""
    env = {**CORE_ENV, **os.environ, "PYTHONIOENCODING": "utf-8",
           "ACOP_DATABASE_URL": f"postgresql+psycopg://{PG_USER}@127.0.0.1:{PG_PORT}/{db}"}
    for name, module in CORE_STEPS:
        done = subprocess.run([sys.executable, "-m", module], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", cwd=ROOT, env=env,
                              stdin=subprocess.DEVNULL)
        if done.returncode != 0:
            say("..", f"{name} 실패 — 코어 없이 요식만 세운다")
            for line in ((done.stdout or "") + (done.stderr or "")).strip().splitlines()[-3:]:
                say("  ", line)
            return False
        say("OK", name)
    return True


def has_core_places(db: str) -> bool:
    ok, out = run_sql(db, sql="SELECT to_regclass('public.places')")
    return ok and "places" in out


#: 이 도구가 새로 만든 DB 에 붙이는 표시. 이 표시가 있는 DB 만 지우고 다시 만들 수 있다
DISPOSABLE = "dining_rebuild:disposable"


def _yes(ok: bool, out: str) -> bool:
    return ok and any(line.strip() == "t" for line in out.splitlines())


def holds_live_core(db: str) -> bool:
    """★`[2026-09-28 cs]` 지키는 DB 인가. 지키면 **지우지도 코어 시드를 다시 넣지도 않고**, 적재 전용 계정으로 돈다.

    요식 표가 코어 DB(`acop_cs`)로 들어왔다. 이 도구의 기본 동작은 「DB 를 지우고 새로 만들기」라서,
    대상을 코어 DB 로 주고 `--keep` 을 빠뜨리면 여행·고객·일정이 통째로 사라진다.
    ☆처음엔 「여행 행이 있나」만 봤다 — 여행이 비었거나 검사가 실패하면 지우는 쪽으로 갔다(코덱스 구현 검토).
      그래서 반대로 판정한다: **이 도구가 만든 일회용 DB(`DISPOSABLE` 표시)만 지울 수 있고**, 코어 표가 있는
      나머지는 다 지킨다. 확인하다 실패해도 지킨다. 없는 DB 는 지킬 것이 없다.
    """
    if not re.fullmatch(r"[A-Za-z0-9_\-]+", db or ""):
        return True
    ok, out = run_sql("postgres", sql=f"SELECT EXISTS (SELECT 1 FROM pg_database WHERE datname = '{db}')",
                      stop_on_error=False)
    if not ok:
        return True
    if not _yes(ok, out):
        return False
    ok, out = run_sql(db, sql=f"SELECT coalesce(shobj_description(oid, 'pg_database'), '') = '{DISPOSABLE}' "
                              "FROM pg_database WHERE datname = current_database()", stop_on_error=False)
    if not ok:
        return True
    if _yes(ok, out):
        return False
    ok, out = run_sql(db, sql="SELECT to_regclass('public.places') IS NOT NULL "
                              "OR to_regclass('public.trips') IS NOT NULL", stop_on_error=False)
    if not ok:
        return True
    if not _yes(ok, out):
        return False                              # 코어 표가 없다 — 요식 전용 DB
    # 요식 팀 규칙: 이름이 dining_ 으로 시작하는 DB 는 이 도구가 만든 일회용이다. ★이름만 믿지 않고 여행 데이터가
    # 없다고 **확인됐을 때만** 받아 준다(확인이 실패하면 지킨다)
    if db.startswith("dining_"):
        ok, out = run_sql(db, sql="SELECT to_regclass('public.trips') IS NULL "
                                  "OR NOT EXISTS (SELECT 1 FROM public.trips)", stop_on_error=False)
        return not _yes(ok, out)
    return True


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
        path = os.path.join(HERE, script.split()[0])
        if not os.path.isfile(path):
            say("!!", f"없는 스크립트 {script}")
            ready = False
    data = DINING_DATA
    for name in ("tourapi_음식점_소개정보.json", "tourapi_서울_음식점_목록.json",
                 "holidays_2026_2027.json"):
        if not os.path.isfile(os.path.join(data, name)):
            say("!!", f"없는 원본 {name}")
            ready = False
    if not ready:
        say("  ", f"데이터는 git 에 없다. 팀 드라이브에서 받아 {data} 에 둔다(datasets/dining/REPORT.md)")
    # 사람이 채운 구글 미연결 시트는 적재가 읽지 않는다. google_sheet.py 로 옮겨야 들어간다.
    got = subprocess.run([sys.executable, os.path.join(HERE, "google_sheet.py"), "--check"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    line = (got.stdout.strip().splitlines() or [""])[-1]
    if re.search(r"링크 [1-9]|폐업 [1-9]", line):
        say("..", f"옮기지 않은 구글 미연결 시트 — {line}")
        say("  ", "python scripts/dining/google_sheet.py 로 옮긴 뒤 세운다(키 필요)")
    if os.path.isfile(os.path.join(data, "truth", "대조표100_검수_2026-09-21.csv")):
        say("OK", "검수 대조표 있음")
    else:
        say("!!", "검수 대조표가 없다. 정답셋 단계가 비게 된다")
    return ready


def main() -> int:
    ap = argparse.ArgumentParser(description="빈 DB 에서 요식 원장을 세운다.")
    ap.add_argument("--db", default=None,
                    help="기본은 코어 DB(`core_db.py`). 코어 여행 데이터가 있으면 --keep 이 있어야 한다")
    ap.add_argument("--keep", action="store_true", help="있는 DB 를 지우지 않는다")
    ap.add_argument("--no-core", action="store_true", help="코어 없이 요식만 세운다")
    ap.add_argument("--check", action="store_true", help="세우지 않고 준비물만 본다")
    ap.add_argument("--target", choices=("dining", "core"), default="dining",
                    help="core: 코어 DB 를 지우지 않고 dining 스키마만 다시 채운다")
    args = ap.parse_args()
    if args.db is None:
        sys.path.insert(0, HERE)
        import core_db  # ★`[2026-09-28 cs]` 기본은 코어 DB

        args.db = core_db.db_name()

    print("요식 원장 세우기" + ("  (코어 DB 의 요식 칸만)" if args.target == "core" else ""))
    if not check():
        return 1
    if args.check:
        return 0
    if args.target == "dining" and not args.keep and not args.db.startswith("dining_"):
        say("!!", f"{args.db} 는 dining_ 으로 시작하지 않는다. 지우고 새로 만들지 않는다")
        say("  ", "코어 DB 라면 --target core(요식 칸만 다시 세운다), 있는 DB 위에 얹으려면 --keep")
        return 1

    started = time.time()
    os.makedirs(BUILD, exist_ok=True)     # 새로 받은 저장소에는 _build 가 없다

    # ★`[2026-09-30]` 팀의 `--target core` 와 우리 안전장치를 합쳤다.
    #   팀 방식: 코어 DB 는 지우지 않고 **dining 칸만** 지우고 다시 채운다(코어 표는 dining 을 참조하지 않아 남는다).
    #   우리가 얹은 것: ① 코어 DB 를 통째로 지우는 길은 막는다(`holds_live_core`) ② 적재는 적재 전용 계정으로 한다(223)
    #   ③ 식당은 운영 테넌트에만 올린다 ④ 칸을 지우면 그 계정의 권한도 같이 사라지므로 다시 준다
    global PG_USER
    if args.target == "core":
        if not has_core_places(args.db):
            say("!!", f"{args.db} 에 코어 places 가 없다. 코어를 먼저 세운다(python -m app.infrastructure.db.migrate)")
            return 1
        ok, out = run_sql(args.db, sql="DROP SCHEMA IF EXISTS dining CASCADE")
        if not ok:
            say("!!", "dining 스키마를 지우지 못했다")
            say("  ", out.strip().splitlines()[0] if out.strip() else "")
            return 1
        say("OK", f"{args.db} 의 dining 스키마만 비웠다. 코어 표는 그대로")
        args.no_core = True                       # 코어 시드는 다시 넣지 않는다
    else:
        if holds_live_core(args.db):
            # ★코어 DB 다 — 지우지도 코어 시드를 다시 넣지도 않는다. 요식 칸의 데이터만 다시 채운다(표는 그대로).
            if not args.keep:
                say("!!", f"{args.db} 는 지키는 DB 다(코어 표가 있고 이 도구가 만든 일회용 DB 가 아니다). 지우지 않는다")
                say("  ", "요식 칸을 다시 세우려면 --target core, 데이터만 다시 채우려면 --keep")
                return 1
            args.no_core = True
            PG_USER = LOADER_USER
            say("OK", f"{args.db} 는 코어 DB 다 — 코어는 건드리지 않고 요식만 얹는다(계정 {LOADER_USER})")

        if not args.keep:
            # 지우고 다시 만든다. 남은 것 위에 얹으면 「처음부터」가 아니다.
            ok, out = run_sql("postgres", sql=f'DROP DATABASE IF EXISTS "{args.db}"')
            if not ok:
                say("!!", f"{args.db} 를 지우지 못했다. 누가 쓰고 있을 수 있다")
                say("  ", out.strip().splitlines()[0] if out.strip() else "")
                return 1
            run_sql("postgres", sql=f'CREATE DATABASE "{args.db}"')
            # ★일회용 표시 — 이 표시가 있어야 다음에 지우고 다시 만들 수 있다(`holds_live_core`)
            run_sql("postgres", sql=f"COMMENT ON DATABASE \"{args.db}\" IS '{DISPOSABLE}'")
            say("OK", f"{args.db} 새로 만들었다")
        else:
            run_sql("postgres", sql=f'CREATE DATABASE "{args.db}"', stop_on_error=False)
            say("OK", f"{args.db} 위에 얹는다")
    if not args.no_core and args.target == "dining":
        build_core(args.db)
    core = has_core_places(args.db)
    say("OK" if core else "..",
        "코어 places 있음 — 매칭기도 올린다" if core else
        "코어 places 없음 — 022 매칭기는 건너뛴다")

    for path in sorted(glob.glob(os.path.join(MIGRATIONS, "[0-9]*_dining_*.sql"))):
        if PG_USER == LOADER_USER:
            # ★코어 DB 의 요식 표는 코어 마이그레이션(`python -m app.infrastructure.db.migrate`)이 올린다 — 이 계정은
            #   표·함수를 만들거나 바꿀 수 없다(223). 표가 없으면 먼저 코어 마이그레이션을 돌리라고 멈춘다
            ok, out = run_sql(args.db, sql="SELECT to_regclass('dining.dn_place') IS NOT NULL")
            if not (ok and any(line.strip() == "t" for line in out.splitlines())):
                say("!!", "요식 표가 없다 — 먼저 python -m app.infrastructure.db.migrate 를 돌린다")
                return 1
            say("OK", "요식 표는 코어 마이그레이션이 올렸다 — 여기서는 데이터만 채운다")
            break
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

    if args.target == "core":
        # ★요식 칸을 새로 만들었다 — 적재 전용 계정의 권한을 다시 주고, 이 뒤 적재는 그 계정으로 한다(코드 실수가 있어도
        #   DB 가 코어 표를 지킨다). 표를 만드는 일은 위에서 끝났다
        ok, out = run_sql(args.db, path=os.path.join(MIGRATIONS, LOADER_GRANTS))
        if not ok:
            say("!!", f"{LOADER_GRANTS} 실패 — 적재 전용 계정 권한을 주지 못했다")
            for line in out.strip().splitlines()[:6]:
                say("  ", line)
            return 1
        PG_USER = LOADER_USER
        say("OK", f"적재 전용 계정({LOADER_USER}) 권한을 다시 줬다 — 이 뒤 적재는 그 계정으로 한다")

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

    # 034 는 마이그레이션 끝에서 분류를 채우지만, 빈 DB 에서는 그때 가게가 없다.
    # 적재가 끝난 뒤 한 번 더 불러야 category 가 찬다.
    for name, sql in AFTER_LOADS:
        ok, out = run_sql(args.db, sql=sql)
        if not ok:
            say("!!", f"{name} 실패")
            for line in out.strip().splitlines()[:6]:
                say("  ", line)
            return 1
        say("OK", name)

    if core:
        sys.path.insert(0, HERE)
        import core_db

        ok, out = run_sql(args.db, sql=link_sql(core_db.operating_tenant()))
        if not ok:
            say("!!", "코어 장소 연결 실패")
            for line in out.strip().splitlines()[:6]:
                say("  ", line)
            return 1
        counts = [" ".join(l.replace("|", " ").split()) for l in out.splitlines()
                  if "|" in l and "result" not in l]
        say("OK", "코어 장소 연결  " + (", ".join(counts) or "이을 후보 없음"))
        ok, out = run_sql(args.db, sql=promote_sql(core_db.operating_tenant()))
        if not ok:
            say("!!", "원장 식당을 코어로 올리기 실패")
            for line in out.strip().splitlines()[:6]:
                say("  ", line)
            return 1
        counts = [" ".join(l.replace("|", " ").split()) for l in out.splitlines()
                  if "|" in l and "result" not in l]
        say("OK", "원장 식당 코어로 올림  " + (", ".join(counts) or "올릴 곳 없음"))

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
    print("  확인기로 보려면:  python scripts/dining/dev_up.py")
    print(f"  다른 DB 를 보려면 DINING_DB={args.db} 를 함께 준다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
