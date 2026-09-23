"""합치기 전후로 요식이 제대로 붙어 있는지 본다.

왜 필요한가.
    합치고 나서 조용히 안 되는 것들이 있다. 도구가 등록되지 않아도 Team 은
    죽지 않고 「모름」으로 답하고, 마이그레이션 번호가 겹쳐도 파일은 둘 다
    존재하며, 링크가 비어도 판정은 그냥 NULL 이 된다.
    전부 「터지지 않고 틀리는」 것이라 눈으로는 안 보인다.

무엇을 보는가.
    1  마이그레이션 번호가 겹치는가
    2  DiningTeam 이 등록된 이름으로 불러지는가
    3  read.dining_state 도구가 코어에 등록되었는가
    4  요식 스키마가 올라와 있는가
    5  코어 장소와 몇 건이나 이어졌는가

    python scripts/dining/preflight.py            전부 본다
    python scripts/dining/preflight.py --no-db    파일만 본다

DB 를 못 보는 환경에서도 1~3 은 답이 나온다.
돌아오는 값은 막는 문제의 수다. 0 이면 합쳐도 된다.
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))          # final_project_cs
MIGRATIONS = os.path.join(ROOT, "app", "infrastructure", "db", "migrations")

#: 요식이 쓰기로 한 구간. 다른 도메인이 여기 들어오면 알려 준다.
DINING_RANGE = range(20, 30)
TEAM_REF = "app.modules.travel_ops.dining:DiningTeam"
TOOL_NAME = "read.dining_state"

BLOCK, WARN, OK = "막음", "봐둘 것", "괜찮음"


class Report:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str]] = []

    def add(self, level: str, title: str, detail: str = "") -> None:
        self.rows.append((level, title, detail))

    def show(self) -> int:
        mark = {BLOCK: "!!", WARN: "..", OK: "OK"}
        for level, title, detail in self.rows:
            print(f"  {mark[level]} {title}")
            for line in (detail or "").splitlines():
                if line.strip():
                    print(f"       {line}")
        blocking = sum(1 for level, _, _ in self.rows if level == BLOCK)
        warned = sum(1 for level, _, _ in self.rows if level == WARN)
        print()
        print(f"  막는 문제 {blocking}, 봐둘 것 {warned}")
        return blocking


# ── 1. 마이그레이션 번호 ──────────────────────────────────────

def check_migrations(rep: Report) -> None:
    by_number: dict[int, list[str]] = defaultdict(list)
    for path in glob.glob(os.path.join(MIGRATIONS, "*.sql")):
        name = os.path.basename(path)
        got = re.match(r"^(\d+)_", name)
        if got:
            by_number[int(got.group(1))].append(name)

    clashes = {n: sorted(v) for n, v in by_number.items() if len(v) > 1}
    if clashes:
        detail = "\n".join(f"{n:03d} — {', '.join(v)}" for n, v in sorted(clashes.items()))
        # 같은 번호가 둘이면 migrate.py 가 이름 순으로 붙인다. 의도한 순서가 아닐 수 있다.
        rep.add(BLOCK, f"마이그레이션 번호가 겹친다 ({len(clashes)}곳)",
                detail + "\n한 트랜잭션에 이름 순으로 붙으므로 의도한 순서가 아닐 수 있다")
    else:
        rep.add(OK, f"마이그레이션 번호가 겹치지 않는다 ({len(by_number)}개)")

    intruders = sorted(name for n, names in by_number.items()
                       if n in DINING_RANGE for name in names
                       if "dining" not in name)
    if intruders:
        rep.add(WARN, "요식 구간(020~029)에 다른 도메인이 들어왔다",
                ", ".join(intruders))

    # 반대쪽도 본다. 남이 우리 칸에 들어온 것만 보면 우리가 넘어간 것은 안 보인다.
    overflow = sorted(name for n, names in by_number.items()
                      if n not in DINING_RANGE for name in names
                      if "dining" in name)
    if overflow:
        rep.add(WARN, f"요식이 제안한 구간(020~029)을 넘었다 ({len(overflow)}개)",
                ", ".join(overflow) + "\n다른 도메인이 030 대를 받으면 겹친다. MERGE.md 「마이그레이션 번호」")


# ── 2. Team 등록 ────────────────────────────────────────────

def check_team(rep: Report) -> None:
    refs = []
    for pattern in ("app/**/*.py", "config/*.yaml", "config/*.yml"):
        for path in glob.glob(os.path.join(ROOT, pattern), recursive=True):
            try:
                text = open(path, encoding="utf-8").read()
            except (OSError, UnicodeDecodeError):
                continue
            if TEAM_REF in text or TEAM_REF.replace(":", ":") in text:
                refs.append(os.path.relpath(path, ROOT))
    if not refs:
        rep.add(BLOCK, "DiningTeam 을 가리키는 등록이 없다",
                f"{TEAM_REF} 를 찾지 못했다")
        return

    # 폴더로 바꾼 뒤에도 같은 이름으로 불러져야 한다. __init__ 이 재수출한다.
    init_path = os.path.join(ROOT, "app", "modules", "travel_ops", "dining", "__init__.py")
    if not os.path.isfile(init_path):
        rep.add(BLOCK, "dining/__init__.py 가 없다", "등록 이름이 풀리지 않는다")
        return
    init = open(init_path, encoding="utf-8").read()
    if "DiningTeam" not in init:
        rep.add(BLOCK, "dining/__init__.py 가 DiningTeam 을 재수출하지 않는다",
                "폴더로 바꾸면서 등록 이름이 끊긴다")
        return
    rep.add(OK, f"DiningTeam 등록 {len(refs)}곳", ", ".join(sorted(refs)))


# ── 3. 도구 등록 ────────────────────────────────────────────

def check_tool(rep: Report) -> None:
    tools_path = os.path.join(ROOT, "app", "tools", "read_tools.py")
    team_path = os.path.join(ROOT, "app", "modules", "travel_ops", "dining", "team.py")
    declared = TOOL_NAME in open(team_path, encoding="utf-8").read()
    registered = TOOL_NAME in open(tools_path, encoding="utf-8").read()

    if declared and registered:
        rep.add(OK, f"{TOOL_NAME} 선언되고 등록됨")
    elif declared and not registered:
        # 막지는 않는다. Team 이 ToolNotAllowed 를 잡아 예전처럼 답한다.
        rep.add(WARN, f"{TOOL_NAME} 이 코어에 등록되지 않았다",
                "요식 판정이 원장에 닿지 않아 늘 「모름」으로 떨어진다.\n"
                "read_tools.py 에 두 줄이 필요하다 — scripts/dining/MERGE.md 참고")
    elif registered and not declared:
        rep.add(WARN, f"{TOOL_NAME} 이 등록됐는데 Team 이 선언하지 않았다")
    else:
        rep.add(WARN, f"{TOOL_NAME} 이 아직 쓰이지 않는다")


# ── 4·5. DB ─────────────────────────────────────────────────

def check_db(rep: Report) -> None:
    try:
        import psycopg
    except ImportError:
        rep.add(WARN, "psycopg 가 없어 DB 를 보지 못했다")
        return

    dsn = os.environ.get("DINING_DSN")
    if not dsn:
        port = os.environ.get("DINING_PG_PORT", "5433")
        user = os.environ.get("DINING_DB_USER", "postgres")
        db = os.environ.get("DINING_DB", "dining_dev")
        dsn = f"postgresql://{user}@localhost:{port}/{db}"
    try:
        conn = psycopg.connect(dsn, connect_timeout=5)
    except Exception as exc:                            # noqa: BLE001
        rep.add(WARN, "DB 에 붙지 못했다", str(exc).splitlines()[0])
        return

    with conn, conn.cursor() as cur:
        cur.execute("SELECT to_regclass('dining.dn_place')")
        if cur.fetchone()[0] is None:
            rep.add(BLOCK, "요식 스키마가 없다", "요식 마이그레이션을 먼저 올려라")
            return
        cur.execute("SELECT count(*) FROM dining.dn_place")
        places = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM dining.v_hours_rule_active")
        rules = cur.fetchone()[0]
        rep.add(OK if places else BLOCK,
                f"요식 원장 {places}곳, 규칙 {rules}건")

        cur.execute("SELECT to_regclass('public.places')")
        core = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM dining.dn_core_place_link")
        linked = cur.fetchone()[0]

        if core is None:
            rep.add(WARN, "코어 places 표가 없다",
                    "원장만 있는 DB 다. 합친 뒤에는 매칭기를 돌려야 한다")
            return
        cur.execute("SELECT count(*) FROM places")
        core_n = cur.fetchone()[0]
        if linked == 0:
            rep.add(BLOCK, f"코어 장소 {core_n}곳과 하나도 이어지지 않았다",
                    "link_core_places 를 돌려야 판정이 코어에 닿는다")
        else:
            share = 100.0 * linked / core_n if core_n else 0
            level = OK if share >= 50 else WARN
            rep.add(level, f"코어 장소 {core_n}곳 중 {linked}곳 이어짐 ({share:.0f}%)",
                    "" if level == OK else "못 이은 곳은 v_link_gap 에서 사유를 본다")


def main() -> int:
    ap = argparse.ArgumentParser(description="합치기 전후 점검.")
    ap.add_argument("--no-db", action="store_true", help="파일만 본다")
    args = ap.parse_args()

    print("요식 합류 점검")
    rep = Report()
    check_migrations(rep)
    check_team(rep)
    check_tool(rep)
    if not args.no_db:
        check_db(rep)
    return rep.show()


if __name__ == "__main__":
    raise SystemExit(main())
