# -*- coding: utf-8 -*-
"""75번 방 ④ 줄인 판 만들기 — 정본 `DATA_DIR\\travel\\processed\\mobility`(읽기만) → 저장소 `datasets/mobility/processed/mobility/`.

자리(9/29 팀장 폴더 배정 · 서버 뜰 때까지 임시): 이 스크립트는 `datasets/mobility/scripts/` 에 있고, 산출 기본값은
`datasets/mobility/processed/mobility/` 다. 그 폴더는 팀 `.gitignore` 가 막으므로 **`git add -f`** 로 추적한다(README 참조).

원칙(75 첫 메시지 · 92차):
  · 정본 무변경 — 여기서는 읽기만 한다
  · 열 제거는 판정기 읽기 코드로 확인한 열만(`verify_time.Timetable.load` L132~156 · 8열)
  · **행 삭제 금지** — `--drop-no-dep` 는 기본 off(후보 · 회귀 171 확인 뒤에만)
  · gz 는 마지막 수단 — 줄인 뒤에도 50 MB 를 넘는 파일만 `.gz` 를 **옆에** 만든다(둘 다 두고 MANIFEST 에 표시 ·
    git 에 무엇을 올릴지는 73 뒤 팀장 판 읽기 코드(#63 .gz 읽기)에 맞춰 정한다)

실행(노트북 PowerShell · 표준 라이브러리만 · 46만 행이라 1~2분):
    python datasets/mobility/scripts/reduce_75.py            (저장소 루트에서 · 정본 위치는 .env DATA_DIR)
옵션:
    --src  <DATA_DIR>\\travel\\processed\\mobility            (기본 · .env 의 DATA_DIR)
    --dst  <repo>\\datasets\\mobility\\processed\\mobility     (기본 · 있으면 안 지우고 멈춘다 · --clean 이면 비우고 다시)
    --gz            50 MB 넘는 파일 옆에 .gz 도 만든다(기본 off · 판정기 gz 읽기는 78 ⑦ 뒤)
    --drop-no-dep   시간표에서 dep_time 없음(출발 없음) 행을 뺀다 — 기본 off
산출:
    <dst>\\**                       줄인 판(A 그대로 · B 열 제거) + 보고서 md
    <dst>\\MANIFEST_git_v1.json      파일 · 크기 · sha256 · 행수 · 원자료 · 확인 시각 · 전/후
    <dst>\\..\\size_table_75.md       전/후 크기표(datasets/mobility/processed/)
"""
import argparse
import gzip
import hashlib
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]                       # datasets/mobility/scripts → 저장소 루트
DEFAULT_DST = REPO_ROOT / "datasets" / "mobility" / "processed" / "mobility"


def default_src():
    """정본 위치 — 저장소 맨 위 .env 의 DATA_DIR(없으면 None → 인자 필수)."""
    import os
    try:
        from dotenv import load_dotenv
        load_dotenv(REPO_ROOT / ".env")
    except ImportError:
        pass
    d = os.environ.get("DATA_DIR")
    return str(Path(d) / "travel" / "processed" / "mobility") if d else None


GZ_LINE = 50 * 1024 * 1024          # GitHub 경고선(파일당). 100 MB 는 거부선

# ── 시간표에서 판정기가 읽는 열(verify_time.py Timetable.load · 2026-09-29 확인) ──
TIMETABLE_KEEP = ["line", "station_nm", "day_type", "dep_time", "dir", "dest_nm", "dest_inferred", "fetched_at"]
#  line/station_nm  : 키 (L140) · fetched_at : 첫 행에서 읽어 evidence observed_at 에 씀(L144 · L1439 — 어느 행이 첫 행이 될지
#  모르므로 전 행에 둔다) · dep_time : to_min (L147) · day_type/dir/dest_nm/dest_inferred : Dep (L151)

