# -*- coding: utf-8 -*-
"""받은 요식 자료(`dining_drive_fetch.py`)로 cs 프로젝트 DB 의 요식 원장(`dining` 스키마)을 **한 트랜잭션에** 다시 채운다. `[2026-10-19]`

    # api 이미지 안에서 돈다(파이썬 · psycopg · scripts/dining · 마이그레이션이 다 있다)
    docker compose run --rm --no-deps -v <자료>/dining:/data/dining:ro -v <이 파일>:/work/dining_ledger_load.py:ro \
        api python /work/dining_ledger_load.py --data /data/dining            # 시험: 끝까지 넣어 보고 되돌린다
    ... api python /work/dining_ledger_load.py --data /data/dining --apply    # 반영

★요식팀 공식 순서(`scripts/dining/rebuild.py --target core`)를 그대로 쓴다 — 마이그레이션 목록 · 적재 순서(`LOADS`) ·
  적재 뒤 계산(`AFTER_LOADS`) · 코어 장소 잇기(`link_sql`) · 원장 식당 코어로 올리기(`promote_sql`)를 그 모듈에서 가져온다.
  다른 점은 하나 — rebuild 는 psql 로 파일마다 따로 커밋해서 중간에 실패하면 반쯤 지워진 원장이 남는다.
  여기서는 **비우기부터 확인까지 한 트랜잭션**이다. 하나라도 실패하거나 확인에 걸리면 통째로 되돌아가 쓰던 원장이 그대로 남는다.
★코어 표(여행 · 일정 · 고객)는 지우지 않는다 — `dining` 스키마만 비운다(코어 표는 dining 을 참조하지 않는다).
  가게 번호(place_uid)는 관광공사 번호에서 만든 고정값이라 다시 채워도 같은 가게는 같은 번호다.
★`--apply` 없이 돌리면 끝까지 넣어 본 뒤 되돌린다(시험). 바뀌는 숫자만 보여 준다.
★DB 가 비우는 동안 요식 표를 읽는 요청은 잠깐(적재 시간만큼) 기다린다 — 사람이 덜 쓰는 시각에 돌린다.

확인(하나라도 걸리면 되돌린다)
    가게 수가 이전의 90% 미만 · 영업시간 규칙이 없는 가게가 10% 넘음 · 코어 장소 연결 0
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

APP = os.environ.get("ACOP_APP_ROOT", "/srv")          # api 이미지의 작업 폴더(`Dockerfile.api` WORKDIR — final_project_cs 와 같은 모양)
sys.path.insert(0, APP)

MIN_PLACE_RATIO = 0.9
MAX_NO_RULE_RATIO = 0.1


class Rollback(Exception):
    """시험 실행 · 확인 실패 — 트랜잭션을 되돌린다."""


def counts(conn) -> dict[str, int]:
    exists = conn.execute("SELECT to_regclass('dining.dn_place') IS NOT NULL").fetchone()[0]
    if not exists:
        return {}
    q = {
        "가게": "SELECT count(*) FROM dining.dn_place",
        "영업 중 가게": "SELECT count(*) FROM dining.dn_place WHERE record_status <> 'closed' AND NOT is_synthetic",
        "영업시간 규칙 있는 가게": "SELECT count(DISTINCT place_uid) FROM dining.dn_hours_rule WHERE retired_at IS NULL",
        "휴무 규칙": "SELECT count(*) FROM dining.dn_closure_rule WHERE retired_at IS NULL",
        "노포 표시": "SELECT count(*) FROM dining.dn_attribute WHERE attr_code = 'nopo' AND retired_at IS NULL",
        "미쉐린 표시": "SELECT count(*) FROM dining.dn_attribute WHERE attr_code = 'michelin' AND retired_at IS NULL",
        "코어 장소 연결": "SELECT count(*) FROM dining.dn_core_place_link",
    }
    out = {k: conn.execute(v).fetchone()[0] for k, v in q.items()}
    if conn.execute("SELECT to_regclass('dining.dn_license_shop') IS NOT NULL").fetchone()[0]:
        out["인허가 식당(이름 찾기)"] = conn.execute("SELECT count(*) FROM dining.dn_license_shop").fetchone()[0]
    return out


_TXN_LINE = re.compile(r"^\s*(BEGIN|COMMIT|ROLLBACK|START\s+TRANSACTION|END)\s*;\s*$", re.I | re.M)


def unwrap(source: str, name: str) -> str:
    """생성된 적재 SQL 의 바깥 `BEGIN;` · `COMMIT;` 한 쌍만 뗀다 — 우리 트랜잭션 안에서 돌리려고.

    마이그레이션은 앱과 같은 검사기(`atomic_sql`, SQL 구문 분석)로 떼지만, 생성 파일은 12MB 가 넘어 그 검사기로는 수십 분 걸렸다.
    생성기가 만드는 모양은 정해져 있다(맨 앞 BEGIN · 맨 끝 COMMIT · 함수 본문 없음). 그 밖의 트랜잭션 줄이 있으면 멈춘다."""
    lines = _TXN_LINE.findall(source)
    if not lines:
        return source
    code = [ln for ln in source.splitlines() if ln.strip() and not ln.strip().startswith("--")]
    if (len(lines) != 2 or not re.fullmatch(r"\s*BEGIN\s*;\s*", code[0], re.I)
            or not re.fullmatch(r"\s*COMMIT\s*;\s*", code[-1], re.I)):
        raise SystemExit(f"{name}: 바깥 BEGIN/COMMIT 한 쌍이 아닌 트랜잭션 줄이 있다 — 한 트랜잭션으로 묶을 수 없어 멈춘다")
    body = re.sub(r"^\s*BEGIN\s*;\s*$", "", source, count=1, flags=re.I | re.M)
    return re.sub(r"^\s*COMMIT\s*;\s*$", "", body, count=1, flags=re.I | re.M)   # 위에서 트랜잭션 줄이 둘뿐임을 확인했다


#: 서울 열린데이터 광장에서 통째로 받은 파일(한글 머리 · CP949) → 요식팀 적재기가 읽는 OpenAPI 칸 이름
OPEN_DATA_HEADERS = {"관리번호": "MGTNO", "사업장명": "BPLCNM", "영업상태명": "TRDSTATENM", "업태구분명": "UPTAENM",
                     "도로명주소": "RDNWHLADDR", "지번주소": "SITEWHLADDR", "전화번호": "SITETEL",
                     "좌표정보(X)": "X", "좌표정보(Y)": "Y", "인허가일자": "APVPERMYMD"}


def _link(src: str, target: str) -> None:
    """요식팀 적재기가 읽는 모양(UTF-8 · OpenAPI 칸 이름)이면 링크, 열린데이터 광장 원본(CP949 · 한글 머리)이면 그 모양으로 옮겨 쓴다.

    ☆팀 드라이브의 인허가 파일은 열린데이터 광장 원본 그대로라 `load_license.rows` 가 첫 줄에서 UnicodeDecodeError 로 죽었다(2026-10-19 시험)."""
    import csv

    with open(src, "rb") as f:
        head = f.read(4096)
    try:
        first = head.decode("utf-8-sig").splitlines()[0]
        encoding = "utf-8-sig"
    except UnicodeDecodeError:
        first, encoding = head.decode("cp949", "replace").splitlines()[0], "cp949"
    if encoding == "utf-8-sig" and "MGTNO" in first:
        try:
            os.symlink(src, target)
        except OSError:
            shutil.copyfile(src, target)       # 링크가 안 되는 곳(윈도 시험)
        return
    with open(src, encoding=encoding, errors="replace", newline="") as fin, \
            open(target, "w", encoding="utf-8", newline="") as fout:
        reader = csv.DictReader(fin)
        missing = [k for k in OPEN_DATA_HEADERS if k not in (reader.fieldnames or [])]
        if missing:
            raise SystemExit(f"인허가 파일 칸을 못 읽었다({os.path.basename(src)}): 없는 칸 {missing}")
        writer = csv.DictWriter(fout, fieldnames=list(OPEN_DATA_HEADERS.values()))
        writer.writeheader()
        for row in reader:
            writer.writerow({api: (row.get(ko) or "") for ko, api in OPEN_DATA_HEADERS.items()})


def license_dir(raw: str, work: str) -> str | None:
    """인허가 CSV 가 있는 폴더 — 요식팀 적재기(`load_license.FILES`)는 `… 인허가 정보_<날짜>.csv` 를 찾는데
    드라이브에는 날짜 없이 `… 인허가 정보.csv` 로 올라간다. 날짜 없는 파일은 임시 폴더에 이름만 붙여(링크) 넘긴다."""
    import load_license   # noqa: E402

    if all(glob.glob(os.path.join(raw, pattern)) for _, pattern in load_license.FILES):
        return raw
    linked = os.path.join(work, "raw")
    os.makedirs(linked, exist_ok=True)
    found = False
    for _, pattern in load_license.FILES:
        dated = glob.glob(os.path.join(raw, pattern))
        plain = glob.glob(os.path.join(raw, pattern.replace("_*.csv", ".csv")))
        for src in dated:
            _link(src, os.path.join(linked, os.path.basename(src)))
        for src in plain if not dated else []:
            _link(src, os.path.join(linked, os.path.basename(src).replace(".csv", "_drive.csv")))
        found = found or bool(dated or plain)
    return linked if found else None


def generate(rebuild, scripts: str) -> list[str]:
    """원본 → 적재 SQL. 요식팀 생성기를 그대로 돌린다(표준 라이브러리 · DB 를 안 쓴다)."""
    produced = []
    for script, out in rebuild.LOADS:
        name, *rest = script.split()
        done = subprocess.run([sys.executable, os.path.join(scripts, name), *rest], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", cwd=APP, stdin=subprocess.DEVNULL,
                              env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        if done.returncode != 0:
            tail = ((done.stdout or "") + (done.stderr or "")).strip().splitlines()[-4:]
            raise SystemExit(f"생성 실패 {script}: " + " / ".join(tail))
        print(f"  생성 {script}", flush=True)
        if out:
            produced.append(os.path.join(rebuild.BUILD, out))
    return produced


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", required=True, help="받은 자료 폴더(`processed/` · `raw/` 가 있는 dining 폴더)")
    ap.add_argument("--apply", action="store_true", help="반영한다. 없으면 끝까지 넣어 보고 되돌린다")
    ap.add_argument("--report", default=None, help="결과 JSON 을 쓸 경로")
    args = ap.parse_args()

    work = tempfile.mkdtemp(prefix="dining-load-")
    try:
        # 생성기가 `processed/_build/` 에 쓰므로 읽기 전용 자료를 쓰기 가능한 자리로 옮겨 둔다
        processed = os.path.join(work, "processed")
        shutil.copytree(os.path.join(args.data, "processed"), processed,
                        ignore=shutil.ignore_patterns("_build"))
        os.environ["DINING_DATA"] = processed
        os.environ["DINING_RAW"] = os.path.join(args.data, "raw")
        scripts = os.path.join(APP, "scripts", "dining")
        sys.path.insert(0, scripts)
        import rebuild            # noqa: E402 — 환경 변수를 정한 뒤 불러야 자료 자리를 따른다
        import core_db            # noqa: E402
        from app.infrastructure.db.migration_sql import atomic_sql   # noqa: E402
        from app.infrastructure.db.session import get_connection     # noqa: E402

        os.makedirs(rebuild.BUILD, exist_ok=True)
        produced = generate(rebuild, scripts)
        migrations = sorted(glob.glob(os.path.join(rebuild.MIGRATIONS, "[0-9]*_dining_*.sql")))
        migrations.append(os.path.join(rebuild.MIGRATIONS, rebuild.LOADER_GRANTS))
        tenant = core_db.operating_tenant()
        report: dict = {"apply": args.apply, "tenant": tenant}
        started = time.time()

        with get_connection() as conn:
            try:
                with conn.transaction():
                    before = counts(conn)
                    report["before"] = before
                    # ★기존 코어 장소 연결을 지키다 — 운영 중에 생긴 연결(고객이 고른 대체 식당 `nearby` · 실행 중 매칭 `runtime:*`)은
                    #   재적재의 매칭기(`link_sql`)가 다시 만들지 못한다. ☆x600 시험(2026-10-20)에서 2,499 → 1,936 으로 줄었고 일정 항목
                    #   장소 38곳의 연결이 섞여 있었다 — 끊기면 그 식당은 휴무 판정이 「모름」이 된다. 가게 번호가 고정값이라 그대로 되살린다
                    keep = bool(before)
                    if keep:
                        conn.execute("CREATE TEMP TABLE _dining_keep_links ON COMMIT DROP AS "
                                     "SELECT tenant_id, core_place_id, place_uid, linked_by, linked_at FROM dining.dn_core_place_link")
                        conn.execute("CREATE TEMP TABLE _dining_item_links ON COMMIT DROP AS "
                                     "SELECT DISTINCT l.tenant_id, l.core_place_id FROM dining.dn_core_place_link l "
                                     "JOIN itinerary_items i ON i.tenant_id = l.tenant_id AND i.place_id = l.core_place_id")
                    conn.execute("DROP SCHEMA IF EXISTS dining CASCADE")
                    for path in migrations:
                        with open(path, encoding="utf-8") as f:
                            conn.execute(atomic_sql(f.read(), os.path.basename(path)))
                    print(f"  요식 표 다시 만듦 — 마이그레이션 {len(migrations)}개", flush=True)
                    for path in produced:
                        with open(path, encoding="utf-8") as f:
                            conn.execute(unwrap(f.read(), os.path.basename(path)))
                        print(f"  적재 {os.path.basename(path)}", flush=True)
                    for name, sql in rebuild.AFTER_LOADS:
                        conn.execute(sql)
                        print(f"  계산 {name}", flush=True)
                    if keep:
                        # 매칭기 · 코어로 올리기 **앞에** 되살린다 — 그래야 매칭기가 그 장소를 다른 가게로 다시 잇지 않고,
                        # 올리기가 이미 이어진 가게를 새 공용 장소로 한 번 더 만들지 않는다. 다시 채운 원장에 없는 가게(폐업 정리)는 못 살린다
                        restored = conn.execute(
                            "INSERT INTO dining.dn_core_place_link (tenant_id, core_place_id, place_uid, linked_by, linked_at) "
                            "SELECT k.tenant_id, k.core_place_id, k.place_uid, k.linked_by, k.linked_at FROM _dining_keep_links k "
                            "WHERE EXISTS (SELECT 1 FROM dining.dn_place p WHERE p.place_uid = k.place_uid) "
                            "ON CONFLICT DO NOTHING").rowcount
                        kept_total = conn.execute("SELECT count(*) FROM _dining_keep_links").fetchone()[0]
                        report["restored_links"] = {"되살림": restored, "이전 연결": kept_total}
                        print(f"  기존 연결 되살림 {restored}/{kept_total}", flush=True)
                    report["link"] = [list(r) for r in conn.execute(rebuild.link_sql(tenant)).fetchall()]
                    report["promote"] = [list(r) for r in conn.execute(rebuild.promote_sql(tenant)).fetchall()]
                    # 인허가 식당(이름 찾기 전용) — CSV 가 있을 때만. 요식팀 `load_license.py` 와 같은 줄을 같은 트랜잭션에 넣는다
                    raw_dir = license_dir(os.environ["DINING_RAW"], work)
                    if raw_dir:
                        import load_license   # noqa: E402

                        seen: set[str] = set()
                        with conn.cursor() as cur, cur.copy(
                                "COPY dining.dn_license_shop (mgt_no, name_ko, name_key, road_address, jibun_address, area, "
                                "category, phone, lat, lng, approved_on, source_kind) FROM STDIN") as copy:
                            for row in load_license.rows(raw_dir):
                                if row[0] in seen:
                                    continue
                                seen.add(row[0])
                                copy.write_row(row)
                    after = counts(conn)
                    report["after"] = after
                    problems = []
                    if before.get("가게") and after["가게"] < before["가게"] * MIN_PLACE_RATIO:
                        problems.append(f"가게 수가 {before['가게']} → {after['가게']} 로 10% 넘게 줄었다")
                    live = after.get("영업 중 가게") or 0
                    if live and (live - min(live, after["영업시간 규칙 있는 가게"])) > live * MAX_NO_RULE_RATIO:
                        problems.append("영업시간 규칙이 없는 가게가 10% 넘는다")
                    if not after.get("코어 장소 연결"):
                        problems.append("코어 장소와 하나도 안 이어졌다")
                    if before.get("인허가 식당(이름 찾기)") and not after.get("인허가 식당(이름 찾기)"):
                        problems.append("인허가 식당(이름 찾기)이 비었다 — 드라이브 raw 에 인허가 CSV 가 없다")
                    if keep:
                        lost = conn.execute(
                            "SELECT count(*) FROM _dining_item_links k WHERE NOT EXISTS (SELECT 1 FROM dining.dn_core_place_link l "
                            "WHERE l.tenant_id = k.tenant_id AND l.core_place_id = k.core_place_id)").fetchone()[0]
                        report["item_links_lost"] = lost
                        if lost:
                            problems.append(f"일정 항목 장소 {lost}곳의 원장 연결이 끊긴다(휴무 판정이 「모름」이 된다)")
                    report["problems"] = problems
                    report["seconds"] = round(time.time() - started, 1)
                    if problems:
                        raise Rollback("확인 실패 — 되돌린다: " + " · ".join(problems))
                    if not args.apply:
                        raise Rollback("시험 실행 — 끝까지 넣어 보고 되돌린다(--apply 로 반영)")
                report["result"] = "applied"
            except Rollback as why:
                report["result"] = "rolled_back"
                report["note"] = str(why)
        text = json.dumps(report, ensure_ascii=False, indent=2, default=str)
        print(text)
        if args.report:
            with open(args.report, "w", encoding="utf-8") as f:
                f.write(text)
        return 0 if report["result"] == "applied" or (not args.apply and not report.get("problems")) else 1
    finally:
        shutil.rmtree(work, ignore_errors=True)        # 이 실행이 만든 임시 사본(자료 원본이 아니다)


if __name__ == "__main__":
    sys.exit(main())