# ── 분류표 · 원자료 · 재생성 스크립트(mobility_scripts/…) ──
A = "A(그대로)"
B = "B(열 제거)"
FILES = [
    # path(상대 · /), 분류, 원자료, 재생성 스크립트, 읽는 코드
    ("timetable_v1.jsonl", B, "서울 열린데이터광장 OA-101(seoul_timetable_*.jsonl) + 국토부 TAGO(tago_timetable.jsonl) · raw\\mobility\\",
     "collect/build_timetable_v1.py → collect/fill_timetable_dest_v1.py(28 · dest_inferred)", "engine/verify_time.py Timetable.load · runtime.py"),
    ("timetable_v1_meta.json", A, "build_timetable_v1.py 가 시간표와 같이 씀", "collect/build_timetable_v1.py", "engine/runtime.py(built_at)"),
    ("line_station_order_v1.json", A, "국가철도공단 표준데이터 FR_CODE + 시간표 관측 + 서울교통공사 역간거리 CSV(54)",
     "collect/build_line_station_order_v1.py", "engine/line_order.py · candidates.py"),
    ("transfer_walk_v1.json", A, "서울교통공사_환승역거리 소요시간 정보_20251231.csv", "collect/build_transfer_walk_v1.py", "engine/transfer_walk.py"),
    ("bus_route_v1.jsonl", A, "서울시 버스 정보 API(seoul_bus_all_routes.json · 캐시)", "collect/build_bus_all_v1.py(45 재생성)", "engine/bus.py"),
    ("bus_stops_v1.jsonl", A, "서울시 버스 정보 API(seoul_bus_all_stops.json · 캐시)", "collect/build_bus_all_v1.py", "engine/bus.py · geo.py"),
    ("station_coords.json", A, "국가철도공단 전체_도시철도역사정보_20260630.xlsx + OA-15442 stations_all.json + config/mobility/station_coord_fix.json",
     "collect/station_coords_build.py(57)", "engine/geo.py"),
    ("station_exits_v1.json", A, "OSM 지하철 출구(raw\\mobility\\osm\\osm_subway_entrances_sudogwon_raw.json)", "collect/build_station_exits_v1.py", "engine/exits.py"),
    ("bike_stations_v1.jsonl", A, "서울 OA-21235 master + OA-15493 bikeList + OA-13252 xlsx(raw\\mobility\\bike\\)", "collect/build_bike_stations_v1.py", "engine/bike.py"),
    ("bus_seg_profile_v1.jsonl.gz", A, "서울 OA-21217 노선별 구간 운행시간 zip 9(raw\\mobility\\bus_speed\\ · 8.7M 행)", "collect/build_bus_seg_profile_v1.py", "engine/bus_profile.py"),
    ("congestion_v1.jsonl", A, "서울교통공사_지하철혼잡도정보_20260630.csv", "collect/congestion_build.py", "engine/congestion.py"),
    ("congestion_line9_v1.jsonl", A, "서울 OA-22197 9호선 혼잡도 xlsx(raw\\mobility\\congestion_line9\\)", "collect/congestion_build.py --line9 (25)", "engine/congestion.py"),
    ("transfer_car_v1.json", A, "국토부 15151816 + 서울교통공사 15098252(raw\\mobility\\car_position\\)", "collect/build_transfer_car_v1.py(46)", "engine/options.py TransferCar(display off)"),
    ("graph/topis_class_factor_v1.json", A, "TOPIS 속도 xlsx(raw\\mobility\\topis\\)", "graph/_build/03b_profile_test.py(18)", "engine/car.py CarGraph"),
    ("graph/topis_link_profile_v1.jsonl.gz", A, "TOPIS 속도 xlsx 2025-09~2026-05", "graph/_build/03b_profile_test.py(18)", "engine/car.py CarGraph"),
    ("graph/osm_way_seg_topis_link_v1.csv", A, "OSM pbf + TOPIS 링크 형상 매칭", "graph/_build/02b_match.py(18)", "engine/car.py CarGraph"),
    ("graph/osm_way_geom_v1.csv", A, "OSM pbf", "graph/_build/01_geom.py(18)", "engine/car.py CarGraph"),
    ("graph/daytype_calendar_v1.csv", A, "holidays KR + 정정(34)", "graph/_build/03b_profile_test.py(18)", "engine/car.py CarGraph"),
]
# 부속 보고서(작은 md · 파일별 커버리지·등급 근거) — 코드는 안 읽는다
REPORTS = ["timetable_v1_coverage.md", "timetable_v1_destfill_report.md", "line_station_order_v1_report.md",
           "transfer_walk_v1_report.md", "bus_route_v1_report.md", "station_coords_report.md",
           "bike_stations_v1_report.md", "bus_seg_profile_v1_report.md", "congestion_v1_report.md",
           "congestion_line9_v1_report.md", "transfer_car_v1_report.md", "graph/README.md"]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def count_rows(p: Path) -> int:
    op = gzip.open if p.suffix == ".gz" else open
    n = 0
    with op(p, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                n += 1
    return n


def fmt(n):
    return f"{n / 1048576:,.1f} MB" if n >= 1048576 else f"{n / 1024:,.1f} KB"


def reduce_timetable(src: Path, dst: Path, drop_no_dep: bool):
    """열 8개만 남긴다. 행 순서·행 수 그대로(--drop-no-dep 아니면). 줄 끝 \\n · ensure_ascii=False · 구분자 최소."""
    keep = TIMETABLE_KEEP
    seen_keys = {}
    n_in = n_out = n_no_dep = 0
    dropped_cols = set()
    with open(src, encoding="utf-8") as fi, open(dst, "w", encoding="utf-8", newline="\n") as fo:
        for raw in fi:
            s = raw.strip()
            if not s:
                continue
            r = json.loads(s)
            n_in += 1
            for k in r:
                seen_keys[k] = seen_keys.get(k, 0) + 1
                if k not in keep:
                    dropped_cols.add(k)
            # 판정기 to_min 과 같은 뜻: None · '' · '000000' · '0' = 출발 없음(시·종착역 표기)
            dep = r.get("dep_time")
            no_dep = dep is None or str(dep).strip() in ("", "000000", "0")
            if no_dep:
                n_no_dep += 1
                if drop_no_dep:
                    continue
            o = {k: r.get(k) for k in keep}
            fo.write(json.dumps(o, ensure_ascii=False, separators=(",", ":")) + "\n")
            n_out += 1
    return {"rows_in": n_in, "rows_out": n_out, "rows_no_dep": n_no_dep,
            "rows_dropped_no_dep": (n_no_dep if drop_no_dep else 0),
            "columns_kept": keep, "columns_dropped": sorted(dropped_cols),
            "columns_seen": seen_keys}


def gzip_file(p: Path) -> Path:
    g = p.with_name(p.name + ".gz")
    with open(p, "rb") as fi, gzip.open(g, "wb", compresslevel=9) as fo:
        shutil.copyfileobj(fi, fo)
    return g


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=default_src(), help="정본 processed/mobility (기본 .env DATA_DIR)")
    ap.add_argument("--dst", default=str(DEFAULT_DST))
    ap.add_argument("--clean", action="store_true")
    ap.add_argument("--gz", action="store_true")
    ap.add_argument("--drop-no-dep", action="store_true")
    a = ap.parse_args()
    if not a.src:
        print("! --src 를 주거나 .env 에 DATA_DIR 을 넣어라"); sys.exit(2)
    src, dst = Path(a.src), Path(a.dst)
    if dst.exists() and any(dst.iterdir()):
        if not a.clean:
            print(f"! {dst} 가 비어 있지 않다 — --clean 을 주면 비우고 다시 만든다")
            sys.exit(2)
        shutil.rmtree(dst)
    dst.mkdir(parents=True, exist_ok=True)
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    entries = []
    tot_before = tot_after = 0

    for rel, cls, raw_src, regen, reader in FILES:
        sp, dp = src / rel, dst / rel
        if not sp.exists():
            print(f"  ! 없음: {rel}")
            entries.append({"path": rel, "class": cls, "missing": True})
            continue
        dp.parent.mkdir(parents=True, exist_ok=True)
        e = {"path": rel, "class": cls, "source_raw": raw_src, "regen_script": regen, "read_by": reader,
             "src_bytes": sp.stat().st_size, "src_sha256": sha256(sp), "checked_at": now}
        if rel == "timetable_v1.jsonl":
            e["reduce"] = reduce_timetable(sp, dp, a.drop_no_dep)
        else:
            shutil.copyfile(sp, dp)
        e["bytes"] = dp.stat().st_size
        e["sha256"] = sha256(dp)
        if rel.endswith((".jsonl", ".jsonl.gz", ".csv")):
            e["rows"] = count_rows(dp) - (1 if rel.endswith(".csv") else 0)   # csv 는 머리글 제외
        e["gz"] = None
        if e["bytes"] > GZ_LINE:
            e["over_50mb"] = True
        if e["bytes"] > GZ_LINE and a.gz:
            g = gzip_file(dp)
            e["gz"] = {"path": rel + ".gz", "bytes": g.stat().st_size, "sha256": sha256(g),
                       "reason": f"줄인 뒤에도 {fmt(e['bytes'])} > 50 MB(GitHub 경고선) — 판정기 loader 가 .gz 를 읽는지는 73 뒤 팀장 판으로 확인"}
        tot_before += e["src_bytes"]
        tot_after += e["bytes"]
        print(f"  {cls:8s} {rel:42s} {fmt(e['src_bytes']):>10s} → {fmt(e['bytes']):>10s}"
              + (f"  (gz {fmt(e['gz']['bytes'])})" if e["gz"] else "") + (f"  rows={e['rows']:,}" if "rows" in e else ""))
        entries.append(e)

    reports = []
    for rel in REPORTS:
        sp, dp = src / rel, dst / rel
        if sp.exists():
            dp.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(sp, dp)
            reports.append({"path": rel, "bytes": dp.stat().st_size, "sha256": sha256(dp)})

    gz_total = sum((e["gz"]["bytes"] if e.get("gz") else e.get("bytes", 0)) for e in entries if not e.get("missing"))
    manifest = {
        "manifest_version": "git_v1", "generated_at": now, "room": 75,
        "src_dir": str(src), "dst_dir": str(dst),
        "rule": {"columns_only_verified_by_loader": True, "row_deletion": "forbidden (drop_no_dep=%s)" % a.drop_no_dep,
                 "gz_threshold_bytes": GZ_LINE, "gz_policy": "last resort — only files still > 50 MB after column reduction; .gz written beside, text kept"},
        "totals": {"src_bytes": tot_before, "dst_bytes_text": tot_after, "dst_bytes_if_gz_used_where_made": gz_total},
        "files": entries, "reports": reports,
    }
    (dst / "MANIFEST_git_v1.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

    lines = [f"# 75 크기표 전/후 — {now}", "", f"정본 합계(올리는 파일만) {fmt(tot_before)} → 줄인 판 {fmt(tot_after)}"
             f" · gz 적용 시 {fmt(gz_total)}", "",
             "| 파일 | 분류 | 전 | 후 | gz | 행 |", "|---|---|---:|---:|---:|---:|"]
    for e in entries:
        if e.get("missing"):
            lines.append(f"| `{e['path']}` | {e['class']} | 없음 | | | |")
            continue
        lines.append(f"| `{e['path']}` | {e['class']} | {fmt(e['src_bytes'])} | {fmt(e['bytes'])} | "
                     f"{fmt(e['gz']['bytes']) if e['gz'] else '—'} | {e.get('rows', ''):,} |" if isinstance(e.get('rows'), int) else
                     f"| `{e['path']}` | {e['class']} | {fmt(e['src_bytes'])} | {fmt(e['bytes'])} | "
                     f"{fmt(e['gz']['bytes']) if e['gz'] else '—'} | |")
    tt = next((e for e in entries if e["path"] == "timetable_v1.jsonl"), None)
    if tt and "reduce" in tt:
        r = tt["reduce"]
        lines += ["", f"시간표: 행 {r['rows_in']:,} → {r['rows_out']:,}(출발없음 {r['rows_no_dep']:,}행 · 뺀 행 {r['rows_dropped_no_dep']:,}) · "
                  f"남긴 열 {r['columns_kept']} · 뺀 열 {r['columns_dropped']}"]
    (dst.parent / "size_table_75.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n합계 {fmt(tot_before)} → {fmt(tot_after)} (gz 적용 시 {fmt(gz_total)})")
    print(f"MANIFEST: {dst / 'MANIFEST_git_v1.json'} · 크기표: {dst.parent / 'size_table_75.md'}")


if __name__ == "__main__":
    main()
